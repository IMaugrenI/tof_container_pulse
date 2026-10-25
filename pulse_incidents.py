"""Incremental, read-only incident lifecycle based on successful Docker observations."""
from __future__ import annotations

import hashlib
from datetime import UTC, datetime

MAX_INCIDENTS = 350
SEVERITIES = {"warn", "critical"}


def incident_key(host: str, container_id: str) -> str:
    """Key is deterministic across renamed containers on the same host."""
    return hashlib.sha256((host + "\x00" + container_id).encode("utf-8")).hexdigest()[:24]


def _id(key: str, started_at: str) -> str:
    return "INC-" + hashlib.sha256((key + "\x00" + started_at).encode("utf-8")).hexdigest()[:20]


def advance_incidents(incidents: list[dict], previous: list[dict], hosts: list[str],
                      observations: list[dict], timestamp: str) -> list[dict]:
    """Only hosts queried successfully may produce incidents or recovery evidence.

    Snapshot #1 for a host is treated as a baseline. Existing unhealthy containers
    are still recorded with the first-observed timestamp, not an invented onset.
    """
    result = [dict(row) for row in incidents]
    current = {
        incident_key(str(row["host"]), str(row["container_id"])): row
        for row in observations if row["host"] in hosts
    }
    prior_seen = {}
    for host in hosts:
        old = next((item for item in reversed(previous) if host in item.get("hosts", [])), None)
        if old is not None:
            for container in old.get("containers", []):
                if container.get("host") == host:
                    prior_seen[incident_key(str(host), str(container["container_id"]))] = container
    open_by_key = {row["container_key"]: row for row in result if row.get("resolved_at") is None}
    for key, record in current.items():
        severity = str(record.get("severity", "unknown"))
        existing = open_by_key.get(key)
        if severity in SEVERITIES:
            if existing is not None:
                existing["last_observed_at"] = timestamp
                existing["last_severity"] = severity
                existing["name"] = str(record.get("name", ""))[:120]
                # Preserve highest observed severity as independently reported severity.
                if severity == "critical":
                    existing["peak_severity"] = "critical"
            else:
                host = str(record["host"])
                first_observation = not any(host in snapshot.get("hosts", []) for snapshot in previous)
                item = {
                    "id": _id(key, timestamp), "container_key": key,
                    "host": host[:120], "name": str(record.get("name", ""))[:120],
                    "started_at": timestamp, "last_observed_at": timestamp,
                    "resolved_at": None, "acknowledged_at": None,
                    "onset_estimate": "first_observed" if first_observation else "since_previous_snapshot",
                    "reason": "unhealthy_container", "last_severity": severity,
                    "peak_severity": severity,
                }
                result.append(item)
        elif existing is not None:
            existing["last_observed_at"] = timestamp
            existing["last_severity"] = severity
            if severity == "ok":
                # UNKNOWN metrics are not evidence that a prior problem recovered.
                existing["resolved_at"] = timestamp
    for key, old in prior_seen.items():
        # A missing container is evidence only when its host's ps -a succeeded.
        if key in current:
            continue
        existing = open_by_key.get(key)
        if existing is not None:
            existing["last_observed_at"] = timestamp
            existing["reason"] = "disappeared_from_listing"
            existing["last_severity"] = "unknown"
        else:
            item = {
                "id": _id(key, timestamp), "container_key": key,
                "host": str(old.get("host", ""))[:120],
                "name": str(old.get("name", ""))[:120],
                "started_at": timestamp, "last_observed_at": timestamp,
                "resolved_at": None, "acknowledged_at": None,
                "onset_estimate": "since_previous_snapshot",
                "reason": "disappeared_from_listing",
                "last_severity": "unknown", "peak_severity": "unknown",
            }
            result.append(item)
    # Preserve all open incidents. Old resolved records are retained up to limit.
    if len(result) > MAX_INCIDENTS:
        open_rows = [row for row in result if row.get("resolved_at") is None]
        closed_rows = [row for row in result if row.get("resolved_at") is not None]
        slots = max(0, MAX_INCIDENTS - len(open_rows))
        result = (closed_rows[-slots:] if slots else []) + open_rows
    return result


def duration_label(row: dict, now: str | None = None) -> str:
    try:
        begin = datetime.fromisoformat(str(row["started_at"]))
        end = datetime.fromisoformat(str(row.get("resolved_at") or now or datetime.now(UTC).isoformat()))
        total_minutes = max(0, int((end - begin).total_seconds() // 60))
        return f"{total_minutes // 60}h {total_minutes % 60:02d}m"
    except (TypeError, ValueError, KeyError):
        return "unknown"
