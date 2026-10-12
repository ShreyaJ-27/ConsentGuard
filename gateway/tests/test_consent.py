from __future__ import annotations

import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import fields

import jwt
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient

from gateway.app.config import Settings
from gateway.app.main import create_app
from gateway.app.services.consent import (
    ConsentState,
    ConsentTokenService,
    load_signing_key,
    target_reference_digest,
)
from gateway.app.services.consent_store import (
    ConsentStoreError,
    SQLiteConsentStore,
)


API_KEY = "test-api-key"
HEADERS = {"X-API-Key": API_KEY}


def _needs_consent_check(
    client: TestClient,
    *,
    scope: str = "face_swap",
    target_ref: str = "opaque-face-ref",
) -> str:
    response = client.post(
        "/v1/check",
        headers=HEADERS,
        json={
            "prompt": "Apply a harmless style",
            "scope": scope,
            "user_ref": "demo-user",
            "target_ref": target_ref,
            "test_signals": {"real_face": True, "minor_risk": False},
        },
    )
    assert response.status_code == 200
    assert response.json()["decision"] == "needs_consent"
    return response.json()["check_id"]


def _new_consent(client: TestClient, check_id: str) -> dict[str, str]:
    response = client.post(
        "/v1/consent/requests",
        headers=HEADERS,
        json={"check_id": check_id},
    )
    assert response.status_code == 200
    return response.json()


def _approved_consent(client: TestClient) -> tuple[str, dict[str, str]]:
    check_id = _needs_consent_check(client)
    request = _new_consent(client, check_id)
    approval = client.post(
        "/v1/consent/approve",
        json={
            "request_id": request["request_id"],
            "demo_action_code": request["demo_action_code"],
        },
    )
    assert approval.status_code == 200
    return check_id, {**request, **approval.json()}


def _jti(token: str) -> str:
    return jwt.decode(
        token, options={"verify_signature": False, "verify_exp": False}
    )["jti"]


def _invalid_signature(token: str) -> str:
    header, payload, signature = token.split(".")
    changed = ("A" if signature[0] != "A" else "B") + signature[1:]
    return f"{header}.{payload}.{changed}"


def test_approval_issues_signed_token_and_gateway_allows_matching_consent(
    settings: Settings,
) -> None:
    client = TestClient(create_app(settings))
    check_id, consent = _approved_consent(client)

    verified = client.post(
        "/v1/generate/verify",
        headers=HEADERS,
        json={
            "check_id": check_id,
            "consent_token": consent["consent_token"],
            "target_ref": "opaque-face-ref",
        },
    )
    assert verified.status_code == 200
    assert verified.json() == {"valid": True, "state": "valid"}

    checked = client.post(
        "/v1/check",
        headers=HEADERS,
        json={
            "prompt": "Apply a harmless style",
            "scope": "face_swap",
            "user_ref": "demo-user",
            "target_ref": "opaque-face-ref",
            "consent_token": consent["consent_token"],
            "consent_check_id": check_id,
            "test_signals": {"real_face": True, "minor_risk": False},
        },
    )
    assert checked.status_code == 200
    assert checked.json()["decision"] == "allow"
    assert checked.json()["reasons"] == ["valid_consent"]
    post_check_verify = client.post(
        "/v1/generate/verify",
        headers=HEADERS,
        json={
            "check_id": checked.json()["check_id"],
            "consent_token": consent["consent_token"],
            "target_ref": "opaque-face-ref",
        },
    )
    assert post_check_verify.json() == {"valid": True, "state": "valid"}


def test_invalid_signature_and_target_mismatch_fail_closed(
    settings: Settings,
) -> None:
    client = TestClient(create_app(settings))
    check_id, consent = _approved_consent(client)
    tampered = _invalid_signature(consent["consent_token"])

    checked = client.post(
        "/v1/check",
        headers=HEADERS,
        json={
            "prompt": "Apply a harmless style",
            "scope": "face_swap",
            "user_ref": "demo-user",
            "target_ref": "opaque-face-ref",
            "consent_token": tampered,
            "consent_check_id": check_id,
            "test_signals": {"real_face": True, "minor_risk": False},
        },
    )
    assert checked.json()["decision"] == "needs_consent"
    assert checked.json()["reasons"] == ["consent_invalid_signature"]

    mismatch = client.post(
        "/v1/generate/verify",
        headers=HEADERS,
        json={
            "check_id": check_id,
            "consent_token": consent["consent_token"],
            "target_ref": "different-face-ref",
        },
    )
    assert mismatch.status_code == 200
    assert mismatch.json() == {"valid": False, "state": "face_mismatch"}


