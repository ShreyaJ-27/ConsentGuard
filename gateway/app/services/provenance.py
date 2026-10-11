from __future__ import annotations

import hashlib
import io
import json
from datetime import datetime, timezone
from typing import Sequence
from PIL import Image, ImageDraw, ImageFont

GENESIS_PREVIOUS_HASH = "0" * 64


def compute_sha256(data: bytes) -> str:
    """Compute the SHA-256 hexadecimal digest for the given bytes."""
    return hashlib.sha256(data).hexdigest()


def compute_dhash(image_bytes: bytes) -> str:
    """Compute a 64-bit difference hash (dHash) formatted as a 16-character hex string.

    Algorithm:
    1. Decode image into memory and convert to 8-bit grayscale.
    2. Resize to 9 columns by 8 rows using high-quality Lanczos resampling.
    3. Compare adjacent horizontal pixels (pixel[x] > pixel[x + 1]) yielding 64 bits.
    4. Format the 64 bits as a 16-character lowercase hexadecimal string.
    """
    try:
        with Image.open(io.BytesIO(image_bytes)) as img:
            gray = img.convert("L").resize((9, 8), Image.Resampling.LANCZOS)
            pixels = list(gray.getdata())
    except Exception as exc:
        raise ValueError("Invalid image bytes for perceptual hashing") from exc

    diff: list[bool] = []
    for row in range(8):
        row_offset = row * 9
        for col in range(8):
            diff.append(pixels[row_offset + col] > pixels[row_offset + col + 1])

    val = 0
    for bit in diff:
        val = (val << 1) | int(bit)
    return f"{val:016x}"


def hamming_distance(hash1: str, hash2: str) -> int:
    """Compute the bitwise Hamming distance between two 16-character hex hashes."""
    if len(hash1) != 16 or len(hash2) != 16:
        raise ValueError("Hashes must be 16-character hexadecimal strings.")
    val1 = int(hash1, 16)
    val2 = int(hash2, 16)
    return bin(val1 ^ val2).count("1")


def add_ai_generated_label(image_bytes: bytes) -> bytes:
    """Add a visible, semi-transparent 'AI-generated' label badge to an image.

    Renders a discrete label badge in the lower-right corner of the image
    to ensure compliance with AI transparency requirements without corrupting
    image integrity.
    """
    try:
        with Image.open(io.BytesIO(image_bytes)) as img:
            working_image = img.convert("RGBA")
            width, height = working_image.size

            overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
            draw = ImageDraw.Draw(overlay)

            text = "AI-generated"
            font = ImageFont.load_default()
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]

            pad_x = 6
            pad_y = 4
            margin = 10

            box_width = text_width + pad_x * 2
            box_height = text_height + pad_y * 2

            left = max(0, width - box_width - margin)
            top = max(0, height - box_height - margin)
            right = left + box_width
            bottom = top + box_height

            draw.rectangle(
                [left, top, right, bottom],
                fill=(20, 20, 20, 190),
                outline=(255, 255, 255, 120),
                width=1,
            )
            draw.text(
                (left + pad_x, top + pad_y),
                text,
                fill=(255, 255, 255, 240),
                font=font,
            )

            stamped = Image.alpha_composite(working_image, overlay)
            out_buf = io.BytesIO()
            stamped.convert("RGB").save(out_buf, format="PNG")
            return out_buf.getvalue()
    except Exception as exc:
        raise ValueError("Failed to apply AI label to image bytes") from exc


def canonical_json(payload: dict) -> bytes:
    """Serialize a dictionary to canonical JSON bytes with deterministic key order."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def compute_entry_hash(previous_hash: str, payload: dict) -> str:
    """Compute the SHA-256 hash of previous_hash concatenated with canonical payload."""
    canonical_bytes = canonical_json(payload)
    return hashlib.sha256(previous_hash.encode("utf-8") + canonical_bytes).hexdigest()


def verify_ledger_chain(records: Sequence) -> tuple[bool, str | None]:
    """Verify cryptographic integrity of a hash-chained ledger sequence.

    Checks:
    1. The genesis record links to GENESIS_PREVIOUS_HASH.
    2. Each subsequent record links to the exact entry_hash of its predecessor.
    3. Each record's entry_hash matches the hash of its previous_hash and canonical payload.
    """
    if not records:
        return True, None

    expected_prev = GENESIS_PREVIOUS_HASH
    for idx, record in enumerate(records):
        if record.previous_hash != expected_prev:
            return (
                False,
                f"Broken hash chain at index {idx} ({record.entry_id}): "
                f"expected previous {expected_prev}, found {record.previous_hash}",
            )

        computed = compute_entry_hash(
            record.previous_hash, record.canonical_payload_dict()
        )
        if computed != record.entry_hash:
            return (
                False,
                f"Tampered payload at index {idx} ({record.entry_id}): "
                f"recomputed hash {computed} does not match {record.entry_hash}",
            )

        expected_prev = record.entry_hash

    return True, None
