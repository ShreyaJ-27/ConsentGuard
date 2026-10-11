from __future__ import annotations

import io
from dataclasses import dataclass
from PIL import Image, ImageDraw

from gateway.app.services.provenance import (
    GENESIS_PREVIOUS_HASH,
    add_ai_generated_label,
    canonical_json,
    compute_dhash,
    compute_entry_hash,
    compute_sha256,
    hamming_distance,
    verify_ledger_chain,
)


@dataclass(frozen=True)
class DummyRecord:
    entry_id: str
    check_id: str
    app_id: str
    timestamp: str
    decision: str
    output_sha256: str
    pre_stamp_sha256: str
    phash: str
    label: str
    previous_hash: str
    entry_hash: str

    def canonical_payload_dict(self) -> dict[str, str]:
        return {
            "app_id": self.app_id,
            "check_id": self.check_id,
            "decision": self.decision,
            "entry_id": self.entry_id,
            "label": self.label,
            "output_sha256": self.output_sha256,
            "phash": self.phash,
            "pre_stamp_sha256": self.pre_stamp_sha256,
            "timestamp": self.timestamp,
        }


def _create_test_image(width: int = 256, height: int = 256) -> bytes:
    img = Image.new("RGB", (width, height), color=(240, 240, 240))
    draw = ImageDraw.Draw(img)
    for i in range(0, width, 16):
        draw.line([(i, 0), (width - i, height)], fill=(i, 100, 255 - i), width=2)
    draw.rectangle([40, 40, 120, 120], fill=(220, 40, 40))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_sha256_stability_and_determinism() -> None:
    data1 = b"consistent byte payload for sha256 testing"
    data2 = b"consistent byte payload for sha256 testing"
    data3 = b"different payload"

    hash1 = compute_sha256(data1)
    hash2 = compute_sha256(data2)
    hash3 = compute_sha256(data3)

    assert len(hash1) == 64
    assert hash1 == hash2
    assert hash1 != hash3


def test_visible_ai_label_adds_watermark_and_preserves_validity() -> None:
    raw_bytes = _create_test_image(200, 200)
    stamped_bytes = add_ai_generated_label(raw_bytes)

    assert stamped_bytes != raw_bytes

    # Stamped bytes should be a valid, loadable image
    with Image.open(io.BytesIO(stamped_bytes)) as img:
        assert img.size == (200, 200)
        assert img.format == "PNG"


def test_perceptual_hash_format() -> None:
    raw_bytes = _create_test_image()
    phash = compute_dhash(raw_bytes)

    assert len(phash) == 16
    assert isinstance(phash, str)
    # Must be valid hex
    int(phash, 16)
    assert phash == phash.lower()


def test_perceptual_hash_resize_and_recompression_experiment() -> None:
    """Empirical robustness experiment for dHash (64-bit difference hash).

    Measures Hamming distance under:
    1. Scaling / resize (256x256 -> 128x128 and 256x256 -> 512x512)
    2. JPEG recompression at quality 85 and quality 60
    """
    raw_bytes = _create_test_image(256, 256)
    orig_hash = compute_dhash(raw_bytes)

    with Image.open(io.BytesIO(raw_bytes)) as orig_img:
        # 1. Resize down to 128x128
        img_down = orig_img.resize((128, 128), Image.Resampling.LANCZOS)
        buf_down = io.BytesIO()
        img_down.save(buf_down, format="PNG")
        hash_down = compute_dhash(buf_down.getvalue())
        dist_down = hamming_distance(orig_hash, hash_down)

        # 2. Resize up to 512x512
        img_up = orig_img.resize((512, 512), Image.Resampling.LANCZOS)
        buf_up = io.BytesIO()
        img_up.save(buf_up, format="PNG")
        hash_up = compute_dhash(buf_up.getvalue())
        dist_up = hamming_distance(orig_hash, hash_up)

        # 3. JPEG recompression at quality 85
        buf_jpeg85 = io.BytesIO()
        orig_img.convert("RGB").save(buf_jpeg85, format="JPEG", quality=85)
        hash_jpeg85 = compute_dhash(buf_jpeg85.getvalue())
        dist_jpeg85 = hamming_distance(orig_hash, hash_jpeg85)

        # 4. JPEG recompression at quality 60
        buf_jpeg60 = io.BytesIO()
        orig_img.convert("RGB").save(buf_jpeg60, format="JPEG", quality=60)
        hash_jpeg60 = compute_dhash(buf_jpeg60.getvalue())
        dist_jpeg60 = hamming_distance(orig_hash, hash_jpeg60)

    # Measured empirical limits:
    # JPEG recompression preserves the gradients closely (distance <= 4 bits out of 64)
    assert dist_jpeg85 <= 4, f"JPEG 85 distance {dist_jpeg85} exceeded threshold"
    assert dist_jpeg60 <= 6, f"JPEG 60 distance {dist_jpeg60} exceeded threshold"

    # Resizing preserves gradients within distance <= 6 bits out of 64 (>90% bit similarity)
    assert dist_down <= 6, f"Downscale distance {dist_down} exceeded threshold"
    assert dist_up <= 6, f"Upscale distance {dist_up} exceeded threshold"


