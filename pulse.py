import html
import json
import shutil
import socket
import subprocess
from datetime import datetime
from pathlib import Path

DEFAULT_CONFIG = {
    "refresh_seconds": 60,
    "cpu_warn_percent": 50.0,
    "memory_warn_mb": 1024.0,
    "docker_timeout_seconds": 8,
    "container_overrides": {},
}


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _run(command, timeout=8):
    return subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)


def _json_lines(text):
    rows = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def _state(status: str) -> str:
    lowered = (status or "").lower()
    if lowered.startswith("up"):
        return "running"
    if "restarting" in lowered:
        return "restarting"
    if "paused" in lowered:
        return "paused"
    if "dead" in lowered:
        return "dead"
    if "exited" in lowered:
        return "exited"
    return "unknown"


def _percent(value: str):
    value = (value or "").replace("%", "").strip()
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _load_config(config_path):
    config = dict(DEFAULT_CONFIG)
    config["container_overrides"] = {}
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
        config[key] = value
    if not isinstance(config.get("container_overrides"), dict):
        config["container_overrides"] = {}
    return config


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


def _parse_mem_used_mb(mem_usage: str):
    left = (mem_usage or "").split("/", 1)[0].strip().lower().replace(" ", "")
    if not left:
        return None
    number = ""
    unit = ""
    for char in left:
        if char.isdigit() or char == ".":
            number += char
        else:
            unit += char
    if not number:
        return None
    value = float(number)
    if unit in ("b", ""):
        return value / (1024 * 1024)
    if unit == "kib":
        return value / 1024
    if unit == "mib":
        return value
    if unit == "gib":
        return value * 1024
    if unit == "tib":
        return value * 1024 * 1024
    if unit == "kb":
        return value / 1000
    if unit == "mb":
        return value
    if unit == "gb":
        return value * 1000
    if unit == "tb":
        return value * 1000 * 1000
    return None


def generate_pulse(output_path="pulse.html", template_path="template.html", config_path=None, state_path=".pulse_state.json"):
    config = _load_config(config_path)
    docker = shutil.which("docker")
    previous_last_success = _read_last_success(state_path)
    generated_at = _now()

    if not docker:
        raise FileNotFoundError("Docker CLI not found in PATH.")

    messages = []
    timeout_seconds = float(config.get("docker_timeout_seconds", 8))
    ps = _run([docker, "ps", "-a", "--format", "{{json .}}"], timeout=timeout_seconds)
    if ps.returncode != 0:
        raise RuntimeError(ps.stderr.strip() or "docker ps failed")

    stats_lookup = {}
    try:
        stats = _run([docker, "stats", "--no-stream", "--format", "{{json .}}"], timeout=timeout_seconds)
        if stats.returncode == 0:
            for row in _json_lines(stats.stdout):
                name = row.get("Name") or row.get("Container")
                if name:
                    stats_lookup[name] = row
        else:
            messages.append(f"Live stats unavailable: {stats.stderr.strip() or 'unknown error'}")
    except Exception:
        messages.append("Live stats unavailable.")

    rows_html = []
    total = running = warn = critical = unknown = 0
    default_cpu_warn = float(config.get("cpu_warn_percent", 50.0))
    default_memory_warn = float(config.get("memory_warn_mb", 1024.0))
    overrides = config.get("container_overrides", {}) or {}

    for row in _json_lines(ps.stdout):
        total += 1
        name = str(row.get("Names") or row.get("Name") or "unknown")
        image = str(row.get("Image") or "-")
        status = str(row.get("Status") or "-")
        running_for = str(row.get("RunningFor") or "-")
        state = _state(status)
        if state == "running":
            running += 1

        container_override = overrides.get(name, {}) if isinstance(overrides, dict) else {}
        cpu_warn = float(container_override.get("cpu_warn_percent", default_cpu_warn))
        memory_warn = float(container_override.get("memory_warn_mb", default_memory_warn))

        stats_row = stats_lookup.get(name, {})
        cpu_value = _percent(str(stats_row.get("CPUPerc", "")))
        mem_perc = str(stats_row.get("MemPerc", "-") or "-")
        mem_usage = str(stats_row.get("MemUsage", "-") or "-")
        mem_used_mb = _parse_mem_used_mb(mem_usage)
        cpu_text = "-" if cpu_value is None else f"{cpu_value:.1f}%"

        severity = "ok"
        note = "-"
        if state != "running":
            severity = "critical"
            critical += 1
            note = f"state is {state}"
        elif not stats_row:
            severity = "unknown"
            unknown += 1
            note = "no live stats"
        else:
            reasons = []
            if cpu_value is not None and cpu_value > cpu_warn:
                reasons.append(f"cpu>{cpu_warn:g}%")
            if mem_used_mb is not None and mem_used_mb > memory_warn:
                reasons.append(f"memory>{memory_warn:g}MB")
            if reasons:
                severity = "warn"
                warn += 1
                note = "; ".join(reasons)

        rows_html.append(
            "<tr>"
            f"<td><code>{html.escape(name)}</code></td>"
            f"<td class='sev-{severity}'>{html.escape(severity.upper())}</td>"
            f"<td>{html.escape(status)}</td>"
            f"<td>{html.escape(state)}</td>"
            f"<td>{html.escape(cpu_text)}</td>"
            f"<td>{html.escape(mem_usage)}</td>"
            f"<td>{html.escape(mem_perc)}</td>"
            f"<td><code>{html.escape(image)}</code></td>"
            f"<td>{html.escape(running_for)}</td>"
            f"<td>{html.escape(note)}</td>"
            "</tr>"
        )

    template = Path(template_path).read_text(encoding="utf-8")
    html_text = template
    html_text = html_text.replace("{{TITLE}}", "CONTAINER PULSE")
    html_text = html_text.replace("{{HOSTNAME}}", html.escape(socket.gethostname()))
    html_text = html_text.replace("{{GENERATED_AT}}", html.escape(generated_at))
    html_text = html_text.replace("{{LAST_SUCCESS_AT}}", html.escape(previous_last_success))
    html_text = html_text.replace("{{REFRESH_SECONDS}}", str(int(config.get("refresh_seconds", 60))))
    html_text = html_text.replace("{{SUMMARY}}", html.escape(f"Total: {total} · Running: {running} · Warn: {warn} · Critical: {critical} · Unknown: {unknown}"))
    html_text = html_text.replace("{{MESSAGES}}", "".join(f"<p>{html.escape(item)}</p>" for item in messages) or "<p>No refresh warnings.</p>")
    html_text = html_text.replace("{{ROWS}}", "\n".join(rows_html))
    Path(output_path).write_text(html_text, encoding="utf-8")
    _write_last_success(state_path, generated_at)
