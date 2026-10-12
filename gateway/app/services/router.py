from __future__ import annotations

from dataclasses import dataclass

from gateway.app.policy import SCOPE_TIERS, Scope, Tier
from gateway.app.services.consent import ConsentState
from gateway.app.services.face_risk import FaceRiskAssessment
from gateway.app.services.risk import RiskAssessment
from gateway.app.schemas import DecisionName


@dataclass(frozen=True)
class RouteDecision:
    decision: DecisionName
    tier: Tier
    reasons: tuple[str, ...]


def decide(
    *,
    scope: Scope,
    face_risk: FaceRiskAssessment,
    request_risk: RiskAssessment,
    consent_state: ConsentState,
    risk_block_threshold: float,
) -> RouteDecision:
    """Pure policy router: the structured scope, not prompt wording, sets the tier."""
    tier = SCOPE_TIERS[scope]
    is_real_face = face_risk.real_face
    if is_real_face is None:
        is_real_face = tier in (Tier.IDENTITY_ALTERING, Tier.SEXUAL_REAL_FACE)

    if tier is Tier.SEXUAL_REAL_FACE:
        return RouteDecision(
            DecisionName.BLOCK, tier, ("sexual_real_face_hard_block",)
        )

    if tier in (Tier.IDENTITY_ALTERING, Tier.SEXUAL_REAL_FACE):
        if face_risk.minor_risk is None:
            return RouteDecision(
                DecisionName.BLOCK, tier, ("minor_risk_unavailable",)
            )
        if face_risk.minor_risk:
            return RouteDecision(DecisionName.BLOCK, tier, ("child_risk_hard_block",))

    if request_risk.score >= risk_block_threshold:
        return RouteDecision(DecisionName.BLOCK, tier, ("high_request_risk",))

    if tier is Tier.BENIGN or not is_real_face:
        return RouteDecision(DecisionName.ALLOW, tier, ("benign_edit",))

    if consent_state is ConsentState.VALID:
        return RouteDecision(DecisionName.ALLOW, tier, ("valid_consent",))

    reason = {
        ConsentState.MISSING: "consent_required",
        ConsentState.INVALID_SIGNATURE: "consent_invalid_signature",
        ConsentState.INVALID_ISSUER: "consent_invalid_issuer",
        ConsentState.INVALID_TOKEN: "consent_invalid_token",
        ConsentState.EXPIRED: "consent_expired",
        ConsentState.REVOKED: "consent_revoked",
        ConsentState.WRONG_SCOPE: "consent_wrong_scope",
        ConsentState.WRONG_APP: "consent_wrong_app",
        ConsentState.FACE_MISMATCH: "consent_face_mismatch",
        ConsentState.UNAVAILABLE: "consent_verification_unavailable",
    }[consent_state]
    return RouteDecision(DecisionName.NEEDS_CONSENT, tier, (reason,))