def test_canonical_json_ordering_and_separators() -> None:
    dict_a = {"b": 2, "a": 1, "nested": {"z": 10, "m": 5}}
    dict_b = {"nested": {"m": 5, "z": 10}, "a": 1, "b": 2}

    json_a = canonical_json(dict_a)
    json_b = canonical_json(dict_b)

    assert json_a == json_b
    assert b" " not in json_a
    assert json_a.startswith(b'{"a":1,"b":2,"nested":')


def test_hash_chain_verification_and_tamper_detection() -> None:
    # 1. Empty chain is valid
    valid_empty, err_empty = verify_ledger_chain([])
    assert valid_empty is True
    assert err_empty is None

    # 2. Build 3 chained records
    records: list[DummyRecord] = []
    prev_hash = GENESIS_PREVIOUS_HASH
    for i in range(3):
        entry_id = f"entry_00{i}"
        payload = {
            "app_id": "test-app",
            "check_id": f"c_{i}",
            "decision": "stamped",
            "entry_id": entry_id,
            "label": "AI-generated",
            "output_sha256": f"out_hash_{i}",
            "phash": "0123456789abcdef",
            "pre_stamp_sha256": f"pre_hash_{i}",
            "timestamp": "2026-10-11T12:00:00Z",
        }
        entry_hash = compute_entry_hash(prev_hash, payload)
        record = DummyRecord(
            entry_id=entry_id,
            check_id=f"c_{i}",
            app_id="test-app",
            timestamp="2026-10-11T12:00:00Z",
            decision="stamped",
            output_sha256=f"out_hash_{i}",
            pre_stamp_sha256=f"pre_hash_{i}",
            phash="0123456789abcdef",
            label="AI-generated",
            previous_hash=prev_hash,
            entry_hash=entry_hash,
        )
        records.append(record)
        prev_hash = entry_hash

    # Chain should verify
    valid, err = verify_ledger_chain(records)
    assert valid is True
    assert err is None

    # Tamper with payload in record 1
    tampered_records = list(records)
    tampered_records[1] = DummyRecord(
        entry_id=records[1].entry_id,
        check_id=records[1].check_id,
        app_id="altered-app-id",  # TAMPERED
        timestamp=records[1].timestamp,
        decision=records[1].decision,
        output_sha256=records[1].output_sha256,
        pre_stamp_sha256=records[1].pre_stamp_sha256,
        phash=records[1].phash,
        label=records[1].label,
        previous_hash=records[1].previous_hash,
        entry_hash=records[1].entry_hash,
    )
    tampered_valid, tampered_err = verify_ledger_chain(tampered_records)
    assert tampered_valid is False
    assert "Tampered payload at index 1" in tampered_err

    # Tamper with chain link (broken previous_hash in record 2)
    broken_link_records = list(records)
    broken_link_records[2] = DummyRecord(
        entry_id=records[2].entry_id,
        check_id=records[2].check_id,
        app_id=records[2].app_id,
        timestamp=records[2].timestamp,
        decision=records[2].decision,
        output_sha256=records[2].output_sha256,
        pre_stamp_sha256=records[2].pre_stamp_sha256,
        phash=records[2].phash,
        label=records[2].label,
        previous_hash="wrong_previous_hash_value",  # BROKEN LINK
        entry_hash=records[2].entry_hash,
    )
    broken_valid, broken_err = verify_ledger_chain(broken_link_records)
    assert broken_valid is False
    assert "Broken hash chain at index 2" in broken_err
