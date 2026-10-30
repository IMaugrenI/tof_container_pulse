"""Bounded, optional local history and changes for Container Pulse.

Only successful Docker host observations participate in comparisons. This module
does not execute Docker, change container state, or contact the network.
"""
from __future__ import annotations

import html
import json
import math
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from i18n_static import l10n_text
from pulse_incidents import advance_incidents, duration_label

VERSION = 1
MAX_SNAPSHOTS = 240
MAX_BYTES = 2_000_000
MAX_APP_SNAPSHOTS = 60
MAX_APP_CHECKS = 100


def _read_payload(path: str | Path) -> dict:
    target = Path(path)
    if not target.exists():
        return {"version": VERSION, "snapshots": [], "incidents": []}
    if target.stat().st_size > MAX_BYTES:
        raise ValueError("History file exceeds bounded storage limit")
    payload = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("version") != VERSION:
        raise ValueError("History file has an unsupported schema")
    snapshots = payload.get("snapshots")
    if not isinstance(snapshots, list):
        raise ValueError("History snapshots are invalid")
    if not isinstance(payload.get("incidents", []), list):
        raise ValueError("History incidents are invalid")
    if not isinstance(payload.get("application_snapshots", []), list):
        raise ValueError("History application snapshots are invalid")
    return payload


def load_history(path: str | Path) -> list[dict]:
    return _read_payload(path)["snapshots"]


def load_incidents(path: str | Path) -> list[dict]:
    return _read_payload(path).get("incidents", [])


def load_application_history(path: str | Path) -> list[dict]:
    """Return local-only app observations, not Docker host observations."""
    return _read_payload(path).get("application_snapshots", [])


def record_application_snapshot(path: str | Path, entries: list[dict],
                                at: str | None = None, max_snapshots: int = MAX_APP_SNAPSHOTS) -> list[dict]:
    """Store explicitly enabled application samples in the existing private history.

    Caller must gate on successful Services collection, enabled Docker history,
    and separate application_history_enabled. No new network calls or files.
    """
    if not isinstance(entries, list) or len(entries) > MAX_APP_CHECKS:
        raise ValueError("Application history supports at most 100 checks")
    if isinstance(max_snapshots, bool) or not isinstance(max_snapshots, int) or not 1 <= max_snapshots <= MAX_APP_SNAPSHOTS:
        raise ValueError("application_history_max_snapshots must be between 1 and 60")
    if not entries:
        return load_application_history(path)
    observed_at = at or datetime.now(UTC).isoformat()
    try:
        when = datetime.fromisoformat(observed_at)
        if when.tzinfo is None or when.utcoffset() is None:
            raise ValueError("naive timestamp")
    except (ValueError, TypeError) as exc:
        raise ValueError("Application collection timestamp must contain a timezone") from exc

    sanitized = []
    names = set()
    for item in entries:
        if not isinstance(item, dict):
            raise ValueError("Application check must be a mapping")
        name = str(item.get("name", ""))[:120].strip()
        if not name or name.casefold() in names:
            raise ValueError("Application history requires distinct, nonempty check names")
        names.add(name.casefold())
        severity = str(item.get("severity", "unknown"))
        severity = severity if severity in ("ok", "warn", "critical", "unknown") else "unknown"
        check_type = str(item.get("type", "unknown"))
        check_type = check_type if check_type in ("url", "tcp", "heartbeat", "http", "file_age") else "unknown"
        state = str(item.get("state", "unknown"))
        state = state if state in ("up", "down", "review", "open", "closed", "fresh", "stale", "missing", "slow") else "unknown"
        latency = _safe_metric(item.get("latency_ms"))
        latency = latency if latency is not None and latency <= 120000 else None
        sanitized.append({"name": name, "type": check_type, "state": state,
                          "severity": severity, "latency_ms": latency,
                          "quality": "unknown" if severity == "unknown" else "observed"})
    payload = _read_payload(path)
    previous = payload.get("application_snapshots", [])
    snapshots = (previous + [{"at": observed_at, "scope": "suite_local",
                              "checks": sanitized}])[-max_snapshots:]
    payload["application_snapshots"] = snapshots
    # Under storage pressure, prune only app history; preserve Docker and incidents.
    while len(json.dumps(payload, ensure_ascii=False).encode("utf-8")) > MAX_BYTES and len(snapshots) > 1:
        snapshots.pop(0)
    _write_payload(path, payload)
    return snapshots


