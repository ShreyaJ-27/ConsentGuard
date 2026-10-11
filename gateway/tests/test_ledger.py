from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from gateway.app.services.ledger import InMemoryLedgerRepository
from gateway.app.services.provenance import GENESIS_PREVIOUS_HASH


def test_ledger_append_and_chaining() -> None:
    ledger = InMemoryLedgerRepository()
    assert ledger.head_hash() == GENESIS_PREVIOUS_HASH

    r1 = ledger.append(
        check_id="c_001",
        app_id="app-a",
        output_sha256="out_sha_1",
        pre_stamp_sha256="pre_sha_1",
        phash="0000000000000000",
        label="AI-generated",
    )
    assert r1.previous_hash == GENESIS_PREVIOUS_HASH
    assert ledger.head_hash() == r1.entry_hash

    r2 = ledger.append(
        check_id="c_002",
        app_id="app-a",
        output_sha256="out_sha_2",
        pre_stamp_sha256="pre_sha_2",
        phash="ffffffffffffffff",
        label="AI-generated",
    )
    assert r2.previous_hash == r1.entry_hash
    assert ledger.head_hash() == r2.entry_hash

    valid, err = ledger.verify_integrity()
    assert valid is True
    assert err is None


def test_ledger_lookup_exact_and_hamming() -> None:
    ledger = InMemoryLedgerRepository()
    ledger.append(
        check_id="c_alpha",
        app_id="app-a",
        output_sha256="out_sha_a",
        pre_stamp_sha256="pre_sha_a",
        phash="0000000000000001",
    )
    ledger.append(
        check_id="c_beta",
        app_id="app-b",
        output_sha256="out_sha_b",
        pre_stamp_sha256="pre_sha_b",
        phash="ffffffffffffffff",
    )

    # 1. Exact match
    match_exact = ledger.lookup_phash("0000000000000001", max_distance=0)
    assert match_exact is not None
    assert match_exact.record.check_id == "c_alpha"
    assert match_exact.distance == 0
    assert match_exact.method == "exact_phash"

    # 2. No match with max_distance=0
    no_match = ledger.lookup_phash("0000000000000003", max_distance=0)
    assert no_match is None

    # 3. Near match with max_distance=2 (0000000000000003 has Hamming distance 1 from 0000000000000001)
    match_near = ledger.lookup_phash("0000000000000003", max_distance=2)
    assert match_near is not None
    assert match_near.record.check_id == "c_alpha"
    assert match_near.distance == 1
    assert match_near.method == "hamming_phash"


def test_ledger_records_do_not_store_sensitive_data() -> None:
    ledger = InMemoryLedgerRepository()
    record = ledger.append(
        check_id="c_privacy_test",
        app_id="app-test",
        output_sha256="hash123",
        pre_stamp_sha256="hash000",
        phash="1234567890abcdef",
    )

    # Verify no raw bytes or sensitive fields exist in record attributes
    record_fields = set(record.__dict__.keys())
    assert "image_bytes" not in record_fields
    assert "prompt" not in record_fields
    assert "api_key" not in record_fields
    assert "face_embedding" not in record_fields
    assert "user_ref" not in record_fields


def test_ledger_thread_safety_under_concurrent_writes() -> None:
    ledger = InMemoryLedgerRepository()
    count = 20

    def append_item(i: int) -> None:
        ledger.append(
            check_id=f"c_conc_{i}",
            app_id="app-worker",
            output_sha256=f"sha_{i}",
            pre_stamp_sha256=f"pre_{i}",
            phash=f"{i:016x}",
        )

    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(append_item, range(count)))

    assert len(ledger.snapshot()) == count
    valid, err = ledger.verify_integrity()
    assert valid is True, f"Integrity failed after concurrent writes: {err}"
