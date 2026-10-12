from __future__ import annotations

from itertools import product

import pytest

from gateway.app.policy import SCOPE_TIERS, Scope, Tier
from gateway.app.schemas import DecisionName
from gateway.app.services.consent import ConsentState
from gateway.app.services.face_risk import FaceRiskAssessment
from gateway.app.services.risk import RiskAssessment
from gateway.app.services.router import decide


@pytest.mark.parametrize(
    ("scope", "expected_tier"),
    [
        (Scope.FILTER, Tier.BENIGN),
        (Scope.LIGHTING, Tier.BENIGN),
        (Scope.CROP, Tier.BENIGN),
        (Scope.BACKGROUND, Tier.BENIGN),
        (Scope.FACE_SWAP, Tier.IDENTITY_ALTERING),
        (Scope.PHOTO_ANIMATION, Tier.IDENTITY_ALTERING),
        (Scope.BODY_EDIT, Tier.IDENTITY_ALTERING),
        (Scope.VOICE_CLONE, Tier.IDENTITY_ALTERING),
        (Scope.SEXUAL_TRANSFORMATION, Tier.SEXUAL_REAL_FACE),
        (Scope.NUDE_TRANSFORMATION, Tier.SEXUAL_REAL_FACE),
    ],
)
def test_policy_assigns_every_known_scope(scope: Scope, expected_tier: Tier) -> None:
    assert SCOPE_TIERS[scope] is expected_tier


def _expected_decision(
    scope: Scope,
    real_face: bool | None,
    minor_risk: bool | None,
    consent: ConsentState,
    risk_score: float,
) -> DecisionName:
    tier = SCOPE_TIERS[scope]
    if tier is Tier.SEXUAL_REAL_FACE:
        return DecisionName.BLOCK
    if tier in (Tier.IDENTITY_ALTERING, Tier.SEXUAL_REAL_FACE):
        if minor_risk is None or minor_risk:
            return DecisionName.BLOCK
    effective_real_face = (
        real_face
        if real_face is not None
        else tier in (Tier.IDENTITY_ALTERING, Tier.SEXUAL_REAL_FACE)
    )
    if tier is Tier.SEXUAL_REAL_FACE and effective_real_face:
        return DecisionName.BLOCK
    if risk_score >= 0.85:
        return DecisionName.BLOCK
    if tier is Tier.BENIGN or not effective_real_face:
        return DecisionName.ALLOW
    if consent is ConsentState.VALID:
        return DecisionName.ALLOW
    return DecisionName.NEEDS_CONSENT


@pytest.mark.parametrize(
    ("scope", "real_face", "minor_risk", "consent", "risk_score"),
    list(
        product(
            (Scope.FILTER, Scope.FACE_SWAP, Scope.BODY_EDIT, Scope.NUDE_TRANSFORMATION),
            (None, False, True),
            (None, False, True),
            tuple(ConsentState),
            (0.0, 0.85),
        )
    ),
)
def test_router_safety_matrix(
    scope: Scope,
    real_face: bool | None,
    minor_risk: bool | None,
    consent: ConsentState,
    risk_score: float,
) -> None:
    result = decide(
        scope=scope,
        face_risk=FaceRiskAssessment(
            real_face=real_face, minor_risk=minor_risk
        ),
        request_risk=RiskAssessment(
            score=risk_score, label="test", source="test"
        ),
        consent_state=consent,
        risk_block_threshold=0.85,
    )
    assert result.decision is _expected_decision(
        scope, real_face, minor_risk, consent, risk_score
    )


@pytest.mark.parametrize("scope", [Scope.FACE_SWAP, Scope.BODY_EDIT])
def test_tier_one_real_face_requires_valid_consent(scope: Scope) -> None:
    for state in ConsentState:
        result = decide(
            scope=scope,
            face_risk=FaceRiskAssessment(real_face=True, minor_risk=False),
            request_risk=RiskAssessment(0.0, "unassessed", "stub"),
            consent_state=state,
            risk_block_threshold=0.85,
        )
        if state is ConsentState.VALID:
            assert result.decision is DecisionName.ALLOW
        else:
            assert result.decision is DecisionName.NEEDS_CONSENT


@pytest.mark.parametrize(
    ("scope", "real_face"),
    [
        (Scope.SEXUAL_TRANSFORMATION, True),
        (Scope.NUDE_TRANSFORMATION, True),
        (Scope.SEXUAL_TRANSFORMATION, None),
        (Scope.NUDE_TRANSFORMATION, None),
        (Scope.SEXUAL_TRANSFORMATION, False),
        (Scope.NUDE_TRANSFORMATION, False),
    ],
)
def test_tier_two_real_face_is_blocked_even_with_valid_consent(
    scope: Scope, real_face: bool | None
) -> None:
    result = decide(
        scope=scope,
        face_risk=FaceRiskAssessment(real_face=real_face, minor_risk=False),
        request_risk=RiskAssessment(0.0, "unassessed", "stub"),
        consent_state=ConsentState.VALID,
        risk_block_threshold=0.85,
    )
    assert result.decision is DecisionName.BLOCK
    assert "sexual_real_face_hard_block" in result.reasons


@pytest.mark.parametrize("scope", [Scope.FACE_SWAP, Scope.NUDE_TRANSFORMATION])
def test_child_risk_blocks_without_consent_override(scope: Scope) -> None:
    result = decide(
        scope=scope,
        face_risk=FaceRiskAssessment(real_face=True, minor_risk=True),
        request_risk=RiskAssessment(0.0, "unassessed", "stub"),
        consent_state=ConsentState.VALID,
        risk_block_threshold=0.85,
    )
    assert result.decision is DecisionName.BLOCK
    expected_reason = (
        "sexual_real_face_hard_block"
        if scope is Scope.NUDE_TRANSFORMATION
        else "child_risk_hard_block"
    )
    assert expected_reason in result.reasons


def test_missing_minor_risk_fails_closed_for_identity_altering_scope() -> None:
    result = decide(
        scope=Scope.FACE_SWAP,
        face_risk=FaceRiskAssessment(real_face=True, minor_risk=None),
        request_risk=RiskAssessment(0.0, "unassessed", "stub"),
        consent_state=ConsentState.VALID,
        risk_block_threshold=0.85,
    )
    assert result.decision is DecisionName.BLOCK
    assert result.reasons == ("minor_risk_unavailable",)


@pytest.mark.parametrize("score", [0.85, 0.9, 1.0])
def test_configured_high_request_risk_blocks(score: float) -> None:
    result = decide(
        scope=Scope.FILTER,
        face_risk=FaceRiskAssessment(real_face=False, minor_risk=False),
        request_risk=RiskAssessment(score, "high", "test"),
        consent_state=ConsentState.MISSING,
        risk_block_threshold=0.85,
    )
    assert result.decision is DecisionName.BLOCK
    assert result.reasons == ("high_request_risk",)


def test_unknown_scope_cannot_fall_back_to_benign() -> None:
    with pytest.raises(KeyError):
        decide(
            scope="unknown_scope",  # type: ignore[arg-type]
            face_risk=FaceRiskAssessment(real_face=False, minor_risk=False),
            request_risk=RiskAssessment(0.0, "unassessed", "stub"),
            consent_state=ConsentState.MISSING,
            risk_block_threshold=0.85,
        )
