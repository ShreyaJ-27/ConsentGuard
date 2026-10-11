from __future__ import annotations

import hashlib
import hmac
import io
import secrets
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import (
    Depends,
    FastAPI,
    File,
    Form,
    Header,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from PIL import Image

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
    LookupProvenance,
    LookupResponse,
    RequestRiskResponse,
    StampReceipt,
)
from gateway.app.services.audit import (
    AuditRecord,
    AuditRepository,
    InMemoryAuditRepository,
)
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
from gateway.app.services.ledger import (
    InMemoryLedgerRepository,
    LedgerRepository,
)
from gateway.app.services.output_store import (
    InMemoryOutputStore,
    OutputStore,
)
from gateway.app.services.provenance import (
    add_ai_generated_label,
    compute_dhash,
    compute_sha256,
)
from gateway.app.services.result_check import (
    ResultCheckContext,
    ResultChecker,
    ResultCheckError,
    StubResultChecker,
)
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
    result_checker: ResultChecker | None = None,
    ledger_repository: LedgerRepository | None = None,
    output_store: OutputStore | None = None,
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
    checker = result_checker or StubResultChecker()
    ledger = ledger_repository or InMemoryLedgerRepository()
    store = output_store or InMemoryOutputStore()

    app = FastAPI(
        title="ConsentGuard Gateway",
        version="0.1.0",
        description=(
            "Prototype risk-tier gateway with defensive output checks, "
            "provenance stamping, and hash-chained ledger."
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
        return JSONResponse(
            status_code=422, content=body.model_dump(mode="json")
        )

    @app.exception_handler(HTTPException)
    async def http_error_handler(
        request: Request, exc: HTTPException
    ) -> JSONResponse:
        del request
        detail_str = str(exc.detail)
        error_messages = {
            "test_signals_disabled": (
                "Demo-only test signals are disabled by configuration."
            ),
            "unauthorized": "A valid API key is required.",
            "rate_limited": "Request rate limit exceeded.",
            "invalid_check_id": (
                "A valid check identifier starting with 'c_' is required."
            ),
            "invalid_phash": (
                "Perceptual hash must be a 16-character hexadecimal string."
            ),
            "invalid_image_format": (
                "Uploaded file must be a valid image (PNG, JPEG, WEBP)."
            ),
            "payload_too_large": (
                "Uploaded image exceeds the configured size limit."
            ),
            "harmful_content_detected": (
                "Output failed safety verification: harmful content detected."
            ),
            "safety_check_indeterminate_high_risk": (
                "Output failed safety verification: indeterminate check for high-risk output."
            ),
            "safety_check_indeterminate": (
                "Output failed safety verification: indeterminate check result."
            ),
            "result_check_failed": (
                "Output safety verification encountered an error and failed closed."
            ),
            "output_rejected": (
                "Output failed safety verification and was rejected."
            ),
            "output_not_found": (
                "Requested output reference was not found or has expired."
            ),
            "stamping_failed": (
                "Failed to apply provenance watermark to output image."
            ),
        }
        body = ErrorResponse(
            error={
                "code": detail_str,
                "message": error_messages.get(
                    detail_str, "Request could not be processed."
                ),
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
        if not secrets.compare_digest(
            supplied_digest, configured.api_key_digest
        ):
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
        if (
            payload.test_signals is not None
            and not configured.enable_test_signals
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="test_signals_disabled",
            )
        if not enforcer.allow_rate_limited_request(app_identity):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="rate_limited",
                headers={
                    "Retry-After": str(configured.rate_limit_window_seconds)
                },
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
                    reasons=tuple(
                        dict.fromkeys((*route.reasons, "restricted_user"))
                    ),
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
        "/v1/output/stamp",
        response_model=StampReceipt,
        responses={
            400: {"model": ErrorResponse},
            401: {"model": ErrorResponse},
            413: {"model": ErrorResponse},
            422: {"model": ErrorResponse},
            500: {"model": ErrorResponse},
        },
        tags=["provenance"],
    )
    async def stamp_output(
        check_id: str = Form(
            ..., description="Check identifier associated with the request"
        ),
        image: UploadFile = File(
            ..., description="Generated image file to inspect and stamp"
        ),
        mock_signal: str | None = Form(
            default=None, description="Test signal for stub result check"
        ),
        high_risk: bool = Form(
            default=False,
            description="Whether the original request was high risk",
        ),
        app_identity: str = Depends(authenticate),
    ) -> StampReceipt:
        if not check_id or not check_id.startswith("c_") or len(check_id) > 64:
            raise HTTPException(
                status_code=422,
                detail="invalid_check_id",
            )

        image_bytes = await image.read()
        if len(image_bytes) > configured.max_output_size_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="payload_too_large",
            )
        if len(image_bytes) < 8:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="invalid_image_format",
            )

        try:
            with Image.open(io.BytesIO(image_bytes)) as pil_img:
                pil_img.verify()
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="invalid_image_format",
            )

        context = ResultCheckContext(
            check_id=check_id,
            app_id=app_identity,
            high_risk=high_risk,
            mock_signal=mock_signal,
        )

        try:
            check_result = checker.check_output(image_bytes, context)
        except ResultCheckError:
            raise HTTPException(
                status_code=422,
                detail="result_check_failed",
            )

        if not check_result.allowed:
            first_reason = (
                check_result.reason_codes[0]
                if check_result.reason_codes
                else "output_rejected"
            )
            raise HTTPException(
                status_code=422,
                detail=first_reason,
            )

        pre_stamp_sha256 = compute_sha256(image_bytes)
        try:
            stamped_bytes = add_ai_generated_label(image_bytes)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="stamping_failed",
            )

        output_sha256 = compute_sha256(stamped_bytes)
        phash = compute_dhash(stamped_bytes)

        record = ledger.append(
            check_id=check_id,
            app_id=app_identity,
            output_sha256=output_sha256,
            pre_stamp_sha256=pre_stamp_sha256,
            phash=phash,
            label="AI-generated",
            decision="stamped",
        )

        output_ref = f"out_{uuid4().hex[:12]}"
        store.store(output_ref, stamped_bytes, "image/png")

        return StampReceipt(
            check_id=check_id,
            entry_id=record.entry_id,
            output_sha256=output_sha256,
            pre_stamp_sha256=pre_stamp_sha256,
            phash=phash,
            label=record.label,
            created_at=record.timestamp,
            ledger_entry_hash=record.entry_hash,
            output_ref=output_ref,
        )

    @app.get(
        "/v1/output/download/{output_ref}",
        responses={
            200: {"content": {"image/png": {}}},
            404: {"model": ErrorResponse},
        },
        tags=["provenance"],
    )
    async def download_output(output_ref: str) -> Response:
        stored = store.get(output_ref)
        if stored is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="output_not_found",
            )
        image_bytes, mime_type = stored
        return Response(content=image_bytes, media_type=mime_type)

    @app.get(
        "/v1/ledger/lookup",
        response_model=LookupResponse,
        responses={
            400: {"model": ErrorResponse},
        },
        tags=["provenance"],
    )
    async def lookup_ledger(
        phash: str = Query(
            ..., description="16-character hexadecimal perceptual hash"
        ),
        max_distance: int = Query(
            default=0,
            ge=0,
            le=64,
            description="Maximum Hamming distance for matching",
        ),
    ) -> LookupResponse:
        clean_phash = phash.strip().lower()
        if len(clean_phash) != 16:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="invalid_phash",
            )
        try:
            int(clean_phash, 16)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="invalid_phash",
            )

        match = ledger.lookup_phash(clean_phash, max_distance=max_distance)
        if match is not None:
            return LookupResponse(
                match=True,
                method=match.method,
                provenance=LookupProvenance(
                    check_id=match.record.check_id,
                    label=match.record.label,
                    created_at=match.record.timestamp,
                    output_sha256=match.record.output_sha256,
                ),
                distance=match.distance,
                message="Matching provenance ledger entry found.",
            )

        return LookupResponse(
            match=False,
            method="exact_phash" if max_distance == 0 else "hamming_phash",
            provenance=None,
            distance=None,
            message=(
                "No matching ledger entry found. A no-match result indicates only "
                "that this perceptual hash does not match an existing ledger entry "
                "under the implemented method; it does not prove authenticity or falsity."
            ),
        )

    @app.get("/v1/ledger/verify", tags=["provenance"])
    async def verify_ledger() -> dict[str, object]:
        valid, error = ledger.verify_integrity()
        return {
            "valid": valid,
            "error": error,
            "entries_count": len(ledger.snapshot()),
            "head_hash": ledger.head_hash(),
        }

    return app