def test_wrong_scope_app_and_unknown_token_are_rejected(settings: Settings) -> None:
    client = TestClient(create_app(settings))
    check_id, consent = _approved_consent(client)
    service = ConsentTokenService(
        store=SQLiteConsentStore(settings.consent_database_path),
        signing_key=load_signing_key(settings.consent_signing_key_path or ""),
        issuer=settings.consent_issuer,
        token_ttl_seconds=settings.consent_token_ttl_seconds,
    )
    token = consent["consent_token"]
    assert service.verify(
        token,
        app_id="another-app",
        scope="face_swap",
        target_ref="opaque-face-ref",
    ) is ConsentState.WRONG_APP
    assert service.verify(
        token,
        app_id=settings.app_id,
        scope="body_edit",
        target_ref="opaque-face-ref",
    ) is ConsentState.WRONG_SCOPE

    unknown_jti = str(uuid.uuid4())
    key = load_signing_key(settings.consent_signing_key_path or "")
    now = int(time.time())
    unknown_token = jwt.encode(
        {
            "iss": settings.consent_issuer,
            "aud": settings.app_id,
            "iat": now,
            "exp": now + 60,
            "jti": unknown_jti,
            "sub": "subject_not_in_database",
            "consent_request_id": "unrecorded-request",
            "scope": "face_swap",
            "target_ref": target_reference_digest("opaque-face-ref"),
        },
        key,
        algorithm="EdDSA",
        headers={"kid": service.key_id},
    )
    assert service.verify(
        unknown_token,
        app_id=settings.app_id,
        scope="face_swap",
        target_ref="opaque-face-ref",
    ) is ConsentState.UNAVAILABLE
    wrong_issuer_claims = jwt.decode(
        unknown_token,
        options={"verify_signature": False, "verify_exp": False},
    )
    wrong_issuer_claims["iss"] = "another-issuer"
    wrong_issuer_token = jwt.encode(
        wrong_issuer_claims,
        key,
        algorithm="EdDSA",
        headers={"kid": service.key_id},
    )
    assert service.verify(
        wrong_issuer_token,
        app_id=settings.app_id,
        scope="face_swap",
        target_ref="opaque-face-ref",
    ) is ConsentState.INVALID_ISSUER
    assert check_id


def test_expired_token_is_rejected(settings: Settings) -> None:
    client = TestClient(create_app(settings))
    check_id, consent = _approved_consent(client)
    key: Ed25519PrivateKey = load_signing_key(
        settings.consent_signing_key_path or ""
    )
    claims = jwt.decode(
        consent["consent_token"],
        options={"verify_signature": False, "verify_exp": False},
    )
    claims["iat"] = int(time.time()) - 120
    claims["exp"] = int(time.time()) - 60
    expired_token = jwt.encode(
        claims,
        key,
        algorithm="EdDSA",
        headers={"kid": jwt.get_unverified_header(consent["consent_token"])["kid"]},
    )
    assert client.post(
        "/v1/generate/verify",
        headers=HEADERS,
        json={
            "check_id": check_id,
            "consent_token": expired_token,
            "target_ref": "opaque-face-ref",
        },
    ).json() == {"valid": False, "state": "expired"}


