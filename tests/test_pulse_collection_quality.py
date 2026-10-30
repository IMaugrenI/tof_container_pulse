"""Targeted quality/provenance and application latency regression checks."""
from unittest.mock import patch

import pytest

from pulse_suite_overview import collection_quality, collection_summary
from services import DEFAULT_SERVICES_CONFIG, _check_tcp, _check_url, _latency_warning_limit


def test_collector_quality_never_conflates_partial_unknown_or_unavailable():
    assert collection_quality("containers", True, {"successful_hosts": [], "failed_hosts": ["remote"]})[0] == "unavailable"
    assert collection_quality("containers", True, {"successful_hosts": ["local"], "failed_hosts": ["remote"]})[0] == "partial"
    assert collection_quality("containers", True, {"successful_hosts": ["local"], "failed_hosts": []})[0] == "collected"
    assert collection_quality("services", True, services=[])[0] == "not_configured"
    assert collection_quality("services", True, services=[{"severity": "unknown"}])[0] == "unavailable"
    assert collection_quality("services", True, services=[{"severity": "unknown"}, {"severity": "ok"}])[0] == "partial"
    assert collection_quality("services", False, services=[{"severity": "ok"}])[0] == "unavailable"
    assert collection_quality("hardware", None)[0] == "unconfirmed"


def test_utc_completion_is_escaped_and_not_mislabeled_sampling_time():
    text = collection_summary(
        {"containers": True, "hardware": True, "ports": False,
         "storage": True, "services": True, "security": True},
        docker_evidence={"successful_hosts": ["local"], "failed_hosts": ["remote"]},
        service_entries=[{"severity": "unknown"}, {"severity": "ok"}],
        completed_at={"containers": "2026-10-30T17:00:00+00:00",
                      "services": "<img onerror=1>"},
    )
    assert "partial Docker collection" in text
    assert "checks include unknown results" in text
    assert "1 hosts collected, 1 unavailable" in text
    assert "2026-10-30T17:00:00+00:00" in text
    assert "<img onerror" not in text and "&lt;img" in text
    assert "not individual metric sampling times" in text


def test_no_docker_success_does_not_count_as_collected():
    text = collection_summary(
        {"containers": True},
        docker_evidence={"successful_hosts": [], "failed_hosts": ["remote"]},
    )
    assert "no Docker hosts collected" in text
    assert "0 of 6 collectors completed" in text


def test_latency_warning_configuration_requires_finite_positive_bounds():
    assert _latency_warning_limit({}) is None
    assert _latency_warning_limit({"latency_warn_ms": 25}) == 25
    for value in (0, -10, 120001, float("inf"), float("nan"), "bad"):
        with pytest.raises(ValueError, match="latency_warn_ms"):
            _latency_warning_limit({"latency_warn_ms": value})


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


def test_slow_http_success_is_warning_not_outage():
    with patch("services.urllib.request.build_opener", return_value=Opener()), \
         patch("services.time.monotonic", side_effect=[20.0, 20.3]):
        result = _check_url(
            {"name": "api", "url": "http://localhost:8000/health", "latency_warn_ms": 200},
            DEFAULT_SERVICES_CONFIG,
        )
    assert result.state == "slow"
    assert result.severity == "warn"
    assert result.latency_ms == pytest.approx(300)
    assert "answered as expected" in result.note


def test_latency_threshold_does_not_change_success_without_optin():
    with patch("services.urllib.request.build_opener", return_value=Opener()), \
         patch("services.time.monotonic", side_effect=[20.0, 20.3]):
        result = _check_url({"url": "http://localhost:8000/health"}, DEFAULT_SERVICES_CONFIG)
    assert result.state == "up"
    assert result.severity == "ok"


def test_slow_tcp_connection_is_warning_not_outage():
    class Connection:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False

    with patch("services.socket.create_connection", return_value=Connection()), \
         patch("services.time.monotonic", side_effect=[100.0, 100.5]):
        result = _check_tcp({"host": "localhost", "port": 5432, "latency_warn_ms": 100},
                            DEFAULT_SERVICES_CONFIG)
    assert result.state == "slow"
    assert result.severity == "warn"
    assert result.latency_ms == pytest.approx(500)


def test_invalid_tcp_configuration_does_not_look_like_a_service_outage():
    for port in (0, 65536, -1, True, "not-a-port"):
        with patch("services.socket.create_connection") as connect:
            result = _check_tcp({"host": "localhost", "port": port}, DEFAULT_SERVICES_CONFIG)
        assert result.severity == "unknown"
        connect.assert_not_called()