def _key(row: dict) -> tuple[str, str]:
    return (str(row["host"]), str(row["container_id"]))


def _changes(previous: list[dict], hosts: list[str], current: list[dict], at: str) -> list[dict]:
    events: list[dict] = []
    for host in hosts:
        previous_host = next((s for s in reversed(previous) if host in s.get("hosts", [])), None)
        now = {_key(x): x for x in current if x["host"] == host}
        if previous_host is None:
            # First observation is a baseline, not evidence of a newly started container.
            continue
        before = {_key(x): x for x in previous_host.get("containers", []) if x["host"] == host}
        for key, item in now.items():
            old = before.get(key)
            if old is None:
                kind, details = "appeared", "Container now listed"
            else:
                changed = [field for field in ("name", "state", "severity", "image") if item[field] != old[field]]
                if not changed:
                    continue
                kind = "changed"
                details = "; ".join(
                    field + ": " + str(old[field]) + " → " + str(item[field]) for field in changed
                )
            events.append({
                "at": at, "host": host, "container": item["name"],
                "kind": kind, "severity": item["severity"], "detail": details,
            })
        for key, old in before.items():
            if key not in now:
                events.append({
                    "at": at, "host": host, "container": old["name"],
                    "kind": "disappeared", "severity": "unknown",
                    "detail": "Container no longer listed on this successfully queried host",
                })
    return events[:200]


def _safe_metric(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return round(number, 3) if math.isfinite(number) and 0 <= number <= 10_000_000 else None


def _write_payload(path: str | Path, payload: dict) -> None:
    dest = Path(path)
    if not dest.parent.is_dir():
        raise FileNotFoundError("History directory does not exist")
    serialized = json.dumps(payload, ensure_ascii=False)
    if len(serialized.encode("utf-8")) > MAX_BYTES:
        raise ValueError("History exceeds bounded storage capacity")
    temp_name = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=dest.parent,
                                         prefix=".pulse-history-", delete=False) as handle:
            temp_name = handle.name
            os.chmod(temp_name, 0o600)
            handle.write(serialized)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, dest)
    finally:
        if temp_name and os.path.exists(temp_name):
            os.unlink(temp_name)


def acknowledge_incident(path: str | Path, incident_id: str, at: str | None = None) -> dict:
    if not isinstance(incident_id, str) or not incident_id.startswith("INC-"):
        raise ValueError("Invalid incident ID")
    payload = _read_payload(path)
    found = next((row for row in payload.get("incidents", [])
                  if row.get("id") == incident_id), None)
    if found is None:
        raise ValueError("Incident ID not found in retained history")
    if found.get("acknowledged_at") is None:
        found["acknowledged_at"] = at or datetime.now(UTC).isoformat()
        _write_payload(path, payload)
    return dict(found)


def record_snapshot(path: str | Path, hosts: list[str], containers: list[dict],
                    max_snapshots: int = 120, at: str | None = None) -> list[dict]:
    """Persist a bounded snapshot and return the latest history.

    No write occurs if no hosts were observed successfully. Callers must not pass
    hosts whose Docker listing failed. Entries never contain Docker env or logs.
    """
    if not hosts:
        return load_history(path)
    if len(set(hosts)) != len(hosts):
        raise ValueError("Duplicate host labels in one snapshot")
    if len(containers) > 1500:
        raise ValueError("Too many container records for bounded history")
    if not 1 <= int(max_snapshots) <= MAX_SNAPSHOTS:
        raise ValueError("history_max_snapshots must be between 1 and 240")

    observations = []
    for item in containers:
        if item.get("host") not in hosts:
            raise ValueError("Container references a host without a successful observation")
        observation = {
            field: str(item.get(field, ""))[:160]
            for field in ("host", "container_id", "name", "state", "severity", "image")
        }
        observation["cpu_percent"] = _safe_metric(item.get("cpu_percent"))
        observation["memory_mb"] = _safe_metric(item.get("memory_mb"))
        observation["memory_percent"] = _safe_metric(item.get("memory_percent"))
        for key, limit in (("ports", 300), ("compose_project", 120), ("compose_service", 120)):
            if key in item:
                observation[key] = str(item[key])[:limit]
        observations.append(observation)
    timestamp = at or datetime.now(UTC).isoformat()
    previous_payload = _read_payload(path)
    prior = previous_payload["snapshots"]
    incidents = advance_incidents(previous_payload.get("incidents", []), prior, hosts, observations, timestamp)
    entry = {
        "at": timestamp, "hosts": list(hosts), "containers": observations,
        "events": _changes(prior, hosts, observations, timestamp),
    }
    snapshots = (prior + [entry])[-int(max_snapshots):]
    payload = {"version": VERSION, "snapshots": snapshots, "incidents": incidents,
               "application_snapshots": previous_payload.get("application_snapshots", [])}
    # Preserve the legacy Docker/incident storage budget before pruning those records.
    app_snapshots = payload["application_snapshots"]
    while len(json.dumps(payload, ensure_ascii=False).encode("utf-8")) > MAX_BYTES and app_snapshots:
        app_snapshots.pop(0)
    # Prefer pruning old resolved incidents over dropping active incidents.
    while len(json.dumps(payload, ensure_ascii=False).encode("utf-8")) > MAX_BYTES:
        closed = [r for r in incidents if r.get("resolved_at") is not None]
        if closed:
            incidents.remove(closed[0])
        elif len(snapshots) > 1:
            snapshots.pop(0)
        else:
            raise ValueError("History exceeds bounded storage capacity")
    _write_payload(path, payload)
    return snapshots


