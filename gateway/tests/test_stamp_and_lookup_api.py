from __future__ import annotations

import io
import sqlite3
from dataclasses import replace

import jwt
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from gateway.app.config import Settings
from gateway.app.main import create_app
from gateway.app.services.ledger import InMemoryLedgerRepository
from gateway.app.services.output_store import InMemoryOutputStore
from gateway.app.services.provenance import compute_sha256
from gateway.app.services.result_check import FLAGGED_FIXTURE_MARKER

API_KEY = "test-api-key"
HEADERS = {"X-API-Key": API_KEY}


def _generate_valid_image_bytes(width: int = 120, height: int = 120) -> bytes:
    img = Image.new("RGB", (width, height), color=(100, 150, 200))
    draw = ImageDraw.Draw(img)
    draw.rectangle([20, 20, 80, 80], fill=(200, 100, 50))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _check(
    client: TestClient,
    *,
    scope: str = "filter",
    target_ref: str | None = None,
    consent_token: str | None = None,
    consent_check_id: str | None = None,
    test_signals: bool = True,
) -> dict[str, object]:
    request: dict[str, object] = {
        "prompt": "Apply a harmless style",
        "scope": scope,
        "user_ref": "stamp-test-user",
    }
    if test_signals:
        request["test_signals"] = {"real_face": True, "minor_risk": False}
    if target_ref is not None:
        request["target_ref"] = target_ref
    if consent_token is not None:
        request["consent_token"] = consent_token
    if consent_check_id is not None:
        request["consent_check_id"] = consent_check_id
    response = client.post("/v1/check", headers=HEADERS, json=request)
    assert response.status_code == 200, response.text
    return response.json()


def _approved_identity_check(client: TestClient) -> tuple[str, str, str]:
    target_ref = "opaque-stamp-target"
    request_check = _check(
        client, scope="face_swap", target_ref=target_ref
    )
    assert request_check["decision"] == "needs_consent"
    consent_request = client.post(
        "/v1/consent/requests",
        headers=HEADERS,
        json={"check_id": request_check["check_id"]},
    )
    assert consent_request.status_code == 200, consent_request.text
    approval = client.post(
        "/v1/consent/approve",
        json={
            "request_id": consent_request.json()["request_id"],
            "demo_action_code": consent_request.json()["demo_action_code"],
        },
    )
    assert approval.status_code == 200, approval.text
    token = approval.json()["consent_token"]
    checked_again = _check(
        client,
        scope="face_swap",
        target_ref=target_ref,
        consent_token=token,
        consent_check_id=str(request_check["check_id"]),
    )
    assert checked_again["decision"] == "allow"
    return str(checked_again["check_id"]), token, target_ref


def _stamp(
    client: TestClient,
    check_id: str,
    image_bytes: bytes,
    *,
    filename: str = "test.png",
    data: dict[str, str] | None = None,
) -> object:
    return client.post(
        "/v1/output/stamp",
        data={"check_id": check_id, **(data or {})},
        files={"image": (filename, image_bytes, "image/png")},
        headers=HEADERS,
    )


def test_stamp_endpoint_requires_authentication(settings: Settings) -> None:
    client = TestClient(create_app(settings))
    image_bytes = _generate_valid_image_bytes()

    no_auth = client.post(
        "/v1/output/stamp",
        data={"check_id": "c_1234567890ab"},
        files={"image": ("test.png", image_bytes, "image/png")},
    )
    assert no_auth.status_code == 401
    assert no_auth.json()["error"]["code"] == "unauthorized"

    bad_auth = client.post(
        "/v1/output/stamp",
        data={"check_id": "c_1234567890ab"},
        files={"image": ("test.png", image_bytes, "image/png")},
        headers={"X-API-Key": "invalid-key"},
    )
    assert bad_auth.status_code == 401
    assert bad_auth.json()["error"]["code"] == "unauthorized"


def test_stamp_validates_check_id_format(settings: Settings) -> None:
    client = TestClient(create_app(settings))
    response = _stamp(client, "bad_id_12345", _generate_valid_image_bytes())
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_check_id"


