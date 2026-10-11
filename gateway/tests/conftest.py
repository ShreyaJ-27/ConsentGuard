from __future__ import annotations

import hashlib

import pytest

from gateway.app.config import Settings


@pytest.fixture
def settings() -> Settings:
    return Settings(
        api_key_digest=hashlib.sha256(b"test-api-key").digest(),
        user_ref_hmac_key=b"test-user-reference-hmac-key-0123456789",
        app_id="test-partner",
        blocked_attempt_threshold=3,
        restriction_window_seconds=7 * 24 * 60 * 60,
        rate_limit_requests=60,
        rate_limit_window_seconds=60,
        risk_block_threshold=0.85,
        enable_test_signals=True,
    )
