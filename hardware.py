import html
import json
import os
import platform
import shutil
import socket
import time
from datetime import datetime
from pathlib import Path

from hardware_sensors import DEFAULT_SENSOR_CONFIG, HardwareSensor, collect_hardware_sensors

DEFAULT_HARDWARE_CONFIG = {
    "refresh_seconds": 60,
    "hardware_cpu_warn_percent": 70.0,
    "hardware_cpu_critical_percent": 90.0,
    "hardware_memory_warn_percent": 80.0,
    "hardware_memory_critical_percent": 90.0,
    "hardware_swap_warn_percent": 30.0,
    "hardware_swap_critical_percent": 60.0,
    "hardware_disk_warn_percent": 80.0,
    "hardware_disk_critical_percent": 90.0,
    "hardware_inode_warn_percent": 80.0,
    "hardware_inode_critical_percent": 90.0,
    "hardware_uptime_warn_days": 30.0,
    "hardware_uptime_critical_days": 60.0,
    **DEFAULT_SENSOR_CONFIG,
}

SEVERITY_RANK = {"ok": 0, "unknown": 1, "warn": 2, "critical": 3}


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _read_last_success(state_path):
    path = Path(state_path)
    if not path.exists():
        return "never"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return "never"
    if isinstance(data, dict):
        return str(data.get("last_success_at") or "never")
    return "never"


def _write_last_success(state_path, value):
    Path(state_path).write_text(json.dumps({"last_success_at": value}, indent=2), encoding="utf-8")


def _load_config(config_path):
    config = dict(DEFAULT_HARDWARE_CONFIG)
    if not config_path:
        return config
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    try:
        import yaml
    except Exception as exc:
        raise RuntimeError("PyYAML is required for config files.") from exc
    loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(loaded, dict):
        raise ValueError("Config file must contain a mapping.")
    for key, value in loaded.items():
        if key in config:
            config[key] = value
    return config


def _read_cpu_times():
    path = Path("/proc/stat")
    if not path.exists():
        return None
    try:
        first_line = path.read_text(encoding="utf-8", errors="ignore").splitlines()[0]
        parts = first_line.split()
        if not parts or parts[0] != "cpu":
            return None
        values = [int(item) for item in parts[1:]]
        idle = values[3] + (values[4] if len(values) > 4 else 0)
        total = sum(values)
        return idle, total
    except Exception:
        return None


def _collect_cpu_percent():
    first = _read_cpu_times()
    if first is None:
        return None
    time.sleep(0.08)
    second = _read_cpu_times()
    if second is None:
        return None
    idle_delta = second[0] - first[0]
    total_delta = second[1] - first[1]
    if total_delta <= 0:
        return None
    return max(0.0, min(100.0, 100.0 * (1.0 - idle_delta / total_delta)))


def _read_meminfo():
    path = Path("/proc/meminfo")
    if not path.exists():
        return {}
    data = {}
    try:
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            if ":" not in line:
                continue
            key, raw_value = line.split(":", 1)
            parts = raw_value.strip().split()
            if parts:
                data[key] = int(parts[0]) * 1024
    except Exception:
        return {}
    return data


def _collect_memory(meminfo):
    total = meminfo.get("MemTotal")
    available = meminfo.get("MemAvailable")
    if total and available is not None and total > 0:
        used = max(0, total - available)
        return used, total, used / total * 100.0
    return None, None, None


def _collect_swap(meminfo):
    total = meminfo.get("SwapTotal")
    free = meminfo.get("SwapFree")
    if total is None or free is None or total <= 0:
        return None, total or 0, None
    used = max(0, total - free)
    return used, total, used / total * 100.0


def _collect_disk(path="/"):
    try:
        usage = shutil.disk_usage(path)
    except Exception:
        return None, None, None
    if usage.total <= 0:
        return usage.used, usage.total, None
    return usage.used, usage.total, usage.used / usage.total * 100.0


def _collect_inode_usage(path="/"):
    try:
        stats = os.statvfs(path)
    except Exception:
        return None, None, None
    total = stats.f_files
    free = stats.f_ffree
    if total <= 0:
        return None, None, None
    used = max(0, total - free)
    return used, total, used / total * 100.0


def _collect_uptime_seconds():
    path = Path("/proc/uptime")
    if not path.exists():
        return None
    try:
        return float(path.read_text(encoding="utf-8", errors="ignore").split()[0])
    except Exception:
        return None


