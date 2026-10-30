"""Bounded historical anomaly hints; never a health or root-cause verdict."""
from datetime import UTC, datetime, timedelta

from pulse_trends import render_anomalies, resource_anomalies


BASE = datetime(2026, 10, 30, 12, tzinfo=UTC)


def snap(i, *, host="server", cpu=12, memory=400, severity="ok", observed=True):
    return {
        "at": (BASE + timedelta(minutes=i)).isoformat(),
        "hosts": [host] if observed else [],
        "containers": ([{
            "host": host, "container_id": "id1", "name": "api",
            "severity": severity, "cpu_percent": cpu, "memory_mb": memory,
        }] if observed else []),
    }


def test_positive_deviation_requires_stable_history_and_real_latest_sample():
    history = [snap(i) for i in range(10)] + [snap(10, cpu=95, memory=1200)]
    rows = resource_anomalies(history)
    assert {row["metric"] for row in rows} == {"cpu_percent", "memory_mb"}
    assert all(row["assessment"] == "unusual_positive_deviation_not_causal_proof" for row in rows)
    assert "no outage, leak, or cause proven" in render_anomalies(history).lower()


def test_missing_sparse_and_unobserved_samples_are_not_anomalies():
    assert resource_anomalies([snap(i) for i in range(5)] + [snap(5, cpu=1000)]) == []
    history = [snap(i, cpu=None, memory=None) for i in range(10)] + [snap(10, cpu=100)]
    assert resource_anomalies(history) == []
    history = [snap(i) for i in range(10)] + [snap(10, observed=False)]
    assert resource_anomalies(history) == []
    history = [snap(i) for i in range(10)] + [snap(10, cpu=1000, severity="unknown")]
    assert resource_anomalies(history) == []


def test_never_borrow_baseline_from_other_host():
    history = [snap(i, host="server-one") for i in range(10)]
    history.append(snap(10, host="server-two", cpu=90, memory=2000))
    assert resource_anomalies(history) == []


def test_stale_baseline_does_not_trigger_deviation():
    history = [snap(i) for i in range(10)]
    history.append(snap(100, cpu=95, memory=2000))
    assert resource_anomalies(history) == []


def test_untrusted_container_name_is_escaped():
    history = [snap(i) for i in range(10)] + [snap(10, cpu=99)]
    history[-1]["containers"][0]["name"] = "<script>alert(1)</script>"
    result = render_anomalies(history)
    assert "<script>" not in result
    assert "&lt;script&gt;" in result
