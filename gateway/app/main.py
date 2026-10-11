from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from gateway.app.config import Settings
from gateway.app.policy import SCOPE_TIERS, Tier, validate_policy
from gateway.app.schemas import (
    CheckRequest,
    CheckResponse,
    DecisionName,
    ErrorResponse,
    HealthResponse,
    RequestRiskResponse,
)
from gateway.app.services.audit import AuditRecord, AuditRepository, InMemoryAuditRepository
from gateway.app.services.consent import (
    ConsentState,
    ConsentVerifier,
    UnavailableConsentVerifier,
)
from gateway.app.services.enforcement import InMemoryEnforcement
from gateway.app.services.face_risk import FaceRiskService, MockFaceRiskService
from gateway.app.services.risk import RequestRiskScorer, StubRequestRiskScorer
from gateway.app.services.router import RouteDecision, decide


def create_app(
    settings: Settings | None = None,
    *,
    consent_verifier: ConsentVerifier | None = None,
    request_risk_scorer: RequestRiskScorer | None = None,
    face_risk_service: FaceRiskService | None = None,
    audit_repository: AuditRepository | None = None,
    enforcement: InMemoryEnforcement | None = None,
) -> FastAPI:
    configured = settings or Settings.from_env()
    validate_policy()
    audit = audit_repository or InMemoryAuditRepository()
    enforcer = enforcement or InMemoryEnforcement(
        blocked_attempt_threshold=configured.blocked_attempt_threshold,
        restriction_window_seconds=configured.restriction_window_seconds,
        rate_limit_requests=configured.rate_limit_requests,
        rate_limit_window_seconds=configured.rate_limit_window_seconds,
    )
    verifier = consent_verifier or UnavailableConsentVerifier()
    risk_scorer = request_risk_scorer or StubRequestRiskScorer()
    face_assessor = face_risk_service or MockFaceRiskService()

    app = FastAPI(
        title="ConsentGuard Gateway",
        version="0.1.0",
        description=(
            "Prototype risk-tier gateway. Risk and face/age signals are stubs or "
            "demo-only signals and do not provide real-world detection."
        ),
    )

    @app.exception_handler(RequestValidationError)
    async def invalid_request_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        del request, exc
        body = ErrorResponse(
            error={
                "code": "invalid_request",
                "message": "Request validation failed.",
            }
        )
        return JSONResponse(status_code=422, content=body.model_dump(mode="json"))

    @app.exception_handler(HTTPException)
    async def http_error_handler(request: Request, exc: HTTPException) -> JSONResponse:
        del request
        body = ErrorResponse(
            error={
                "code": str(exc.detail),
                "message": {
                    "test_signals_disabled": (
                        "Demo-only test signals are disabled by configuration."
                    ),
                    "unauthorized": "A valid API key is required.",
                    "rate_limited": "Request rate limit exceeded.",
                }.get(str(exc.detail), "Request could not be processed."),
            }
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=body.model_dump(mode="json"),
            headers=exc.headers,
        )

    async def authenticate(
        x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    ) -> str:
        if x_api_key is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthorized"
            )
        supplied_digest = hashlib.sha256(x_api_key.encode("utf-8")).digest()
        if not secrets.compare_digest(supplied_digest, configured.api_key_digest):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthorized"
            )
        return configured.app_id

    @app.get("/health", response_model=HealthResponse, tags=["health"])
    async def health() -> HealthResponse:
        return HealthResponse(status="ok")

    @app.post(
        "/v1/check",
        response_model=CheckResponse,
        responses={
            400: {"model": ErrorResponse},
            401: {"model": ErrorResponse},
            422: {"model": ErrorResponse},
            429: {"model": ErrorResponse},
        },
        tags=["checks"],
    )
    async def check(
        payload: CheckRequest,
        app_identity: str = Depends(authenticate),
    ) -> CheckResponse:
        if payload.test_signals is not None and not configured.enable_test_signals:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="test_signals_disabled",
            )
        if not enforcer.allow_rate_limited_request(app_identity):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="rate_limited",
                headers={"Retry-After": str(configured.rate_limit_window_seconds)},
            )

        user_ref = hmac.new(
            configured.user_ref_hmac_key,
            f"{app_identity}\0{payload.user_ref}".encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        tier = SCOPE_TIERS[payload.scope]
        request_risk = risk_scorer.assess(payload.prompt)
        face_risk = face_assessor.assess(payload)

        if enforcer.is_restricted(user_ref):
            route = RouteDecision(
                decision=DecisionName.BLOCK,
                tier=tier,
                reasons=("restricted_user",),
            )
        else:
            needs_consent_check = (
                tier is Tier.IDENTITY_ALTERING
                and face_risk.real_face is not False
                and face_risk.minor_risk is False
                and request_risk.score < configured.risk_block_threshold
            )
            consent_state = (
                verifier.verify(
                    payload.consent_token,
                    app_id=app_identity,
                    scope=payload.scope.value,
                )
                if needs_consent_check
                else ConsentState.MISSING
            )
            route = decide(
                scope=payload.scope,
                face_risk=face_risk,
                request_risk=request_risk,
                consent_state=consent_state,
                risk_block_threshold=configured.risk_block_threshold,
            )

        check_id = f"c_{uuid4().hex[:12]}"
        if route.decision is DecisionName.BLOCK:
            if enforcer.record_blocked_attempt(user_ref):
                route = RouteDecision(
                    decision=route.decision,
                    tier=route.tier,
                    reasons=tuple(dict.fromkeys((*route.reasons, "restricted_user"))),
                )

        audit.record(
            AuditRecord(
                check_id=check_id,
                pseudonymous_user_ref=user_ref,
                tier=int(route.tier),
                decision=route.decision,
                reason_codes=route.reasons,
                timestamp=datetime.now(timezone.utc),
            )
        )
        return CheckResponse(
            check_id=check_id,
            decision=route.decision,
            tier=int(route.tier),
            reasons=list(route.reasons),
            consent_required=route.decision is DecisionName.NEEDS_CONSENT,
            request_risk=RequestRiskResponse(
                score=request_risk.score,
                label=request_risk.label,
                source=request_risk.source,
            ),
        )

    return app
