import html
import json
import os
import shutil
import socket
import time
from datetime import datetime
from pathlib import Path

from hardware import generate_hardware_pulse as generate_linux_hardware_pulse
from i18n_static import l10n_text
from platform_support import bytes_to_gib, list_windows_drives, os_family, percent, platform_label, run_command, run_powershell

DEFAULT_HARDWARE_XPLAT_CONFIG = {
    "refresh_seconds": 60,
    "hardware_cpu_warn_percent": 70.0,
    "hardware_cpu_critical_percent": 90.0,
    "hardware_memory_warn_percent": 80.0,
    "hardware_memory_critical_percent": 90.0,
    "hardware_swap_warn_percent": 30.0,
    "hardware_swap_critical_percent": 60.0,
    "hardware_disk_warn_percent": 80.0,
    "hardware_disk_critical_percent": 90.0,
    "hardware_uptime_warn_days": 30.0,
    "hardware_uptime_critical_days": 60.0,
}

SEVERITY_RANK = {"ok": 0, "unknown": 1, "warn": 2, "critical": 3}


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _read_last_success(state_path):
    path = Path(state_path)
    if not path.exists():
        return "never"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return str(data.get("last_success_at") or "never") if isinstance(data, dict) else "never"
    except Exception:
        return "never"


def _write_last_success(state_path, value):
    Path(state_path).write_text(json.dumps({"last_success_at": value}, indent=2), encoding="utf-8")


def _load_config(config_path):
    config = dict(DEFAULT_HARDWARE_XPLAT_CONFIG)
    if not config_path:
        return config
    path = Path(config_path)
    if not path.exists():
        return config
    try:
        import yaml
        loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return config
    if isinstance(loaded, dict):
        for key, value in loaded.items():
            if key in config:
                config[key] = value
    return config


def _level(value, warn, critical):
    if value is None:
        return "unknown"
    if float(value) >= float(critical):
        return "critical"
    if float(value) >= float(warn):
        return "warn"
    return "ok"


def _overall(levels):
    return max(levels or ["unknown"], key=lambda item: SEVERITY_RANK.get(item, 0))


def _format_percent(value):
    return "-" if value is None else f"{float(value):.1f}%"


