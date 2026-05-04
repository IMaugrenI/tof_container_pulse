import html
import ipaddress
import json
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

DEFAULT_PORT_CONFIG = {
    "refresh_seconds": 60,
    "port_command_timeout_seconds": 2.0,
    "port_allowed_listeners": [],
}

SEVERITY_RANK = {"ok": 0, "unknown": 1, "warn": 2, "critical": 3}
SEVERITY_SORT = {"critical": 0, "warn": 1, "unknown": 2, "ok": 3}
EXPOSURE_SORT = {
    "all-interfaces": 0,
    "specific-interface": 1,
    "cgnat-or-mesh": 2,
    "private-lan": 3,
    "ipv6-link-local": 4,
    "ipv6-unique-local": 5,
    "local-only": 6,
    "allowed": 7,
    "unknown": 8,
}


@dataclass(frozen=True)
class PortEntry:
    protocol: str
    state: str
    bind_address: str
    display_address: str
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
    entries = []
    if shutil.which("ss"):
        result = _run_command(["ss", "-H", "-lntu", "-p"], timeout)
        if result and result.returncode == 0:
            entries = _parse_ss_output(result.stdout, config)
    elif shutil.which("netstat"):
        result = _run_command(["netstat", "-tuln"], timeout)
        if result and result.returncode == 0:
            entries = _parse_netstat_output(result.stdout, config)

    return _sort_entries(_dedupe_entries(entries))


def _parse_ss_output(output, config):
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
        entries.append(_build_entry(protocol, state, bind_address, port, process, config))
    return entries


def _parse_netstat_output(output, config):
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
        entries.append(_build_entry(protocol, state, bind_address, port, "-", config))
    return entries


def _build_entry(protocol, state, bind_address, port, process, config):
    exposure, severity, note = _classify_bind(bind_address)
    entry = PortEntry(
        protocol=protocol,
        state=state,
        bind_address=bind_address,
        display_address=_display_address(bind_address),
        port=port,
        exposure=exposure,
        severity=severity,
        process=_short_process(process),
        note=note,
    )
    if _is_allowed(entry, config.get("port_allowed_listeners") or []):
        return PortEntry(
            protocol=entry.protocol,
            state=entry.state,
            bind_address=entry.bind_address,
            display_address=entry.display_address,
            port=entry.port,
            exposure="allowed",
            severity="ok",
            process=entry.process,
            note="Matched configured allowed listener. Review config if this should no longer be expected.",
        )
    return entry


def _split_address_port(value):
    value = value.strip()
    if value.startswith("[") and "]:" in value:
        address, port = value.rsplit(":", 1)
        return address.strip("[]"), port
    if ":" in value:
        address, port = value.rsplit(":", 1)
        return address.strip("[]"), port
    return value, "-"


def _normalize_address(address):
    normalized = (address or "").lower().strip().strip("[]")
    if "%" in normalized:
        normalized = normalized.split("%", 1)[0]
    return normalized


def _classify_bind(address):
    normalized = _normalize_address(address)

    if normalized.startswith("127.") or normalized in {"::1", "localhost"}:
        return "local-only", "ok", "Bound to localhost only."
    if normalized in {"0.0.0.0", "::", "*", ""}:
        return "all-interfaces", "warn", "Listening on all interfaces. Review whether this is intended."

    ip_obj = _parse_ip(normalized)
    if ip_obj is None:
        return "unknown", "unknown", "Bind address could not be classified. Review manually."

    if ip_obj.is_loopback:
        return "local-only", "ok", "Bound to loopback only."
    if ip_obj.version == 4 and ip_obj in ipaddress.ip_network("100.64.0.0/10"):
        return "cgnat-or-mesh", "warn", "Bound to CGNAT/mesh-style address. Review VPN or overlay exposure."
    if ip_obj.is_link_local:
        return "ipv6-link-local" if ip_obj.version == 6 else "link-local", "warn", "Bound to link-local address. Review local-network exposure."
    if ip_obj.version == 6 and ip_obj.is_private:
        return "ipv6-unique-local", "warn", "Bound to private IPv6/ULA-style address. Review local-network exposure."
    if ip_obj.is_private:
        return "private-lan", "warn", "Bound to private LAN address. Review whether LAN exposure is intended."

    return "specific-interface", "warn", "Bound to non-localhost interface. Review exposure."


def _parse_ip(address):
    try:
        return ipaddress.ip_address(address)
    except ValueError:
        return None


def _display_address(address):
    normalized = _normalize_address(address)
    ip_obj = _parse_ip(normalized)
    if ip_obj is not None and ip_obj.version == 6:
        return ip_obj.compressed
    return address or "-"


