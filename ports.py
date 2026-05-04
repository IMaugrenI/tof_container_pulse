import html
import json
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

DEFAULT_PORT_CONFIG = {
    "refresh_seconds": 60,
    "port_command_timeout_seconds": 2.0,
}

SEVERITY_RANK = {"ok": 0, "unknown": 1, "warn": 2, "critical": 3}


@dataclass(frozen=True)
class PortEntry:
    protocol: str
    state: str
    bind_address: str
    port: str
    exposure: str
    severity: str
    process: str
    note: str


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
    config = dict(DEFAULT_PORT_CONFIG)
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


def _run_command(command, timeout):
    try:
        return subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=float(timeout),
        )
    except Exception:
        return None


def _collect_port_entries(config):
    timeout = config.get("port_command_timeout_seconds", 2.0)
    if shutil.which("ss"):
        result = _run_command(["ss", "-H", "-lntu", "-p"], timeout)
        if result and result.returncode == 0:
            return _parse_ss_output(result.stdout)
    if shutil.which("netstat"):
        result = _run_command(["netstat", "-tuln"], timeout)
        if result and result.returncode == 0:
            return _parse_netstat_output(result.stdout)
    return []


def _parse_ss_output(output):
    entries = []
    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) < 5:
            continue
        protocol = parts[0].lower()
        state = parts[1]
        local = parts[4]
        process = " ".join(parts[6:]) if len(parts) > 6 else "-"
        bind_address, port = _split_address_port(local)
        exposure, severity, note = _classify_bind(bind_address)
        entries.append(
            PortEntry(
                protocol=protocol,
                state=state,
                bind_address=bind_address,
                port=port,
                exposure=exposure,
                severity=severity,
                process=_short_process(process),
                note=note,
            )
        )
    return entries


def _parse_netstat_output(output):
    entries = []
    for line in output.splitlines():
        line = line.strip()
        if not line or line.startswith(("Proto", "Active")):
            continue
        parts = line.split()
        if len(parts) < 4:
            continue
        protocol = parts[0].lower()
        local = parts[3]
        state = parts[5] if len(parts) > 5 else "LISTEN"
        bind_address, port = _split_address_port(local)
        exposure, severity, note = _classify_bind(bind_address)
        entries.append(
            PortEntry(
                protocol=protocol,
                state=state,
                bind_address=bind_address,
                port=port,
                exposure=exposure,
                severity=severity,
                process="-",
                note=note,
            )
        )
    return entries


def _split_address_port(value):
    value = value.strip()
    if value.startswith("[") and "]:" in value:
        address, port = value.rsplit(":", 1)
        return address.strip("[]"), port
    if ":" in value:
        address, port = value.rsplit(":", 1)
        return address.strip("[]"), port
    return value, "-"


def _classify_bind(address):
    normalized = address.lower().strip("[]")
    if "%" in normalized:
        normalized = normalized.split("%", 1)[0]

    if normalized.startswith("127.") or normalized in {"::1", "localhost"}:
        return "local-only", "ok", "Bound to localhost only."
    if normalized in {"0.0.0.0", "::", "*", ""}:
        return "all-interfaces", "warn", "Listening on all interfaces. Review whether this is intended."
    return "specific-interface", "warn", "Listening on a specific non-localhost interface. Review exposure."


def _short_process(process):
    if not process or process == "-":
        return "-"
    process = process.replace('users:(("', "").replace('"', "")
    if len(process) > 90:
        return process[:87] + "..."
    return process


def _overall(entries):
    if not entries:
        return "unknown"
    return max((entry.severity for entry in entries), key=lambda item: SEVERITY_RANK.get(item, 0))


def _summary_cards(entries):
    total = len(entries)
    local = sum(1 for entry in entries if entry.exposure == "local-only")
    all_ifaces = sum(1 for entry in entries if entry.exposure == "all-interfaces")
    specific = sum(1 for entry in entries if entry.exposure == "specific-interface")
    warn = sum(1 for entry in entries if entry.severity == "warn")
    return "\n".join(
        [
            _card("card-total", "TOTAL", str(total), "ok" if total else "unknown"),
            _card("card-local", "LOCAL", str(local), "ok"),
            _card("card-public", "ALL IFACES", str(all_ifaces), "warn" if all_ifaces else "ok"),
            _card("card-specific", "SPECIFIC", str(specific), "warn" if specific else "ok"),
            _card("card-warn", "REVIEW", str(warn), "warn" if warn else "ok"),
        ]
    )


