from __future__ import annotations

import hashlib

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from gateway.app.config import Settings


@pytest.fixture
def settings(tmp_path) -> Settings:
    signing_key = Ed25519PrivateKey.generate()
    key_path = tmp_path / "test-consent-signing-key.pem"
    key_path.write_bytes(
        signing_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
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
        consent_database_path=str(tmp_path / "consent.sqlite3"),
        consent_signing_key_path=str(key_path),
        enable_demo_subject_actions=True,
    )
