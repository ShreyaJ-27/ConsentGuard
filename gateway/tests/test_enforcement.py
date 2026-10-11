from __future__ import annotations

from dataclasses import fields

from gateway.app.services.audit import AuditRecord
from gateway.app.services.enforcement import InMemoryEnforcement


def test_blocked_attempts_trigger_and_expire_restriction() -> None:
    engine = InMemoryEnforcement(
        blocked_attempt_threshold=3,
        restriction_window_seconds=100,
        rate_limit_requests=10,
        rate_limit_window_seconds=60,
    )

    assert not engine.record_blocked_attempt("pseudonymous-user", now=10)
    assert not engine.is_restricted("pseudonymous-user", now=10)
    assert not engine.record_blocked_attempt("pseudonymous-user", now=20)
    assert engine.record_blocked_attempt("pseudonymous-user", now=30)
    assert engine.is_restricted("pseudonymous-user", now=30)
    assert not engine.is_restricted("pseudonymous-user", now=131)


def test_rate_limit_is_per_authenticated_app_and_windowed() -> None:
    engine = InMemoryEnforcement(
        blocked_attempt_threshold=3,
        restriction_window_seconds=100,
        rate_limit_requests=2,
        rate_limit_window_seconds=10,
    )
    assert engine.allow_rate_limited_request("app-a", now=1)
    assert engine.allow_rate_limited_request("app-a", now=2)
    assert not engine.allow_rate_limited_request("app-a", now=3)
    assert engine.allow_rate_limited_request("app-b", now=3)
    assert engine.allow_rate_limited_request("app-a", now=12)


def test_audit_schema_contains_only_required_metadata() -> None:
    assert {field.name for field in fields(AuditRecord)} == {
        "check_id",
        "pseudonymous_user_ref",
        "tier",
        "decision",
        "reason_codes",
        "timestamp",
    }
