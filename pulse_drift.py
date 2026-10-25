"""Drift comparisons from existing read-only Docker observations (no inspect)."""
from __future__ import annotations
import html
import re
from collections import Counter
from i18n_static import l10n_text

PORT_RE = re.compile(r"(?:(\d{1,5})->)?(\d{1,5})/(tcp|udp|sctp)\b")

def normalize_ports(raw):
    values = set()
    for public, target, proto in PORT_RE.findall(str(raw or "")[:4096]):
        if int(target) > 65535 or (public and int(public) > 65535):
            continue
        values.add((int(public) if public else 0, int(target), proto))
    return ",".join((str(a) + "->" if a else "") + str(b) + "/" + c
                    for a, b, c in sorted(values))[:300]

def _identity(row):
    project = row.get("compose_project")
    service = row.get("compose_service")
    host = str(row.get("host", ""))
    if project and service:
        return host, "compose", str(project), str(service)
    return host, "name", str(row.get("name", ""))

def detect_drift(snapshots, limit=30):
    """Match stable IDs first, then uniquely identified Compose/name replacements."""
    if not 1 <= limit <= 100:
        raise ValueError("Invalid drift limit")
    previous = {}
    events = []
    for snapshot in snapshots[-120:]:
        for host in snapshot.get("hosts", []):
            now = [x for x in snapshot.get("containers", []) if x.get("host") == host]
            if host in previous:
                old = previous[host]
                old_id = {x.get("container_id"): x for x in old}
                old_counts = Counter(_identity(x) for x in old)
                new_counts = Counter(_identity(x) for x in now)
                old_names = {_identity(x):x for x in old if old_counts[_identity(x)] == 1}
                for row in now:
                    prior = old_id.get(row.get("container_id"))
                    if prior is None and new_counts[_identity(row)] == 1:
                        prior = old_names.get(_identity(row))
                    if prior is None:
                        continue
                    fields = []
                    if prior.get("container_id") != row.get("container_id"):
                        fields.append("recreated")
                    if prior.get("image") != row.get("image"):
                        fields.append("image")
                    if "ports" in prior and "ports" in row and prior["ports"] != row["ports"]:
                        fields.append("ports")
                    if fields:
                        events.append({
                            "at": str(snapshot.get("at", ""))[:50],
                            "host": str(host)[:120], "name": str(row.get("name", ""))[:120],
                            "fields": fields,
                            "images": [str(prior.get("image", ""))[:120], str(row.get("image", ""))[:120]],
                            "ports": [str(prior.get("ports", ""))[:300], str(row.get("ports", ""))[:300]],
                        })
            previous[host] = now
    return events[-limit:][::-1]

def render_drift(snapshots):
    esc = lambda x: html.escape(str(x), quote=True)
    items = []
    for row in detect_drift(snapshots):
        changes = []
        for field in row["fields"]:
            if field == "recreated":
                changes.append("container recreated")
            else:
                before, after = row["images"] if field == "image" else row["ports"]
                changes.append(field + ": " + (before or "-") + " → " + (after or "-"))
        items.append("<tr><td>" + esc(row["at"]) + "</td><td>" + esc(row["host"]) +
                     " / " + esc(row["name"]) + "</td><td>" +
                     esc("; ".join(changes)) + "</td></tr>")
    body = ('<div class="table-shell"><table><thead><tr><th>UTC</th><th>Container</th>'
            '<th>Observed changes</th></tr></thead><tbody>' + "".join(items) +
            '</tbody></table></div>') if items else "<p>" + l10n_text(
                "No observed drift in the retained history.",
                "Keine Änderungen im gespeicherten Verlauf beobachtet.") + "</p>"
    return ('<section class="pulse-drift" aria-label="Observed image and port drift">'
            '<div class="table-title"><h2>' +
            l10n_text("Image & port drift", "Image- und Portänderungen") +
            '</h2><span>' + l10n_text(
                "Observed metadata only; not a security assessment.",
                "Nur beobachtete Metadaten; keine Sicherheitsbewertung.") +
            '</span></div>' + body + '</section>')
