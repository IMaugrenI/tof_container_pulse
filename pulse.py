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
    "hosts": None,
}

SEVERITY_ORDER = {
    "critical": 0,
    "warn": 1,
    "unknown": 2,
    "ok": 3,
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
    hosts = config.get("hosts")
    if hosts is not None and not isinstance(hosts, list):
        raise ValueError("hosts must be a list when provided.")
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


def _render_html(template_path, output_path, generated_at, previous_last_success, refresh_seconds, counts, messages, rows_html):
    template = Path(template_path).read_text(encoding="utf-8")
    html_text = template
    html_text = html_text.replace("{{TITLE}}", "CONTAINER PULSE")
    html_text = html_text.replace("{{GENERATED_AT}}", html.escape(generated_at))
    html_text = html_text.replace("{{LAST_SUCCESS_AT}}", html.escape(previous_last_success))
    html_text = html_text.replace("{{REFRESH_SECONDS}}", str(int(refresh_seconds)))
    html_text = html_text.replace("{{TOTAL}}", str(int(counts.get("total", 0))))
    html_text = html_text.replace("{{RUNNING}}", str(int(counts.get("running", 0))))
    html_text = html_text.replace("{{WARN}}", str(int(counts.get("warn", 0))))
    html_text = html_text.replace("{{CRITICAL}}", str(int(counts.get("critical", 0))))
    html_text = html_text.replace("{{UNKNOWN}}", str(int(counts.get("unknown", 0))))
    html_text = html_text.replace("{{MESSAGES}}", "".join(f"<p>{html.escape(item)}</p>" for item in messages) or "<p>No refresh warnings.</p>")
    html_text = html_text.replace("{{ROWS}}", "\n".join(rows_html))
    Path(output_path).write_text(html_text, encoding="utf-8")


def _normalized_hosts(config):
    hosts = config.get("hosts")
    if hosts:
        normalized = []
        for item in hosts:
            if not isinstance(item, dict):
                continue
            normalized.append(
                {
                    "name": str(item.get("name") or item.get("docker_context") or "unknown-host"),
                    "docker_context": item.get("docker_context"),
                }
            )
        if normalized:
            return normalized
    return [{"name": socket.gethostname(), "docker_context": None}]


def _docker_base_command(docker_cli, docker_context):
    command = [docker_cli]
    if docker_context:
        command.extend(["--context", str(docker_context)])
    return command


def _render_row_html(host_name, name, severity, status, state, cpu_text, mem_usage, mem_perc, image, running_for, note):
    return (
        "<tr>"
        f"<td><code>{html.escape(host_name)}</code></td>"
        f"<td><code>{html.escape(name)}</code></td>"
        f"<td><span class='sev-badge sev-{severity}'>{html.escape(severity.upper())}</span></td>"
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


def _collect_host_rows(host_name, docker_context, docker_cli, config):
    timeout_seconds = float(config.get("docker_timeout_seconds", 8))
    default_cpu_warn = float(config.get("cpu_warn_percent", 50.0))
    default_memory_warn = float(config.get("memory_warn_mb", 1024.0))
    overrides = config.get("container_overrides", {}) or {}

    messages = []
    rendered_rows = []
    counts = {"total": 0, "running": 0, "warn": 0, "critical": 0, "unknown": 0}

    base_cmd = _docker_base_command(docker_cli, docker_context)
    ps = _run(base_cmd + ["ps", "-a", "--format", "{{json .}}"], timeout=timeout_seconds)
    if ps.returncode != 0:
        raise RuntimeError(ps.stderr.strip() or f"docker ps failed for host {host_name}")

    stats_lookup = {}
    try:
        stats = _run(base_cmd + ["stats", "--no-stream", "--format", "{{json .}}"], timeout=timeout_seconds)
        if stats.returncode == 0:
            for row in _json_lines(stats.stdout):
                name = row.get("Name") or row.get("Container")
                if name:
                    stats_lookup[name] = row
        else:
            messages.append(f"Host {host_name}: live stats unavailable: {stats.stderr.strip() or 'unknown error'}")
    except Exception:
        messages.append(f"Host {host_name}: live stats unavailable.")

    for row in _json_lines(ps.stdout):
        counts["total"] += 1
        name = str(row.get("Names") or row.get("Name") or "unknown")
        image = str(row.get("Image") or "-")
        status = str(row.get("Status") or "-")
        running_for = str(row.get("RunningFor") or "-")
        state = _state(status)
        if state == "running":
            counts["running"] += 1

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
            counts["critical"] += 1
            note = f"state is {state}"
        elif not stats_row:
            severity = "unknown"
            counts["unknown"] += 1
            note = "no live stats"
        else:
            reasons = []
            if cpu_value is not None and cpu_value > cpu_warn:
                reasons.append(f"cpu>{cpu_warn:g}%")
            if mem_used_mb is not None and mem_used_mb > memory_warn:
                reasons.append(f"memory>{memory_warn:g}MB")
            if reasons:
                severity = "warn"
                counts["warn"] += 1
                note = "; ".join(reasons)

        rendered_rows.append(
            (
                SEVERITY_ORDER.get(severity, 99),
                host_name.lower(),
                name.lower(),
                _render_row_html(
                    host_name=host_name,
                    name=name,
                    severity=severity,
                    status=status,
                    state=state,
                    cpu_text=cpu_text,
                    mem_usage=mem_usage,
                    mem_perc=mem_perc,
                    image=image,
                    running_for=running_for,
                    note=note,
                ),
            )
        )

    rendered_rows.sort(key=lambda item: (item[0], item[1], item[2]))
    rows_html = [item[3] for item in rendered_rows]
    return rows_html, messages, counts


def generate_pulse(output_path="pulse.html", template_path="template.html", config_path=None, state_path=".pulse_state.json"):
    generated_at = _now()
    previous_last_success = _read_last_success(state_path)
    config = dict(DEFAULT_CONFIG)

    try:
        config = _load_config(config_path)
        docker = shutil.which("docker")
        if not docker:
            raise FileNotFoundError("Docker CLI not found in PATH.")

        messages = []
        rows_html = []
        counts = {"total": 0, "running": 0, "warn": 0, "critical": 0, "unknown": 0}

        for host in _normalized_hosts(config):
            host_name = host["name"]
            docker_context = host.get("docker_context")
            try:
                host_rows, host_messages, host_counts = _collect_host_rows(
                    host_name=host_name,
                    docker_context=docker_context,
                    docker_cli=docker,
                    config=config,
                )
                rows_html.extend(host_rows)
                messages.extend(host_messages)
                counts["total"] += host_counts["total"]
                counts["running"] += host_counts["running"]
                counts["warn"] += host_counts["warn"]
                counts["critical"] += host_counts["critical"]
                counts["unknown"] += host_counts["unknown"]
            except Exception as exc:
                messages.append(f"Host {host_name}: refresh failed: {exc}")

        _render_html(
            template_path=template_path,
            output_path=output_path,
            generated_at=generated_at,
            previous_last_success=previous_last_success,
            refresh_seconds=config.get("refresh_seconds", 60),
            counts=counts,
            messages=messages,
            rows_html=rows_html,
        )
        _write_last_success(state_path, generated_at)
        return True
    except Exception as exc:
        _render_html(
            template_path=template_path,
            output_path=output_path,
            generated_at=generated_at,
            previous_last_success=previous_last_success,
            refresh_seconds=config.get("refresh_seconds", 60),
            counts={"total": 0, "running": 0, "warn": 0, "critical": 0, "unknown": 0},
            messages=[f"Refresh failed: {exc}"],
            rows_html=[],
        )
        return False
