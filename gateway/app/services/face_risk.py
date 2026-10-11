from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from gateway.app.schemas import CheckRequest


@dataclass(frozen=True)
class FaceRiskAssessment:
    real_face: bool | None
    minor_risk: bool | None


class FaceRiskService(Protocol):
    def assess(self, request: CheckRequest) -> FaceRiskAssessment: ...


class MockFaceRiskService:
    """Demo-only adapter for untrusted request signals; never detects faces or age."""

    def assess(self, request: CheckRequest) -> FaceRiskAssessment:
        signals = request.test_signals
        return FaceRiskAssessment(
            real_face=signals.real_face if signals is not None else None,
            minor_risk=(
                signals.minor_risk
                if signals is not None
                else None
            ),
        )
