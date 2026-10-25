"""Conservative historical host overview and illustrative memory trend estimates.

Only the retained, successfully collected container resource samples are
considered. No host scanning, extrapolation from unknown metrics or
claims of guaranteed capacity/incident prediction.
"""
from __future__ import annotations

import html
import math
import statistics
from collections import Counter, defaultdict
from datetime import datetime

from i18n_static import l10n_text


def _sample(value):
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
        if math.isfinite(number) and 0 <= number <= 10_000_000:
            return number
    except (TypeError, ValueError):
        pass
    return None


def _parsed(value):
    try:
        parsed = datetime.fromisoformat(str(value))
        return parsed.timestamp() if parsed.tzinfo else None
    except (ValueError, TypeError, OverflowError):
        return None


def memory_projection(points, threshold_mb):
    """Simple rate-of-change illustration with strict quality gates.

    Returns minutes until a configured warning threshold, or None.
    A positive slope alone is never a reliable operational prediction.
    """
    threshold = _sample(threshold_mb)
    if not threshold or threshold <= 0:
        return None
    valid = []
    for timestamp, value in points[-24:]:
        t = _parsed(timestamp)
        v = _sample(value)
        if t is not None and v is not None and (not valid or t > valid[-1][0]):
            valid.append((t, v))
    if len(valid) < 5 or (valid[-1][0] - valid[0][0]) < 1200:
        return None
    elapsed_minutes = (valid[-1][0] - valid[0][0]) / 60
    first = statistics.median(v for _,v in valid[:max(2, len(valid)//3)])
    last = statistics.median(v for _,v in valid[-max(2, len(valid)//3):])
    increase = last - first
    if increase < max(20, threshold * 0.05):
        return None
    slope = increase / elapsed_minutes
    if slope <= 0 or last >= threshold:
        return None
    eta = (threshold - last) / slope
    if 0 < eta <= 1440:
        return round(eta)
    return None


def capacity_rows(snapshots, memory_warn_mb=1024, max_hosts=15, max_containers=12):
    """Last 48 observations; preserve host scoping and absent-metric ambiguity."""
    previous = {}
    series = defaultdict(list)
    for snap in snapshots[-48:]:
        instant = str(snap.get("at", ""))[:50]
        containers = snap.get("containers", [])
        for host in snap.get("hosts", []):
            seen = [r for r in containers if r.get("host") == host]
            previous[str(host)] = {"at": instant, "containers": seen}
            for row in seen:
                series[(str(host), str(row.get("container_id", "")))].append(
                    (instant, row.get("memory_mb")))
    overview = []
    for host in sorted(previous)[:max_hosts]:
        records = previous[host]["containers"]
        level = Counter(str(r.get("severity", "unknown")) for r in records)
        overview.append({
            "host": host, "last_success": previous[host]["at"],
            "containers": len(records),
            "warn": level["warn"], "critical": level["critical"],
            "unknown": level["unknown"],
        })
    current = [
        (str(host), str(row.get("container_id", "")), row)
        for host, details in previous.items()
        for row in details["containers"]
    ]
    outlook = []
    for host, ident, row in current:
        eta = memory_projection(series[(host, ident)], memory_warn_mb)
        if eta is not None:
            outlook.append({
                "host": host, "name": str(row.get("name", ""))[:120],
                "minutes": eta, "warning_mb": float(memory_warn_mb),
                "quality": "illustrative_linear_change",
            })
    outlook.sort(key=lambda x:x["minutes"])
    return {"hosts": overview, "outlook": outlook[:max_containers],
            "observations_examined": min(len(snapshots), 48)}


def render_capacity(snapshots, memory_warn_mb=1024):
    if not snapshots:
        return ""
    data = capacity_rows(snapshots, memory_warn_mb)
    esc = lambda value: html.escape(str(value), quote=True)
    host_rows = [
        "<tr><td>" + esc(h["host"]) + "</td><td>" + esc(h["last_success"]) +
        "</td><td>" + esc(h["containers"]) + "</td><td>" +
        esc(h["warn"]) + " / " + esc(h["critical"]) + " / " + esc(h["unknown"]) +
        "</td></tr>"
        for h in data["hosts"]
    ]
    outlook_rows = [
        "<li>" + esc(r["host"]) + " / " + esc(r["name"]) + ": " +
        esc(r["minutes"]) + l10n_text(" min (illustrative only)",
                                       " Min. (nur rechnerischer Anhaltspunkt)") + "</li>"
        for r in data["outlook"]
    ]
    if not outlook_rows:
        outlook_rows = ["<li>" + l10n_text(
            "Insufficient stable history for an illustrative memory trend.",
            "Keine ausreichende stabile Historie für einen rechnerischen Speichertrend.") + "</li>"]
    return (
        '<section class="pulse-capacity" aria-label="Multi-host capacity observations">'
        '<div class="table-title"><h2>' +
        l10n_text("Host and capacity overview", "Host- und Kapazitätsüberblick") +
        '</h2><span>' + l10n_text(
            "Observed data only; memory trend is not a prediction.",
            "Nur beobachtete Daten; Speichertrend ist keine Prognose.") +
        '</span></div><div class="table-shell"><table><thead><tr><th>Host</th>'
        '<th>Last successful scan</th><th>Containers</th><th>Warn/Critical/Unknown</th>'
        '</tr></thead><tbody>' + "".join(host_rows) + '</tbody></table></div>'
        '<h3>' + l10n_text("Illustrative time to configured memory warning level",
                             "Rechnerische Zeit bis zur konfigurierten Speicherwarnung") +
        '</h3><ul>' + "".join(outlook_rows) + '</ul></section>'
    )
