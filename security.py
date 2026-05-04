import html
import json
import os
import socket
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from i18n_static import l10n_text

DEFAULT_SECURITY_CONFIG = {
    "refresh_seconds": 60,
    "security_command_timeout_seconds": 1.5,
    "security_auth_log_max_lines": 600,
    "security_failed_login_warn_count": 5,
    "security_failed_login_critical_count": 20,
    "security_check_docker_socket": True,
    "security_check_auth_log": True,
    "security_check_fail2ban": True,
    "security_check_sessions": True,
}

SEVERITY_RANK = {"ok": 0, "unknown": 1, "warn": 2, "critical": 3}
SEVERITY_SORT = {"critical": 0, "warn": 1, "unknown": 2, "ok": 3}

AUTH_LOG_CANDIDATES = (
    "/var/log/auth.log",
    "/var/log/secure",
)


@dataclass(frozen=True)
class SecurityEntry:
    name: str
    area: str
    value: str
    state: str
    severity: str
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
    config = dict(DEFAULT_SECURITY_CONFIG)
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
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except FileNotFoundError:
        return 127, "", "command not found"
    except Exception as exc:
        return 1, "", str(exc)


def _entry(name_en, name_de, area_en, area_de, value, state, severity, note_en, note_de):
    return SecurityEntry(
        name=l10n_text(name_en, name_de),
        area=l10n_text(area_en, area_de),
        value=str(value),
        state=l10n_text(state, state),
        severity=severity,
        note=l10n_text(note_en, note_de),
    )


def _check_sessions(config):
    timeout = float(config.get("security_command_timeout_seconds", 1.5))
    code, stdout, _stderr = _run_command(["who"], timeout)
    if code == 127:
        return _entry(
            "Active login sessions",
            "Aktive Login-Sitzungen",
            "Login",
            "Login",
            "unavailable",
            "unknown",
            "unknown",
            "The local 'who' command is unavailable on this system.",
            "Der lokale Befehl 'who' ist auf diesem System nicht verfügbar.",
        )
    if code != 0:
        return _entry(
            "Active login sessions",
            "Aktive Login-Sitzungen",
            "Login",
            "Login",
            "unreadable",
            "unknown",
            "unknown",
            "Active sessions could not be read without extra permissions.",
            "Aktive Sitzungen konnten ohne zusätzliche Rechte nicht gelesen werden.",
        )
    lines = [line for line in stdout.splitlines() if line.strip()]
    if not lines:
        return _entry(
            "Active login sessions",
            "Aktive Login-Sitzungen",
            "Login",
            "Login",
            "0",
            "ok",
            "ok",
            "No active terminal login sessions were reported.",
            "Es wurden keine aktiven Terminal-Login-Sitzungen gemeldet.",
        )
    return _entry(
        "Active login sessions",
        "Aktive Login-Sitzungen",
        "Login",
        "Login",
        len(lines),
        "review",
        "warn",
        "One or more terminal login sessions are active. This can be normal if you are logged in, but review if unexpected.",
        "Eine oder mehrere Terminal-Login-Sitzungen sind aktiv. Das kann normal sein, wenn du eingeloggt bist; prüfe es, falls unerwartet.",
    )


def _read_tail_lines(path, max_lines):
    try:
        lines = Path(path).read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:
        return None
    return lines[-max_lines:]


