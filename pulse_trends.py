"""Static, bounded resource trend charts for the existing Pulse HTML output."""
from __future__ import annotations

import html
import math
import statistics
from collections import defaultdict
from datetime import datetime

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


_DEFAULT_ANOMALY_RULES = {
    "anomaly_min_samples": 8,
    "anomaly_min_span_seconds": 300,
    "anomaly_max_sample_age_seconds": 3600,
    "anomaly_cpu_min_rise_percent": 20,
    "anomaly_memory_min_rise_mb": 128,
}


def anomaly_rules(config: dict | None = None) -> dict:
    """Validate opt-in sensitivity without relaxing conservative evidence gates."""
    config = config or {}
    bounds = {
        "anomaly_min_samples": (8, 24),
        "anomaly_min_span_seconds": (300, 3600),
        "anomaly_max_sample_age_seconds": (300, 3600),
        "anomaly_cpu_min_rise_percent": (10, 100),
        "anomaly_memory_min_rise_mb": (32, 65536),
    }
    rules = {}
    for key, fallback in _DEFAULT_ANOMALY_RULES.items():
        value = config.get(key, fallback)
        if isinstance(value, bool):
            raise ValueError(f"{key} must be a finite number in its supported range")
        try:
            number = float(value)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError(f"{key} must be a finite number in its supported range") from exc
        low, high = bounds[key]
        if not math.isfinite(number) or not low <= number <= high:
            raise ValueError(f"{key} must be between {low} and {high}")
        if key in ("anomaly_min_samples", "anomaly_min_span_seconds",
                   "anomaly_max_sample_age_seconds") and not number.is_integer():
            raise ValueError(f"{key} must be an integer")
        rules[key] = int(number) if number.is_integer() else number
    return rules


def resource_anomalies(snapshots: list[dict], limit: int = 12,
                       rules: dict | None = None) -> list[dict]:
    """Conservative positive outliers from retained, successful per-host samples.

    This is a statistical hint, not a failure, leak or root-cause diagnosis.
    The latest observation must itself include a successful host collection.
    """
    settings = anomaly_rules(rules)
    if len(snapshots) < settings["anomaly_min_samples"] + 2:
        return []
    previous = defaultdict(lambda: defaultdict(list))
    for snap in snapshots[-49:-1]:
        try:
            instant = datetime.fromisoformat(str(snap.get("at", "")))
            timestamp = instant.timestamp() if instant.tzinfo is not None else None
        except (ValueError, TypeError, OverflowError):
            timestamp = None
        if timestamp is None:
            continue
        hosts = set(snap.get("hosts", []))
        for item in snap.get("containers", [])[:1500]:
            host = str(item.get("host", ""))
            ident = str(item.get("container_id", ""))
            if host not in hosts or not ident:
                continue
            for metric in ("cpu_percent", "memory_mb"):
                value = _sample(item.get(metric))
                if value is not None:
                    previous[(host, ident)][metric].append((timestamp, value))

    last = snapshots[-1]
    try:
        instant = datetime.fromisoformat(str(last.get("at", "")))
        now = instant.timestamp() if instant.tzinfo is not None else None
    except (ValueError, TypeError, OverflowError):
        now = None
    if now is None:
        return []
    hosts = set(last.get("hosts", []))
    results = []
    for item in last.get("containers", [])[:1500]:
        host = str(item.get("host", ""))
        ident = str(item.get("container_id", ""))
        if host not in hosts or not ident or str(item.get("severity", "unknown")) == "unknown":
            continue
        for metric, absolute_delta in (
            ("cpu_percent", settings["anomaly_cpu_min_rise_percent"]),
            ("memory_mb", settings["anomaly_memory_min_rise_mb"]),
        ):
            current = _sample(item.get(metric))
            samples = previous.get((host, ident), {}).get(metric, [])
            valid = [(t, v) for t, v in samples if 0 < now - t <= 86400]
            if current is None or len(valid) < settings["anomaly_min_samples"]:
                continue
            # Require enough elapsed evidence and a recent preceding measurement.
            if (valid[-1][0] - valid[0][0] < settings["anomaly_min_span_seconds"]
                    or now - valid[-1][0] > settings["anomaly_max_sample_age_seconds"]):
                continue
            gaps = [valid[i][0] - valid[i - 1][0] for i in range(1, len(valid))]
            if any(g <= 0 for g in gaps) or max(gaps) > max(900, statistics.median(gaps) * 4):
                continue
            baseline = statistics.median(v for _, v in valid)
            mad = statistics.median(abs(v - baseline) for _, v in valid)
            required = max(absolute_delta, 0.7 * baseline, 4 * mad)
            if current <= baseline + required:
                continue
            results.append({
                "host": host[:120], "name": str(item.get("name", ident))[:120],
                "metric": metric, "current": round(current, 1),
                "baseline": round(baseline, 1), "samples": len(valid),
                "assessment": "unusual_positive_deviation_not_causal_proof",
            })
            if len(results) >= max(0, min(limit, 12)):
                return results
    return results


def render_anomalies(snapshots: list[dict], rules: dict | None = None) -> str:
    settings = anomaly_rules(rules)
    if not snapshots:
        return ""
    rows = resource_anomalies(snapshots, rules=settings)
    if not rows:
        count = len(snapshots)
        return ('<section class="pulse-anomalies" aria-label="Resource deviation evidence">'
                '<div class="table-title"><h2>' +
                l10n_text("Resource deviation evidence", "Ressourcenabweichungen und Nachweisqualität") +
                '</h2></div><p>' + (
                    l10n_text(
                        f"Only {count} saved observations; at least {settings['anomaly_min_samples']} valid historical samples "
                        "plus a recent current sample are needed. No resource verdict.",
                        f"Nur {count} gespeicherte Beobachtungen; mindestens {settings['anomaly_min_samples']} gültige "
                        "historische Messungen plus eine aktuelle Messung sind erforderlich. Kein Ressourcenurteil."
                    ) if count < settings["anomaly_min_samples"] + 2 else l10n_text(
                        "No positive deviation passed every evidence gate. This does not prove healthy resources; "
                        "samples may be missing, stale or too sparse.",
                        "Keine positive Abweichung erfüllt alle Nachweiskriterien. Das beweist keine gesunden Ressourcen; "
                        "Messungen können fehlen, veraltet oder zu dünn sein."
                    )) + '</p></section>')
    out = []
    for item in rows:
        unit = "%" if item["metric"] == "cpu_percent" else "MiB"
        out.append("<tr><td>" + html.escape(item["host"]) + " / " +
                   html.escape(item["name"]) + "</td><td>" + html.escape(item["metric"]) +
                   "</td><td>" + str(item["current"]) + " " + unit +
                   "</td><td>" + str(item["baseline"]) + " " + unit +
                   "</td><td>" + str(item["samples"]) + "</td></tr>")
    return ('<section class="pulse-anomalies" aria-label="Resource deviations">'
            '<div class="table-title"><h2>' +
            l10n_text("Unusual resource deviations", "Ungewöhnliche Ressourcenabweichungen") +
            '</h2><span>' +
            l10n_text("Historical comparison only; no outage, leak, or cause proven.",
                      "Nur historischer Vergleich; kein Ausfall, Leak oder Ursache nachgewiesen.") +
            '</span></div><div class="table-shell"><table><thead><tr><th>Host / Container</th>'
            '<th>Metric</th><th>Current</th><th>Baseline</th><th>Samples</th>'
            '</tr></thead><tbody>' + "".join(out) + '</tbody></table></div></section>')
