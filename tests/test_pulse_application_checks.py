"""Targeted tests for application-observation reuse and URL-check boundaries."""
from unittest.mock import patch

import pytest

from pulse_suite_overview import application_checks_summary
from services import (
    DEFAULT_SERVICES_CONFIG,
    ServiceEntry,
    _NoRedirectHandler,
    _check_url,
    _collect_services,
    generate_services_pulse,
)


def test_app_observations_are_local_and_escaped():
    page = application_checks_summary([
        {"name": "<img src=x onerror=alert(1)>", "type": "url",
         "state": "up", "severity": "ok", "latency_ms": 12.3}
    ], True)
    assert "<img src=" not in page
    assert "&lt;img" in page
    assert "No automatic association with remote Docker contexts" in page
    assert "12 ms" in page


def test_absent_check_is_not_healthy_and_collection_failure_is_unknown():
    assert "not proof of healthy applications" in application_checks_summary([], True)
    assert "health is unknown" in application_checks_summary(None, False)


def test_unconfigured_external_url_is_never_contacted():
    with patch("urllib.request.build_opener") as open_mock:
        result = _check_url({"url": "https://outside.example/test?secret=hidden"},
                            DEFAULT_SERVICES_CONFIG)
    assert result.severity == "unknown"
    assert "secret" not in result.target
    open_mock.assert_not_called()


def test_non_http_url_is_rejected_and_userinfo_is_not_exposed():
    for url in ("file:///etc/passwd", "http://user:pass@localhost:8080/test?token=private"):
        with patch("urllib.request.build_opener") as open_mock:
            entry = _check_url({"url": url, "allow_external": True}, DEFAULT_SERVICES_CONFIG)
        assert entry.severity == "unknown"
        assert "pass" not in entry.target
        assert "private" not in entry.target
        open_mock.assert_not_called()


def test_redirect_handler_refuses_implicit_follow():
    assert _NoRedirectHandler().redirect_request(
        None, None, 302, "found", {"Location": "https://outside.example"}, "https://outside.example"
    ) is None


def test_successful_url_check_shares_only_redacted_target():
    class Response:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def getcode(self):
            return 200
    class Opener:
        def open(self, request, timeout):
            return Response()
    with patch("urllib.request.build_opener", return_value=Opener()) as build_opener:
        row = _check_url({"url": "http://localhost:8080/private?token=secret"},
                         DEFAULT_SERVICES_CONFIG)
    assert row.severity == "ok"
    assert row.target == "http://localhost:8080"
    assert isinstance(build_opener.call_args.args[0], _NoRedirectHandler)


def test_service_checks_bounded_before_collecting():
    with pytest.raises(ValueError, match="max 100"):
        _collect_services({"service_checks": [{"type": "tcp"}] * 101})


def test_service_probe_timeout_must_be_bounded():
    for value in (-1, 0, 31, "invalid", float("inf")):
        with pytest.raises(ValueError, match="timeout"):
            _check_url({"url": "http://localhost:8000/health", "timeout_seconds": value},
                       DEFAULT_SERVICES_CONFIG)


def test_existing_service_generator_can_supply_inprocess_evidence():
    entry = ServiceEntry(name="model", check_type="url", target="http://localhost:11434",
                         state="up", severity="ok", latency_ms=9.1, note="ok")
    sink = {}
    with patch("services._load_config", return_value=DEFAULT_SERVICES_CONFIG), \
         patch("services._collect_services", return_value=[entry]), \
         patch("services._render"), patch("services._write_last_success"):
        assert generate_services_pulse(observation_sink=sink) is True
    assert sink["entries"] == [
        {"name": "model", "type": "url", "state": "up", "severity": "ok", "latency_ms": 9.1}
    ]