def _check_auth_log(config):
    max_lines = int(config.get("security_auth_log_max_lines", 600))
    selected_path = None
    lines = None
    for candidate in AUTH_LOG_CANDIDATES:
        if Path(candidate).exists():
            selected_path = candidate
            lines = _read_tail_lines(candidate, max_lines)
            break
    if selected_path is None:
        return _entry(
            "Auth log visibility",
            "Auth-Log-Sichtbarkeit",
            "Login",
            "Login",
            "not found",
            "unknown",
            "unknown",
            "No common auth log file was found. This is normal on some distributions or restricted environments.",
            "Keine typische Auth-Log-Datei gefunden. Das ist auf manchen Distributionen oder eingeschränkten Umgebungen normal.",
        )
    if lines is None:
        return _entry(
            "Auth log visibility",
            "Auth-Log-Sichtbarkeit",
            "Login",
            "Login",
            selected_path,
            "unknown",
            "unknown",
            "The auth log exists but could not be read without extra permissions.",
            "Das Auth-Log existiert, konnte aber ohne zusätzliche Rechte nicht gelesen werden.",
        )

    lowered = [line.lower() for line in lines]
    failed = sum(1 for line in lowered if "failed password" in line or "authentication failure" in line)
    warn_at = int(config.get("security_failed_login_warn_count", 5))
    critical_at = int(config.get("security_failed_login_critical_count", 20))
    if failed >= critical_at:
        severity = "critical"
        state = "critical"
        note_en = "Many failed login hints were found in the recent auth log tail. Review access and exposure. No action was taken."
        note_de = "Viele fehlgeschlagene Login-Hinweise wurden im jüngsten Auth-Log-Ausschnitt gefunden. Prüfe Zugriff und Erreichbarkeit. Es wurde nichts geändert."
    elif failed >= warn_at:
        severity = "warn"
        state = "review"
        note_en = "Some failed login hints were found. This may be normal on exposed systems, but should be reviewed."
        note_de = "Einige fehlgeschlagene Login-Hinweise wurden gefunden. Das kann bei erreichbaren Systemen normal sein, sollte aber geprüft werden."
    else:
        severity = "ok"
        state = "ok"
        note_en = "No unusual amount of failed login hints was found in the recent auth log tail."
        note_de = "Im jüngsten Auth-Log-Ausschnitt wurde keine ungewöhnliche Menge fehlgeschlagener Login-Hinweise gefunden."
    return _entry(
        "Failed login hints",
        "Fehlgeschlagene Login-Hinweise",
        "Login",
        "Login",
        failed,
        state,
        severity,
        note_en,
        note_de,
    )


def _check_fail2ban(config):
    timeout = float(config.get("security_command_timeout_seconds", 1.5))
    code, stdout, stderr = _run_command(["fail2ban-client", "status"], timeout)
    if code == 127:
        return _entry(
            "Fail2Ban visibility",
            "Fail2Ban-Sichtbarkeit",
            "Protection",
            "Schutz",
            "not installed",
            "unknown",
            "unknown",
            "Fail2Ban was not detected. This is not automatically bad; some systems use other protection layers.",
            "Fail2Ban wurde nicht erkannt. Das ist nicht automatisch schlecht; manche Systeme nutzen andere Schutzebenen.",
        )
    if code != 0:
        return _entry(
            "Fail2Ban visibility",
            "Fail2Ban-Sichtbarkeit",
            "Protection",
            "Schutz",
            "unavailable",
            "unknown",
            "unknown",
            f"Fail2Ban status could not be read: {stderr or 'no output'}",
            f"Fail2Ban-Status konnte nicht gelesen werden: {stderr or 'keine Ausgabe'}",
        )
    jails = "0"
    for line in stdout.splitlines():
        if "Jail list" in line:
            jail_list = line.split(":", 1)[-1].strip()
            jails = "0" if not jail_list else str(len([item for item in jail_list.split(",") if item.strip()]))
            break
    return _entry(
        "Fail2Ban status",
        "Fail2Ban-Status",
        "Protection",
        "Schutz",
        jails,
        "ok",
        "ok",
        "Fail2Ban responded to a read-only status request.",
        "Fail2Ban hat auf eine nur lesende Statusabfrage geantwortet.",
    )


def _check_docker_socket(config):
    path = Path("/var/run/docker.sock")
    if not path.exists():
        return _entry(
            "Docker socket",
            "Docker-Socket",
            "Local access",
            "Lokaler Zugriff",
            "not found",
            "ok",
            "ok",
            "Docker socket was not found at the common path. Nothing to review here for this check.",
            "Der Docker-Socket wurde am üblichen Pfad nicht gefunden. Für diesen Check gibt es hier nichts zu prüfen.",
        )
    try:
        stat = path.stat()
        mode = oct(stat.st_mode & 0o777)
    except Exception:
        return _entry(
            "Docker socket",
            "Docker-Socket",
            "Local access",
            "Lokaler Zugriff",
            "exists",
            "review",
            "warn",
            "Docker socket exists but its permissions could not be read. Review who can access Docker locally.",
            "Der Docker-Socket existiert, aber seine Rechte konnten nicht gelesen werden. Prüfe, wer lokal auf Docker zugreifen kann.",
        )
    if stat.st_mode & 0o002:
        severity = "critical"
        state = "critical"
        note_en = "Docker socket appears world-writable. Review local permissions urgently. No change was made."
        note_de = "Der Docker-Socket wirkt für alle schreibbar. Prüfe lokale Rechte dringend. Es wurde nichts geändert."
    else:
        severity = "warn"
        state = "review"
        note_en = "Docker socket exists. This is normal on Docker hosts, but users with access can control Docker. Review group membership."
        note_de = "Der Docker-Socket existiert. Das ist auf Docker-Hosts normal, aber Nutzer mit Zugriff können Docker steuern. Prüfe Gruppenmitgliedschaften."
    return _entry(
        "Docker socket",
        "Docker-Socket",
        "Local access",
        "Lokaler Zugriff",
        mode,
        state,
        severity,
        note_en,
        note_de,
    )