def test_malformed_tampered_and_invalid_signature_tokens_fail_closed(
    settings: Settings,
) -> None:
    client = TestClient(create_app(settings))
    _, consent = _approved_consent(client)
    service = ConsentTokenService(
        store=SQLiteConsentStore(settings.consent_database_path),
        signing_key=load_signing_key(settings.consent_signing_key_path or ""),
        issuer=settings.consent_issuer,
        token_ttl_seconds=settings.consent_token_ttl_seconds,
    )

    for malformed in ("not-a-jwt", "a.b.c", ""):
        assert service.verify(
            malformed,
            app_id=settings.app_id,
            scope="face_swap",
            target_ref="opaque-face-ref",
        ) is ConsentState.INVALID_TOKEN

    token = consent["consent_token"]
    assert service.verify(
        _invalid_signature(token),
        app_id=settings.app_id,
        scope="face_swap",
        target_ref="opaque-face-ref",
    ) is ConsentState.INVALID_SIGNATURE
    header, payload, signature = token.split(".")
    changed_payload = ("A" if payload[0] != "A" else "B") + payload[1:]
    assert service.verify(
        f"{header}.{changed_payload}.{signature}",
        app_id=settings.app_id,
        scope="face_swap",
        target_ref="opaque-face-ref",
    ) is ConsentState.INVALID_SIGNATURE


def test_required_claims_and_time_claim_validation_fail_closed(
    settings: Settings,
) -> None:
    client = TestClient(create_app(settings))
    _, consent = _approved_consent(client)
    service = ConsentTokenService(
        store=SQLiteConsentStore(settings.consent_database_path),
        signing_key=load_signing_key(settings.consent_signing_key_path or ""),
        issuer=settings.consent_issuer,
        token_ttl_seconds=settings.consent_token_ttl_seconds,
    )
    key = load_signing_key(settings.consent_signing_key_path or "")
    original = jwt.decode(
        consent["consent_token"],
        options={"verify_signature": False, "verify_exp": False},
    )
    kid = jwt.get_unverified_header(consent["consent_token"])["kid"]

    for missing_claim in ("iss", "aud", "iat", "exp", "jti", "sub",
                          "consent_request_id", "scope", "target_ref"):
        claims = dict(original)
        del claims[missing_claim]
        token = jwt.encode(claims, key, algorithm="EdDSA", headers={"kid": kid})
        assert service.verify(
            token,
            app_id=settings.app_id,
            scope="face_swap",
            target_ref="opaque-face-ref",
        ) is ConsentState.INVALID_TOKEN, missing_claim

    for invalid_time in (
        {"iat": int(time.time()) + 120},
        {"iat": "not-a-time"},
        {"nbf": int(time.time()) + 120},
        {"exp": "not-a-time"},
        {"iat": int(original["iat"]) - 60},
    ):
        claims = {**original, **invalid_time}
        token = jwt.encode(claims, key, algorithm="EdDSA", headers={"kid": kid})
        assert service.verify(
            token,
            app_id=settings.app_id,
            scope="face_swap",
            target_ref="opaque-face-ref",
        ) is ConsentState.INVALID_TOKEN


def test_audience_scope_subject_request_and_target_are_bound(
    settings: Settings,
) -> None:
    client = TestClient(create_app(settings))
    _, consent = _approved_consent(client)
    service = ConsentTokenService(
        store=SQLiteConsentStore(settings.consent_database_path),
        signing_key=load_signing_key(settings.consent_signing_key_path or ""),
        issuer=settings.consent_issuer,
        token_ttl_seconds=settings.consent_token_ttl_seconds,
    )
    key = load_signing_key(settings.consent_signing_key_path or "")
    original = jwt.decode(
        consent["consent_token"],
        options={"verify_signature": False, "verify_exp": False},
    )
    kid = jwt.get_unverified_header(consent["consent_token"])["kid"]

    def resign(**changes: object) -> str:
        claims = {**original, **changes}
        return jwt.encode(claims, key, algorithm="EdDSA", headers={"kid": kid})

    assert service.verify(
        resign(aud="different-app"),
        app_id=settings.app_id,
        scope="face_swap",
        target_ref="opaque-face-ref",
    ) is ConsentState.WRONG_APP
    assert service.verify(
        resign(aud=[settings.app_id, "another-app"]),
        app_id=settings.app_id,
        scope="face_swap",
        target_ref="opaque-face-ref",
    ) is ConsentState.INVALID_TOKEN
    assert service.verify(
        resign(scope="body_edit"),
        app_id=settings.app_id,
        scope="face_swap",
        target_ref="opaque-face-ref",
    ) is ConsentState.WRONG_SCOPE
    assert service.verify(
        resign(sub="another-subject"),
        app_id=settings.app_id,
        scope="face_swap",
        target_ref="opaque-face-ref",
    ) is ConsentState.INVALID_TOKEN
    assert service.verify(
        resign(consent_request_id="another-request"),
        app_id=settings.app_id,
        scope="face_swap",
        target_ref="opaque-face-ref",
    ) is ConsentState.INVALID_TOKEN
    assert service.verify(
        resign(target_ref=target_reference_digest("other-target")),
        app_id=settings.app_id,
        scope="face_swap",
        target_ref="opaque-face-ref",
    ) is ConsentState.FACE_MISMATCH


