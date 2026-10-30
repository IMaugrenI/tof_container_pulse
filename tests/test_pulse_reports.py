import json

import pytest

from pulse_history import record_snapshot
from pulse_reports import build_report, export_report


def row(host="private-server", ident="db-secret", severity="warn", cpu=95):
    return {
        "host": host, "container_id": ident, "name": ident,
        "image": "internal/app:v1", "state": "running", "severity": severity,
        "cpu_percent": cpu, "memory_percent": 90.0, "memory_mb": 240,
    }


def test_report_omits_names_and_exposes_correlations(tmp_path):
    history = tmp_path / "history.json"
    record_snapshot(history, ["private-server"], [row(ident="first"), row(ident="secret-db")])
    report = build_report(history)
    assert report["hosts"][0]["host_alias"] == "host-1"
    assert len(report["correlations"]) == 1
    text = json.dumps(report)
    for private in ("private-server", "first", "secret-db", "internal/app"):
        assert private not in text


def test_missing_host_does_not_indicate_recovery(tmp_path):
    history = tmp_path / "history.json"
    record_snapshot(history, ["private-server"], [row()])
    record_snapshot(history, [], [])
    report = build_report(history)
    assert report["incidents"][0]["resolved_at"] == ""


def test_export_creates_new_file_and_never_overwrites(tmp_path):
    history = tmp_path / "history.json"
    record_snapshot(history, ["private-server"], [row()])
    report_path = tmp_path / "incident.json"
    export_report(history, report_path)
    before = report_path.read_bytes()
    assert json.loads(before)["schema_version"] == 1
    with pytest.raises(FileExistsError):
        export_report(history, report_path)
    assert report_path.read_bytes() == before


def test_refuses_unknown_parent(tmp_path):
    with pytest.raises(FileNotFoundError):
        export_report(tmp_path / "no-history.json", tmp_path / "missing-dir" / "report.json")


def test_report_anonymizes_resource_deviation_evidence(tmp_path):
    from datetime import UTC, datetime, timedelta

    base = datetime(2026, 10, 30, 12, tzinfo=UTC)
    history = tmp_path / "history-anomaly.json"
    for i in range(11):
        observation = row(host="secret-internal-host", ident="hidden-container", severity="ok",
                          cpu=90 if i == 10 else 12)
        observation["memory_mb"] = 1500 if i == 10 else 400
        observation["memory_percent"] = 90 if i == 10 else 25
        record_snapshot(history, ["secret-internal-host"], [observation],
                        at=(base + timedelta(minutes=i)).isoformat())
    report = build_report(history)
    assert report["hosts"][0]["unusual_cpu_containers"] == 1
    assert report["hosts"][0]["unusual_memory_containers"] == 1
    assert any(x["signal"] == "historical_resource_deviation" for x in report["correlations"])
    exported = json.dumps(report)
    assert "secret-internal-host" not in exported
    assert "hidden-container" not in exported
    assert "internal/app" not in exported