def _check_hostname():
    try:
        value = socket.gethostname()
    except Exception:
        value = "unknown"
    return _entry(
        "Host identity",
        "Host-Identität",
        "Context",
        "Kontext",
        value,
        "ok",
        "ok",
        "Local hostname context for this static snapshot.",
        "Lokaler Hostname-Kontext für diesen statischen Schnappschuss.",
    )


def _collect_entries(config):
    entries = [_check_hostname()]
    if bool(config.get("security_check_sessions", True)):
        entries.append(_check_sessions(config))
    if bool(config.get("security_check_auth_log", True)):
        entries.append(_check_auth_log(config))
    if bool(config.get("security_check_fail2ban", True)):
        entries.append(_check_fail2ban(config))
    if bool(config.get("security_check_docker_socket", True)):
        entries.append(_check_docker_socket(config))
    entries.sort(key=lambda item: (SEVERITY_SORT.get(item.severity, 9), item.area, item.name))
    return entries


def _overall(entries):
    if not entries:
        return "unknown"
    return max((entry.severity for entry in entries), key=lambda item: SEVERITY_RANK.get(item, 0))


def _summary_counts(entries):
    return {
        "total": len(entries),
        "ok": sum(1 for entry in entries if entry.severity == "ok"),
        "warn": sum(1 for entry in entries if entry.severity == "warn"),
        "critical": sum(1 for entry in entries if entry.severity == "critical"),
        "unknown": sum(1 for entry in entries if entry.severity == "unknown"),
    }


def _card(css_class, label_en, label_de, value, state):
    return (
        f"<div class='card {html.escape(css_class)}'>"
        f"<span>{l10n_text(label_en, label_de)}</span>"
        f"<strong>{html.escape(str(value))}</strong>"
        f"<small class='state state-{html.escape(state)}'>{html.escape(state.upper())}</small>"
        "</div>"
    )


def _summary_cards(entries):
    counts = _summary_counts(entries)
    return "\n".join(
        [
            _card("card-total", "Signals", "Signale", counts["total"], "ok" if counts["total"] else "unknown"),
            _card("card-ok", "OK", "OK", counts["ok"], "ok"),
            _card("card-warn", "Review", "Prüfen", counts["warn"], "warn" if counts["warn"] else "ok"),
            _card("card-critical", "Critical", "Kritisch", counts["critical"], "critical" if counts["critical"] else "ok"),
            _card("card-unknown", "Unknown", "Unbekannt", counts["unknown"], "unknown" if counts["unknown"] else "ok"),
        ]
    )


def _overall_recommendation(overall):
    if overall == "critical":
        return l10n_text(
            "Security Pulse found a critical review signal. Inspect the critical row first. No automatic change was made.",
            "Security Pulse hat ein kritisches Prüfsignal gefunden. Prüfe zuerst die kritische Zeile. Es wurde nichts automatisch geändert.",
        )
    if overall == "warn":
        return l10n_text(
            "Some local security signals should be reviewed. This does not prove a problem; it highlights where to look.",
            "Einige lokale Sicherheitssignale sollten geprüft werden. Das beweist kein Problem; es zeigt nur, wo du hinschauen solltest.",
        )
    if overall == "unknown":
        return l10n_text(
            "Some security signals could not be read without extra permissions or tools. Review manually if needed.",
            "Einige Sicherheitssignale konnten ohne zusätzliche Rechte oder Tools nicht gelesen werden. Prüfe bei Bedarf manuell.",
        )
    return l10n_text(
        "Basic local security signals look calm. Security Pulse did not change anything.",
        "Die einfachen lokalen Sicherheitssignale wirken ruhig. Security Pulse hat nichts geändert.",
    )


def _entry_row(entry):
    return (
        "<tr>"
        f"<td><strong>{entry.name}</strong></td>"
        f"<td>{entry.area}</td>"
        f"<td><code>{html.escape(entry.value)}</code></td>"
        f"<td>{entry.state}</td>"
        f"<td><span class='sev-badge sev-{html.escape(entry.severity)}'>{html.escape(entry.severity.upper())}</span></td>"
        f"<td>{entry.note}</td>"
        "</tr>"
    )


