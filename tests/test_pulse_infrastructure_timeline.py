"""Evidence-only infrastructure timeline from bounded existing snapshots."""
from pulse_history import infrastructure_timeline_items, render_infrastructure_timeline


def test_events_require_successful_host_collection_and_ordered_timestamps():
    snapshots = [{
        "at": "2026-10-30T10:00:00+00:00", "hosts": ["host-one"],
        "events": [
            {"at": "2026-10-30T10:00:00+00:00", "host": "host-one",
             "container": "api", "kind": "changed", "detail": "state changed"},
            {"at": "2026-10-30T10:01:00+00:00", "host": "host-two",
             "container": "api", "kind": "disappeared", "detail": "unverified"},
        ],
    }]
    incidents = [{
        "id": "INC-123", "host": "host-one", "name": "api",
        "started_at": "2026-10-30T10:02:00+00:00",
        "resolved_at": "2026-10-30T10:04:00+00:00",
        "onset_estimate": "since_previous_snapshot",
    }]
    rows = infrastructure_timeline_items(snapshots, incidents)
    assert len(rows) == 3
    assert rows[0]["kind"] == "incident_recovery_observed"
    assert rows[1]["kind"] == "incident_first_observed"
    assert rows[1]["evidence"] == "incident_record_since_previous_snapshot"
    assert all(row["host"] == "host-one" for row in rows)


def test_malformed_times_and_unobserved_network_data_are_not_invented():
    observations = [{
        "at": "2026-10-30", "hosts": ["h"],
        "events": [{"host": "h", "container": "x", "kind": "changed",
                    "at": "not-a-time", "detail": "unknown"}],
    }]
    assert infrastructure_timeline_items(observations, []) == []
    assert render_infrastructure_timeline(observations, []) == ""


def test_timeline_bounds_and_html_escaping():
    at = "2026-10-30T12:00:00+00:00"
    events = [{"at": at, "host": "host<script>", "container": "<img src=x>",
               "kind": "changed", "detail": "<svg onload=alert(1)>"}] * 60
    snapshots = [{"at": at, "hosts": ["host<script>"], "events": events}]
    assert len(infrastructure_timeline_items(snapshots, [], limit=10)) == 10
    assert len(infrastructure_timeline_items(snapshots, [])) == 30
    html = render_infrastructure_timeline(snapshots, [])
    assert "<script>" not in html and "<img src=x>" not in html
    assert "&lt;script&gt;" in html and "&lt;svg" in html
    assert "not proven outage or recovery times" in html


def test_incident_unknown_onset_is_not_promoted_to_verified_event_start():
    rows = infrastructure_timeline_items([], [{
        "id": "INC-456", "host": "one", "name": "db",
        "started_at": "2026-10-30T10:02:00+00:00",
        "onset_estimate": "guess", "resolved_at": None,
    }])
    assert rows[0]["evidence"] == "incident_record_unknown"
