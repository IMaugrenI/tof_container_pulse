import html
import json
import shutil
import socket
import subprocess
from datetime import datetime
from pathlib import Path


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


def generate_pulse(output_path="pulse.html", template_path="template.html"):
    docker = shutil.which("docker")
    if not docker:
        raise FileNotFoundError("Docker CLI not found in PATH.")

    ps = _run([docker, "ps", "-a", "--format", "{{json .}}"])
    if ps.returncode != 0:
        raise RuntimeError(ps.stderr.strip() or "docker ps failed")

    stats_lookup = {}
    try:
        stats = _run([docker, "stats", "--no-stream", "--format", "{{json .}}"])
        if stats.returncode == 0:
            for row in _json_lines(stats.stdout):
                name = row.get("Name") or row.get("Container")
                if name:
                    stats_lookup[name] = row
    except Exception:
        pass

    rows_html = []
    total = running = warn = critical = unknown = 0

    for row in _json_lines(ps.stdout):
        total += 1
        name = str(row.get("Names") or row.get("Name") or "unknown")
        image = str(row.get("Image") or "-")
        status = str(row.get("Status") or "-")
        running_for = str(row.get("RunningFor") or "-")
        state = _state(status)
        if state == "running":
            running += 1

        stats_row = stats_lookup.get(name, {})
        cpu_value = _percent(str(stats_row.get("CPUPerc", "")))
        mem_perc = str(stats_row.get("MemPerc", "-") or "-")
        mem_usage = str(stats_row.get("MemUsage", "-") or "-")
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
        elif cpu_value is not None and cpu_value > 50:
            severity = "warn"
            warn += 1
            note = "cpu>50%"

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
    html_text = html_text.replace("{{GENERATED_AT}}", html.escape(_now()))
    html_text = html_text.replace("{{SUMMARY}}", html.escape(f"Total: {total} · Running: {running} · Warn: {warn} · Critical: {critical} · Unknown: {unknown}"))
    html_text = html_text.replace("{{ROWS}}", "\n".join(rows_html))
    Path(output_path).write_text(html_text, encoding="utf-8")
