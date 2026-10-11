from __future__ import annotations

from collections import OrderedDict
from threading import Lock
from typing import Protocol


class OutputStore(Protocol):
    """Protocol for temporary storage of stamped outputs."""

    def store(
        self, output_ref: str, image_bytes: bytes, mime_type: str = "image/png"
    ) -> None: ...

    def get(self, output_ref: str) -> tuple[bytes, str] | None: ...


class InMemoryOutputStore:
    """Non-durable, short-lived in-memory output store for local development.

    Retains recently stamped demo outputs up to a fixed capacity.
    Replaceable boundary for cloud object storage (e.g. S3, GCS) in production.
    """

    def __init__(self, capacity: int = 50) -> None:
        self._capacity = capacity
        self._store: OrderedDict[str, tuple[bytes, str]] = OrderedDict()
        self._lock = Lock()

    def store(
        self, output_ref: str, image_bytes: bytes, mime_type: str = "image/png"
    ) -> None:
        with self._lock:
            if len(self._store) >= self._capacity:
                self._store.popitem(last=False)
            self._store[output_ref] = (image_bytes, mime_type)

    def get(self, output_ref: str) -> tuple[bytes, str] | None:
        with self._lock:
            return self._store.get(output_ref)