def _card(css_class, label, value, state):
    return (
        f"<div class='card {html.escape(css_class)}'>"
        f"<span>{html.escape(label)}</span>"
        f"<strong>{html.escape(value)}</strong>"
        f"<small class='state state-{html.escape(state)}'>{html.escape(state.upper())}</small>"
        "</div>"
    )


def _entry_row(entry):
    return (
        "<tr>"
        f"<td><code>{html.escape(entry.protocol)}</code></td>"
        f"<td><code>{html.escape(entry.state)}</code></td>"
        f"<td><code>{html.escape(entry.bind_address)}</code></td>"
        f"<td><code>{html.escape(entry.port)}</code></td>"
        f"<td><span class='sev-badge sev-{html.escape(entry.severity)}'>{html.escape(entry.severity.upper())}</span></td>"
        f"<td>{html.escape(entry.exposure)}</td>"
        f"<td><code>{html.escape(entry.process)}</code></td>"
        f"<td>{html.escape(entry.note)}</td>"
        "</tr>"
    )


def _recommendation(overall):
    if overall == "warn":
        return "Review all-interface and non-localhost listeners. Port Pulse does not change firewall or service settings."
    if overall == "unknown":
        return "No local port data was collected. Ensure `ss` or `netstat` is available if you want Port Pulse details."
    return "No review needed. Listening ports appear local-only or intentionally narrow."


def _empty_notice():
    return """
      <section class="health-panel" aria-label="Port scan notice">
        <div class="health-head">
          <h2>Port Overview</h2>
          <span class="pill">No local data</span>
        </div>
        <p class="recommendation">No listening-port data was collected. Port Pulse uses local read-only tools such as <code>ss</code> or <code>netstat</code>.</p>
      </section>
""".rstrip()


def _port_table(entries):
    if not entries:
        return _empty_notice()
    rows = "\n".join(_entry_row(entry) for entry in entries)
    return f"""
      <section class="health-panel" aria-label="Port details">
        <div class="health-head">
          <h2>Local Listening Ports</h2>
          <span class="pill">Read-only local inspection</span>
        </div>
        <section class="table-shell" aria-label="Port table">
          <table>
            <thead>
              <tr>
                <th>Protocol</th>
                <th>State</th>
                <th>Bind</th>
                <th>Port</th>
                <th>Severity</th>
                <th>Exposure</th>
                <th>Process</th>
                <th>Notes</th>
              </tr>
            </thead>
            <tbody>
              {rows}
            </tbody>
          </table>
        </section>
      </section>
""".rstrip()


def _render(template_path, output_path, generated_at, previous_last_success, config, entries):
    overall = _overall(entries)
    template = Path(template_path).read_text(encoding="utf-8")
    replacements = {
        "{{TITLE}}": "PORT PULSE",
        "{{REFRESH_SECONDS}}": str(int(config.get("refresh_seconds", 60))),
        "{{GENERATED_AT}}": html.escape(generated_at),
        "{{LAST_SUCCESS_AT}}": html.escape(previous_last_success),
        "{{OVERALL}}": html.escape(overall.upper()),
        "{{OVERALL_CLASS}}": html.escape(overall),
        "{{RECOMMENDATION}}": html.escape(_recommendation(overall)),
        "{{SUMMARY_CARDS}}": _summary_cards(entries),
        "{{PORT_TABLE}}": _port_table(entries),
        "{{MESSAGES}}": "<p>No port refresh warnings.</p>",
    }
    html_text = template
    for key, value in replacements.items():
        html_text = html_text.replace(key, value)
    Path(output_path).write_text(html_text, encoding="utf-8")


def generate_port_pulse(
    output_path="ports.html",
    template_path="ports_template.html",
    config_path=None,
    state_path=".port_pulse_state.json",
):
    generated_at = _now()
    previous_last_success = _read_last_success(state_path)
    config = dict(DEFAULT_PORT_CONFIG)
    try:
        config = _load_config(config_path)
        entries = _collect_port_entries(config)
        _render(template_path, output_path, generated_at, previous_last_success, config, entries)
        _write_last_success(state_path, generated_at)
        return True
    except Exception as exc:
        _render(template_path, output_path, generated_at, previous_last_success, config, [])
        path = Path(output_path)
        if path.exists():
            html_text = path.read_text(encoding="utf-8")
            html_text = html_text.replace("<p>No port refresh warnings.</p>", f"<p>{html.escape(f'Port refresh failed: {exc}')}</p>")
            path.write_text(html_text, encoding="utf-8")
        return False
