from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse

from gateway.app.config import Settings
from gateway.app.policy import SCOPE_TIERS, Tier, validate_policy
from gateway.app.schemas import (
    CheckRequest,
    CheckResponse,
    ConsentApprovalResponse,
    ConsentRequestCreate,
    ConsentRequestResponse,
    ConsentRevocationRequest,
    ConsentStateResponse,
    ConsentSubjectAction,
    ConsentTokenVerificationRequest,
    ConsentTokenVerificationResponse,
    DecisionName,
    ErrorResponse,
    HealthResponse,
    RequestRiskResponse,
)
from gateway.app.services.audit import AuditRecord, AuditRepository, InMemoryAuditRepository
from gateway.app.services.consent import (
    ConsentState,
    ConsentTokenService,
    ConsentVerifier,
    UnavailableConsentVerifier,
    action_secret_digest,
    load_signing_key,
    new_demo_action_secret,
    target_reference_digest,
)
from gateway.app.services.consent_store import (
    CheckContext,
    ConsentStoreError,
    SQLiteConsentStore,
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
    consent_store = SQLiteConsentStore(configured.consent_database_path)
    token_service = None
    if configured.consent_signing_key_path is not None:
        token_service = ConsentTokenService(
            store=consent_store,
            signing_key=load_signing_key(configured.consent_signing_key_path),
            issuer=configured.consent_issuer,
            token_ttl_seconds=configured.consent_token_ttl_seconds,
        )
    elif consent_verifier is None:
        raise ValueError(
            "CONSENTGUARD_SIGNING_KEY_PATH must point to a protected Ed25519 key."
        )
    verifier = consent_verifier or token_service or UnavailableConsentVerifier()
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
                    "demo_subject_actions_disabled": (
                        "Subject actions are disabled; demo approval is simulated."
                    ),
                    "consent_not_found": "Consent request or check was not found.",
                    "consent_conflict": "Consent state does not allow this action.",
                    "check_not_eligible": "Check is expired or does not require consent.",
                    "target_required": "A target reference is required for consent.",
                    "consent_request_exists": (
                        "A consent request already exists for this check."
                    ),
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

    def demo_subject_actions_enabled() -> None:
        if not configured.enable_demo_subject_actions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="demo_subject_actions_disabled",
            )

    def consent_store_error(exc: ConsentStoreError) -> HTTPException:
        if exc.code == "consent_not_found":
            return HTTPException(status_code=404, detail="consent_not_found")
        if exc.code in {"check_not_eligible", "target_required"}:
            return HTTPException(status_code=400, detail=exc.code)
        if exc.code == "consent_request_exists":
            return HTTPException(status_code=409, detail=exc.code)
        return HTTPException(status_code=409, detail="consent_conflict")

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
        check_id = f"c_{uuid4().hex[:12]}"
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
            if not needs_consent_check:
                consent_state = ConsentState.MISSING
            elif payload.target_ref is None:
                consent_state = verifier.verify(
                    payload.consent_token,
                    app_id=app_identity,
                    scope=payload.scope.value,
                )
            else:
                consent_state = verifier.verify(
                    payload.consent_token,
                    app_id=app_identity,
                    scope=payload.scope.value,
                    target_ref=payload.target_ref,
                )
            route = decide(
                scope=payload.scope,
                face_risk=face_risk,
                request_risk=request_risk,
                consent_state=consent_state,
                risk_block_threshold=configured.risk_block_threshold,
            )

        consent_store.record_check(
            CheckContext(
                check_id=check_id,
                app_id=app_identity,
                scope=payload.scope.value,
                target_digest=(
                    target_reference_digest(payload.target_ref)
                    if payload.target_ref is not None
                    else None
                ),
                decision=route.decision.value,
                expires_at=int(time.time()) + 15 * 60,
            )
        )
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

    @app.post(
        "/v1/consent/requests",
        response_model=ConsentRequestResponse,
        tags=["consent"],
    )
    async def create_consent_request(
        payload: ConsentRequestCreate,
        app_identity: str = Depends(authenticate),
    ) -> ConsentRequestResponse:
        now = int(time.time())
        action_secret = new_demo_action_secret()
        request_id = f"cr_{uuid4().hex}"
        try:
            record = consent_store.create_request(
                request_id=request_id,
                check_id=payload.check_id,
                app_id=app_identity,
                subject_ref=f"subject_{uuid4().hex}",
                action_secret_hash=action_secret_digest(action_secret),
                now=now,
                expires_at=now + 10 * 60,
            )
        except ConsentStoreError as exc:
            raise consent_store_error(exc) from exc
        return ConsentRequestResponse(
            request_id=record.request_id,
            status=record.status,
            expires_at=record.expires_at,
            demo_action_code=(
                action_secret if configured.enable_demo_subject_actions else None
            ),
        )

    @app.post(
        "/v1/consent/approve",
        response_model=ConsentApprovalResponse,
        tags=["consent"],
    )
    async def approve_consent(
        payload: ConsentSubjectAction,
    ) -> ConsentApprovalResponse:
        demo_subject_actions_enabled()
        if token_service is None:
            raise HTTPException(status_code=503, detail="consent_unavailable")
        request_record = consent_store.get_request(payload.request_id)
        if request_record is None:
            raise HTTPException(status_code=404, detail="consent_not_found")
        try:
            token, expires_at = token_service.approve(
                request_record, action_secret=payload.demo_action_code
            )
        except ConsentStoreError as exc:
            raise consent_store_error(exc) from exc
        return ConsentApprovalResponse(
            request_id=payload.request_id,
            status="approved",
            consent_token=token,
            expires_at=expires_at,
        )

    @app.post(
        "/v1/consent/deny",
        response_model=ConsentStateResponse,
        tags=["consent"],
    )
    async def deny_consent(
        payload: ConsentSubjectAction,
    ) -> ConsentStateResponse:
        demo_subject_actions_enabled()
        try:
            token_service.deny(
                payload.request_id, action_secret=payload.demo_action_code
            )
        except ConsentStoreError as exc:
            raise consent_store_error(exc) from exc
        return ConsentStateResponse(request_id=payload.request_id, status="denied")

    @app.post(
        "/v1/consent/status",
        response_model=ConsentStateResponse,
        tags=["consent"],
    )
    async def get_consent_status(
        payload: ConsentSubjectAction,
    ) -> ConsentStateResponse:
        demo_subject_actions_enabled()
        record = consent_store.get_request_status(
            payload.request_id,
            action_secret_hash=action_secret_digest(payload.demo_action_code),
        )
        if record is None:
            raise HTTPException(status_code=404, detail="consent_not_found")
        request_status = (
            "expired"
            if record.status == "pending" and record.expires_at <= int(time.time())
            else record.status
        )
        return ConsentStateResponse(
            request_id=record.request_id,
            status=request_status,
            expires_at=record.expires_at,
        )

    @app.post(
        "/v1/consent/revoke",
        response_model=ConsentStateResponse,
        tags=["consent"],
    )
    async def revoke_consent(
        payload: ConsentRevocationRequest,
    ) -> ConsentStateResponse:
        demo_subject_actions_enabled()
        if token_service is None:
            raise HTTPException(status_code=503, detail="consent_unavailable")
        try:
            token_service.revoke(payload.jti, action_secret=payload.demo_action_code)
        except ConsentStoreError as exc:
            raise consent_store_error(exc) from exc
        return ConsentStateResponse(status="revoked")

    @app.post(
        "/v1/generate/verify",
        response_model=ConsentTokenVerificationResponse,
        tags=["consent"],
    )
    async def verify_consent_token(
        payload: ConsentTokenVerificationRequest,
        app_identity: str = Depends(authenticate),
    ) -> ConsentTokenVerificationResponse:
        context = consent_store.get_check(
            payload.check_id, app_id=app_identity, now=int(time.time())
        )
        if (
            context is None
            or context.decision
            not in {DecisionName.NEEDS_CONSENT.value, DecisionName.ALLOW.value}
            or context.target_digest is None
        ):
            raise HTTPException(status_code=404, detail="consent_not_found")
        if not hmac.compare_digest(
            context.target_digest, target_reference_digest(payload.target_ref)
        ):
            return ConsentTokenVerificationResponse(
                valid=False, state=ConsentState.FACE_MISMATCH.value
            )
        state = verifier.verify(
            payload.consent_token,
            app_id=app_identity,
            scope=context.scope,
            target_ref=payload.target_ref,
        )
        return ConsentTokenVerificationResponse(
            valid=state is ConsentState.VALID,
            state=state.value,
        )

    @app.get("/passport", include_in_schema=False)
    @app.get("/passport/", include_in_schema=False)
    async def consent_passport() -> FileResponse:
        return FileResponse(Path(__file__).parent / "static" / "passport.html")

    return app
