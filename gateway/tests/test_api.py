from __future__ import annotations

from dataclasses import fields

from fastapi.testclient import TestClient

from gateway.app.config import Settings
from gateway.app.main import create_app
from gateway.app.services.audit import InMemoryAuditRepository
from gateway.app.services.consent import ConsentState
from gateway.app.services.risk import RiskAssessment

API_KEY = "test-api-key"


class FixedConsentVerifier:
    def __init__(self, state: ConsentState) -> None:
        self.state = state
        self.calls: list[tuple[str | None, str, str]] = []

    def verify(self, token: str | None, *, app_id: str, scope: str) -> ConsentState:
        self.calls.append((token, app_id, scope))
        return self.state


class FixedRiskScorer:
    def __init__(self, score: float) -> None:
        self.score = score

    def assess(self, prompt: str) -> RiskAssessment:
        return RiskAssessment(self.score, "test", "test")


def _settings(
    base: Settings,
    *,
    threshold: int | None = None,
    rate_limit: int | None = None,
) -> Settings:
    values = {field.name: getattr(base, field.name) for field in fields(Settings)}
    if threshold is not None:
        values["blocked_attempt_threshold"] = threshold
    if rate_limit is not None:
        values["rate_limit_requests"] = rate_limit
    return Settings(**values)


def _request(
    *,
    scope: str = "filter",
    prompt: str = "Apply a cartoon filter",
    user_ref: str = "demo-user-1",
    **extra: object,
) -> dict[str, object]:
    return {
        "prompt": prompt,
        "scope": scope,
        "user_ref": user_ref,
        **extra,
    }


def test_health_docs_and_check_response_schema(settings: Settings) -> None:
    client = TestClient(create_app(settings))
    assert client.get("/health").status_code == 200
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/docs").status_code == 200
    schema = client.get("/openapi.json").json()
    assert "/v1/check" in schema["paths"]
    assert schema["paths"]["/v1/check"]["post"]["requestBody"]

    response = client.post(
        "/v1/check",
        json=_request(),
        headers={"X-API-Key": API_KEY},
    )
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
        "check_id",
        "decision",
        "tier",
        "reasons",
        "consent_required",
        "request_risk",
    }
    assert body["check_id"].startswith("c_")
    assert body["decision"] == "allow"
    assert body["tier"] == 0
    assert body["consent_required"] is False
    assert body["request_risk"] == {
        "score": 0.0,
        "label": "unassessed",
        "source": "stub",
    }


def test_tier_one_missing_consent_fails_to_consent_required(settings: Settings) -> None:
    client = TestClient(create_app(settings))
    response = client.post(
        "/v1/check",
        json=_request(
            scope="face_swap",
            test_signals={"real_face": True, "minor_risk": False},
        ),
        headers={"X-API-Key": API_KEY},
    )
    assert response.status_code == 200
    assert response.json()["decision"] == "needs_consent"
    assert response.json()["reasons"] == ["consent_required"]


def test_valid_consent_boundary_receives_server_app_and_scope(settings: Settings) -> None:
    verifier = FixedConsentVerifier(ConsentState.VALID)
    client = TestClient(create_app(settings, consent_verifier=verifier))
    response = client.post(
        "/v1/check",
        json=_request(
            scope="face_swap",
            consent_token="opaque-demo-token",
            test_signals={"real_face": True, "minor_risk": False},
        ),
        headers={"X-API-Key": API_KEY},
    )
    assert response.status_code == 200
    assert response.json()["decision"] == "allow"
    assert verifier.calls == [("opaque-demo-token", "test-partner", "face_swap")]


def test_unavailable_verifier_never_approves_supplied_token(settings: Settings) -> None:
    client = TestClient(create_app(settings))
    response = client.post(
        "/v1/check",
        json=_request(
            scope="face_swap",
            consent_token="unverified-token",
            test_signals={"real_face": True, "minor_risk": False},
        ),
        headers={"X-API-Key": API_KEY},
    )
    assert response.status_code == 200
    assert response.json()["decision"] == "needs_consent"
    assert response.json()["reasons"] == ["consent_verification_unavailable"]


def test_tier_two_and_minor_risk_cannot_be_overridden(settings: Settings) -> None:
    verifier = FixedConsentVerifier(ConsentState.VALID)
    client = TestClient(create_app(settings, consent_verifier=verifier))
    tier_two = client.post(
        "/v1/check",
        json=_request(
            scope="nude_transformation",
            consent_token="valid-token",
            test_signals={"real_face": True, "minor_risk": False},
        ),
        headers={"X-API-Key": API_KEY},
    )
    child_tier_one = client.post(
        "/v1/check",
        json=_request(
            scope="face_swap",
            consent_token="valid-token",
            test_signals={"real_face": True, "minor_risk": True},
        ),
        headers={"X-API-Key": API_KEY},
    )
    assert tier_two.json()["decision"] == "block"
    assert tier_two.json()["reasons"] == ["sexual_real_face_hard_block"]
    assert child_tier_one.json()["decision"] == "block"
    assert child_tier_one.json()["reasons"] == ["child_risk_hard_block"]
    assert verifier.calls == []


