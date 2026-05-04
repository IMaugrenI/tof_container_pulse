import html
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from i18n_static import l10n_text
from platform_support import os_family, run_command, run_powershell
from ports import generate_port_pulse as generate_linux_port_pulse

DEFAULT_CONFIG = {"refresh_seconds": 60, "port_command_timeout_seconds": 2.0}
RANK = {"ok": 0, "unknown": 1, "warn": 2, "critical": 3}
SORT = {"critical": 0, "warn": 1, "unknown": 2, "ok": 3}
KNOWN = {"22": ("SSH remote login", "SSH-Fernzugriff"), "53": ("DNS resolver", "DNS-Resolver"), "80": ("HTTP web server", "HTTP-Webserver"), "443": ("HTTPS web server", "HTTPS-Webserver"), "3000": ("dev web app", "Entwicklungs-Webapp"), "5173": ("Vite dev app", "Vite-Entwicklungsapp"), "5432": ("PostgreSQL", "PostgreSQL"), "6379": ("Redis", "Redis"), "8000": ("dev API", "Entwicklungs-API"), "8080": ("web app", "Webapp"), "11434": ("local LLM API", "lokale LLM-API")}

@dataclass(frozen=True)
class Entry:
    proto: str
    state: str
    bind: str
    port: str
    exposure: str
    severity: str
    note: str


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def _last(path):
    p = Path(path)
    if not p.exists():
        return "never"
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return str(data.get("last_success_at") or "never") if isinstance(data, dict) else "never"
    except Exception:
        return "never"

def _save(path, value):
    Path(path).write_text(json.dumps({"last_success_at": value}, indent=2), encoding="utf-8")

def _cfg(config_path):
    config = dict(DEFAULT_CONFIG)
    if not config_path or not Path(config_path).exists():
        return config
    try:
        import yaml
        data = yaml.safe_load(Path(config_path).read_text(encoding="utf-8")) or {}
        if isinstance(data, dict):
            config.update({k: v for k, v in data.items() if k in config})
    except Exception:
        pass
    return config

def _split(local):
    local = (local or "").strip()
    if local.startswith("[") and "]:" in local:
        a, p = local.rsplit(":", 1); return a.strip("[]"), p
    if ":" in local:
        a, p = local.rsplit(":", 1); return a.strip("[]"), p
    return local or "-", "-"

def _classify(bind):
    b = (bind or "").lower().strip().strip("[]")
    if b.startswith("127.") or b in {"::1", "localhost"}:
        return "local-only", "ok", l10n_text("Only this device should reach it.", "Nur dieses Gerät sollte ihn erreichen.")
    if b in {"0.0.0.0", "::", "*", ""}:
        return "all interfaces", "warn", l10n_text("This listens on all interfaces. Review whether that is intended.", "Dieser Dienst lauscht auf allen Schnittstellen. Prüfe, ob das beabsichtigt ist.")
    if b.startswith("10.") or b.startswith("192.168.") or re.match(r"^172\.(1[6-9]|2[0-9]|3[0-1])\.", b) or b.startswith("fe80"):
        return "LAN/mesh", "warn", l10n_text("This may be reachable inside LAN, VPN, or mesh networks.", "Das könnte im LAN, VPN oder Mesh erreichbar sein.")
    return "specific interface", "warn", l10n_text("This is not localhost. Review exposure.", "Das ist nicht localhost. Prüfe die Erreichbarkeit.")

def _hint(port):
    en, de = KNOWN.get(str(port), ("unknown or app-specific service", "unbekannter oder app-spezifischer Dienst"))
    return l10n_text(en, de)

def _entry(proto, state, local):
    bind, port = _split(local)
    exposure, severity, meaning = _classify(bind)
    return Entry(proto.lower(), state or "LISTEN", bind or "-", port or "-", exposure, severity, f"{l10n_text('Likely', 'Vermutlich')}: {_hint(port)}. {meaning}")

def _parse_netstat(text):
    entries = []
    for raw in text.splitlines():
        parts = raw.split()
        if len(parts) < 4 or not parts[0].lower().startswith(("tcp", "udp")):
            continue
        proto = parts[0].lower(); state = parts[5] if proto.startswith("tcp") and len(parts) > 5 else "LISTEN"
        if proto.startswith("tcp") and state.upper() not in {"LISTEN", "LISTENING"}:
            continue
        entries.append(_entry(proto, state, parts[3]))
    return entries

def _collect(config):
    timeout = float(config.get("port_command_timeout_seconds", 2.0))
    if os_family() == "windows":
        ps = run_powershell("Get-NetTCPConnection -State Listen | ForEach-Object {\"tcp $($_.State) $($_.LocalAddress):$($_.LocalPort)\"}", timeout=timeout + 2)
        if ps.code == 0 and ps.stdout:
            return [_entry(p[0], p[1], p[2]) for p in (line.split(maxsplit=2) for line in ps.stdout.splitlines()) if len(p) == 3]
        res = run_command(["netstat", "-an"], timeout=timeout); return _parse_netstat(res.stdout) if res.code == 0 else []
    if os_family() == "macos":
        out = []
        for proto in ("tcp", "udp"):
            res = run_command(["netstat", "-an", "-p", proto], timeout=timeout)
            if res.code == 0: out.extend(_parse_netstat(res.stdout))
        return out
    return []

