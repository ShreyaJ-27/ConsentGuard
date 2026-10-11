from __future__ import annotations

from collections import defaultdict, deque
from threading import Lock
from time import monotonic
from typing import Protocol


class RestrictionReview(Protocol):
    def restriction_cleared(self, pseudonymous_user_ref: str) -> bool: ...


class NoopRestrictionReview:
    """Extension point for a future reviewer/appeal workflow."""

    def restriction_cleared(self, pseudonymous_user_ref: str) -> bool:
        del pseudonymous_user_ref
        return False


class InMemoryEnforcement:
    """Process-local counters and sliding-window rate limiting."""

    def __init__(
        self,
        *,
        blocked_attempt_threshold: int,
        restriction_window_seconds: int,
        rate_limit_requests: int,
        rate_limit_window_seconds: int,
        review: RestrictionReview | None = None,
    ) -> None:
        self._threshold = blocked_attempt_threshold
        self._restriction_window = restriction_window_seconds
        self._rate_limit_requests = rate_limit_requests
        self._rate_limit_window = rate_limit_window_seconds
        self._review = review or NoopRestrictionReview()
        self._blocked_attempts: dict[str, deque[float]] = defaultdict(deque)
        self._rate_windows: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def allow_rate_limited_request(self, app_id: str, now: float | None = None) -> bool:
        current = monotonic() if now is None else now
        with self._lock:
            requests = self._rate_windows[app_id]
            self._prune(requests, current, self._rate_limit_window)
            if len(requests) >= self._rate_limit_requests:
                return False
            requests.append(current)
            return True

    def is_restricted(self, user_ref: str, now: float | None = None) -> bool:
        current = monotonic() if now is None else now
        with self._lock:
            attempts = self._blocked_attempts[user_ref]
            self._prune(attempts, current, self._restriction_window)
            threshold_reached = len(attempts) >= self._threshold
        return threshold_reached and not self._review.restriction_cleared(user_ref)

    def record_blocked_attempt(
        self, user_ref: str, now: float | None = None
    ) -> bool:
        current = monotonic() if now is None else now
        with self._lock:
            attempts = self._blocked_attempts[user_ref]
            self._prune(attempts, current, self._restriction_window)
            attempts.append(current)
            return len(attempts) >= self._threshold

    @staticmethod
    def _prune(entries: deque[float], now: float, window: int) -> None:
        cutoff = now - window
        while entries and entries[0] <= cutoff:
            entries.popleft()
