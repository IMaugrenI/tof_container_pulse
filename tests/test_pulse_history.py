from __future__ import annotations

import json

import pytest

from pulse_history import load_history, record_snapshot, render_incidents


def sample(name="api", state="running", severity="ok", image="svc:v1"):
    return [{"host": "local", "container_id": "abc", "name": name,
             "state": state, "severity": severity, "image": image}]


def test_baseline_then_incident_and_recovery(tmp_path):
    path = tmp_path / "history.json"
    first = record_snapshot(path, ["local"], sample(), at="2026-01-01T00:00:00+00:00")
    assert first[-1]["events"] == []
    second = record_snapshot(path, ["local"], sample(state="exited", severity="critical"),
                             at="2026-01-01T00:01:00+00:00")
    assert len(second[-1]["events"]) == 1
    assert "state: running" in second[-1]["events"][0]["detail"]
    third = record_snapshot(path, ["local"], sample(), at="2026-01-01T00:02:00+00:00")
    assert len(third[-1]["events"]) == 1
    assert "Störungs-" in render_incidents(third)


def test_unavailable_host_does_not_create_disappearance(tmp_path):
    path = tmp_path / "history.json"
    record_snapshot(path, ["local"], sample())
    before = path.read_bytes()
    record_snapshot(path, [], [])
    assert path.read_bytes() == before
    # Another host can succeed without interpreting local as disappeared.
    snapshots = record_snapshot(path, ["remote"], [
        {"host": "remote", "container_id": "new", "name": "db",
         "state": "running", "severity": "ok", "image": "db:v1"}
    ])
    assert snapshots[-1]["events"] == []


def test_confirmed_disappearance_and_retention(tmp_path):
    path = tmp_path / "history.json"
    record_snapshot(path, ["local"], sample(), max_snapshots=2)
    snapshots = record_snapshot(path, ["local"], [], max_snapshots=2)
    assert snapshots[-1]["events"][0]["kind"] == "disappeared"
    snapshots = record_snapshot(path, ["local"], [], max_snapshots=2)
    assert len(snapshots) == 2
    assert snapshots[-1]["events"] == []


def test_invalid_history_is_not_overwritten(tmp_path):
    path = tmp_path / "history.json"
    path.write_text('{"wrong":true}', encoding="utf-8")
    with pytest.raises(ValueError):
        record_snapshot(path, ["local"], sample())
    assert json.loads(path.read_text()) == {"wrong": True}


def test_output_escapes_untrusted_values(tmp_path):
    path = tmp_path / "history.json"
    record_snapshot(path, ["local"], sample())
    snapshots = record_snapshot(path, ["local"], sample(name="<script>"), max_snapshots=5)
    fragment = render_incidents(snapshots)
    assert "<script>" not in fragment
    assert "&lt;script&gt;" in fragment


def test_rejects_unobserved_host(tmp_path):
    with pytest.raises(ValueError, match="successful observation"):
        record_snapshot(tmp_path / "history.json", ["local"], [
            {"host": "other", "container_id": "1", "name": "c"}])