def test_unknown_expired_cross_app_and_ineligible_checks_cannot_be_stamped(
    settings: Settings,
) -> None:
    client = TestClient(create_app(settings))
    image_bytes = _generate_valid_image_bytes()

    unknown = _stamp(client, "c_unknown_check", image_bytes)
    assert unknown.status_code == 404
    assert unknown.json()["error"]["code"] == "check_not_found"

    pending = _check(client, scope="face_swap", target_ref="pending-target")
    pending_stamp = _stamp(client, str(pending["check_id"]), image_bytes)
    assert pending_stamp.status_code == 409
    assert pending_stamp.json()["error"]["code"] == "check_not_eligible"

    blocked = _check(client, scope="sexual_transformation", target_ref="blocked")
    assert blocked["decision"] == "block"
    blocked_stamp = _stamp(client, str(blocked["check_id"]), image_bytes)
    assert blocked_stamp.status_code == 409
    assert blocked_stamp.json()["error"]["code"] == "check_not_eligible"

    allowed = _check(client)
    with sqlite3.connect(settings.consent_database_path) as connection:
        connection.execute(
            "UPDATE checks SET expires_at = 0 WHERE check_id = ?",
            (allowed["check_id"],),
        )
    expired = _stamp(client, str(allowed["check_id"]), image_bytes)
    assert expired.status_code == 404
    assert expired.json()["error"]["code"] == "check_not_found"

    other_allowed = _check(client)
    different_app = TestClient(
        create_app(replace(settings, app_id="another-app"))
    )
    cross_app = _stamp(
        different_app, str(other_allowed["check_id"]), image_bytes
    )
    assert cross_app.status_code == 404
    assert cross_app.json()["error"]["code"] == "check_not_found"


def test_stamp_requires_current_consent_for_identity_altering_check(
    settings: Settings,
) -> None:
    ledger = InMemoryLedgerRepository()
    store = InMemoryOutputStore()
    client = TestClient(
        create_app(settings, ledger_repository=ledger, output_store=store)
    )
    check_id, consent_token, target_ref = _approved_identity_check(client)

    missing_consent = _stamp(
        client, check_id, _generate_valid_image_bytes()
    )
    assert missing_consent.status_code == 409
    assert missing_consent.json()["error"]["code"] == "consent_required"

    stamp = _stamp(
        client,
        check_id,
        _generate_valid_image_bytes(),
        data={"consent_token": consent_token, "target_ref": "wrong-target"},
    )
    assert stamp.status_code == 409
    assert stamp.json()["error"]["code"] == "consent_required"
    assert ledger.snapshot() == ()

    valid = _stamp(
        client,
        check_id,
        _generate_valid_image_bytes(),
        data={"consent_token": consent_token, "target_ref": target_ref},
    )
    assert valid.status_code == 200, valid.text


def test_revocation_after_allow_check_prevents_stamping(settings: Settings) -> None:
    ledger = InMemoryLedgerRepository()
    client = TestClient(create_app(settings, ledger_repository=ledger))
    target_ref = "revocation-race-target"
    original_check = _check(client, scope="face_swap", target_ref=target_ref)
    request_response = client.post(
        "/v1/consent/requests",
        headers=HEADERS,
        json={"check_id": original_check["check_id"]},
    )
    assert request_response.status_code == 200
    action_code = request_response.json()["demo_action_code"]
    approval = client.post(
        "/v1/consent/approve",
        json={
            "request_id": request_response.json()["request_id"],
            "demo_action_code": action_code,
        },
    )
    assert approval.status_code == 200
    token = approval.json()["consent_token"]
    recheck = _check(
        client,
        scope="face_swap",
        target_ref=target_ref,
        consent_token=token,
        consent_check_id=str(original_check["check_id"]),
    )
    assert recheck["decision"] == "allow"
    claims = jwt.decode(
        token,
        options={"verify_signature": False, "verify_exp": False},
        algorithms=["EdDSA"],
    )

    revoked = client.post(
        "/v1/consent/revoke",
        json={"jti": claims["jti"], "demo_action_code": action_code},
    )
    assert revoked.status_code == 200
    stamp = _stamp(
        client,
        str(recheck["check_id"]),
        _generate_valid_image_bytes(),
        data={"consent_token": token, "target_ref": target_ref},
    )

    assert stamp.status_code == 409
    assert stamp.json()["error"]["code"] == "consent_required"
    assert ledger.snapshot() == ()


def test_corrupt_and_oversized_images_do_not_mutate_output_or_ledger(
    settings: Settings,
) -> None:
    small_settings = replace(settings, max_output_size_bytes=64)
    ledger = InMemoryLedgerRepository()
    store = InMemoryOutputStore()
    client = TestClient(
        create_app(
            small_settings, ledger_repository=ledger, output_store=store
        )
    )
    check = _check(client, test_signals=False)

    corrupt = _stamp(client, str(check["check_id"]), b"plain text is not an image")
    assert corrupt.status_code == 400
    assert corrupt.json()["error"]["code"] == "invalid_image_format"
    assert ledger.snapshot() == ()

    oversized = _stamp(client, str(check["check_id"]), b"x" * 65)
    assert oversized.status_code == 413
    assert oversized.json()["error"]["code"] == "payload_too_large"
    assert ledger.snapshot() == ()
    assert store._store == {}


