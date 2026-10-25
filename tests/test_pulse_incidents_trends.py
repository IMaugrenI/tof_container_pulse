from __future__ import annotations

import json
from pulse_history import acknowledge_incident, load_history, load_incidents, record_snapshot
from pulse_incidents import duration_label
from pulse_trends import render_trends


def row(*, state="running", severity="ok", cpu=12.5, mem=104.0, name="api"):
    return [{"host": "local", "container_id": "abc", "name": name,
             "image": "api:1", "state": state, "severity": severity,
             "cpu_percent": cpu, "memory_mb": mem, "memory_percent": 7.5}]


def test_metrics_are_bounded_and_rendered(tmp_path):
    path = tmp_path / "hist.json"
    record_snapshot(path, ["local"], row(), at="2026-10-25T12:00:00+00:00")
    record_snapshot(path, ["local"], row(cpu=30, mem=220), at="2026-10-25T12:01:00+00:00")
    snapshots = load_history(path)
    assert snapshots[-1]["containers"][0]["cpu_percent"] == 30
    assert "Resource" in render_trends(snapshots)
    assert "<svg" in render_trends(snapshots)


def test_incident_lifecycle_and_ack(tmp_path):
    path = tmp_path / "hist.json"
    record_snapshot(path, ["local"], row(severity="warn"), at="2026-10-25T12:00:00+00:00")
    incidents = load_incidents(path)
    assert len(incidents) == 1
    assert incidents[0]["onset_estimate"] == "first_observed"
    incident_id = incidents[0]["id"]
    result = acknowledge_incident(path, incident_id, at="2026-10-25T12:01:00+00:00")
    assert result["acknowledged_at"] == "2026-10-25T12:01:00+00:00"
    record_snapshot(path, [], [])
    assert load_incidents(path)[0]["resolved_at"] is None
    record_snapshot(path, ["local"], row(severity="critical", state="exited"),
                    at="2026-10-25T12:02:00+00:00")
    assert load_incidents(path)[0]["peak_severity"] == "critical"
    record_snapshot(path, ["local"], row(), at="2026-10-25T12:04:00+00:00")
    ended = load_incidents(path)[0]
    assert ended["resolved_at"] == "2026-10-25T12:04:00+00:00"
    assert duration_label(ended) == "0h 04m"
    assert acknowledge_incident(path, incident_id)["acknowledged_at"] == result["acknowledged_at"]


def test_disappearance_only_from_successfully_observed_host(tmp_path):
    path = tmp_path / "hist.json"
    record_snapshot(path, ["local"], row(), at="2026-10-25T12:00:00+00:00")
    record_snapshot(path, [], [], at="2026-10-25T12:01:00+00:00")
    assert load_incidents(path) == []
    record_snapshot(path, ["local"], [], at="2026-10-25T12:02:00+00:00")
    incidents = load_incidents(path)
    assert len(incidents) == 1
    assert incidents[0]["reason"] == "disappeared_from_listing"
    record_snapshot(path, ["local"], row(), at="2026-10-25T12:03:00+00:00")
    assert load_incidents(path)[0]["resolved_at"] == "2026-10-25T12:03:00+00:00"


def test_legacy_history_payload_migrates_without_deletion(tmp_path):
    path = tmp_path / "hist.json"
    path.write_text(json.dumps({"version": 1, "snapshots": [
        {"at": "2026-10-25T11:00:00+00:00", "hosts": ["local"], "containers": row(),
         "events": []}]}))
    record_snapshot(path, ["local"], row(cpu=20), at="2026-10-25T12:00:00+00:00")
    assert len(load_history(path)) == 2
    assert isinstance(load_incidents(path), list)


def test_invalid_metrics_not_recorded_or_drawn(tmp_path):
    path = tmp_path / "hist.json"
    record_snapshot(path, ["local"], row(cpu=float("inf"), mem=-2))
    values = load_history(path)[0]["containers"][0]
    assert values["cpu_percent"] is None
    assert values["memory_mb"] is None
    assert render_trends(load_history(path)) == ""


def test_unknown_metrics_do_not_falsely_resolve_existing_incident(tmp_path):
    path = tmp_path / "hist.json"
    record_snapshot(path, ["local"], row(severity="warn"), at="2026-10-25T12:00:00+00:00")
    record_snapshot(path, ["local"], row(severity="unknown", cpu=None, mem=None),
                    at="2026-10-25T12:01:00+00:00")
    incident = load_incidents(path)[0]
    assert incident["resolved_at"] is None
    assert incident["last_severity"] == "unknown"
    record_snapshot(path, ["local"], row(severity="ok"), at="2026-10-25T12:02:00+00:00")
    assert load_incidents(path)[0]["resolved_at"] == "2026-10-25T12:02:00+00:00"


def test_lots_of_closed_incidents_do_not_increase_unbounded_retention():
    from pulse_incidents import MAX_INCIDENTS, advance_incidents
    records = [
        {"id": f"INC-{i}", "container_key": f"key-{i}", "resolved_at": "2026-10-25",
         "started_at": "2026-10-24", "host": "h", "name": "n"}
        for i in range(MAX_INCIDENTS + 20)
    ]
    pruned = advance_incidents(records, [], [], [], "2026-10-25T12:00:00+00:00")
    assert len(pruned) == MAX_INCIDENTS
