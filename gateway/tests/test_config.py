from __future__ import annotations

import hashlib

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient

from gateway.app.config import Settings
from gateway.app.main import create_app
from gateway.app.services.consent import load_signing_key


def test_documented_environment_settings_are_loaded(monkeypatch, tmp_path) -> None:
    api_key = "local-api-key-for-test-that-is-long"
    hmac_key = "local-hmac-key-for-test-that-is-long"
    signing_key_path = tmp_path / "signing-key.pem"
    database_path = tmp_path / "consent.sqlite3"
    monkeypatch.setenv("CONSENTGUARD_API_KEY", api_key)
    monkeypatch.setenv("CONSENTGUARD_USER_REF_HMAC_KEY", hmac_key)
    monkeypatch.setenv("CONSENTGUARD_APP_ID", "configured-app")
    monkeypatch.setenv("CONSENTGUARD_BLOCKED_ATTEMPT_THRESHOLD", "4")
    monkeypatch.setenv("CONSENTGUARD_RESTRICTION_WINDOW_SECONDS", "3600")
    monkeypatch.setenv("CONSENTGUARD_RATE_LIMIT_REQUESTS", "12")
    monkeypatch.setenv("CONSENTGUARD_RATE_LIMIT_WINDOW_SECONDS", "30")
    monkeypatch.setenv("CONSENTGUARD_RISK_BLOCK_THRESHOLD", "0.9")
    monkeypatch.setenv("CONSENTGUARD_ENABLE_TEST_SIGNALS", "true")
    monkeypatch.setenv("CONSENTGUARD_SIGNING_KEY_PATH", str(signing_key_path))
    monkeypatch.setenv("CONSENTGUARD_CONSENT_ISSUER", "tests.local")
    monkeypatch.setenv("CONSENTGUARD_CONSENT_TOKEN_TTL_SECONDS", "120")
    monkeypatch.setenv("CONSENTGUARD_CONSENT_DATABASE_PATH", str(database_path))
    monkeypatch.setenv("CONSENTGUARD_ENABLE_DEMO_SUBJECT_ACTIONS", "true")
    monkeypatch.setenv("CONSENTGUARD_MAX_OUTPUT_SIZE_BYTES", "4096")

    settings = Settings.from_env()

    assert settings.api_key_digest == hashlib.sha256(api_key.encode()).digest()
    assert settings.user_ref_hmac_key == hmac_key.encode()
    assert settings.app_id == "configured-app"
    assert settings.blocked_attempt_threshold == 4
    assert settings.restriction_window_seconds == 3600
    assert settings.rate_limit_requests == 12
    assert settings.rate_limit_window_seconds == 30
    assert settings.risk_block_threshold == 0.9
    assert settings.enable_test_signals is True
    assert settings.consent_signing_key_path == str(signing_key_path)
    assert settings.consent_database_path == str(database_path)
    assert settings.consent_issuer == "tests.local"
    assert settings.consent_token_ttl_seconds == 120
    assert settings.enable_demo_subject_actions is True
    assert settings.max_output_size_bytes == 4096


def test_sensitive_demo_flags_default_to_disabled(monkeypatch) -> None:
    monkeypatch.setenv("CONSENTGUARD_API_KEY", "a" * 32)
    monkeypatch.setenv("CONSENTGUARD_USER_REF_HMAC_KEY", "b" * 32)
    for name in (
        "CONSENTGUARD_ENABLE_TEST_SIGNALS",
        "CONSENTGUARD_ENABLE_DEMO_SUBJECT_ACTIONS",
    ):
        monkeypatch.delenv(name, raising=False)

    settings = Settings.from_env()

    assert settings.enable_test_signals is False
    assert settings.enable_demo_subject_actions is False
    assert settings.consent_signing_key_path is None
    assert settings.consent_database_path == "consentguard.sqlite3"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("consent_database_path", ""),
        ("consent_signing_key_path", ""),
        ("consent_issuer", " "),
        ("consent_token_ttl_seconds", 0),
        ("max_output_size_bytes", 0),
    ],
)
def test_invalid_consent_and_upload_settings_are_rejected(
    settings: Settings, field: str, value: object
) -> None:
    with pytest.raises(ValueError):
        Settings(
            **{
                **{
                    name: getattr(settings, name)
                    for name in settings.__dataclass_fields__
                },
                field: value,
            }
        )


def test_invalid_boolean_environment_value_is_rejected(monkeypatch) -> None:
    monkeypatch.setenv("CONSENTGUARD_API_KEY", "a" * 32)
    monkeypatch.setenv("CONSENTGUARD_USER_REF_HMAC_KEY", "b" * 32)
    monkeypatch.setenv("CONSENTGUARD_ENABLE_DEMO_SUBJECT_ACTIONS", "sometimes")

    with pytest.raises(ValueError, match="CONSENTGUARD_ENABLE_DEMO_SUBJECT_ACTIONS"):
        Settings.from_env()


def test_application_starts_from_documented_environment_settings(
    monkeypatch, tmp_path
) -> None:
    key_path = tmp_path / "consent-signing-key.pem"
    private_key = Ed25519PrivateKey.generate()
    key_path.write_bytes(
        private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    monkeypatch.setenv("CONSENTGUARD_API_KEY", "local-api-key-for-test-that-is-long")
    monkeypatch.setenv(
        "CONSENTGUARD_USER_REF_HMAC_KEY", "local-hmac-key-for-test-that-is-long"
    )
    monkeypatch.setenv("CONSENTGUARD_APP_ID", "env-startup-test")
    monkeypatch.setenv("CONSENTGUARD_SIGNING_KEY_PATH", str(key_path))
    monkeypatch.setenv(
        "CONSENTGUARD_CONSENT_DATABASE_PATH", str(tmp_path / "consent.sqlite3")
    )
    monkeypatch.setenv("CONSENTGUARD_CONSENT_ISSUER", "env-test.local")
    monkeypatch.setenv("CONSENTGUARD_CONSENT_TOKEN_TTL_SECONDS", "300")
    monkeypatch.setenv("CONSENTGUARD_ENABLE_TEST_SIGNALS", "false")
    monkeypatch.setenv("CONSENTGUARD_ENABLE_DEMO_SUBJECT_ACTIONS", "false")

    client = TestClient(create_app())

    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/docs").status_code == 200
    openapi = client.get("/openapi.json").json()
    assert "/v1/check" in openapi["paths"]
    assert "/v1/consent/requests" in openapi["paths"]
    assert "/v1/output/stamp" in openapi["paths"]


def test_invalid_ed25519_key_fails_with_safe_startup_error(tmp_path) -> None:
    key_path = tmp_path / "invalid-key.pem"
    key_path.write_bytes(b"not a private key")

    with pytest.raises(ValueError, match="Unable to load configured Ed25519"):
        load_signing_key(str(key_path))


def test_non_ed25519_private_key_is_rejected(tmp_path) -> None:
    from cryptography.hazmat.primitives.asymmetric import rsa

    key_path = tmp_path / "rsa-key.pem"
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    key_path.write_bytes(
        private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )

    with pytest.raises(ValueError, match="must be an Ed25519 private key"):
        load_signing_key(str(key_path))
