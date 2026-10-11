from __future__ import annotations

from enum import Enum
from typing import Protocol


class ConsentState(str, Enum):
    MISSING = "missing"
    VALID = "valid"
    INVALID_SIGNATURE = "invalid_signature"
    EXPIRED = "expired"
    REVOKED = "revoked"
    WRONG_SCOPE = "wrong_scope"
    WRONG_APP = "wrong_app"
    FACE_MISMATCH = "face_mismatch"
    UNAVAILABLE = "unavailable"


class ConsentVerifier(Protocol):
    def verify(self, token: str | None, *, app_id: str, scope: str) -> ConsentState: ...


class UnavailableConsentVerifier:
    """Safe integration boundary; token verification is not implemented here."""

    def verify(self, token: str | None, *, app_id: str, scope: str) -> ConsentState:
        del app_id, scope
        return ConsentState.MISSING if token is None else ConsentState.UNAVAILABLE
