from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from gateway.app.policy import Scope


class DecisionName(str, Enum):
    ALLOW = "allow"
    NEEDS_CONSENT = "needs_consent"
    BLOCK = "block"


class MockSafetySignals(BaseModel):
    model_config = ConfigDict(extra="forbid")

    real_face: bool | None = Field(
        default=None,
        description=(
            "Demo-only mock signal; not trusted face detection. Omit when unknown."
        ),
    )
    minor_risk: bool | None = Field(
        default=None,
        description=(
            "Demo-only mock signal; not trusted age detection. Omit when unknown."
        ),
    )


class CheckRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt: str = Field(min_length=1, max_length=4000)
    scope: Scope
    user_ref: str = Field(min_length=1, max_length=256)
    consent_token: str | None = Field(default=None, max_length=8192)
    target_ref: str | None = Field(
        default=None,
        min_length=1,
        max_length=512,
        description="Opaque target reference; not proof of the subject's identity.",
    )
    test_signals: MockSafetySignals | None = Field(
        default=None,
        description=(
            "Test/demo-only signals. Production deployments must use a trusted "
            "server-side face and age risk service instead."
        ),
    )


class RequestRiskResponse(BaseModel):
    score: float
    label: str
    source: str


class CheckResponse(BaseModel):
    check_id: str
    decision: DecisionName
    tier: int
    reasons: list[str]
    consent_required: bool
    request_risk: RequestRiskResponse


class ConsentRequestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    check_id: str = Field(min_length=1, max_length=64)


class ConsentRequestResponse(BaseModel):
    request_id: str
    status: str
    expires_at: int
    demo_action_code: str | None = None


class ConsentSubjectAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str = Field(min_length=1, max_length=64)
    demo_action_code: str = Field(min_length=32, max_length=128)


class ConsentApprovalResponse(BaseModel):
    request_id: str
    status: str
    consent_token: str
    expires_at: int


class ConsentRevocationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    jti: str = Field(min_length=1, max_length=64)
    demo_action_code: str = Field(min_length=32, max_length=128)


class ConsentStateResponse(BaseModel):
    request_id: str | None = None
    status: str
    expires_at: int | None = None


class ConsentTokenVerificationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    check_id: str = Field(min_length=1, max_length=64)
    consent_token: str = Field(min_length=1, max_length=8192)
    target_ref: str = Field(min_length=1, max_length=512)


class ConsentTokenVerificationResponse(BaseModel):
    valid: bool
    state: str


class HealthResponse(BaseModel):
    status: str


class ErrorBody(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorBody


class StampReceipt(BaseModel):
    check_id: str
    entry_id: str
    output_sha256: str
    pre_stamp_sha256: str
    phash: str
    label: str
    created_at: str
    ledger_entry_hash: str
    output_ref: str | None = None


class LookupProvenance(BaseModel):
    check_id: str
    label: str
    created_at: str
    output_sha256: str


class LookupResponse(BaseModel):
    match: bool
    method: str
    provenance: LookupProvenance | None = None
    message: str | None = None
    distance: int | None = None