def render_incidents(snapshots: list[dict]) -> str:
    """Readable snapshot count and recent, HTML-escaped change records."""
    events = [e for snapshot in snapshots for e in snapshot.get("events", [])]
    recent = events[-12:][::-1]
    items = []
    for event in recent:
        safe = lambda field: html.escape(str(event.get(field, "")), quote=True)
        items.append(
            "<tr><td>" + safe("at") + "</td><td>" + safe("host") +
            "</td><td>" + safe("container") + "</td><td>" + safe("kind") +
            "</td><td>" + safe("detail") + "</td></tr>"
        )
    count = l10n_text(
        f"{len(snapshots)} saved observations; {len(events)} detected changes in the retained window.",
        f"{len(snapshots)} gespeicherte Beobachtungen; {len(events)} erkannte Änderungen im Aufbewahrungszeitraum."
    )
    if not items:
        body = "<p>" + l10n_text("No recorded changes yet.", "Noch keine Änderungen aufgezeichnet.") + "</p>"
    else:
        body = (
            '<div class="table-shell"><table><thead><tr><th>UTC</th><th>Host</th>'
            "<th>Container</th><th>Event</th><th>Detail</th></tr></thead>"
            "<tbody>" + "".join(items) + "</tbody></table></div>"
        )
    return (
        '<section aria-label="Incident history" class="pulse-history">'
        '<section class="table-title"><h2>' +
        l10n_text("Incident & change history", "Störungs- und Änderungsverlauf") +
        '</h2><span>' + count + '</span></section>' + body + '</section>'
    )


def render_incident_center(incidents: list[dict], at: str | None = None) -> str:
    """Read-only incident dashboard; acknowledgements require explicit local CLI."""
    esc = lambda s: html.escape(str(s), quote=True)
    recent = sorted(incidents, key=lambda r: r.get("started_at", ""), reverse=True)[:25]
    rows = []
    for row in recent:
        status = ("resolved" if row.get("resolved_at") else
                  "acknowledged" if row.get("acknowledged_at") else "open")
        rows.append(
            "<tr><td><code>" + esc(row.get("id", "")) + "</code></td>"
            "<td>" + esc(row.get("host", "")) + " / " + esc(row.get("name", "")) + "</td>"
            "<td>" + esc(status) + "</td>"
            "<td>" + esc(row.get("started_at", "")) + "</td>"
            "<td>" + esc(duration_label(row, at)) + "</td>"
            "<td>" + esc(row.get("reason", "")) + "</td></tr>"
        )
    if not rows:
        body = "<p>" + l10n_text(
            "No incidents registered in the retained window.",
            "Keine Vorfälle im gespeicherten Zeitraum registriert."
        ) + "</p>"
    else:
        body = ('<div class="table-shell"><table><thead><tr>'
                '<th>ID</th><th>Container</th><th>Status</th><th>Start UTC</th>'
                '<th>Duration</th><th>Reason</th></tr></thead><tbody>' +
                "".join(rows) + "</tbody></table></div>")
    open_count = sum(1 for row in incidents if row.get("resolved_at") is None)
    resolved_count = len(incidents) - open_count
    return (
        '<section class="pulse-incidents" aria-label="Incident lifecycle">'
        '<div class="table-title"><h2>' + l10n_text("Incident center", "Incident Center") +
        '</h2><span>' + l10n_text(
            f"{open_count} open · {resolved_count} resolved · acknowledgement through local CLI only",
            f"{open_count} offen · {resolved_count} behoben · Bestätigung nur über lokale CLI"
        ) + '</span></div>' + body + "</section>"
    )


