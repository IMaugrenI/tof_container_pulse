"""B4-B6 source-bounded diagnostics, sensitivity and static UX contracts."""
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from pulse_trends import anomaly_rules, resource_anomalies, render_anomalies
from pulse_suite_overview import (
    add_suite_summary, diagnosis_queue, evidence_navigation, render_diagnosis_queue,
    table_filter_controls,
)


def snapshot(i, cpu=12, memory=400, host="srv", observed=True):
    return {
        "at": (datetime(2026, 10, 31, 11, tzinfo=UTC) + timedelta(minutes=i)).isoformat(),
        "hosts": [host] if observed else [],
        "containers": [{
            "host": host, "container_id": "id",
            "name": "api", "severity": "ok",
            "cpu_percent": cpu, "memory_mb": memory
        }] if observed else [],
    }


def test_configurable_thresholds_keep_scope_and_baseline_quality():
    snapshots = [snapshot(i) for i in range(10)] + [snapshot(10, cpu=40, memory=500)]
    assert resource_anomalies(snapshots) == []
    altered = {
        "anomaly_cpu_min_rise_percent": 10,
        "anomaly_memory_min_rise_mb": 64,
    }
    rows = resource_anomalies(snapshots, rules=altered)
    assert {r["metric"] for r in rows} == {"cpu_percent"}
    # Relative baseline increase is still enforced; weak changes cannot be forced.
    assert all(r["assessment"] == "unusual_positive_deviation_not_causal_proof" for r in rows)
    assert resource_anomalies([snapshot(i, host="other") for i in range(10)] +
                              [snapshot(10, cpu=90, host="srv")], rules=altered) == []


def test_anomaly_configuration_rejects_unsafe_values():
    examples = [
        ("anomaly_min_samples", 2),
        ("anomaly_min_samples", 8.5),
        ("anomaly_min_span_seconds", 100),
        ("anomaly_max_sample_age_seconds", 7201),
        ("anomaly_cpu_min_rise_percent", float("nan")),
        ("anomaly_memory_min_rise_mb", "bad"),
        ("anomaly_memory_min_rise_mb", True),
    ]
    for key, value in examples:
        with pytest.raises(ValueError, match=key):
            anomaly_rules({key: value})


def test_resource_uncertainty_panel_never_calls_all_clear():
    page = render_anomalies([snapshot(0), snapshot(1)])
    assert "Only 2 saved observations" in page
    assert "No resource verdict" in page
    many = render_anomalies([snapshot(i) for i in range(12)])
    assert "does not prove healthy resources" in many
    assert "no outage, leak, or cause proven" in render_anomalies(
        [snapshot(i) for i in range(10)] + [snapshot(10, cpu=99)]
    ).lower()


def test_diagnostic_queue_bounds_and_preserves_local_scope():
    data = {
        "failed_hosts": ["remote-offline"],
        "containers": [
            {"host": "remote", "project": "stack", "service": "api", "severity": "critical"},
            {"host": "remote", "project": "stack", "service": "db", "severity": "warn"},
        ],
    }
    apps = [{"name": "health", "severity": "critical"}]
    rows = diagnosis_queue(data, apps, {"services": True})
    assert rows[0]["priority"] == "critical"
    assert len(rows) == 4
    assert any(x["source"] == "services" and x["scope"] == "suite_local / health" for x in rows)
    assert any(x["signal"] == "collection_unavailable" and x["priority"] == "unknown" for x in rows)
    assert "remote-offline" in render_diagnosis_queue(data, apps, {"services": True})
    assert len(diagnosis_queue(data, [{"name": str(i), "severity": "critical"} for i in range(100)],
                               {"services": True})) == 12


def test_queue_rejects_inferred_causality_and_escapes_names():
    data = {"failed_hosts": ["<svg onload=x>"], "containers": [
        {"host": "<img>", "project": "stack", "service": "api", "severity": "warn"}
    ]}
    text = render_diagnosis_queue(data, [{"name": "<script>", "severity": "critical"}],
                                  {"services": True})
    assert "<svg onload=x>" not in text and "<img>" not in text and "<script>" not in text
    assert "&lt;svg" in text and "&lt;script&gt;" in text
    assert "never causal proof" in text
    assert "separate explicit CLI action" in text
    assert diagnosis_queue({"containers": []}, [], {"services": True}) == []


def test_navigation_only_references_existing_sections_and_original_pages():
    html = evidence_navigation({"pulse-app-summary", "pulse-suite-summary"})
    assert 'href="#pulse-suite-summary"' in html
    assert 'href="#pulse-app-summary"' in html
    assert 'href="#pulse-app-history"' not in html
    for page in ("pulse.html", "hardware.html", "ports.html", "storage.html", "services.html", "security.html"):
        assert 'href="' + page + '"' in html
    assert "Pulse evidence navigation" in html
    assert table_filter_controls("invalid") == ""
    for target in ("pulse-triage-queue", "pulse-app-summary", "pulse-infrastructure-matrix"):
        assert f'data-filter-target="{target}"' in table_filter_controls(target)


def test_existing_dashboard_gains_accessible_read_only_filters_and_ids(tmp_path):
    path = tmp_path / "pulse.html"
    path.write_text('<main><section class="feature-strip" aria-label="Design principles">'
                    '</section></main></body>', encoding="utf-8")
    statuses = {"containers": True, "services": True}
    docker = {"failed_hosts": ["offline"], "projects": [
        {"host": "one", "project": "stack", "services": [
            {"service": "api", "severities": ["warn"]}], "edges": []}
    ]}
    assert add_suite_summary(path, statuses, [{"name": "api", "severity": "ok"}], docker)
    result = path.read_text(encoding="utf-8")
    for panel in ("pulse-suite-summary", "pulse-triage-queue", "pulse-app-summary", "pulse-infrastructure-matrix"):
        assert f'id="{panel}"' in result
    assert 'href="#pulse-app-history"' not in result
    assert 'data-filter-target="pulse-triage-queue"' in result
    assert 'data-filter-target="pulse-infrastructure-matrix"' in result
    assert "row.hidden = !match" in result
    assert "select.addEventListener('change', applyFilter)" in result
    assert add_suite_summary(path, statuses, [], docker) is False


def test_missing_services_result_is_unknown_not_application_outage():
    rows = diagnosis_queue({}, None, {"services": False})
    assert len(rows) == 1
    assert rows[0]["signal"] == "collection_unavailable"
    assert rows[0]["priority"] == "unknown"
