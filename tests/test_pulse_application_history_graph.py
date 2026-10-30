"""B1-B3: opt-in app history and evidence-only combined graph."""
import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from pulse_history import (
    load_application_history, load_history, record_application_snapshot, record_snapshot
)
from pulse_suite_overview import application_history_summary, infrastructure_matrix, add_suite_summary


BASE = datetime(2026, 10, 30, 13, tzinfo=UTC)


def timestamp(i):
    return (BASE + timedelta(minutes=i)).isoformat()


def app(name="api", severity="ok", latency=30, **extra):
    return {"name": name, "severity": severity, "state": "up",
            "type": "url", "latency_ms": latency, **extra}


def docker_row(host="a"):
    return {"host": host, "container_id": "one", "name": "database",
            "state": "running", "image": "internal/restricted:1",
            "severity": "ok", "cpu_percent": 20, "memory_mb": 250}


def test_application_samples_reuse_same_history_file_and_survive_docker_updates(tmp_path):
    path = tmp_path / "private_history.json"
    record_snapshot(path, ["a"], [docker_row()], at=timestamp(0))
    record_application_snapshot(path, [app(latency=40)], at=timestamp(1))
    record_snapshot(path, ["a"], [docker_row()], at=timestamp(2))
    record_application_snapshot(path, [app(severity="warn", latency=100)], at=timestamp(3))
    saved = load_application_history(path)
    assert len(saved) == 2
    assert len(load_history(path)) == 2
    assert saved[0]["scope"] == "suite_local"
    assert saved[-1]["checks"][0]["latency_ms"] == 100
    text = json.dumps(saved)
    assert "internal/restricted" not in text
    assert "container_id" not in text
    assert "target" not in text
    assert "a/" not in text
    assert (path.stat().st_mode & 0o777) == 0o600


def test_history_rejects_ambiguous_samples_without_modifying_history(tmp_path):
    path = tmp_path / "history.json"
    record_application_snapshot(path, [app()], at=timestamp(0))
    previous = path.read_bytes()
    bad = (
        [app("API"), app("api")],
        [app("x")] * 101,
        [app(name="")],
        [app(name=" ")]
    )
    for entries in bad:
        with pytest.raises(ValueError):
            record_application_snapshot(path, entries, at=timestamp(1))
    with pytest.raises(ValueError):
        record_application_snapshot(path, [app()], at="2026-10-30T00:00:00")
    with pytest.raises(ValueError):
        record_application_snapshot(path, [app()], at=timestamp(1), max_snapshots=61)
    assert path.read_bytes() == previous


def test_application_history_is_bounded_and_unknown_is_not_zero(tmp_path):
    path = tmp_path / "app.json"
    for i in range(8):
        record_application_snapshot(path, [app(latency=None if i == 7 else i * 12,
                                              severity="unknown" if i == 7 else "ok")],
                                    at=timestamp(i), max_snapshots=3)
    history = load_application_history(path)
    assert len(history) == 3
    assert history[-1]["checks"][0]["quality"] == "unknown"
    assert history[-1]["checks"][0]["latency_ms"] is None
    page = application_history_summary(history)
    assert "Application history" in page
    assert "<td>UNKNOWN</td>" in page
    assert "No remote Docker-host inference" in page
    assert application_history_summary(None) == ""


def test_untrusted_app_names_are_escaped_in_history_summary():
    history = [{"at": timestamp(0), "scope": "suite_local",
                "checks": [app("<svg onload=x>")]}]
    page = application_history_summary(history)
    assert "<svg onload=" not in page
    assert "&lt;svg" in page


def test_existing_history_schema_still_reads_without_application_key(tmp_path):
    path = tmp_path / "old.json"
    path.write_text(json.dumps({"version": 1, "snapshots": [], "incidents": []}))
    assert load_application_history(path) == []