def test_denial_and_approval_replay_are_rejected(settings: Settings) -> None:
    client = TestClient(create_app(settings))
    request = _new_consent(client, _needs_consent_check(client))
    action = {
        "request_id": request["request_id"],
        "demo_action_code": request["demo_action_code"],
    }
    denied = client.post("/v1/consent/deny", json=action)
    assert denied.status_code == 200
    assert denied.json()["status"] == "denied"
    assert client.post("/v1/consent/status", json=action).json()["status"] == "denied"
    assert (
        TestClient(create_app(settings))
        .post(
            "/v1/consent/status",
            json={
                "request_id": request["request_id"],
                "demo_action_code": request["demo_action_code"],
            },
        )
        .json()["status"]
        == "denied"
    )
    bad_status = client.post(
        "/v1/consent/status",
        json={
            "request_id": request["request_id"],
            "demo_action_code": "wrong-demo-action-code-" * 2,
        },
    )
    assert bad_status.status_code == 404
    assert client.post("/v1/consent/approve", json=action).status_code == 409

    replay_request = _new_consent(client, _needs_consent_check(client))
    replay_action = {
        "request_id": replay_request["request_id"],
        "demo_action_code": replay_request["demo_action_code"],
    }
    first = client.post("/v1/consent/approve", json=replay_action)
    second = client.post("/v1/consent/approve", json=replay_action)
    assert first.status_code == 200
    assert second.status_code == 409


def test_concurrent_approval_commits_only_one_token(settings: Settings) -> None:
    client = TestClient(create_app(settings))
    request = _new_consent(client, _needs_consent_check(client))
    store = SQLiteConsentStore(settings.consent_database_path)
    request_record = store.get_request(request["request_id"])
    assert request_record is not None
    service = ConsentTokenService(
        store=store,
        signing_key=load_signing_key(settings.consent_signing_key_path or ""),
        issuer=settings.consent_issuer,
        token_ttl_seconds=settings.consent_token_ttl_seconds,
    )

    def approve_once() -> str | None:
        try:
            token, _ = service.approve(
                request_record, action_secret=request["demo_action_code"]
            )
            return token
        except ConsentStoreError:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: approve_once(), range(2)))
    tokens = [token for token in results if token is not None]
    assert len(tokens) == 1
    assert service.verify(
        tokens[0],
        app_id=settings.app_id,
        scope="face_swap",
        target_ref="opaque-face-ref",
    ) is ConsentState.VALID


def test_revocation_is_checked_on_every_verification(settings: Settings) -> None:
    client = TestClient(create_app(settings))
    check_id, consent = _approved_consent(client)
    revoked = client.post(
        "/v1/consent/revoke",
        json={
            "jti": _jti(consent["consent_token"]),
            "demo_action_code": consent["demo_action_code"],
        },
    )
    assert revoked.status_code == 200
    assert revoked.json()["status"] == "revoked"

    verified = client.post(
        "/v1/generate/verify",
        headers=HEADERS,
        json={
            "check_id": check_id,
            "consent_token": consent["consent_token"],
            "target_ref": "opaque-face-ref",
        },
    )
    assert verified.json() == {"valid": False, "state": "revoked"}
    restarted_verified = TestClient(create_app(settings)).post(
        "/v1/generate/verify",
        headers=HEADERS,
        json={
            "check_id": check_id,
            "consent_token": consent["consent_token"],
            "target_ref": "opaque-face-ref",
        },
    )
    assert restarted_verified.json() == {"valid": False, "state": "revoked"}

    checked = client.post(
        "/v1/check",
        headers=HEADERS,
        json={
            "prompt": "Apply a harmless style",
            "scope": "face_swap",
            "user_ref": "demo-user",
            "target_ref": "opaque-face-ref",
            "consent_token": consent["consent_token"],
            "consent_check_id": check_id,
            "test_signals": {"real_face": True, "minor_risk": False},
        },
    )
    assert checked.json()["decision"] == "needs_consent"
    assert checked.json()["reasons"] == ["consent_revoked"]


