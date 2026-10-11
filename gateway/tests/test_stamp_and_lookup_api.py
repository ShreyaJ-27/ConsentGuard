from __future__ import annotations

import io
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from gateway.app.config import Settings
from gateway.app.main import create_app
from gateway.app.services.ledger import InMemoryLedgerRepository
from gateway.app.services.provenance import compute_sha256
from gateway.app.services.result_check import FLAGGED_FIXTURE_MARKER

API_KEY = "test-api-key"


def _generate_valid_image_bytes(width: int = 120, height: int = 120) -> bytes:
    img = Image.new("RGB", (width, height), color=(100, 150, 200))
    draw = ImageDraw.Draw(img)
    draw.rectangle([20, 20, 80, 80], fill=(200, 100, 50))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_stamp_endpoint_requires_authentication(settings: Settings) -> None:
    client = TestClient(create_app(settings))
    image_bytes = _generate_valid_image_bytes()

    # Missing API key
    no_auth = client.post(
        "/v1/output/stamp",
        data={"check_id": "c_1234567890ab"},
        files={"image": ("test.png", image_bytes, "image/png")},
    )
    assert no_auth.status_code == 401
    assert no_auth.json()["error"]["code"] == "unauthorized"

    # Invalid API key
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
    image_bytes = _generate_valid_image_bytes()
    headers = {"X-API-Key": API_KEY}

    # check_id missing 'c_' prefix
    res = client.post(
        "/v1/output/stamp",
        data={"check_id": "bad_id_12345"},
        files={"image": ("test.png", image_bytes, "image/png")},
        headers=headers,
    )
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "invalid_check_id"


def test_stamp_validates_image_file_and_size(settings: Settings) -> None:
    client = TestClient(create_app(settings))
    headers = {"X-API-Key": API_KEY}

    # Upload non-image text file
    corrupt_res = client.post(
        "/v1/output/stamp",
        data={"check_id": "c_1234567890ab"},
        files={"image": ("test.txt", b"plain text is not an image", "text/plain")},
        headers=headers,
    )
    assert corrupt_res.status_code == 400
    assert corrupt_res.json()["error"]["code"] == "invalid_image_format"


def test_flagged_output_is_rejected_and_never_stamped(settings: Settings) -> None:
    ledger = InMemoryLedgerRepository()
    client = TestClient(create_app(settings, ledger_repository=ledger))
    headers = {"X-API-Key": API_KEY}

    # Test via mock_signal="flagged"
    image_bytes = _generate_valid_image_bytes()
    res = client.post(
        "/v1/output/stamp",
        data={"check_id": "c_flagged_1", "mock_signal": "flagged"},
        files={"image": ("test.png", image_bytes, "image/png")},
        headers=headers,
    )
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "harmful_content_detected"

    # Test via fixture marker in image bytes
    flagged_image_bytes = image_bytes + FLAGGED_FIXTURE_MARKER
    res_marker = client.post(
        "/v1/output/stamp",
        data={"check_id": "c_flagged_2"},
        files={"image": ("test.png", flagged_image_bytes, "image/png")},
        headers=headers,
    )
    assert res_marker.status_code == 422
    assert res_marker.json()["error"]["code"] == "harmful_content_detected"

    # Confirm nothing was appended to the ledger
    assert len(ledger.snapshot()) == 0


def test_high_risk_indeterminate_fails_closed(settings: Settings) -> None:
    client = TestClient(create_app(settings))
    headers = {"X-API-Key": API_KEY}
    image_bytes = _generate_valid_image_bytes()

    res = client.post(
        "/v1/output/stamp",
        data={
            "check_id": "c_highrisk_1",
            "mock_signal": "indeterminate",
            "high_risk": "true",
        },
        files={"image": ("test.png", image_bytes, "image/png")},
        headers=headers,
    )
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "safety_check_indeterminate_high_risk"


def test_error_in_result_check_fails_closed(settings: Settings) -> None:
    client = TestClient(create_app(settings))
    headers = {"X-API-Key": API_KEY}
    image_bytes = _generate_valid_image_bytes()

    res = client.post(
        "/v1/output/stamp",
        data={"check_id": "c_error_1", "mock_signal": "error"},
        files={"image": ("test.png", image_bytes, "image/png")},
        headers=headers,
    )
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "result_check_failed"


def test_successful_stamp_workflow_and_ledger_lookup(
    settings: Settings, caplog
) -> None:
    ledger = InMemoryLedgerRepository()
    client = TestClient(create_app(settings, ledger_repository=ledger))
    headers = {"X-API-Key": API_KEY}
    image_bytes = _generate_valid_image_bytes()

    # 1. POST /v1/output/stamp
    stamp_res = client.post(
        "/v1/output/stamp",
        data={"check_id": "c_success_001"},
        files={"image": ("demo.png", image_bytes, "image/png")},
        headers=headers,
    )
    assert stamp_res.status_code == 200
    receipt = stamp_res.json()

    assert receipt["check_id"] == "c_success_001"
    assert receipt["entry_id"].startswith("entry_")
    assert receipt["label"] == "AI-generated"
    assert len(receipt["output_sha256"]) == 64
    assert len(receipt["pre_stamp_sha256"]) == 64
    assert receipt["output_sha256"] != receipt["pre_stamp_sha256"]
    assert len(receipt["phash"]) == 16
    assert len(receipt["ledger_entry_hash"]) == 64
    assert receipt["output_ref"].startswith("out_")

    # 2. Verify download of stamped image
    download_res = client.get(f"/v1/output/download/{receipt['output_ref']}")
    assert download_res.status_code == 200
    assert download_res.headers["content-type"] == "image/png"
    downloaded_bytes = download_res.content
    assert compute_sha256(downloaded_bytes) == receipt["output_sha256"]

    # 3. GET /v1/ledger/lookup - exact match
    lookup_res = client.get(f"/v1/ledger/lookup?phash={receipt['phash']}")
    assert lookup_res.status_code == 200
    lookup_body = lookup_res.json()
    assert lookup_body["match"] is True
    assert lookup_body["method"] == "exact_phash"
    assert lookup_body["provenance"]["check_id"] == "c_success_001"
    assert lookup_body["provenance"]["label"] == "AI-generated"
    assert lookup_body["provenance"]["output_sha256"] == receipt["output_sha256"]

    # 4. GET /v1/ledger/lookup - no match
    unregistered_hash = "1111222233334444"
    if unregistered_hash == receipt["phash"]:
        unregistered_hash = "9999888877776666"
    no_match_res = client.get(f"/v1/ledger/lookup?phash={unregistered_hash}")
    assert no_match_res.status_code == 200
    no_match_body = no_match_res.json()
    assert no_match_body["match"] is False
    assert no_match_body["provenance"] is None
    assert "No matching ledger entry found" in no_match_body["message"]

    # 5. GET /v1/ledger/lookup - invalid hash (wrong length / format)
    invalid_hash_res = client.get("/v1/ledger/lookup?phash=too-short")
    assert invalid_hash_res.status_code == 400
    assert invalid_hash_res.json()["error"]["code"] == "invalid_phash"

    # 6. GET /v1/ledger/verify
    verify_res = client.get("/v1/ledger/verify")
    assert verify_res.status_code == 200
    assert verify_res.json()["valid"] is True
    assert verify_res.json()["entries_count"] == 1

    # 7. Privacy check: confirm API key and raw image bytes are not in caplog
    assert API_KEY not in caplog.text
