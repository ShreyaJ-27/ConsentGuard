from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


FLAGGED_FIXTURE_MARKER = b"__FLAGGED_HARMFUL_OUTPUT__"


class ResultCheckError(Exception):
    """Raised when an error occurs during output safety analysis."""


@dataclass(frozen=True)
class ResultCheckContext:
    """Contextual metadata passed to output safety checkers."""

    check_id: str
    app_id: str
    high_risk: bool = False
    mock_signal: str | None = None


@dataclass(frozen=True)
class ResultCheck:
    """Structured result of defensive output inspection."""

    allowed: bool
    reason_codes: tuple[str, ...]
    checks_run: tuple[str, ...]
    is_indeterminate: bool = False


class ResultChecker(Protocol):
    """Interface for verifying generated content before acceptance and provenance stamping."""

    def check_output(
        self, image_bytes: bytes, context: ResultCheckContext
    ) -> ResultCheck: ...


class StubResultChecker:
    """Prototype result-check stub for defensive output verification.

    IMPORTANT SAFETY NOTICE:
    This is an explicitly labelled test stub and does NOT provide real-world
    NSFW, nudity, or biometric face safety classification. It exists solely to
    exercise the fail-closed gateway workflow and automated test suites.
    Never describe or use this stub as a production safety classifier.
    """

    def check_output(
        self, image_bytes: bytes, context: ResultCheckContext
    ) -> ResultCheck:
        checks_run = ("stub_nsfw_check", "stub_face_harm_check")

        if not image_bytes or len(image_bytes) < 8:
            return ResultCheck(
                allowed=False,
                reason_codes=("invalid_image_data",),
                checks_run=checks_run,
            )

        if (
            context.mock_signal == "flagged"
            or FLAGGED_FIXTURE_MARKER in image_bytes
        ):
            return ResultCheck(
                allowed=False,
                reason_codes=("harmful_content_detected",),
                checks_run=checks_run,
            )

        if context.mock_signal == "error":
            raise ResultCheckError("Simulated safety check failure")

        if context.mock_signal == "indeterminate":
            if context.high_risk:
                return ResultCheck(
                    allowed=False,
                    reason_codes=("safety_check_indeterminate_high_risk",),
                    checks_run=checks_run,
                    is_indeterminate=True,
                )
            return ResultCheck(
                allowed=False,
                reason_codes=("safety_check_indeterminate",),
                checks_run=checks_run,
                is_indeterminate=True,
            )

        return ResultCheck(
            allowed=True,
            reason_codes=("output_check_passed",),
            checks_run=checks_run,
        )
