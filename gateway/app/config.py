from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass

from gateway.app.policy import RISK_BLOCK_THRESHOLD


def _required_secret(name: str) -> str:
    value = os.getenv(name, "")
    if len(value) < 32:
        raise ValueError(f"{name} must contain at least 32 characters.")
    return value


def _boolean_setting(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean value.")


@dataclass(frozen=True)
class Settings:
    api_key_digest: bytes
    user_ref_hmac_key: bytes
    app_id: str = "local-demo"
    blocked_attempt_threshold: int = 3
    restriction_window_seconds: int = 7 * 24 * 60 * 60
    rate_limit_requests: int = 60
    rate_limit_window_seconds: int = 60
    risk_block_threshold: float = RISK_BLOCK_THRESHOLD
    enable_test_signals: bool = False

    def __post_init__(self) -> None:
        if len(self.api_key_digest) != hashlib.sha256().digest_size:
            raise ValueError("api_key_digest must be a SHA-256 digest.")
        if len(self.user_ref_hmac_key) < 32:
            raise ValueError("user_ref_hmac_key must contain at least 32 bytes.")
        if not self.app_id.strip():
            raise ValueError("app_id must not be empty.")
        if self.blocked_attempt_threshold < 1:
            raise ValueError("blocked_attempt_threshold must be positive.")
        if self.restriction_window_seconds < 1:
            raise ValueError("restriction_window_seconds must be positive.")
        if self.rate_limit_requests < 1 or self.rate_limit_window_seconds < 1:
            raise ValueError("Rate-limit settings must be positive.")
        if not 0 <= self.risk_block_threshold <= 1:
            raise ValueError("risk_block_threshold must be between 0 and 1.")

    @classmethod
    def from_env(cls) -> Settings:
        api_key = _required_secret("CONSENTGUARD_API_KEY")
        hmac_key = _required_secret("CONSENTGUARD_USER_REF_HMAC_KEY")
        return cls(
            api_key_digest=hashlib.sha256(api_key.encode("utf-8")).digest(),
            user_ref_hmac_key=hmac_key.encode("utf-8"),
            app_id=os.getenv("CONSENTGUARD_APP_ID", "local-demo"),
            blocked_attempt_threshold=int(
                os.getenv("CONSENTGUARD_BLOCKED_ATTEMPT_THRESHOLD", "3")
            ),
            restriction_window_seconds=int(
                os.getenv("CONSENTGUARD_RESTRICTION_WINDOW_SECONDS", "604800")
            ),
            rate_limit_requests=int(
                os.getenv("CONSENTGUARD_RATE_LIMIT_REQUESTS", "60")
            ),
            rate_limit_window_seconds=int(
                os.getenv("CONSENTGUARD_RATE_LIMIT_WINDOW_SECONDS", "60")
            ),
            risk_block_threshold=float(
                os.getenv(
                    "CONSENTGUARD_RISK_BLOCK_THRESHOLD",
                    str(RISK_BLOCK_THRESHOLD),
                )
            ),
            enable_test_signals=_boolean_setting(
                "CONSENTGUARD_ENABLE_TEST_SIGNALS"
            ),
        )
