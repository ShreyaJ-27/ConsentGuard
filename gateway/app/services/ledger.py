from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Lock
from typing import Protocol
from uuid import uuid4

from gateway.app.services.provenance import (
    GENESIS_PREVIOUS_HASH,
    compute_entry_hash,
    hamming_distance,
    verify_ledger_chain,
)


@dataclass(frozen=True)
class LedgerRecord:
    """Tamper-evident record of an allowed output and its provenance metadata.

    CRITICAL PRIVACY GUARANTEE:
    Ledger records NEVER store raw image bytes, user prompts, user identities,
    passkeys, API keys, bearer tokens, phone numbers, or face embeddings.
    """

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
        """Dictionary representation used for canonical JSON serialization and hashing."""
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


@dataclass(frozen=True)
class LedgerMatch:
    """Result of looking up an image hash in the provenance ledger."""

    record: LedgerRecord
    distance: int
    method: str


class LedgerRepository(Protocol):
    """Abstract interface for hash-chained provenance ledger persistence."""

    def append(
        self,
        *,
        check_id: str,
        app_id: str,
        output_sha256: str,
        pre_stamp_sha256: str,
        phash: str,
        label: str = "AI-generated",
        decision: str = "stamped",
        timestamp: str | None = None,
    ) -> LedgerRecord: ...

    def get_by_entry_id(self, entry_id: str) -> LedgerRecord | None: ...

    def get_by_check_id(self, check_id: str) -> LedgerRecord | None: ...

    def lookup_phash(
        self, phash: str, max_distance: int = 0
    ) -> LedgerMatch | None: ...

    def verify_integrity(self) -> tuple[bool, str | None]: ...

    def snapshot(self) -> tuple[LedgerRecord, ...]: ...

    def head_hash(self) -> str: ...


class InMemoryLedgerRepository:
    """Process-local, non-durable in-memory hash-chained ledger.

    Provides a thread-safe, locally verifiable prototype implementation
    adhering to the hash-chain specification. Replaceable boundary for
    durable SQL/PostgreSQL persistence in production deployments.
    """

    def __init__(self) -> None:
        self._entries: list[LedgerRecord] = []
        self._by_entry_id: dict[str, LedgerRecord] = {}
        self._by_check_id: dict[str, LedgerRecord] = {}
        self._lock = Lock()

    def append(
        self,
        *,
        check_id: str,
        app_id: str,
        output_sha256: str,
        pre_stamp_sha256: str,
        phash: str,
        label: str = "AI-generated",
        decision: str = "stamped",
        timestamp: str | None = None,
    ) -> LedgerRecord:
        with self._lock:
            prev_hash = (
                self._entries[-1].entry_hash
                if self._entries
                else GENESIS_PREVIOUS_HASH
            )
            entry_id = f"entry_{uuid4().hex[:12]}"
            ts_str = (
                timestamp
                if timestamp is not None
                else datetime.now(timezone.utc).isoformat()
            )

            payload = {
                "app_id": app_id,
                "check_id": check_id,
                "decision": decision,
                "entry_id": entry_id,
                "label": label,
                "output_sha256": output_sha256,
                "phash": phash,
                "pre_stamp_sha256": pre_stamp_sha256,
                "timestamp": ts_str,
            }

            entry_hash = compute_entry_hash(prev_hash, payload)

            record = LedgerRecord(
                entry_id=entry_id,
                check_id=check_id,
                app_id=app_id,
                timestamp=ts_str,
                decision=decision,
                output_sha256=output_sha256,
                pre_stamp_sha256=pre_stamp_sha256,
                phash=phash,
                label=label,
                previous_hash=prev_hash,
                entry_hash=entry_hash,
            )

            self._entries.append(record)
            self._by_entry_id[entry_id] = record
            self._by_check_id[check_id] = record
            return record

    def get_by_entry_id(self, entry_id: str) -> LedgerRecord | None:
        with self._lock:
            return self._by_entry_id.get(entry_id)

    def get_by_check_id(self, check_id: str) -> LedgerRecord | None:
        with self._lock:
            return self._by_check_id.get(check_id)

    def lookup_phash(
        self, phash: str, max_distance: int = 0
    ) -> LedgerMatch | None:
        with self._lock:
            # 1. Exact match pass
            for entry in self._entries:
                if entry.phash == phash:
                    return LedgerMatch(
                        record=entry, distance=0, method="exact_phash"
                    )

            # 2. Near match pass (Hamming distance)
            if max_distance > 0:
                best_match: LedgerRecord | None = None
                best_dist: int = max_distance + 1
                for entry in self._entries:
                    try:
                        dist = hamming_distance(entry.phash, phash)
                        if dist <= max_distance and dist < best_dist:
                            best_match = entry
                            best_dist = dist
                    except ValueError:
                        continue
                if best_match is not None:
                    return LedgerMatch(
                        record=best_match,
                        distance=best_dist,
                        method="hamming_phash",
                    )

            return None

    def verify_integrity(self) -> tuple[bool, str | None]:
        with self._lock:
            return verify_ledger_chain(self._entries)

    def snapshot(self) -> tuple[LedgerRecord, ...]:
        with self._lock:
            return tuple(self._entries)

    def head_hash(self) -> str:
        with self._lock:
            return (
                self._entries[-1].entry_hash
                if self._entries
                else GENESIS_PREVIOUS_HASH
            )
