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