def test_unsupported_and_animated_images_are_rejected(settings: Settings) -> None:
    client = TestClient(create_app(settings))
    check = _check(client)

    bmp_buffer = io.BytesIO()
    Image.new("RGB", (16, 16), color="red").save(bmp_buffer, format="BMP")
    bmp = _stamp(client, str(check["check_id"]), bmp_buffer.getvalue())
    assert bmp.status_code == 400
    assert bmp.json()["error"]["code"] == "invalid_image_format"

    frames = [
        Image.new("RGB", (16, 16), color=color)
        for color in ("red", "blue")
    ]
    animated_buffer = io.BytesIO()
    frames[0].save(
        animated_buffer,
        format="GIF",
        save_all=True,
        append_images=frames[1:],
        duration=100,
        loop=0,
    )
    animated = _stamp(
        client, str(check["check_id"]), animated_buffer.getvalue()
    )
    assert animated.status_code == 400
    assert animated.json()["error"]["code"] == "invalid_image_format"


def test_flagged_output_is_rejected_and_never_stamped(settings: Settings) -> None:
    ledger = InMemoryLedgerRepository()
    store = InMemoryOutputStore()
    client = TestClient(
        create_app(settings, ledger_repository=ledger, output_store=store)
    )
    image_bytes = _generate_valid_image_bytes()
    first_check = _check(client)
    flagged = _stamp(
        client,
        str(first_check["check_id"]),
        image_bytes,
        data={"mock_signal": "flagged"},
    )
    assert flagged.status_code == 422
    assert flagged.json()["error"]["code"] == "harmful_content_detected"

    second_check = _check(client)
    marker_image = image_bytes + FLAGGED_FIXTURE_MARKER
    marked = _stamp(client, str(second_check["check_id"]), marker_image)
    assert marked.status_code == 422
    assert marked.json()["error"]["code"] == "harmful_content_detected"
    assert ledger.snapshot() == ()
    assert store._store == {}


def test_high_risk_indeterminate_and_checker_errors_fail_closed(
    settings: Settings,
) -> None:
    ledger = InMemoryLedgerRepository()
    client = TestClient(create_app(settings, ledger_repository=ledger))
    check_id, consent_token, target_ref = _approved_identity_check(client)
    image_bytes = _generate_valid_image_bytes()

    indeterminate = _stamp(
        client,
        check_id,
        image_bytes,
        data={
            "mock_signal": "indeterminate",
            "consent_token": consent_token,
            "target_ref": target_ref,
        },
    )
    assert indeterminate.status_code == 422
    assert indeterminate.json()["error"]["code"] == (
        "safety_check_indeterminate_high_risk"
    )

    checker_error = _stamp(
        client,
        check_id,
        image_bytes,
        data={
            "mock_signal": "error",
            "consent_token": consent_token,
            "target_ref": target_ref,
        },
    )
    assert checker_error.status_code == 422
    assert checker_error.json()["error"]["code"] == "result_check_failed"
    assert ledger.snapshot() == ()