def _signals_table(entries):
    if not entries:
        return f"""
      <section class="health-panel" aria-label="Security notice">
        <div class="health-head">
          <h2>{l10n_text('Security Signals', 'Sicherheitssignale')}</h2>
          <span class="pill">{l10n_text('No signals collected', 'Keine Signale gesammelt')}</span>
        </div>
        <p class="recommendation">{l10n_text('No security signals were collected in this run.', 'In diesem Lauf wurden keine Sicherheitssignale gesammelt.')}</p>
      </section>
""".rstrip()

    rows = "\n".join(_entry_row(entry) for entry in entries)
    counts = _summary_counts(entries)
    return f"""
      <section class="health-panel" aria-label="Security signal details">
        <div class="health-head">
          <h2>{l10n_text('Security Signals', 'Sicherheitssignale')}</h2>
          <span class="pill">{l10n_text('Read-only local review', 'Nur lesende lokale Sichtprüfung')}</span>
        </div>
        <section class="messages" aria-label="Security plain summary">
          <p><strong>{l10n_text('Plain meaning', 'Einfache Bedeutung')}</strong>: {l10n_text('Security Pulse shows local hints that may deserve attention. It does not prove that something is wrong and it does not change the system.', 'Security Pulse zeigt lokale Hinweise, die Aufmerksamkeit verdienen könnten. Es beweist nicht, dass etwas falsch ist, und ändert nichts am System.')}</p>
          <p>{l10n_text('Summary', 'Zusammenfassung')}: {counts['total']} {l10n_text('signals', 'Signale')} · OK {counts['ok']} · WARN {counts['warn']} · CRITICAL {counts['critical']} · UNKNOWN {counts['unknown']}</p>
        </section>
        <section class="table-shell" aria-label="Security signals table">
          <table>
            <thead>
              <tr>
                <th>{l10n_text('Signal', 'Signal')}</th>
                <th>{l10n_text('Area', 'Bereich')}</th>
                <th>{l10n_text('Value', 'Wert')}</th>
                <th>{l10n_text('State', 'Zustand')}</th>
                <th>{l10n_text('Severity', 'Status')}</th>
                <th>{l10n_text('Plain-English help', 'Einfache Erklärung')}</th>
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
        "{{TITLE}}": "SECURITY PULSE",
        "{{REFRESH_SECONDS}}": str(int(config.get("refresh_seconds", 60))),
        "{{GENERATED_AT}}": html.escape(generated_at),
        "{{LAST_SUCCESS_AT}}": html.escape(previous_last_success),
        "{{OVERALL}}": html.escape(overall.upper()),
        "{{OVERALL_CLASS}}": html.escape(overall),
        "{{RECOMMENDATION}}": _overall_recommendation(overall),
        "{{SUMMARY_CARDS}}": _summary_cards(entries),
        "{{SECURITY_TABLE}}": _signals_table(entries),
        "{{MESSAGES}}": f"<p>{l10n_text('No security refresh warnings.', 'Keine Sicherheits-Aktualisierungswarnungen.')}</p>",
    }
    html_text = template
    for key, value in replacements.items():
        html_text = html_text.replace(key, value)
    Path(output_path).write_text(html_text, encoding="utf-8")


def generate_security_pulse(
    output_path="security.html",
    template_path="security_template.html",
    config_path=None,
    state_path=".security_pulse_state.json",
):
    generated_at = _now()
    previous_last_success = _read_last_success(state_path)
    config = dict(DEFAULT_SECURITY_CONFIG)
    try:
        config = _load_config(config_path)
        entries = _collect_entries(config)
        _render(template_path, output_path, generated_at, previous_last_success, config, entries)
        _write_last_success(state_path, generated_at)
        return True
    except Exception as exc:
        _render(template_path, output_path, generated_at, previous_last_success, config, [])
        path = Path(output_path)
        if path.exists():
            html_text = path.read_text(encoding="utf-8")
            error = l10n_text(f"Security refresh failed: {exc}", f"Sicherheits-Aktualisierung fehlgeschlagen: {exc}")
            html_text = html_text.replace(
                f"<p>{l10n_text('No security refresh warnings.', 'Keine Sicherheits-Aktualisierungswarnungen.')}</p>",
                f"<p>{error}</p>",
            )
            path.write_text(html_text, encoding="utf-8")
        return False