def test_authentication_validation_and_unknown_scope(settings: Settings) -> None:
    client = TestClient(create_app(settings))
    assert client.post("/v1/check", json=_request()).status_code == 401
    bad_key = client.post(
        "/v1/check", json=_request(), headers={"X-API-Key": "wrong"}
    )
    assert bad_key.status_code == 401
    assert bad_key.json() == {
        "error": {
            "code": "unauthorized",
            "message": "A valid API key is required.",
        }
    }
    unknown_scope = client.post(
        "/v1/check",
        json=_request(scope="surprise"),
        headers={"X-API-Key": API_KEY},
    )
    assert unknown_scope.status_code == 422
    assert unknown_scope.json()["error"]["code"] == "invalid_request"
    assert "surprise" not in unknown_scope.text
    unexpected_app_id = client.post(
        "/v1/check",
        json={**_request(), "app_id": "untrusted"},
        headers={"X-API-Key": API_KEY},
    )
    assert unexpected_app_id.status_code == 422


def test_repeated_blocks_restrict_later_benign_check(settings: Settings) -> None:
    client = TestClient(create_app(_settings(settings, threshold=2)))
    headers = {"X-API-Key": API_KEY}
    for _ in range(2):
        response = client.post(
            "/v1/check",
            json=_request(
                scope="sexual_transformation",
                test_signals={"real_face": True, "minor_risk": False},
            ),
            headers=headers,
        )
        assert response.json()["decision"] == "block"
    assert "restricted_user" in response.json()["reasons"]

    restricted = client.post("/v1/check", json=_request(), headers=headers)
    assert restricted.status_code == 200
    assert restricted.json()["decision"] == "block"
    assert restricted.json()["reasons"] == ["restricted_user"]


def test_high_risk_signal_and_rate_limit(settings: Settings) -> None:
    app = create_app(
        _settings(settings, rate_limit=1),
        request_risk_scorer=FixedRiskScorer(0.9),
    )
    client = TestClient(app)
    headers = {"X-API-Key": API_KEY}
    first = client.post("/v1/check", json=_request(), headers=headers)
    assert first.json()["decision"] == "block"
    limited = client.post("/v1/check", json=_request(), headers=headers)
    assert limited.status_code == 429
    assert limited.headers["Retry-After"] == "60"
    assert limited.json()["error"]["code"] == "rate_limited"


def test_audit_never_persists_raw_user_prompt_or_token(
    settings: Settings, caplog
) -> None:
    repository = InMemoryAuditRepository()
    client = TestClient(create_app(settings, audit_repository=repository))
    prompt = "sensitive prompt phrase"
    user_ref = "identifiable-user-value"
    token = "raw-consent-token-value"
    response = client.post(
        "/v1/check",
        json=_request(
            prompt=prompt,
            user_ref=user_ref,
            scope="face_swap",
            consent_token=token,
            test_signals={"real_face": True, "minor_risk": False},
        ),
        headers={"X-API-Key": API_KEY},
    )
    assert response.status_code == 200
    entries = repository.snapshot()
    assert len(entries) == 1
    entry = entries[0]
    assert entry.pseudonymous_user_ref != user_ref
    assert prompt not in repr(entry)
    assert user_ref not in repr(entry)
    assert token not in repr(entry)
    assert prompt not in caplog.text
    assert user_ref not in caplog.text
    assert token not in caplog.text
    assert API_KEY not in caplog.text


def test_test_signals_require_explicit_opt_in_and_missing_age_fails_closed(
    settings: Settings,
) -> None:
    values = {field.name: getattr(settings, field.name) for field in fields(Settings)}
    values["enable_test_signals"] = False
    client = TestClient(create_app(Settings(**values)))
    headers = {"X-API-Key": API_KEY}

    rejected = client.post(
        "/v1/check",
        json=_request(
            scope="face_swap",
            test_signals={"real_face": False, "minor_risk": False},
        ),
        headers=headers,
    )
    assert rejected.status_code == 400
    assert rejected.json()["error"]["code"] == "test_signals_disabled"

    fail_closed = client.post(
        "/v1/check",
        json=_request(scope="face_swap"),
        headers=headers,
    )
    assert fail_closed.status_code == 200
    assert fail_closed.json()["decision"] == "block"
    assert fail_closed.json()["reasons"] == ["minor_risk_unavailable"]