def _is_allowed(entry, allowed_listeners):
    for item in allowed_listeners:
        if not isinstance(item, dict):
            continue
        protocol = str(item.get("protocol", "")).lower()
        port = str(item.get("port", ""))
        bind = str(item.get("bind", item.get("bind_address", "")))
        exposure = str(item.get("exposure", ""))

        if protocol and protocol != entry.protocol:
            continue
        if port and port != entry.port:
            continue
        if bind and _normalize_address(bind) != _normalize_address(entry.bind_address):
            continue
        if exposure and exposure != entry.exposure:
            continue
        return True
    return False


def _short_process(process):
    if not process or process == "-":
        return "-"
    process = process.replace('users:(("', "").replace('"', "")
    process = process.replace("pid=", "pid ").replace("fd=", "fd ")
    if len(process) > 90:
        return process[:87] + "..."
    return process


def _dedupe_entries(entries):
    seen = set()
    result = []
    for entry in entries:
        key = (entry.protocol, entry.bind_address, entry.port, entry.state)
        if key in seen:
            continue
        seen.add(key)
        result.append(entry)
    return result


def _sort_entries(entries):
    def key(entry):
        try:
            port_number = int(entry.port)
        except ValueError:
            port_number = 999999
        return (
            SEVERITY_SORT.get(entry.severity, SEVERITY_SORT["unknown"]),
            EXPOSURE_SORT.get(entry.exposure, EXPOSURE_SORT["unknown"]),
            port_number,
            entry.protocol,
            entry.display_address,
        )

    return sorted(entries, key=key)


def _overall(entries):
    if not entries:
        return "unknown"
    return max((entry.severity for entry in entries), key=lambda item: SEVERITY_RANK.get(item, 0))


def _summary_counts(entries):
    return {
        "total": len(entries),
        "local": sum(1 for entry in entries if entry.exposure == "local-only"),
        "all_interfaces": sum(1 for entry in entries if entry.exposure == "all-interfaces"),
        "private_or_mesh": sum(1 for entry in entries if entry.exposure in {"private-lan", "cgnat-or-mesh", "ipv6-link-local", "ipv6-unique-local", "link-local"}),
        "allowed": sum(1 for entry in entries if entry.exposure == "allowed"),
        "review": sum(1 for entry in entries if entry.severity == "warn"),
    }


def _summary_cards(entries):
    counts = _summary_counts(entries)
    return "\n".join(
        [
            _card("card-total", "TOTAL", str(counts["total"]), "ok" if counts["total"] else "unknown"),
            _card("card-local", "LOCAL", str(counts["local"]), "ok"),
            _card("card-public", "ALL IFACES", str(counts["all_interfaces"]), "warn" if counts["all_interfaces"] else "ok"),
            _card("card-specific", "LAN/MESH", str(counts["private_or_mesh"]), "warn" if counts["private_or_mesh"] else "ok"),
            _card("card-warn", "REVIEW", str(counts["review"]), "warn" if counts["review"] else "ok"),
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
    title = "" if entry.display_address == entry.bind_address else f" title='{html.escape(entry.bind_address)}'"
    return (
        "<tr>"
        f"<td><code>{html.escape(entry.protocol)}</code></td>"
        f"<td><code>{html.escape(entry.state)}</code></td>"
        f"<td><code{title}>{html.escape(entry.display_address)}</code></td>"
        f"<td><code>{html.escape(entry.port)}</code></td>"
        f"<td><span class='sev-badge sev-{html.escape(entry.severity)}'>{html.escape(entry.severity.upper())}</span></td>"
        f"<td>{html.escape(entry.exposure)}</td>"
        f"<td><code>{html.escape(entry.process)}</code></td>"
        f"<td>{html.escape(entry.note)}</td>"
        "</tr>"
    )


def _recommendation(overall):
    if overall == "warn":
        return "Review all-interface, LAN, mesh, and non-localhost listeners. Port Pulse does not change firewall or service settings."
    if overall == "unknown":
        return "No local port data was collected. Ensure `ss` or `netstat` is available if you want Port Pulse details."
    return "No review needed. Listening ports appear local-only or explicitly allowed."


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


def _review_summary(entries):
    if not entries:
        return ""
    counts = _summary_counts(entries)
    return (
        '<section class="messages" aria-label="Port review summary">'
        f"<p><strong>Port summary</strong>: {counts['total']} listeners · "
        f"local {counts['local']} · all-interfaces {counts['all_interfaces']} · "
        f"LAN/mesh {counts['private_or_mesh']} · allowed {counts['allowed']} · review {counts['review']}</p>"
        "<p>WARN means review exposure; it does not mean Port Pulse changed or blocked anything.</p>"
        "</section>"
    )


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
        {_review_summary(entries)}
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
