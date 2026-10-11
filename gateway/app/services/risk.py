from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class RiskAssessment:
    score: float
    label: str
    source: str

    def __post_init__(self) -> None:
        if not 0 <= self.score <= 1:
            raise ValueError("Risk score must be between 0 and 1.")
        if not self.label or not self.source:
            raise ValueError("Risk label and source must not be empty.")


class RequestRiskScorer(Protocol):
    def assess(self, prompt: str) -> RiskAssessment: ...


class StubRequestRiskScorer:
    """Explicitly untrained stub; does not classify prompts or languages."""

    def assess(self, prompt: str) -> RiskAssessment:
        del prompt
        return RiskAssessment(score=0.0, label="unassessed", source="stub")
