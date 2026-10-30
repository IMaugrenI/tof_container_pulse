"""Scoped infrastructure links without discovery, remote scans or inferred causality."""
from unittest.mock import patch

import pytest

from pulse import _normalized_hosts, generate_pulse
from pulse_suite_overview import declared_link_summary, operator_diagnostic_hint


def evidence():
    return {
        "successful_hosts": ["one", "two"],
        "failed_hosts": ["offline"],
        "containers": [
            {"host": "one", "project": "stack", "service": "api", "severity": "warn"},
            {"host": "two", "project": "stack", "service": "api", "severity": "ok"},
        ],
    }


def link(host="one", service="api", check="My API"):
    return {"check": check, "host": host, "project": "stack", "service": service}


def app(name="My API", severity="critical"):
    return {"name": name, "severity": severity, "type": "url", "state": "down"}


def test_explicit_link_never_uses_other_host():
    html = declared_link_summary([link("two")], evidence(), [app()], True)
    assert "<td>OK</td>" in html
    assert "<td>CRITICAL</td>" in html
    assert "not dependency or causal proof" in html.lower() or "not dependency" in html.lower()


def test_failed_host_and_missing_container_are_not_outages():
    missing = declared_link_summary([link("one", service="absent")], evidence(), [app()], True)
    failed = declared_link_summary([link("offline")], evidence(), [app()], True)
    assert "NOT_OBSERVED" in missing
    assert "NOT_COLLECTED" in failed
    assert "NOT_COLLECTED" not in missing


def test_ambiguous_application_name_is_unknown():
    html = declared_link_summary([link()], evidence(), [app(), app()], True)
    assert "<td>UNKNOWN</td>" in html


def test_no_automatic_links_and_escaped_operator_labels():
    assert declared_link_summary([], evidence(), [app()], True) == ""
    bad = link(check="<script>")
    html = declared_link_summary([bad], evidence(), [], False)
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_unbounded_link_config_is_rejected_without_rendering_names():
    html = declared_link_summary([link()] * 51, evidence(), [app()], True)
    assert "at most 50" in html
    assert "My API" not in html


def test_duplicate_context_aliases_rejected_before_collection():
    with pytest.raises(ValueError, match="Duplicate host aliases"):
        _normalized_hosts({"hosts": [
            {"name": "Local", "docker_context": "one"},
            {"name": "local", "docker_context": "two"},
        ]})


def test_docker_generator_reuses_existing_collection_without_extra_query():
    sink = {}
    observation = {"host": "one", "name": "api", "container_id": "a", "severity": "warn",
                   "compose_project": "stack", "compose_service": "api"}
    with patch("pulse._load_config", return_value={"hosts": [{"name": "one", "docker_context": "one"}],
                                                   "history_enabled": False, "topology_enabled": False,
                                                   "diagnostics_enabled": False}), \
         patch("pulse.shutil.which", return_value="docker"), \
         patch("pulse._collect_host_rows", return_value=([], [], {"total": 1, "running": 1,
                                                                  "warn": 1, "critical": 0, "unknown": 0},
                                                          [observation])) as collector, \
         patch("pulse._render_html"), patch("pulse._write_last_success"):
        assert generate_pulse(observation_sink=sink) is True
    collector.assert_called_once()
    assert sink["successful_hosts"] == ["one"]
    assert sink["containers"] == [{"host": "one", "project": "stack",
                                   "service": "api", "severity": "warn"}]


def test_rule_based_guidance_never_claims_cause_or_automation():
    assert "no common cause established" in operator_diagnostic_hint("critical", "warn")[0]
    assert "despite Docker OK" in operator_diagnostic_hint("critical", "ok")[0]
    assert "outage not confirmed" in operator_diagnostic_hint("critical", "not_observed")[0]
    assert "state is unknown" in operator_diagnostic_hint("ok", "not_collected")[0]
    assert "all replicas" in operator_diagnostic_hint("ok", "critical")[0]
    assert "ambiguous" in operator_diagnostic_hint("unknown", "ok")[0]
    assert "Mixed" in operator_diagnostic_hint("ok", "mixed")[0]


def test_operator_diagnostic_hint_is_visible_on_existing_link_table():
    html = declared_link_summary([link()], evidence(), [app()], True)
    assert "Manual diagnostic hint" in html
    assert "no common cause established" in html