def test_mock_result_signals_are_disabled_by_default(settings: Settings) -> None:
    client = TestClient(
        create_app(replace(settings, enable_test_signals=False))
    )
    check = _check(client, test_signals=False)
    response = _stamp(
        client,
        str(check["check_id"]),
        _generate_valid_image_bytes(),
        data={"mock_signal": "flagged"},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "test_signals_disabled"


def test_duplicate_stamp_is_rejected_without_appending_another_entry(
    settings: Settings,
) -> None:
    ledger = InMemoryLedgerRepository()
    client = TestClient(create_app(settings, ledger_repository=ledger))
    check = _check(client)
    check_id = str(check["check_id"])
    image_bytes = _generate_valid_image_bytes()

    first = _stamp(client, check_id, image_bytes)
    second = _stamp(client, check_id, image_bytes)
    assert first.status_code == 200
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "output_already_stamped"
    assert len(ledger.snapshot()) == 1


def test_ledger_failure_does_not_leave_output_or_accepted_entry(
    settings: Settings,
) -> None:
    class FailingLedger(InMemoryLedgerRepository):
        def append(self, **kwargs: object):
            raise OSError("persistence failure")

    class TrackingStore(InMemoryOutputStore):
        last_ref: str | None = None

        def store(
            self,
            output_ref: str,
            image_bytes: bytes,
            app_id: str,
            mime_type: str = "image/png",
        ) -> None:
            self.last_ref = output_ref
            super().store(output_ref, image_bytes, app_id, mime_type)

    ledger = FailingLedger()
    store = TrackingStore()
    client = TestClient(
        create_app(settings, ledger_repository=ledger, output_store=store)
    )
    check = _check(client)
    failed = _stamp(
        client, str(check["check_id"]), _generate_valid_image_bytes()
    )

    assert failed.status_code == 500
    assert failed.json()["error"]["code"] == "output_persistence_failed"
    assert ledger.snapshot() == ()
    assert store.last_ref is not None
    assert store.get(store.last_ref, settings.app_id) is None


def test_partial_output_store_failure_is_cleaned_up(settings: Settings) -> None:
    class PartiallyFailingStore(InMemoryOutputStore):
        last_ref: str | None = None

        def store(
            self,
            output_ref: str,
            image_bytes: bytes,
            app_id: str,
            mime_type: str = "image/png",
        ) -> None:
            self.last_ref = output_ref
            super().store(output_ref, image_bytes, app_id, mime_type)
            raise OSError("simulated partial write failure")

    ledger = InMemoryLedgerRepository()
    store = PartiallyFailingStore()
    client = TestClient(
        create_app(settings, ledger_repository=ledger, output_store=store)
    )
    check = _check(client)

    failed = _stamp(
        client, str(check["check_id"]), _generate_valid_image_bytes()
    )

    assert failed.status_code == 500
    assert failed.json()["error"]["code"] == "output_persistence_failed"
    assert store.last_ref is not None
    assert store.get(store.last_ref, settings.app_id) is None
    assert ledger.snapshot() == ()


def test_successful_stamp_download_lookup_and_ledger_verification(
    settings: Settings, caplog
) -> None:
    ledger = InMemoryLedgerRepository()
    store = InMemoryOutputStore()
    client = TestClient(
        create_app(settings, ledger_repository=ledger, output_store=store)
    )
    image_bytes = _generate_valid_image_bytes()
    check = _check(client)
    check_id = str(check["check_id"])

    stamp = _stamp(client, check_id, image_bytes)
    assert stamp.status_code == 200, stamp.text
    receipt = stamp.json()
    assert receipt["check_id"] == check_id
    assert receipt["entry_id"].startswith("entry_")
    assert receipt["label"] == "AI-generated"
    assert len(receipt["output_sha256"]) == 64
    assert len(receipt["pre_stamp_sha256"]) == 64
    assert receipt["output_sha256"] != receipt["pre_stamp_sha256"]
    assert len(receipt["phash"]) == 16
    assert len(receipt["ledger_entry_hash"]) == 64
    assert receipt["output_ref"].startswith("out_")

    unauthenticated_download = client.get(
        f"/v1/output/download/{receipt['output_ref']}"
    )
    assert unauthenticated_download.status_code == 401

    cross_app = TestClient(
        create_app(
            replace(settings, app_id="other-app"),
            output_store=store,
        )
    )
    cross_app_download = cross_app.get(
        f"/v1/output/download/{receipt['output_ref']}", headers=HEADERS
    )
    assert cross_app_download.status_code == 404

    download = client.get(
        f"/v1/output/download/{receipt['output_ref']}", headers=HEADERS
    )
    assert download.status_code == 200
    assert download.headers["content-type"] == "image/png"
    assert compute_sha256(download.content) == receipt["output_sha256"]

    lookup = client.get(f"/v1/ledger/lookup?phash={receipt['phash']}")
    assert lookup.status_code == 200
    body = lookup.json()
    assert body["match"] is True
    assert body["method"] == "exact_phash"
    assert body["provenance"]["check_id"] == check_id
    assert body["provenance"]["label"] == "AI-generated"
    assert body["provenance"]["output_sha256"] == receipt["output_sha256"]

    no_match = client.get("/v1/ledger/lookup?phash=1111222233334444")
    assert no_match.status_code == 200
    assert no_match.json()["match"] is False
    assert no_match.json()["provenance"] is None
    assert "No matching ledger entry found" in no_match.json()["message"]

    invalid_hash = client.get("/v1/ledger/lookup?phash=too-short")
    assert invalid_hash.status_code == 400
    assert invalid_hash.json()["error"]["code"] == "invalid_phash"

    verified = client.get("/v1/ledger/verify")
    assert verified.status_code == 200
    assert verified.json()["valid"] is True
    assert verified.json()["entries_count"] == 1
    assert API_KEY not in caplog.text
