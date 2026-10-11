from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from threading import Lock
from typing import Protocol

from gateway.app.schemas import DecisionName


@dataclass(frozen=True)
class AuditRecord:
    check_id: str
    pseudonymous_user_ref: str
    tier: int
    decision: DecisionName
    reason_codes: tuple[str, ...]
    timestamp: datetime


class AuditRepository(Protocol):
    def record(self, entry: AuditRecord) -> None: ...


class InMemoryAuditRepository:
    """Process-local, non-durable metadata-only audit storage."""

    def __init__(self) -> None:
        self._entries: list[AuditRecord] = []
        self._lock = Lock()

    def record(self, entry: AuditRecord) -> None:
        with self._lock:
            self._entries.append(entry)

    def snapshot(self) -> tuple[AuditRecord, ...]:
        with self._lock:
            return tuple(self._entries)