def _dedupe(entries):
    seen = set(); out = []
    for e in entries:
        key = (e.proto, e.state, e.bind, e.port)
        if key not in seen:
            seen.add(key); out.append(e)
    return sorted(out, key=lambda e: (SORT.get(e.severity, 9), e.port, e.proto, e.bind))

def _overall(entries):
    return max((e.severity for e in entries), key=lambda s: RANK.get(s, 0)) if entries else "unknown"

def _card(cls, en, de, val, state):
    return f"<div class='card {cls}'><span>{l10n_text(en,de)}</span><strong>{html.escape(str(val))}</strong><small class='state state-{html.escape(state)}'>{html.escape(state.upper())}</small></div>"

def _cards(entries):
    total=len(entries); local=sum(e.exposure=='local-only' for e in entries); review=sum(e.severity=='warn' for e in entries); lan=sum(e.exposure=='LAN/mesh' for e in entries); allif=sum(e.exposure=='all interfaces' for e in entries)
    return "\n".join([_card('card-total','TOTAL','GESAMT',total,'ok' if total else 'unknown'),_card('card-local','LOCAL','LOKAL',local,'ok'),_card('card-public','ALL IFACES','ALLE NETZE',allif,'warn' if allif else 'ok'),_card('card-specific','LAN/MESH','LAN/MESH',lan,'warn' if lan else 'ok'),_card('card-warn','REVIEW','PRÜFEN',review,'warn' if review else 'ok')])

def _table(entries):
    if not entries:
        return f"<section class='health-panel'><div class='health-head'><h2>{l10n_text('Port Overview','Port-Übersicht')}</h2><span class='pill'>{l10n_text('No local data','Keine lokalen Daten')}</span></div><p class='recommendation'>{l10n_text('No listening-port data was collected on this platform.','Auf dieser Plattform wurden keine Daten zu lauschenden Ports gesammelt.')}</p></section>"
    rows = ''.join(f"<tr><td><code>{html.escape(e.proto)}</code></td><td><code>{html.escape(e.state)}</code></td><td><code>{html.escape(e.bind)}</code></td><td><code>{html.escape(e.port)}</code></td><td><span class='sev-badge sev-{e.severity}'>{e.severity.upper()}</span></td><td>{html.escape(e.exposure)}</td><td><code>-</code></td><td>{e.note}</td></tr>" for e in entries)
    return f"<section class='health-panel'><div class='health-head'><h2>{l10n_text('Local Listening Ports','Lokale lauschende Ports')}</h2><span class='pill'>{l10n_text('Cross-platform read-only inspection','Plattformübergreifende Nur-Lese-Prüfung')}</span></div><section class='messages'><p>{l10n_text('Port Pulse only explains what is listening. It does not change ports or firewall rules.','Port Pulse erklärt nur, was lauscht. Es ändert keine Ports oder Firewall-Regeln.')}</p></section><section class='table-shell'><table><thead><tr><th>{l10n_text('Protocol','Protokoll')}</th><th>{l10n_text('State','Zustand')}</th><th>Bind</th><th>Port</th><th>{l10n_text('Severity','Schweregrad')}</th><th>{l10n_text('Exposure','Erreichbarkeit')}</th><th>{l10n_text('Process','Prozess')}</th><th>{l10n_text('Plain-English help','Einfache Erklärung')}</th></tr></thead><tbody>{rows}</tbody></table></section></section>"

def _render(template_path, output_path, generated, previous, config, entries):
    overall = _overall(entries); text = Path(template_path).read_text(encoding='utf-8')
    for k,v in {"{{TITLE}}":"PORT PULSE","{{REFRESH_SECONDS}}":str(int(config.get('refresh_seconds',60))),"{{GENERATED_AT}}":html.escape(generated),"{{LAST_SUCCESS_AT}}":html.escape(previous),"{{OVERALL}}":overall.upper(),"{{OVERALL_CLASS}}":overall,"{{RECOMMENDATION}}":l10n_text('Cross-platform port data collected where available. Review WARN rows.','Plattformübergreifende Portdaten wurden gesammelt, soweit verfügbar. Prüfe WARN-Zeilen.'),"{{SUMMARY_CARDS}}":_cards(entries),"{{PORT_TABLE}}":_table(entries),"{{MESSAGES}}":f"<p>{l10n_text('No port refresh warnings.','Keine Port-Aktualisierungswarnungen.')}</p>"}.items():
        text = text.replace(k, v)
    Path(output_path).write_text(text, encoding='utf-8')

def generate_port_pulse(output_path='ports.html', template_path='ports_template.html', config_path=None, state_path='.port_pulse_state.json'):
    if os_family() == 'linux':
        return generate_linux_port_pulse(output_path=output_path, template_path=template_path, config_path=config_path, state_path=state_path)
    generated = _now(); previous = _last(state_path); config = _cfg(config_path)
    try:
        entries = _dedupe(_collect(config)); _render(template_path, output_path, generated, previous, config, entries); _save(state_path, generated); return True
    except Exception:
        _render(template_path, output_path, generated, previous, config, []); return False
