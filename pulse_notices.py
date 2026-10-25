"""Opt-in local notification inbox for NEW and RESOLVED incidents only.

No emails, native notifications, Docker actions or outbound connections.
A pre-existing incident is baseline on first enablement; no notification spam.
"""
from __future__ import annotations

import html
import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from i18n_static import l10n_text

MAX_BYTES = 500_000
MAX_EVENTS = 100


def _load(path):
    target = Path(path)
    if not target.exists():
        return None
    if target.is_symlink() or target.stat().st_size > MAX_BYTES:
        raise ValueError("Unsafe or oversized local notifications store")
    data = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("version") != 1:
        raise ValueError("Unsupported local notifications schema")
    if not isinstance(data.get("known"), dict) or not isinstance(data.get("events"), list):
        raise ValueError("Invalid local notifications payload")
    return data


def _save(path, data):
    target = Path(path)
    if not target.parent.is_dir() or target.is_symlink():
        raise ValueError("Notification destination parent missing or path is a symlink")
    serialized = json.dumps(data, ensure_ascii=False)
    if len(serialized.encode("utf-8")) > MAX_BYTES:
        raise ValueError("Notification state exceeds configured storage limit")
    temp = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=target.parent,
                                         prefix=".pulse-notice-", delete=False) as fd:
            temp = fd.name
            os.chmod(temp, 0o600)
            fd.write(serialized)
            fd.flush()
            os.fsync(fd.fileno())
        os.replace(temp, target)
    finally:
        if temp and os.path.exists(temp):
            os.unlink(temp)


def refresh_notices(path, incidents, at=None):
    """Return recent local notices, tracking only IDs and status transitions."""
    prior = _load(path)
    known = {} if prior is None else dict(prior["known"])
    events = [] if prior is None else list(prior["events"])
    stamp = at or datetime.now(UTC).isoformat()
    for incident in incidents[-350:]:
        ident = str(incident.get("id", ""))
        if not ident.startswith("INC-") or len(ident) > 60:
            continue
        resolved = bool(incident.get("resolved_at"))
        previous = known.get(ident)
        if prior is not None:
            event = None
            if previous is None and not resolved:
                event = "opened"
            elif previous is False and resolved:
                event = "resolved"
            if event is not None:
                events.append({
                    "at": stamp, "id": ident, "state": event,
                    "severity": str(incident.get("peak_severity", "unknown"))[:30],
                })
        known[ident] = resolved
    # Preserve at most the currently retained 350 incident IDs.
    retained = {str(i.get("id", "")) for i in incidents[-350:]}
    known = {key:value for key,value in known.items() if key in retained}
    events = events[-MAX_EVENTS:]
    state = {"version": 1, "known": known, "events": events}
    if prior != state:
        _save(path, state)
    return events


def render_notices(events):
    esc = lambda v: html.escape(str(v), quote=True)
    last = events[-15:][::-1]
    body = "".join(
        "<li>" + esc(event.get("at", "")) + " / " + esc(event.get("id", "")) +
        " / " + esc(event.get("state", "")) + " / " +
        esc(event.get("severity", "")) + "</li>"
        for event in last
    )
    if not body:
        body = "<li>" + l10n_text(
            "No new local notices. The first read is intentionally a baseline.",
            "Keine neuen lokalen Hinweise. Die erste Erfassung bildet bewusst nur die Ausgangslage.") + "</li>"
    return ('<section class="pulse-notices" aria-label="Local notification inbox">'
            '<div class="table-title"><h2>' +
            l10n_text("Local notification inbox", "Lokale Hinweisablage") +
            '</h2><span>' + l10n_text(
                "Stored locally; no desktop or remote push.",
                "Lokal gespeichert; keine Desktop- oder Remote-Benachrichtigung.") +
            '</span></div><ul>' + body + '</ul></section>')