def _format_uptime(seconds):
    if seconds is None:
        return "-"
    total = int(max(0, seconds))
    days, rem = divmod(total, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, _ = divmod(rem, 60)
    if days:
        return f"{days}d {hours:02d}h"
    if hours:
        return f"{hours}h {minutes:02d}m"
    return f"{minutes}m"


def _card(css_class, label_en, label_de, value, state):
    return f"<div class='card {html.escape(css_class)}'><span>{l10n_text(label_en, label_de)}</span><strong>{html.escape(str(value))}</strong><small class='state state-{html.escape(state)}'>{html.escape(state.upper())}</small></div>"


def _metric_bar(label_html, value_text, percent_value, level):
    width = "0%" if percent_value is None else f"{max(0.0, min(float(percent_value), 100.0)):.1f}%"
    return f"<div class='metric-row metric-{html.escape(level)}'><span class='metric-label'>{label_html}</span><span class='metric-value'>{html.escape(value_text)}</span><span class='metric-track'><span class='metric-fill' style='width:{width}'></span></span></div>"


def _collect_with_psutil():
    try:
        import psutil
    except Exception:
        return None
    try:
        cpu_percent = psutil.cpu_percent(interval=0.08)
        memory = psutil.virtual_memory()
        swap = psutil.swap_memory()
        disk = psutil.disk_usage(str(Path.home().anchor or "/"))
        boot_time = psutil.boot_time()
        return {
            "cpu_percent": cpu_percent,
            "memory_percent": memory.percent,
            "memory_total": memory.total,
            "swap_percent": swap.percent if swap.total else None,
            "swap_total": swap.total,
            "disk_percent": disk.percent,
            "disk_total": disk.total,
            "uptime_seconds": max(0.0, time.time() - boot_time),
            "load_text": " / ".join(f"{item:.2f}" for item in os.getloadavg()) if hasattr(os, "getloadavg") else "-",
            "load_percent": None,
        }
    except Exception:
        return None


def _collect_macos_fallback():
    disk_total = disk_used = None
    try:
        usage = shutil.disk_usage("/")
        disk_total = usage.total
        disk_used = usage.used
    except Exception:
        pass
    memory_total = None
    result = run_command(["sysctl", "-n", "hw.memsize"], timeout=1.5)
    if result.code == 0:
        try:
            memory_total = int(result.stdout.strip())
        except Exception:
            memory_total = None
    uptime_seconds = None
    boot = run_command(["sysctl", "-n", "kern.boottime"], timeout=1.5)
    if boot.code == 0 and "sec =" in boot.stdout:
        try:
            sec = int(boot.stdout.split("sec =", 1)[1].split(",", 1)[0].strip())
            uptime_seconds = max(0, time.time() - sec)
        except Exception:
            pass
    load = None
    try:
        load = os.getloadavg()
    except Exception:
        pass
    return {
        "cpu_percent": None,
        "memory_percent": None,
        "memory_total": memory_total,
        "swap_percent": None,
        "swap_total": None,
        "disk_percent": percent(disk_used, disk_total),
        "disk_total": disk_total,
        "uptime_seconds": uptime_seconds,
        "load_text": " / ".join(f"{item:.2f}" for item in load) if load else "-",
        "load_percent": None,
    }


def _collect_windows_fallback():
    disk_total = disk_used = None
    drives = list_windows_drives()
    root = drives[0] if drives else "C:\\"
    try:
        usage = shutil.disk_usage(root)
        disk_total = usage.total
        disk_used = usage.used
    except Exception:
        pass
    memory_total = memory_free = None
    ps = run_powershell("$m=Get-CimInstance Win32_OperatingSystem; [string]::Join(',', @($m.TotalVisibleMemorySize,$m.FreePhysicalMemory,(Get-Date $m.LastBootUpTime -UFormat %s)))", timeout=3)
    uptime_seconds = None
    if ps.code == 0 and ps.stdout:
        parts = [item.strip() for item in ps.stdout.split(",")]
        if len(parts) >= 2:
            try:
                memory_total = int(parts[0]) * 1024
                memory_free = int(parts[1]) * 1024
            except Exception:
                pass
    memory_used = None if memory_total is None or memory_free is None else max(0, memory_total - memory_free)
    return {
        "cpu_percent": None,
        "memory_percent": percent(memory_used, memory_total),
        "memory_total": memory_total,
        "swap_percent": None,
        "swap_total": None,
        "disk_percent": percent(disk_used, disk_total),
        "disk_total": disk_total,
        "uptime_seconds": uptime_seconds,
        "load_text": "not available on Windows",
        "load_percent": None,
    }


def _collect_snapshot(config):
    family = os_family()
    data = _collect_with_psutil()
    if data is None:
        data = _collect_macos_fallback() if family == "macos" else _collect_windows_fallback() if family == "windows" else {}

    cpu_level = _level(data.get("cpu_percent"), config["hardware_cpu_warn_percent"], config["hardware_cpu_critical_percent"])
    memory_level = _level(data.get("memory_percent"), config["hardware_memory_warn_percent"], config["hardware_memory_critical_percent"])
    swap_level = _level(data.get("swap_percent"), config["hardware_swap_warn_percent"], config["hardware_swap_critical_percent"])
    disk_level = _level(data.get("disk_percent"), config["hardware_disk_warn_percent"], config["hardware_disk_critical_percent"])
    uptime_level = "ok" if data.get("uptime_seconds") is not None else "unknown"
    overall = _overall([cpu_level, memory_level, swap_level, disk_level, uptime_level])

    cards = [
        _card("card-cpu", "CPU", "CPU", _format_percent(data.get("cpu_percent")), cpu_level),
        _card("card-ram", "RAM", "RAM", _format_percent(data.get("memory_percent")), memory_level),
        _card("card-swap", "SWAP", "SWAP", _format_percent(data.get("swap_percent")), swap_level),
        _card("card-disk", "DISK", "PLATTE", _format_percent(data.get("disk_percent")), disk_level),
        _card("card-uptime", "UPTIME", "LAUFZEIT", _format_uptime(data.get("uptime_seconds")), uptime_level),
    ]
    metrics = [
        _metric_bar(l10n_text("CPU Usage", "CPU-Auslastung"), _format_percent(data.get("cpu_percent")), data.get("cpu_percent"), cpu_level),
        _metric_bar(l10n_text("Load Average", "Systemlast"), str(data.get("load_text") or "-"), data.get("load_percent"), "unknown" if data.get("load_percent") is None else "ok"),
        _metric_bar(l10n_text("Memory", "Arbeitsspeicher"), f"{_format_percent(data.get('memory_percent'))} / {bytes_to_gib(data.get('memory_total'))}", data.get("memory_percent"), memory_level),
        _metric_bar(l10n_text("Swap", "Swap"), f"{_format_percent(data.get('swap_percent'))} / {bytes_to_gib(data.get('swap_total'))}", data.get("swap_percent"), swap_level),
        _metric_bar(l10n_text("Root Disk", "Root-Platte"), f"{_format_percent(data.get('disk_percent'))} / {bytes_to_gib(data.get('disk_total'))}", data.get("disk_percent"), disk_level),
        _metric_bar(l10n_text("Uptime", "Laufzeit"), _format_uptime(data.get("uptime_seconds")), None, uptime_level),
    ]
    recommendation = l10n_text(
        "Cross-platform hardware signals were collected where this OS exposes them without extra tools. Some values can be unavailable without psutil or platform-specific permissions.",
        "Plattformübergreifende Hardware-Signale wurden gesammelt, soweit dieses OS sie ohne Zusatztools bereitstellt. Einige Werte können ohne psutil oder plattformspezifische Rechte fehlen.",
    )
    return {"overall": overall, "cards": cards, "metrics": metrics, "recommendation": recommendation}


def _optional_sensor_notice():
    return f"""
      <section class="health-panel" aria-label="Optional sensors">
        <div class="health-head"><h2>{l10n_text('Optional Sensors', 'Optionale Sensoren')}</h2><span class="pill">{l10n_text('Platform dependent', 'Plattformabhängig')}</span></div>
        <p class="recommendation">{l10n_text('Live sensors are currently Linux-first. On macOS and Windows, Hardware Pulse shows safe baseline host signals unless optional adapters are added later.', 'Live-Sensoren sind aktuell Linux-first. Auf macOS und Windows zeigt Hardware Pulse sichere Basis-Host-Signale, bis später optionale Adapter ergänzt werden.')}</p>
      </section>
""".rstrip()


def _render(template_path, output_path, generated_at, previous_last_success, refresh_seconds, snapshot):
    template = Path(template_path).read_text(encoding="utf-8")
    replacements = {
        "{{TITLE}}": "HARDWARE PULSE",
        "{{REFRESH_SECONDS}}": str(int(refresh_seconds)),
        "{{GENERATED_AT}}": html.escape(generated_at),
        "{{LAST_SUCCESS_AT}}": html.escape(previous_last_success),
        "{{HOSTNAME}}": html.escape(socket.gethostname()),
        "{{PLATFORM}}": html.escape(platform_label()),
        "{{OVERALL}}": html.escape(snapshot["overall"].upper()),
        "{{OVERALL_CLASS}}": html.escape(snapshot["overall"]),
        "{{RECOMMENDATION}}": snapshot["recommendation"],
        "{{SUMMARY_CARDS}}": "\n".join(snapshot["cards"]),
        "{{METRIC_ROWS}}": "\n".join(snapshot["metrics"]),
        "{{SENSOR_ROWS}}": "",
        "{{MESSAGES}}": f"<p>{l10n_text('No hardware refresh warnings.', 'Keine Hardware-Aktualisierungswarnungen.')}</p>",
    }
    html_text = template
    for key, value in replacements.items():
        html_text = html_text.replace(key, value)
    start_marker = '      <section class="health-panel" aria-label="Optional sensors">'
    end_marker = '      <p class="footer-note"'
    start = html_text.find(start_marker)
    end = html_text.find(end_marker, start)
    if start != -1 and end != -1:
        html_text = html_text[:start] + _optional_sensor_notice() + "\n\n" + html_text[end:]
    Path(output_path).write_text(html_text, encoding="utf-8")


def generate_hardware_pulse(output_path="hardware.html", template_path="hardware_template.html", config_path=None, state_path=".hardware_pulse_state.json"):
    if os_family() == "linux":
        return generate_linux_hardware_pulse(output_path=output_path, template_path=template_path, config_path=config_path, state_path=state_path)
    generated_at = _now()
    previous = _read_last_success(state_path)
    config = _load_config(config_path)
    try:
        snapshot = _collect_snapshot(config)
        _render(template_path, output_path, generated_at, previous, config.get("refresh_seconds", 60), snapshot)
        _write_last_success(state_path, generated_at)
        return True
    except Exception as exc:
        snapshot = {
            "overall": "unknown",
            "cards": [_card("card-total", "Platform", "Plattform", os_family(), "unknown")],
            "metrics": [],
            "recommendation": l10n_text(f"Hardware refresh failed on this platform: {exc}", f"Hardware-Aktualisierung auf dieser Plattform fehlgeschlagen: {exc}"),
        }
        _render(template_path, output_path, generated_at, previous, config.get("refresh_seconds", 60), snapshot)
        return False