# Universal Observer B3: bounded timeline built only from retained historical evidence.
_TIMELINE_KINDS = {"appeared", "changed", "disappeared"}


def infrastructure_timeline_items(snapshots: list[dict], incidents: list[dict],
                                  limit: int = 30) -> list[dict]:
    """Combine existing Docker change evidence and incident observations.

    Times are observation timestamps, never inferred start or outage times.
    No current service-check values are inserted into historical records.
    """
    items = []
    for snapshot in snapshots[-48:]:
        observed_hosts = set(str(host) for host in snapshot.get("hosts", [])[:80])
        for event in snapshot.get("events", [])[:200]:
            host = str(event.get("host", ""))[:120]
            kind = str(event.get("kind", ""))
            if not host or host not in observed_hosts or kind not in _TIMELINE_KINDS:
                continue
            items.append({
                "at": str(event.get("at") or snapshot.get("at") or "")[:50],
                "host": host, "subject": str(event.get("container", ""))[:120],
                "kind": "docker_" + kind, "evidence": "successful_docker_listing",
                "detail": str(event.get("detail", ""))[:300],
            })

    for incident in incidents[-350:]:
        host = str(incident.get("host", ""))[:120]
        ident = str(incident.get("id", ""))
        if not host or not ident.startswith("INC-"):
            continue
        beginning = str(incident.get("started_at") or "")[:50]
        if beginning:
            estimate = str(incident.get("onset_estimate", "first_observed"))
            if estimate not in ("first_observed", "since_previous_snapshot"):
                estimate = "unknown"
            items.append({
                "at": beginning, "host": host,
                "subject": str(incident.get("name", ""))[:120],
                "kind": "incident_first_observed",
                "evidence": "incident_record_" + estimate,
                "detail": ident[:50],
            })
        end = str(incident.get("resolved_at") or "")[:50]
        if end:
            items.append({
                "at": end, "host": host,
                "subject": str(incident.get("name", ""))[:120],
                "kind": "incident_recovery_observed", "evidence": "successful_docker_observation",
                "detail": ident[:50],
            })

    # Unsupported or malformed timestamps cannot establish an ordering.
    def parsed(item):
        try:
            dt = datetime.fromisoformat(item["at"])
            return dt.timestamp() if dt.tzinfo is not None else None
        except (ValueError, TypeError, OverflowError):
            return None

    ordered = [(parsed(item), item) for item in items]
    ordered = [(at, item) for at, item in ordered if at is not None]
    ordered.sort(key=lambda x: (x[0], x[1]["host"], x[1]["kind"]), reverse=True)
    return [item for _, item in ordered[:max(0, min(limit, 30))]]


def render_infrastructure_timeline(snapshots: list[dict], incidents: list[dict]) -> str:
    items = infrastructure_timeline_items(snapshots, incidents)
    if not items:
        return ""
    esc = lambda value: html.escape(str(value), quote=True)
    rows = [
        "<tr><td>" + esc(item["at"]) + "</td><td>" + esc(item["host"]) +
        "</td><td>" + esc(item["subject"]) + "</td><td>" +
        esc(item["kind"]) + "</td><td>" + esc(item["evidence"]) +
        "</td><td>" + esc(item["detail"]) + "</td></tr>"
        for item in items
    ]
    return (
        '<section class="pulse-infrastructure-timeline" aria-label="Infrastructure observation timeline">'
        '<div class="table-title"><h2>' +
        l10n_text("Infrastructure timeline", "Infrastruktur-Zeitachse") +
        '</h2><span>' +
        l10n_text("Observed evidence only; timestamps are not proven outage or recovery times.",
                  "Nur beobachtete Belege; Zeitstempel sind keine bewiesenen Ausfall- oder Wiederherstellungszeiten.") +
        '</span></div><div class="table-shell"><table><thead><tr><th>UTC</th><th>Host</th>'
        '<th>Object</th><th>Event</th><th>Evidence</th><th>Detail</th></tr></thead><tbody>' +
        "".join(rows) + '</tbody></table></div></section>'
    )
