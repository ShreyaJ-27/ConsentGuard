from __future__ import annotations

import hashlib
import hmac
import io
import secrets
import sqlite3
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
from fastapi.responses import FileResponse, JSONResponse
from PIL import Image

from gateway.app.config import Settings
from gateway.app.policy import SCOPE_TIERS, Scope, Tier, validate_policy
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
    LedgerVerificationResponse,
    LookupProvenance,
    LookupResponse,
    MockResultSignal,
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
    LedgerConflictError,
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
            "check_not_found": "The check does not exist, has expired, or is unavailable to this application.",
            "check_not_eligible": "The check decision is not eligible for this operation.",
            "consent_required": "A valid, unexpired consent grant is required for this operation.",
            "consent_store_unavailable": "Consent storage is unavailable; the request failed closed.",
            "demo_subject_actions_disabled": "Simulated subject actions are disabled by configuration.",
            "output_already_stamped": "An output has already been stamped for this check.",
            "output_persistence_failed": "The output could not be safely persisted.",
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

    @app.get("/passport/", include_in_schema=False, tags=["consent"])
    async def consent_passport() -> FileResponse:
        return FileResponse(Path(__file__).parent / "static" / "passport.html")

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
        if payload.consent_check_id is not None and payload.consent_token is None:
            raise HTTPException(
                status_code=400, detail="invalid_consent_binding"
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
            elif payload.consent_token is None:
                consent_state = ConsentState.MISSING
            elif isinstance(verifier, ConsentTokenService):
                if payload.consent_check_id is None:
                    consent_state = ConsentState.INVALID_TOKEN
                else:
                    consent_state = verifier.verify(
                        payload.consent_token,
                        app_id=app_identity,
                        scope=payload.scope.value,
                        target_ref=payload.target_ref,
                        check_id=payload.consent_check_id,
                    )
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
                consent_check_id=(
                    payload.consent_check_id
                    if route.decision is DecisionName.ALLOW
                    and "valid_consent" in route.reasons
                    else None
                ),
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
        "/v1/consent/requests",
        response_model=ConsentRequestResponse,
        responses={
            400: {"model": ErrorResponse},
            401: {"model": ErrorResponse},
            409: {"model": ErrorResponse},
            503: {"model": ErrorResponse},
        },
        tags=["consent"],
    )
    async def create_consent_request(
        payload: ConsentRequestCreate,
        app_identity: str = Depends(authenticate),
    ) -> ConsentRequestResponse:
        if token_service is None:
            raise HTTPException(
                status_code=503, detail="consent_store_unavailable"
            )
        if not enforcer.allow_rate_limited_request(app_identity):
            raise HTTPException(
                status_code=429,
                detail="rate_limited",
                headers={"Retry-After": str(configured.rate_limit_window_seconds)},
            )
        now = int(time.time())
        action_code = new_demo_action_secret()
        request_id = f"cr_{uuid4().hex}"
        try:
            request_record = consent_store.create_request(
                request_id=request_id,
                check_id=payload.check_id,
                app_id=app_identity,
                subject_ref=f"sub_{uuid4().hex}",
                action_secret_hash=action_secret_digest(action_code),
                now=now,
                expires_at=now + configured.consent_token_ttl_seconds,
            )
        except ConsentStoreError as exc:
            raise consent_store_error(exc) from exc
        except sqlite3.Error as exc:
            raise HTTPException(
                status_code=503, detail="consent_store_unavailable"
            ) from exc
        return ConsentRequestResponse(
            request_id=request_record.request_id,
            status=request_record.status,
            expires_at=request_record.expires_at,
            demo_action_code=(
                action_code if configured.enable_demo_subject_actions else None
            ),
        )

    @app.post(
        "/v1/consent/approve",
        response_model=ConsentApprovalResponse,
        responses={
            403: {"model": ErrorResponse},
            404: {"model": ErrorResponse},
            409: {"model": ErrorResponse},
            503: {"model": ErrorResponse},
        },
        tags=["consent"],
    )
    async def approve_consent(
        payload: ConsentSubjectAction,
    ) -> ConsentApprovalResponse:
        demo_subject_actions_enabled()
        if token_service is None:
            raise HTTPException(
                status_code=503, detail="consent_store_unavailable"
            )
        try:
            request_record = consent_store.get_request(payload.request_id)
            if request_record is None:
                raise HTTPException(status_code=404, detail="consent_not_found")
            token, expires_at = token_service.approve(
                request_record, action_secret=payload.demo_action_code
            )
        except ConsentStoreError as exc:
            raise consent_store_error(exc) from exc
        except sqlite3.Error as exc:
            raise HTTPException(
                status_code=503, detail="consent_store_unavailable"
            ) from exc
        return ConsentApprovalResponse(
            request_id=payload.request_id,
            status="approved",
            consent_token=token,
            expires_at=expires_at,
        )

    @app.post(
        "/v1/consent/deny",
        response_model=ConsentStateResponse,
        responses={
            403: {"model": ErrorResponse},
            404: {"model": ErrorResponse},
            409: {"model": ErrorResponse},
            503: {"model": ErrorResponse},
        },
        tags=["consent"],
    )
    async def deny_consent(payload: ConsentSubjectAction) -> ConsentStateResponse:
        demo_subject_actions_enabled()
        if token_service is None:
            raise HTTPException(
                status_code=503, detail="consent_store_unavailable"
            )
        try:
            token_service.deny(
                payload.request_id, action_secret=payload.demo_action_code
            )
            request_record = consent_store.get_request(payload.request_id)
        except ConsentStoreError as exc:
            raise consent_store_error(exc) from exc
        except sqlite3.Error as exc:
            raise HTTPException(
                status_code=503, detail="consent_store_unavailable"
            ) from exc
        if request_record is None:
            raise HTTPException(status_code=404, detail="consent_not_found")
        return ConsentStateResponse(
            request_id=request_record.request_id,
            status="denied",
            expires_at=request_record.expires_at,
        )

    @app.post(
        "/v1/consent/status",
        response_model=ConsentStateResponse,
        responses={
            403: {"model": ErrorResponse},
            404: {"model": ErrorResponse},
            503: {"model": ErrorResponse},
        },
        tags=["consent"],
    )
    async def consent_status(
        payload: ConsentSubjectAction,
    ) -> ConsentStateResponse:
        demo_subject_actions_enabled()
        try:
            request_record = consent_store.get_request_status(
                payload.request_id,
                action_secret_hash=action_secret_digest(payload.demo_action_code),
            )
        except sqlite3.Error as exc:
            raise HTTPException(
                status_code=503, detail="consent_store_unavailable"
            ) from exc
        if request_record is None:
            raise HTTPException(status_code=404, detail="consent_not_found")
        request_status = request_record.status
        if request_status == "pending" and request_record.expires_at <= int(time.time()):
            request_status = "expired"
        return ConsentStateResponse(
            request_id=request_record.request_id,
            status=request_status,
            expires_at=request_record.expires_at,
        )

    @app.post(
        "/v1/consent/revoke",
        response_model=ConsentStateResponse,
        responses={
            403: {"model": ErrorResponse},
            404: {"model": ErrorResponse},
            409: {"model": ErrorResponse},
            503: {"model": ErrorResponse},
        },
        tags=["consent"],
    )
    async def revoke_consent(
        payload: ConsentRevocationRequest,
    ) -> ConsentStateResponse:
        demo_subject_actions_enabled()
        if token_service is None:
            raise HTTPException(
                status_code=503, detail="consent_store_unavailable"
            )
        try:
            token_record = consent_store.get_token(payload.jti)
            token_service.revoke(
                payload.jti, action_secret=payload.demo_action_code
            )
        except ConsentStoreError as exc:
            raise consent_store_error(exc) from exc
        except sqlite3.Error as exc:
            raise HTTPException(
                status_code=503, detail="consent_store_unavailable"
            ) from exc
        if token_record is None:
            raise HTTPException(status_code=404, detail="consent_not_found")
        return ConsentStateResponse(
            request_id=token_record.request_id,
            status="revoked",
            expires_at=token_record.expires_at,
        )

    @app.post(
        "/v1/generate/verify",
        response_model=ConsentTokenVerificationResponse,
        responses={
            401: {"model": ErrorResponse},
            503: {"model": ErrorResponse},
        },
        tags=["consent"],
    )
    async def verify_consent(
        payload: ConsentTokenVerificationRequest,
        app_identity: str = Depends(authenticate),
    ) -> ConsentTokenVerificationResponse:
        if token_service is None:
            return ConsentTokenVerificationResponse(
                valid=False, state=ConsentState.UNAVAILABLE.value
            )
        now = int(time.time())
        try:
            check_context = consent_store.get_check(
                payload.check_id, app_id=app_identity, now=now
            )
        except sqlite3.Error as exc:
            raise HTTPException(
                status_code=503, detail="consent_store_unavailable"
            ) from exc
        if check_context is None:
            return ConsentTokenVerificationResponse(
                valid=False, state="check_not_found"
            )
        try:
            scope = Scope(check_context.scope)
        except ValueError:
            return ConsentTokenVerificationResponse(
                valid=False, state="check_not_eligible"
            )
        if (
            SCOPE_TIERS[scope] is not Tier.IDENTITY_ALTERING
            or check_context.decision not in {"needs_consent", "allow"}
        ):
            return ConsentTokenVerificationResponse(
                valid=False, state="check_not_eligible"
            )
        if check_context.target_digest != target_reference_digest(
            payload.target_ref
        ):
            return ConsentTokenVerificationResponse(
                valid=False, state=ConsentState.FACE_MISMATCH.value
            )
        consent_check_id = check_context.consent_check_id or check_context.check_id
        state = token_service.verify(
            payload.consent_token,
            app_id=app_identity,
            scope=check_context.scope,
            target_ref=payload.target_ref,
            check_id=consent_check_id,
        )
        return ConsentTokenVerificationResponse(
            valid=state is ConsentState.VALID, state=state.value
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
        mock_signal: MockResultSignal | None = Form(
            default=None,
            description="Test-only signal for the explicitly enabled result-check stub",
        ),
        consent_token: str | None = Form(
            default=None,
            description="Required for identity-altering checks with consent",
        ),
        target_ref: str | None = Form(
            default=None,
            description="Opaque target reference matching the consent-bound check",
        ),
        app_identity: str = Depends(authenticate),
    ) -> StampReceipt:
        if not check_id or not check_id.startswith("c_") or len(check_id) > 64:
            raise HTTPException(
                status_code=422,
                detail="invalid_check_id",
            )

        try:
            check_context = consent_store.get_check(
                check_id, app_id=app_identity, now=int(time.time())
            )
        except sqlite3.Error as exc:
            raise HTTPException(
                status_code=503, detail="consent_store_unavailable"
            ) from exc
        if check_context is None:
            raise HTTPException(status_code=404, detail="check_not_found")
        if check_context.decision != DecisionName.ALLOW.value:
            raise HTTPException(status_code=409, detail="check_not_eligible")

        try:
            scope = Scope(check_context.scope)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail="check_not_eligible") from exc
        tier = SCOPE_TIERS[scope]
        if tier is Tier.SEXUAL_REAL_FACE:
            raise HTTPException(status_code=409, detail="check_not_eligible")
        if tier is Tier.IDENTITY_ALTERING:
            if (
                token_service is None
                or check_context.consent_check_id is None
                or consent_token is None
                or target_ref is None
                or check_context.target_digest
                != target_reference_digest(target_ref)
            ):
                raise HTTPException(status_code=409, detail="consent_required")
            state = token_service.verify(
                consent_token,
                app_id=app_identity,
                scope=check_context.scope,
                target_ref=target_ref,
                check_id=check_context.consent_check_id,
            )
            if state is not ConsentState.VALID:
                if state is ConsentState.UNAVAILABLE:
                    raise HTTPException(
                        status_code=503, detail="consent_store_unavailable"
                    )
                raise HTTPException(status_code=409, detail="consent_required")
        elif tier is not Tier.BENIGN:
            raise HTTPException(status_code=409, detail="check_not_eligible")

        if mock_signal is not None and not configured.enable_test_signals:
            raise HTTPException(status_code=400, detail="test_signals_disabled")
        if ledger.get_by_check_id(check_id) is not None:
            raise HTTPException(status_code=409, detail="output_already_stamped")

        image_bytes = await image.read(configured.max_output_size_bytes + 1)
        if len(image_bytes) > configured.max_output_size_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail="payload_too_large",
            )
        if len(image_bytes) < 8:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="invalid_image_format",
            )

        try:
            with Image.open(io.BytesIO(image_bytes)) as pil_img:
                if pil_img.format not in {"PNG", "JPEG", "WEBP"} or getattr(
                    pil_img, "n_frames", 1
                ) != 1:
                    raise ValueError("Unsupported image format.")
                pil_img.verify()
        except (
            OSError,
            ValueError,
            SyntaxError,
            Image.DecompressionBombError,
        ) as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="invalid_image_format",
            ) from exc

        context = ResultCheckContext(
            check_id=check_id,
            app_id=app_identity,
            high_risk=tier is not Tier.BENIGN,
            mock_signal=mock_signal,
        )

        try:
            check_result = checker.check_output(image_bytes, context)
        except Exception as exc:
            raise HTTPException(
                status_code=422,
                detail="result_check_failed",
            ) from exc

        if not check_result.allowed or check_result.is_indeterminate:
            first_reason = (
                check_result.reason_codes[0]
                if check_result.reason_codes
                else (
                    "safety_check_indeterminate"
                    if check_result.is_indeterminate
                    else "output_rejected"
                )
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
        output_ref = f"out_{uuid4().hex}"
        try:
            store.store(output_ref, stamped_bytes, app_identity, "image/png")
        except Exception as exc:
            try:
                store.delete(output_ref, app_identity)
            except Exception as cleanup_error:
                raise HTTPException(
                    status_code=500, detail="output_persistence_failed"
                ) from cleanup_error
            raise HTTPException(
                status_code=500, detail="output_persistence_failed"
            ) from exc
        try:
            record = ledger.append(
                check_id=check_id,
                app_id=app_identity,
                output_sha256=output_sha256,
                pre_stamp_sha256=pre_stamp_sha256,
                phash=phash,
                label="AI-generated",
                decision="stamped",
            )
        except LedgerConflictError as exc:
            store.delete(output_ref, app_identity)
            raise HTTPException(
                status_code=409, detail="output_already_stamped"
            ) from exc
        except Exception as exc:
            try:
                store.delete(output_ref, app_identity)
            except Exception as cleanup_error:
                raise HTTPException(
                    status_code=500, detail="output_persistence_failed"
                ) from cleanup_error
            raise HTTPException(
                status_code=500, detail="output_persistence_failed"
            ) from exc

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
    async def download_output(
        output_ref: str,
        app_identity: str = Depends(authenticate),
    ) -> Response:
        stored = store.get(output_ref, app_identity)
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

    @app.get(
        "/v1/ledger/verify",
        response_model=LedgerVerificationResponse,
        tags=["provenance"],
    )
    async def verify_ledger() -> LedgerVerificationResponse:
        valid, error = ledger.verify_integrity()
        return LedgerVerificationResponse(
            valid=valid,
            error=error,
            entries_count=len(ledger.snapshot()),
            head_hash=ledger.head_hash(),
        )

    return app