def test_database_state_survives_app_recreation(settings: Settings) -> None:
    first_client = TestClient(create_app(settings))
    check_id, consent = _approved_consent(first_client)

    second_client = TestClient(create_app(settings))
    verified = second_client.post(
        "/v1/generate/verify",
        headers=HEADERS,
        json={
            "check_id": check_id,
            "consent_token": consent["consent_token"],
            "target_ref": "opaque-face-ref",
        },
    )
    assert verified.json() == {"valid": True, "state": "valid"}


def test_passport_page_is_served_by_gateway(settings: Settings) -> None:
    response = TestClient(create_app(settings)).get("/passport/")
    assert response.status_code == 200
    assert "Consent Passport" in response.text
    assert "/v1/consent/approve" in response.text
    assert "/v1/consent/revoke" in response.text


def test_demo_subject_actions_are_disabled_by_default(
    settings: Settings,
) -> None:
    values = {field.name: getattr(settings, field.name) for field in fields(Settings)}
    values["enable_demo_subject_actions"] = False
    client = TestClient(create_app(Settings(**values)))
    check_id = _needs_consent_check(client)
    request = client.post(
        "/v1/consent/requests",
        headers=HEADERS,
        json={"check_id": check_id},
    )
    assert request.status_code == 200
    assert request.json()["demo_action_code"] is None
    action = {
        "request_id": request.json()["request_id"],
        "demo_action_code": "x" * 43,
    }
    assert client.post("/v1/consent/approve", json=action).status_code == 403
    assert client.post("/v1/consent/deny", json=action).status_code == 403
    assert client.post("/v1/consent/status", json=action).status_code == 403
    assert client.post(
        "/v1/consent/revoke",
        json={
            "jti": str(uuid.uuid4()),
            "demo_action_code": action["demo_action_code"],
        },
    ).status_code == 403


def test_consent_request_rejects_unrecorded_and_wrong_app_check_ids(
    settings: Settings,
) -> None:
    client = TestClient(create_app(settings))
    missing = client.post(
        "/v1/consent/requests",
        headers=HEADERS,
        json={"check_id": "forged-check-id"},
    )
    assert missing.status_code == 400
    assert missing.json()["error"]["code"] == "check_not_eligible"

    check_id = _needs_consent_check(client)
    wrong_app_settings = Settings(
        **{
            **{field.name: getattr(settings, field.name) for field in fields(Settings)},
            "app_id": "different-app",
        }
    )
    wrong_app_client = TestClient(create_app(wrong_app_settings))
    response = wrong_app_client.post(
        "/v1/consent/requests",
        headers=HEADERS,
        json={"check_id": check_id},
    )
    assert response.status_code == 400


def test_targetless_check_cannot_create_consent_request(settings: Settings) -> None:
    client = TestClient(create_app(settings))
    response = client.post(
        "/v1/check",
        headers=HEADERS,
        json={
            "prompt": "Apply a harmless style",
            "scope": "face_swap",
            "user_ref": "demo-user",
            "test_signals": {"real_face": True, "minor_risk": False},
        },
    )
    assert response.json()["decision"] == "needs_consent"
    request = client.post(
        "/v1/consent/requests",
        headers=HEADERS,
        json={"check_id": response.json()["check_id"]},
    )
    assert request.status_code == 400
    assert request.json()["error"]["code"] == "target_required"
