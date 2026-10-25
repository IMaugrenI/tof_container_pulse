"""Bounded, optional local history and changes for Container Pulse.

Only successful Docker host observations participate in comparisons. This module
does not execute Docker, change container state, or contact the network.
"""
from __future__ import annotations

import html
import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from i18n_static import l10n_text

VERSION = 1
MAX_SNAPSHOTS = 240
MAX_BYTES = 2_000_000


def load_history(path: str | Path) -> list[dict]:
    target = Path(path)
    if not target.exists():
        return []
    if target.stat().st_size > MAX_BYTES:
        raise ValueError("History file exceeds bounded storage limit")
    payload = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("version") != VERSION:
        raise ValueError("History file has an unsupported schema")
    snapshots = payload.get("snapshots")
    if not isinstance(snapshots, list):
        raise ValueError("History snapshots are invalid")
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
                changed = [field for field in ("state", "severity", "image") if item[field] != old[field]]
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
        observations.append({
            field: str(item.get(field, ""))[:160]
            for field in ("host", "container_id", "name", "state", "severity", "image")
        })
    timestamp = at or datetime.now(UTC).isoformat()
    prior = load_history(path)
    entry = {
        "at": timestamp, "hosts": list(hosts), "containers": observations,
        "events": _changes(prior, hosts, observations, timestamp),
    }
    snapshots = (prior + [entry])[-int(max_snapshots):]
    serialized = json.dumps({"version": VERSION, "snapshots": snapshots}, ensure_ascii=False)
    while len(serialized.encode("utf-8")) > MAX_BYTES and len(snapshots) > 1:
        snapshots.pop(0)
        serialized = json.dumps({"version": VERSION, "snapshots": snapshots}, ensure_ascii=False)
    if len(serialized.encode("utf-8")) > MAX_BYTES:
        raise ValueError("Snapshot exceeds bounded history capacity")

    dest = Path(path)
    # Explicitly configured paths must already have a parent; never create unknown trees.
    if not dest.parent.is_dir():
        raise FileNotFoundError("History directory does not exist")
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