def test_shared_graph_respects_host_project_scope_and_explicit_links_only():
    docker = {
        "successful_hosts": ["host-a", "host-b"], "failed_hosts": ["unreachable"],
        "projects": [
            {"host": "host-a", "project": "stack",
             "services": [{"service": "api", "severities": ["warn"]},
                          {"service": "db", "severities": ["ok"]}],
             "edges": [{"from": "api", "to": "db", "present": True}]},
            {"host": "host-b", "project": "stack",
             "services": [{"service": "api", "severities": ["ok"]}],
             "edges": []}
        ],
    }
    html = infrastructure_matrix(
        docker, [{"check": "health", "host": "host-a", "project": "stack", "service": "api"}],
        [app("health", severity="critical")], True
    )
    a = html.split("host-a / stack", 1)[1].split("host-b / stack", 1)[0]
    b = html.split("host-b / stack", 1)[1]
    assert "health (CRITICAL)" in a
    assert "health (CRITICAL)" not in b
    assert "db (observed)" in a
    assert "unreachable" in html
    assert "no outage proven" in html
    assert "independent states, never causal proof" in html


def test_graph_cannot_infer_links_without_explicit_declaration():
    data = {"projects": [{"host": "x", "project": "p",
                           "services": [{"service": "api", "severities": ["ok"]}], "edges": []}]}
    view = infrastructure_matrix(data, [], [app("api", severity="critical")], True)
    assert "api" in view
    assert "api (CRITICAL)" not in view


def test_graph_escapes_untrusted_names_and_marks_missing_targets():
    data = {"projects": [{"host": "<script>", "project": "p",
                           "services": [{"service": "api", "severities": ["warn"]}],
                           "edges": [{"from": "api", "to": "<img>", "present": False}]}]}
    view = infrastructure_matrix(data, [], [], False)
    assert "<script>" not in view and "<img>" not in view
    assert "&lt;script&gt;" in view and "&lt;img&gt;" in view
    assert "(not observed)" in view


def test_suite_injection_contains_history_and_graph_without_second_page(tmp_path):
    path = tmp_path / "pulse.html"
    path.write_text('<section class="feature-strip" aria-label="Design principles"></section>')
    docker = {"projects": [{"host": "a", "project": "p",
                            "services": [{"service": "s", "severities": ["ok"]}], "edges": []}]}
    hist = [{"at": timestamp(0), "scope": "suite_local", "checks": [app()]}]
    assert add_suite_summary(path, {"services": True}, [app()], docker,
                             application_history=hist)
    result = path.read_text()
    assert 'class="pulse-infrastructure-matrix"' in result
    assert 'class="pulse-app-history"' in result
    assert add_suite_summary(path, {"services": True}, [app()], docker,
                             application_history=hist) is False


def test_run_requires_double_optin_and_successful_services_collection():
    import run
    from unittest.mock import patch
    # No actual collector, network call, or generated file.
    args = SimpleNamespace(config=None, output="nothing.html", template="", state_file="",
                           hardware_output="", hardware_template="", hardware_state_file="",
                           ports_output="", ports_template="", ports_state_file="",
                           storage_output="", storage_template="", storage_state_file="",
                           services_output="", services_template="", services_state_file="",
                           security_output="", security_template="", security_state_file="")
    def verify(config, service_result, should_store):
        with patch("run._load_config", return_value=config), \
             patch("run.generate_pulse", return_value=True), \
             patch("run.generate_hardware_pulse", return_value=True), \
             patch("run.generate_port_pulse", return_value=True), \
             patch("run.generate_storage_pulse", return_value=True), \
             patch("run.generate_services_pulse", side_effect=lambda **kwargs: (
                 kwargs["observation_sink"].update({"entries": [app()]}) or service_result
             )), \
             patch("run.generate_security_pulse", return_value=True), \
             patch("run.record_application_snapshot") as store, \
             patch("run.load_application_history", return_value=[]), \
             patch("run.add_suite_summary"):
            run.generate_suite(args)
            assert store.called is should_store
    verify({"history_enabled": True, "application_history_enabled": False}, True, False)
    verify({"history_enabled": False, "application_history_enabled": True}, True, False)
    verify({"history_enabled": "true", "application_history_enabled": True}, True, False)
    verify({"history_enabled": True, "application_history_enabled": True}, False, False)
    verify({"history_enabled": True, "application_history_enabled": True}, True, True)
