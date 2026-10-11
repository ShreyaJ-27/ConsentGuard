from __future__ import annotations

import pytest

from gateway.app.services.result_check import (
    FLAGGED_FIXTURE_MARKER,
    ResultCheckContext,
    ResultCheckError,
    StubResultChecker,
)


def _safe_image_fixture() -> bytes:
    # Minimal 8-byte dummy header for non-empty bytes
    return b"RIFF\x00\x00\x00\x00WEBPVP8 "


def test_stub_result_checker_allows_safe_fixture() -> None:
    checker = StubResultChecker()
    context = ResultCheckContext(check_id="c_test123", app_id="test-partner")
    result = checker.check_output(_safe_image_fixture(), context)

    assert result.allowed is True
    assert result.reason_codes == ("output_check_passed",)
    assert "stub_nsfw_check" in result.checks_run
    assert result.is_indeterminate is False


def test_stub_result_checker_rejects_flagged_marker() -> None:
    checker = StubResultChecker()
    context = ResultCheckContext(check_id="c_test123", app_id="test-partner")
    flagged_bytes = _safe_image_fixture() + FLAGGED_FIXTURE_MARKER
    result = checker.check_output(flagged_bytes, context)

    assert result.allowed is False
    assert result.reason_codes == ("harmful_content_detected",)
    assert result.is_indeterminate is False


def test_stub_result_checker_rejects_flagged_mock_signal() -> None:
    checker = StubResultChecker()
    context = ResultCheckContext(
        check_id="c_test123",
        app_id="test-partner",
        mock_signal="flagged",
    )
    result = checker.check_output(_safe_image_fixture(), context)

    assert result.allowed is False
    assert result.reason_codes == ("harmful_content_detected",)


def test_stub_result_checker_fails_closed_on_indeterminate_high_risk() -> None:
    checker = StubResultChecker()
    context = ResultCheckContext(
        check_id="c_test123",
        app_id="test-partner",
        high_risk=True,
        mock_signal="indeterminate",
    )
    result = checker.check_output(_safe_image_fixture(), context)

    assert result.allowed is False
    assert result.reason_codes == ("safety_check_indeterminate_high_risk",)
    assert result.is_indeterminate is True


def test_stub_result_checker_fails_closed_on_indeterminate_standard() -> None:
    checker = StubResultChecker()
    context = ResultCheckContext(
        check_id="c_test123",
        app_id="test-partner",
        high_risk=False,
        mock_signal="indeterminate",
    )
    result = checker.check_output(_safe_image_fixture(), context)

    assert result.allowed is False
    assert result.reason_codes == ("safety_check_indeterminate",)
    assert result.is_indeterminate is True


def test_stub_result_checker_raises_on_error_signal() -> None:
    checker = StubResultChecker()
    context = ResultCheckContext(
        check_id="c_test123",
        app_id="test-partner",
        mock_signal="error",
    )
    with pytest.raises(ResultCheckError, match="Simulated safety check failure"):
        checker.check_output(_safe_image_fixture(), context)


def test_stub_result_checker_rejects_empty_or_too_small_payload() -> None:
    checker = StubResultChecker()
    context = ResultCheckContext(check_id="c_test123", app_id="test-partner")

    res_empty = checker.check_output(b"", context)
    assert res_empty.allowed is False
    assert res_empty.reason_codes == ("invalid_image_data",)

    res_tiny = checker.check_output(b"123", context)
    assert res_tiny.allowed is False
    assert res_tiny.reason_codes == ("invalid_image_data",)