def _collect_load_average():
    try:
        return os.getloadavg()
    except Exception:
        return None


def _bytes_to_gib(value):
    if value is None:
        return "-"
    return f"{value / (1024 ** 3):.1f} GiB"


def _format_count(value):
    if value is None:
        return "-"
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"{value / 1_000:.1f}K"
    return str(value)


def _format_percent(value):
    if value is None:
        return "-"
    return f"{value:.1f}%"


def _format_uptime(seconds):
    if seconds is None:
        return "-"
    total = int(seconds)
    days, rem = divmod(total, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, _ = divmod(rem, 60)
    if days:
        return f"{days}d {hours:02d}h"
    if hours:
        return f"{hours}h {minutes:02d}m"
    return f"{minutes}m"


def _level_percent(value, warn, critical):
    if value is None:
        return "unknown"
    if value >= float(critical):
        return "critical"
    if value >= float(warn):
        return "warn"
    return "ok"


def _level_uptime(seconds, warn_days, critical_days):
    if seconds is None:
        return "unknown"
    days = seconds / 86400.0
    if days >= float(critical_days):
        return "critical"
    if days >= float(warn_days):
        return "warn"
    return "ok"


def _overall(levels):
    return max(levels or ["unknown"], key=lambda item: SEVERITY_RANK.get(item, 0))


def _metric_bar(label, value_text, percent, level):
    width = "0%" if percent is None else f"{max(0.0, min(float(percent), 100.0)):.1f}%"
    return (
        f"<div class='metric-row metric-{html.escape(level)}'>"
        f"<span class='metric-label'>{html.escape(label)}</span>"
        f"<span class='metric-value'>{html.escape(value_text)}</span>"
        f"<span class='metric-track'><span class='metric-fill' style='width:{width}'></span></span>"
        "</div>"
    )


def _summary_card(css_class, label, value, state):
    return (
        f"<div class='card {html.escape(css_class)}'>"
        f"<span>{html.escape(label)}</span>"
        f"<strong>{html.escape(value)}</strong>"
        f"<small class='state state-{html.escape(state)}'>{html.escape(state.upper())}</small>"
        "</div>"
    )


def _sensor_row(name, value, state, note):
    return (
        "<tr>"
        f"<td>{html.escape(name)}</td>"
        f"<td><code>{html.escape(value)}</code></td>"
        f"<td><span class='sev-badge sev-{html.escape(state)}'>{html.escape(state.upper())}</span></td>"
        f"<td>{html.escape(note)}</td>"
        "</tr>"
    )


def _short_source(source: str) -> str:
    if source.startswith("/sys/class/"):
        return source.removeprefix("/sys/class/")
    return source


def _sensor_to_row(sensor: HardwareSensor):
    note = f"{sensor.note} Source: {_short_source(sensor.source)}."
    name = f"{sensor.name} ({sensor.category})"
    return _sensor_row(name, sensor.value, sensor.state, note)


def _sensor_summary(sensors: list[HardwareSensor]) -> str:
    counts = {"ok": 0, "warn": 0, "critical": 0, "unknown": 0}
    categories: dict[str, int] = {}
    for sensor in sensors:
        counts[sensor.state] = counts.get(sensor.state, 0) + 1
        categories[sensor.category] = categories.get(sensor.category, 0) + 1

    category_text = ", ".join(f"{name}: {count}" for name, count in sorted(categories.items())) or "none"
    return (
        '<div class="messages" aria-label="Sensor summary">'
        f"<p><strong>Sensor summary</strong>: {len(sensors)} found · "
        f"OK {counts.get('ok', 0)} · WARN {counts.get('warn', 0)} · "
        f"CRITICAL {counts.get('critical', 0)} · UNKNOWN {counts.get('unknown', 0)}</p>"
        f"<p>Categories: {html.escape(category_text)}</p>"
        "</div>"
    )


def _recommendation(overall):
    if overall == "critical":
        return "Immediate inspection recommended. Check CPU pressure, memory pressure, disk usage, inode usage, sensors, and host stability."
    if overall == "warn":
        return "Review host pressure and sensor warnings. Plan maintenance if the warning persists. No automatic action is executed."
    if overall == "unknown":
        return "Some host signals are unavailable on this platform. Review unavailable rows if needed."
    return "No action needed. Basic host and sensor signals look healthy."


def _optional_sensor_notice():
    return """
      <section class="health-panel" aria-label="Optional sensors">
        <div class="health-head">
          <h2 data-i18n="sensorOverview">Optional Sensors</h2>
          <span class="pill" data-i18n="optionalLater">Optional deep-dive later</span>
        </div>
        <p class="recommendation"><strong>Sensor status</strong>: No live sensor values were exposed by this host during this run, or sensor collection is disabled.</p>
        <p class="recommendation">Hardware Pulse can render generic sensor rows for temperature, fan RPM, GPU, VRAM, and future sensor adapters when values are available.</p>
      </section>
""".rstrip()


def _replace_empty_sensor_section(html_text, sensor_rows):
    if sensor_rows:
        return html_text

    start_marker = '      <section class="health-panel" aria-label="Optional sensors">'
    end_marker = '      <p class="footer-note"'
    start = html_text.find(start_marker)
    end = html_text.find(end_marker, start)
    if start == -1 or end == -1:
        return html_text

    return html_text[:start] + _optional_sensor_notice() + "\n\n" + html_text[end:]


def _insert_sensor_summary(html_text, sensor_rows, sensor_summary):
    if not sensor_rows or not sensor_summary:
        return html_text
    marker = '        <section class="table-shell" aria-label="Sensor details">'
    if marker not in html_text:
        return html_text
    return html_text.replace(marker, f"        {sensor_summary}\n{marker}", 1)


def _collect_sensor_rows(config):
    try:
        sensors = collect_hardware_sensors(config)
    except Exception:
        return [], [], ""
    rows = [_sensor_to_row(sensor) for sensor in sensors]
    levels = [sensor.state for sensor in sensors]
    summary = _sensor_summary(sensors) if sensors else ""
    return rows, levels, summary


def _collect_snapshot(config):
    cpu_percent = _collect_cpu_percent()
    meminfo = _read_meminfo()
    mem_used, mem_total, mem_percent = _collect_memory(meminfo)
    swap_used, swap_total, swap_percent = _collect_swap(meminfo)
    disk_used, disk_total, disk_percent = _collect_disk("/")
    inode_used, inode_total, inode_percent = _collect_inode_usage("/")
    uptime_seconds = _collect_uptime_seconds()
    load_average = _collect_load_average()
    sensor_rows, sensor_levels, sensor_summary = _collect_sensor_rows(config)

    load_text = "-"
    load_percent = None
    load_level = "unknown"
    cpu_count = os.cpu_count() or 1
    if load_average:
        load_text = f"{load_average[0]:.2f} / {load_average[1]:.2f} / {load_average[2]:.2f}"
        load_percent = min(100.0, load_average[0] / cpu_count * 100.0)
        load_level = _level_percent(load_percent, 70, 90)

    levels = {
        "cpu": _level_percent(cpu_percent, config["hardware_cpu_warn_percent"], config["hardware_cpu_critical_percent"]),
        "memory": _level_percent(mem_percent, config["hardware_memory_warn_percent"], config["hardware_memory_critical_percent"]),
        "swap": _level_percent(swap_percent, config["hardware_swap_warn_percent"], config["hardware_swap_critical_percent"]),
        "disk": _level_percent(disk_percent, config["hardware_disk_warn_percent"], config["hardware_disk_critical_percent"]),
        "inodes": _level_percent(inode_percent, config["hardware_inode_warn_percent"], config["hardware_inode_critical_percent"]),
        "uptime": _level_uptime(uptime_seconds, config["hardware_uptime_warn_days"], config["hardware_uptime_critical_days"]),
        "load": load_level,
    }
    overall = _overall([*levels.values(), *sensor_levels])

    return {
        "hostname": socket.gethostname(),
        "platform": f"{platform.system()} {platform.release()} / {platform.machine()}",
        "overall": overall,
        "recommendation": _recommendation(overall),
        "summary_cards": [
            _summary_card("card-cpu", "CPU", _format_percent(cpu_percent), levels["cpu"]),
            _summary_card("card-ram", "RAM", _format_percent(mem_percent), levels["memory"]),
            _summary_card("card-swap", "SWAP", _format_percent(swap_percent), levels["swap"]),
            _summary_card("card-disk", "DISK", _format_percent(disk_percent), levels["disk"]),
            _summary_card("card-uptime", "UPTIME", _format_uptime(uptime_seconds), levels["uptime"]),
        ],
        "metrics": [
            _metric_bar("CPU Usage", _format_percent(cpu_percent), cpu_percent, levels["cpu"]),
            _metric_bar("Load Average", f"{load_text} / {cpu_count} cores", load_percent, levels["load"]),
            _metric_bar("Memory", f"{_format_percent(mem_percent)} / {_bytes_to_gib(mem_total)}", mem_percent, levels["memory"]),
            _metric_bar("Swap", f"{_format_percent(swap_percent)} / {_bytes_to_gib(swap_total)}", swap_percent, levels["swap"]),
            _metric_bar("Root Disk", f"{_format_percent(disk_percent)} / {_bytes_to_gib(disk_total)}", disk_percent, levels["disk"]),
            _metric_bar("Root Inodes", f"{_format_percent(inode_percent)} / {_format_count(inode_used)} used", inode_percent, levels["inodes"]),
            _metric_bar("Uptime", _format_uptime(uptime_seconds), None, levels["uptime"]),
        ],
        "sensors": sensor_rows,
        "sensor_summary": sensor_summary,
    }


def _render_html(template_path, output_path, generated_at, previous_last_success, refresh_seconds, snapshot, messages):
    template = Path(template_path).read_text(encoding="utf-8")
    sensor_rows = snapshot.get("sensors", [])
    sensor_summary = snapshot.get("sensor_summary", "")
    replacements = {
        "{{TITLE}}": "HARDWARE PULSE",
        "{{REFRESH_SECONDS}}": str(int(refresh_seconds)),
        "{{GENERATED_AT}}": html.escape(generated_at),
        "{{LAST_SUCCESS_AT}}": html.escape(previous_last_success),
        "{{HOSTNAME}}": html.escape(snapshot.get("hostname", "unknown")),
        "{{PLATFORM}}": html.escape(snapshot.get("platform", "unknown")),
        "{{OVERALL}}": html.escape(str(snapshot.get("overall", "unknown")).upper()),
        "{{OVERALL_CLASS}}": html.escape(str(snapshot.get("overall", "unknown"))),
        "{{RECOMMENDATION}}": html.escape(snapshot.get("recommendation", "No recommendation available.")),
        "{{SUMMARY_CARDS}}": "\n".join(snapshot.get("summary_cards", [])),
        "{{METRIC_ROWS}}": "\n".join(snapshot.get("metrics", [])),
        "{{SENSOR_ROWS}}": "\n".join(sensor_rows),
        "{{MESSAGES}}": "".join(f"<p>{html.escape(item)}</p>" for item in messages) or "<p>No hardware refresh warnings.</p>",
    }
    html_text = template
    for key, value in replacements.items():
        html_text = html_text.replace(key, value)
    html_text = _insert_sensor_summary(html_text, sensor_rows, sensor_summary)
    html_text = _replace_empty_sensor_section(html_text, sensor_rows)
    Path(output_path).write_text(html_text, encoding="utf-8")


def generate_hardware_pulse(
    output_path="hardware.html",
    template_path="hardware_template.html",
    config_path=None,
    state_path=".hardware_pulse_state.json",
):
    generated_at = _now()
    previous_last_success = _read_last_success(state_path)
    config = dict(DEFAULT_HARDWARE_CONFIG)
    try:
        config = _load_config(config_path)
        snapshot = _collect_snapshot(config)
        _render_html(
            template_path=template_path,
            output_path=output_path,
            generated_at=generated_at,
            previous_last_success=previous_last_success,
            refresh_seconds=config.get("refresh_seconds", 60),
            snapshot=snapshot,
            messages=[],
        )
        _write_last_success(state_path, generated_at)
        return True
    except Exception as exc:
        snapshot = {
            "hostname": socket.gethostname(),
            "platform": f"{platform.system()} {platform.release()} / {platform.machine()}",
            "overall": "unknown",
            "recommendation": "Hardware Pulse could not refresh completely. Review the warning message.",
            "summary_cards": [
                _summary_card("card-cpu", "CPU", "-", "unknown"),
                _summary_card("card-ram", "RAM", "-", "unknown"),
                _summary_card("card-swap", "SWAP", "-", "unknown"),
                _summary_card("card-disk", "DISK", "-", "unknown"),
                _summary_card("card-uptime", "UPTIME", "-", "unknown"),
            ],
            "metrics": [],
            "sensors": [],
            "sensor_summary": "",
        }
        _render_html(
            template_path=template_path,
            output_path=output_path,
            generated_at=generated_at,
            previous_last_success=previous_last_success,
            refresh_seconds=config.get("refresh_seconds", 60),
            snapshot=snapshot,
            messages=[f"Hardware refresh failed: {exc}"],
        )
        return False
