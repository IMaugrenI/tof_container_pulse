"""Static, bounded resource trend charts for the existing Pulse HTML output."""
from __future__ import annotations

import html
import math
from collections import defaultdict

from i18n_static import l10n_text


def _sample(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        numeric = float(value)
    except (ValueError, TypeError):
        return None
    return round(numeric, 3) if math.isfinite(numeric) and 0 <= numeric <= 10_000_000 else None


def _sparkline(values: list[float | None], label: str) -> str:
    # Gaps are not zeros; only valid, contiguous measurements form each line.
    valid = [v for v in values if v is not None]
    if not valid:
        return "<span>" + l10n_text("No measurements yet", "Noch keine Messwerte") + "</span>"
    height = 48.0
    upper = max(max(valid) * 1.15, 1)
    segments: list[list[str]] = []
    running: list[str] = []
    for i, value in enumerate(values):
        if value is None:
            if running:
                segments.append(running)
                running = []
            continue
        x = 7.0 + i * (226.0 / max(1, len(values) - 1))
        y = height - 4.0 - (value / upper) * (height - 8.0)
        running.append(f"{x:.1f},{y:.1f}")
    if running:
        segments.append(running)
    strokes = "".join(
        '<polyline fill="none" stroke="currentColor" stroke-width="2" points="' +
        " ".join(points) + '"/>' for points in segments if len(points) > 1
    )
    points = "".join(
        '<circle fill="currentColor" cx="' + p.split(",")[0] + '" cy="' +
        p.split(",")[1] + '" r="2"/>' for seg in segments for p in seg[-1:]
    )
    current = f"{valid[-1]:.1f}"
    return (
        '<svg viewBox="0 0 240 48" role="img" aria-label="' + html.escape(label, quote=True) +
        '" class="pulse-trend-chart">' + strokes + points + "</svg>"
        '<span class="pulse-trend-value">' + current + "</span>"
    )


def render_trends(snapshots: list[dict], limit: int = 8) -> str:
    if not snapshots:
        return ""
    series: dict[tuple[str, str], list[dict]] = defaultdict(list)
    # Only a host's successful observation contributes; missing hosts create no samples.
    for snap in snapshots[-24:]:
        for row in snap.get("containers", []):
            identity = (str(row.get("host", "")), str(row.get("container_id", "")))
            series[identity].append(row)
    # Most recently seen containers first; source data is bounded by record_snapshot.
    keys = sorted(series, key=lambda k: len(series[k]), reverse=True)[:limit]
    rows = []
    for host, ident in keys:
        samples = series[(host, ident)]
        if not any(_sample(row.get("cpu_percent")) is not None or
                   _sample(row.get("memory_mb")) is not None for row in samples):
            continue
        name = html.escape(str(samples[-1].get("name", ident)), quote=True)
        host_name = html.escape(host, quote=True)
        cpu = [_sample(row.get("cpu_percent")) for row in samples]
        mem = [_sample(row.get("memory_mb")) for row in samples]
        rows.append(
            "<tr><td><strong>" + name + "</strong><br><code>" + host_name + "</code></td>"
            "<td>" + _sparkline(cpu, "CPU percent") + "</td>"
            "<td>" + _sparkline(mem, "Memory MiB") + "</td></tr>"
        )
    if not rows:
        return ""
    return (
        '<section class="pulse-trends" aria-label="Resource trends">'
        '<div class="table-title"><h2>' +
        l10n_text("Resource trends", "Ressourcenverläufe") +
        '</h2><span>' + l10n_text(
            "Last 24 saved observations; gaps and unavailable metrics are not zero.",
            "Letzte 24 Beobachtungen; Lücken und fehlende Metriken sind nicht Null."
        ) + '</span></div><div class="table-shell"><table><thead><tr><th>Container</th>'
        '<th>CPU %</th><th>Memory MiB</th></tr></thead><tbody>' + "".join(rows) +
        "</tbody></table></div></section>"
    )
