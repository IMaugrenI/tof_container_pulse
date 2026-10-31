"""Opt-in anonymized incident export using saved Pulse history, no Docker calls."""
from __future__ import annotations

import json
import math
import os
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from pulse_history import load_history, load_incidents
from pulse_trends import resource_anomalies

LEVELS = ("ok", "warn", "critical", "unknown")
REASONS = {"unhealthy_container", "disappeared_from_listing"}


def _high(value: object, threshold: float) -> bool:
    try:
        number = float(value)
        return math.isfinite(number) and threshold <= number <= 10000
    except (ValueError, TypeError):
        return False


def build_report(history_path: str | Path, anomaly_config: dict | None = None) -> dict:
    """Only identifiers from a fixed whitelist are emitted; all hosts are aliased."""
    snapshots = load_history(history_path)
    incidents = load_incidents(history_path)
    names = sorted({str(h) for item in snapshots for h in item.get("hosts", [])})
    aliases = {host: f"host-{i + 1}" for i, host in enumerate(names)}
    latest = {}
    for item in snapshots:
        for host in item.get("hosts", []):
            latest[str(host)] = (
                str(item.get("at", ""))[:50],
                [row for row in item.get("containers", []) if row.get("host") == host],
            )
    active = Counter(str(item.get("host", "")) for item in incidents
                     if item.get("resolved_at") is None)
    deviation_counts = Counter((item["host"], item["metric"]) for item in resource_anomalies(snapshots, rules=anomaly_config))
    summary, cooccurrences = [], []
    for host, alias in aliases.items():
        captured, containers = latest.get(host, ("", []))
        count = Counter(str(r.get("severity", "unknown")) for r in containers)
        cpu = sum(_high(r.get("cpu_percent"), 80) for r in containers)
        memory = sum(_high(r.get("memory_percent"), 85) for r in containers)
        summary.append({
            "host_alias": alias, "last_observed_at": captured,
            "containers": len(containers), "open_incidents": active[host],
            "severity_counts": {level: count[level] for level in LEVELS},
            "high_cpu_containers": cpu, "high_memory_containers": memory,
            "unusual_cpu_containers": deviation_counts[(host, "cpu_percent")],
            "unusual_memory_containers": deviation_counts[(host, "memory_mb")],
        })
        if active[host] >= 2 and (cpu or memory):
            cooccurrences.append({
                "host_alias": alias,
                "signal": "multiple_incidents_and_resource_pressure",
                "caution": "Shared host does not prove shared root cause",
            })
        if deviation_counts[(host, "cpu_percent")] or deviation_counts[(host, "memory_mb")]:
            cooccurrences.append({
                "host_alias": alias,
                "signal": "historical_resource_deviation",
                "caution": "Statistical change only; examine workload and measurements manually",
            })
    reports = [{
        "id": str(row.get("id", ""))[:50],
        "host_alias": aliases[str(row["host"])],
        "started_at": str(row.get("started_at", ""))[:50],
        "last_observed_at": str(row.get("last_observed_at", ""))[:50],
        "resolved_at": str(row.get("resolved_at") or "")[:50],
        "acknowledged": bool(row.get("acknowledged_at")),
        "peak_severity": str(row.get("peak_severity", "unknown"))
            if row.get("peak_severity") in LEVELS else "unknown",
        "reason": row.get("reason") if row.get("reason") in REASONS else "unspecified",
    } for row in incidents[-100:] if str(row.get("host", "")) in aliases]
    return {
        "schema_version": 1, "generated_at_utc": datetime.now(UTC).isoformat(),
        "observations": len(snapshots), "hosts": summary,
        "correlations": cooccurrences, "incidents": reports,
        "limitations": "Docker history only; missing metrics are not zeros; co-occurrence and statistical deviations do not prove causality.",
    }


def export_report(history_path: str | Path, destination: str | Path,
                  anomaly_config: dict | None = None) -> dict:
    """Create a new mode-0600 file, never overwrite a report or scan Docker."""
    payload = build_report(history_path, anomaly_config=anomaly_config)
    target = Path(destination)
    if not target.parent.is_dir():
        raise FileNotFoundError("Report directory does not exist")
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(target, flags, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            json.dump(payload, output, indent=2)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
    except Exception:
        target.unlink(missing_ok=True)
        raise
    return {"report": str(target), "incident_count": len(payload["incidents"])}
