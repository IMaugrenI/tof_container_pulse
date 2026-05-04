import html
import json
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
    "security_session_warn_count": 4,
    "security_session_critical_count": 10,
    "security_docker_group_warn_count": 4,
    "security_check_docker_socket": True,
    "security_check_auth_log": True,
    "security_check_fail2ban": True,
    "security_check_sessions": True,
    "security_check_reboot_required": True,
    "security_check_firewall_visibility": True,
    "security_check_ssh_config": True,
    "security_check_docker_group": True,
    "security_check_sensitive_file_permissions": True,
}

SEVERITY_RANK = {"ok": 0, "unknown": 1, "warn": 2, "critical": 3}
SEVERITY_SORT = {"critical": 0, "warn": 1, "unknown": 2, "ok": 3}

AUTH_LOG_CANDIDATES = ("/var/log/auth.log", "/var/log/secure")
SSH_CONFIG_PATH = Path("/etc/ssh/sshd_config")
SENSITIVE_PERMISSION_TARGETS = (
    ("/etc/sudoers", 0o022),
    ("/etc/ssh/sshd_config", 0o022),
)

STATE_LABELS = {
    "ok": ("ok", "ok"),
    "active": ("active", "aktiv"),
    "optional": ("optional", "optional"),
    "present": ("present", "vorhanden"),
    "review": ("review", "prüfen"),
    "critical": ("critical", "kritisch"),
    "unknown": ("unknown", "unbekannt"),
    "needed": ("needed", "nötig"),
    "calm": ("calm", "ruhig"),
}


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


def _state_text(state):
    return l10n_text(*STATE_LABELS.get(state, (state, state)))


def _entry(name_en, name_de, area_en, area_de, value, state, severity, note_en, note_de):
    return SecurityEntry(
        name=l10n_text(name_en, name_de),
        area=l10n_text(area_en, area_de),
        value=str(value),
        state=_state_text(state),
        severity=severity,
        note=l10n_text(note_en, note_de),
    )


def _check_sessions(config):
    timeout = float(config.get("security_command_timeout_seconds", 1.5))
    code, stdout, _stderr = _run_command(["who"], timeout)
    if code == 127:
        return _entry("Active login sessions", "Aktive Login-Sitzungen", "Login", "Login", "unavailable", "unknown", "unknown", "The local 'who' command is unavailable on this system.", "Der lokale Befehl 'who' ist auf diesem System nicht verfügbar.")
    if code != 0:
        return _entry("Active login sessions", "Aktive Login-Sitzungen", "Login", "Login", "unreadable", "unknown", "unknown", "Active sessions could not be read without extra permissions.", "Aktive Sitzungen konnten ohne zusätzliche Rechte nicht gelesen werden.")
    lines = [line for line in stdout.splitlines() if line.strip()]
    session_count = len(lines)
    warn_at = int(config.get("security_session_warn_count", 4))
    critical_at = int(config.get("security_session_critical_count", 10))
    if session_count <= 0:
        return _entry("Active login sessions", "Aktive Login-Sitzungen", "Login", "Login", "0", "ok", "ok", "No active terminal login sessions were reported.", "Es wurden keine aktiven Terminal-Login-Sitzungen gemeldet.")
    if session_count >= critical_at:
        return _entry("Active login sessions", "Aktive Login-Sitzungen", "Login", "Login", session_count, "critical", "critical", "Many terminal login sessions are active. Review whether this is expected. No session was changed.", "Viele Terminal-Login-Sitzungen sind aktiv. Prüfe, ob das erwartet ist. Es wurde keine Sitzung verändert.")
    if session_count >= warn_at:
        return _entry("Active login sessions", "Aktive Login-Sitzungen", "Login", "Login", session_count, "review", "warn", "Several terminal login sessions are active. This can be normal, but review if unexpected.", "Mehrere Terminal-Login-Sitzungen sind aktiv. Das kann normal sein, sollte aber geprüft werden, falls unerwartet.")
    return _entry("Active login sessions", "Aktive Login-Sitzungen", "Login", "Login", session_count, "active", "ok", "A small number of terminal login sessions is active. This is normal when you are logged in locally or using a terminal.", "Eine kleine Anzahl Terminal-Login-Sitzungen ist aktiv. Das ist normal, wenn du lokal angemeldet bist oder ein Terminal nutzt.")


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
        return _entry("Auth log visibility", "Auth-Log-Sichtbarkeit", "Login", "Login", "not found", "optional", "ok", "No common auth log file was found. This is normal on some distributions or restricted environments.", "Keine typische Auth-Log-Datei gefunden. Das ist auf manchen Distributionen oder eingeschränkten Umgebungen normal.")
    if lines is None:
        return _entry("Auth log visibility", "Auth-Log-Sichtbarkeit", "Login", "Login", selected_path, "unknown", "unknown", "The auth log exists but could not be read without extra permissions.", "Das Auth-Log existiert, konnte aber ohne zusätzliche Rechte nicht gelesen werden.")
    lowered = [line.lower() for line in lines]
    failed = sum(1 for line in lowered if "failed password" in line or "authentication failure" in line)
    warn_at = int(config.get("security_failed_login_warn_count", 5))
    critical_at = int(config.get("security_failed_login_critical_count", 20))
    if failed >= critical_at:
        return _entry("Failed login hints", "Fehlgeschlagene Login-Hinweise", "Login", "Login", failed, "critical", "critical", "Many failed login hints were found in the recent auth log tail. Review access and exposure. No action was taken.", "Viele fehlgeschlagene Login-Hinweise wurden im jüngsten Auth-Log-Ausschnitt gefunden. Prüfe Zugriff und Erreichbarkeit. Es wurde nichts geändert.")
    if failed >= warn_at:
        return _entry("Failed login hints", "Fehlgeschlagene Login-Hinweise", "Login", "Login", failed, "review", "warn", "Some failed login hints were found. This may be normal on exposed systems, but should be reviewed.", "Einige fehlgeschlagene Login-Hinweise wurden gefunden. Das kann bei erreichbaren Systemen normal sein, sollte aber geprüft werden.")
    return _entry("Failed login hints", "Fehlgeschlagene Login-Hinweise", "Login", "Login", failed, "ok", "ok", "No unusual amount of failed login hints was found in the recent auth log tail.", "Im jüngsten Auth-Log-Ausschnitt wurde keine ungewöhnliche Menge fehlgeschlagener Login-Hinweise gefunden.")


def _check_fail2ban(config):
    timeout = float(config.get("security_command_timeout_seconds", 1.5))
    code, stdout, stderr = _run_command(["fail2ban-client", "status"], timeout)
    if code == 127:
        return _entry("Fail2Ban visibility", "Fail2Ban-Sichtbarkeit", "Protection", "Schutz", "not installed", "optional", "ok", "Fail2Ban was not detected. This is not automatically bad; some systems use other protection layers.", "Fail2Ban wurde nicht erkannt. Das ist nicht automatisch schlecht; manche Systeme nutzen andere Schutzebenen.")
    if code != 0:
        return _entry("Fail2Ban visibility", "Fail2Ban-Sichtbarkeit", "Protection", "Schutz", "unavailable", "unknown", "unknown", f"Fail2Ban status could not be read: {stderr or 'no output'}", f"Fail2Ban-Status konnte nicht gelesen werden: {stderr or 'keine Ausgabe'}")
    jails = "0"
    for line in stdout.splitlines():
        if "Jail list" in line:
            jail_list = line.split(":", 1)[-1].strip()
            jails = "0" if not jail_list else str(len([item for item in jail_list.split(",") if item.strip()]))
            break
    return _entry("Fail2Ban status", "Fail2Ban-Status", "Protection", "Schutz", jails, "ok", "ok", "Fail2Ban responded to a read-only status request.", "Fail2Ban hat auf eine nur lesende Statusabfrage geantwortet.")


def _check_docker_socket(config):
    path = Path("/var/run/docker.sock")
    if not path.exists():
        return _entry("Docker socket", "Docker-Socket", "Local access", "Lokaler Zugriff", "not found", "optional", "ok", "Docker socket was not found at the common path. Nothing to review here for this check.", "Der Docker-Socket wurde am üblichen Pfad nicht gefunden. Für diesen Check gibt es hier nichts zu prüfen.")
    try:
        stat = path.stat()
        mode = oct(stat.st_mode & 0o777)
    except Exception:
        return _entry("Docker socket", "Docker-Socket", "Local access", "Lokaler Zugriff", "exists", "unknown", "unknown", "Docker socket exists but its permissions could not be read. Review who can access Docker locally if needed.", "Der Docker-Socket existiert, aber seine Rechte konnten nicht gelesen werden. Prüfe bei Bedarf, wer lokal auf Docker zugreifen kann.")
    if stat.st_mode & 0o002:
        return _entry("Docker socket", "Docker-Socket", "Local access", "Lokaler Zugriff", mode, "critical", "critical", "Docker socket appears world-writable. Review local permissions urgently. No change was made.", "Der Docker-Socket wirkt für alle schreibbar. Prüfe lokale Rechte dringend. Es wurde nichts geändert.")
    return _entry("Docker socket", "Docker-Socket", "Local access", "Lokaler Zugriff", mode, "present", "ok", "Docker socket exists. This is normal on Docker hosts. Users with Docker access can control Docker, so review group membership during normal maintenance.", "Der Docker-Socket existiert. Das ist auf Docker-Hosts normal. Nutzer mit Docker-Zugriff können Docker steuern; prüfe Gruppenmitgliedschaften bei normaler Wartung.")


def _check_reboot_required(config):
    path = Path("/var/run/reboot-required")
    if path.exists():
        return _entry("Reboot required", "Neustart erforderlich", "Maintenance", "Wartung", "yes", "review", "warn", "The system reports that a reboot may be required after updates. Plan a controlled restart when it fits.", "Das System meldet, dass nach Updates eventuell ein Neustart nötig ist. Plane einen kontrollierten Neustart, wenn es passt.")
    return _entry("Reboot required", "Neustart erforderlich", "Maintenance", "Wartung", "no", "calm", "ok", "No reboot-required marker was found.", "Es wurde kein Neustart-erforderlich-Marker gefunden.")


def _check_firewall_visibility(config):
    timeout = float(config.get("security_command_timeout_seconds", 1.5))
    code, stdout, _stderr = _run_command(["ufw", "status"], timeout)
    if code != 127:
        text = stdout.lower()
        if "status: active" in text:
            return _entry("Firewall visibility", "Firewall-Sichtbarkeit", "Network", "Netzwerk", "ufw active", "active", "ok", "UFW reports an active firewall status. No rule was changed.", "UFW meldet eine aktive Firewall. Es wurde keine Regel verändert.")
        if "status: inactive" in text:
            return _entry("Firewall visibility", "Firewall-Sichtbarkeit", "Network", "Netzwerk", "ufw inactive", "review", "warn", "UFW is installed but inactive. This can be intentional, but review if this host is exposed.", "UFW ist installiert, aber inaktiv. Das kann beabsichtigt sein; prüfe es, falls dieser Host erreichbar ist.")
        return _entry("Firewall visibility", "Firewall-Sichtbarkeit", "Network", "Netzwerk", "ufw available", "unknown", "unknown", "UFW responded, but its status could not be classified.", "UFW hat geantwortet, aber der Status konnte nicht eingeordnet werden.")
    code, stdout, _stderr = _run_command(["firewall-cmd", "--state"], timeout)
    if code != 127:
        state = stdout.strip().lower()
        if state == "running":
            return _entry("Firewall visibility", "Firewall-Sichtbarkeit", "Network", "Netzwerk", "firewalld running", "active", "ok", "firewalld reports running. No rule was changed.", "firewalld meldet running. Es wurde keine Regel verändert.")
        return _entry("Firewall visibility", "Firewall-Sichtbarkeit", "Network", "Netzwerk", f"firewalld {state or 'unknown'}", "optional", "ok", "firewalld is available but not running. This can be normal when another protection layer is used.", "firewalld ist vorhanden, läuft aber nicht. Das kann normal sein, wenn eine andere Schutzebene genutzt wird.")
    return _entry("Firewall visibility", "Firewall-Sichtbarkeit", "Network", "Netzwerk", "not detected", "optional", "ok", "No common local firewall tool was detected. This is an orientation hint, not proof of exposure.", "Kein übliches lokales Firewall-Tool wurde erkannt. Das ist ein Orientierungshinweis, kein Beweis für Erreichbarkeit.")


def _parse_ssh_value(lines, key):
    key_lower = key.lower()
    value = None
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) >= 2 and parts[0].lower() == key_lower:
            value = parts[1].lower()
    return value


def _check_ssh_config(config):
    if not SSH_CONFIG_PATH.exists():
        return _entry("SSH configuration", "SSH-Konfiguration", "Login", "Login", "not found", "optional", "ok", "No sshd_config was found at the common path. SSH may be absent or configured elsewhere.", "Am üblichen Pfad wurde keine sshd_config gefunden. SSH fehlt eventuell oder ist anders konfiguriert.")
    try:
        lines = SSH_CONFIG_PATH.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:
        return _entry("SSH configuration", "SSH-Konfiguration", "Login", "Login", "unreadable", "unknown", "unknown", "sshd_config exists but could not be read without extra permissions. No content was shown.", "sshd_config existiert, konnte aber ohne zusätzliche Rechte nicht gelesen werden. Es wurden keine Inhalte angezeigt.")
    root_login = _parse_ssh_value(lines, "PermitRootLogin") or "default"
    password_auth = _parse_ssh_value(lines, "PasswordAuthentication") or "default"
    risky = []
    if root_login in {"yes", "without-password", "prohibit-password"}:
        risky.append("root-login")
    if password_auth == "yes":
        risky.append("password-auth")
    if risky:
        return _entry("SSH configuration", "SSH-Konfiguration", "Login", "Login", ", ".join(risky), "review", "warn", "SSH configuration has options worth reviewing. Security Pulse did not show file contents or change anything.", "Die SSH-Konfiguration enthält Optionen, die geprüft werden sollten. Security Pulse zeigt keine Dateiinhalte und ändert nichts.")
    return _entry("SSH configuration", "SSH-Konfiguration", "Login", "Login", "basic flags calm", "calm", "ok", "Basic SSH flags look calm in the readable configuration snapshot.", "Die einfachen SSH-Flags wirken im lesbaren Konfigurations-Schnappschuss ruhig.")


def _check_docker_group(config):
    group_path = Path("/etc/group")
    if not group_path.exists():
        return _entry("Docker group members", "Docker-Gruppenmitglieder", "Local access", "Lokaler Zugriff", "group file missing", "unknown", "unknown", "The local group file was not found, so Docker group membership could not be counted.", "Die lokale Gruppen-Datei wurde nicht gefunden, deshalb konnte die Docker-Gruppenmitgliedschaft nicht gezählt werden.")
    try:
        lines = group_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:
        return _entry("Docker group members", "Docker-Gruppenmitglieder", "Local access", "Lokaler Zugriff", "unreadable", "unknown", "unknown", "The local group file could not be read, so Docker group membership could not be counted.", "Die lokale Gruppen-Datei konnte nicht gelesen werden, deshalb konnte die Docker-Gruppenmitgliedschaft nicht gezählt werden.")
    docker_line = next((line for line in lines if line.startswith("docker:")), None)
    if docker_line is None:
        return _entry("Docker group members", "Docker-Gruppenmitglieder", "Local access", "Lokaler Zugriff", "0", "optional", "ok", "No local docker group was found. This can be normal on systems without Docker group access.", "Keine lokale Docker-Gruppe gefunden. Das kann auf Systemen ohne Docker-Gruppenzugriff normal sein.")
    members = docker_line.split(":")[-1].strip()
    count = 0 if not members else len([item for item in members.split(",") if item.strip()])
    warn_at = int(config.get("security_docker_group_warn_count", 4))
    if count >= warn_at:
        return _entry("Docker group members", "Docker-Gruppenmitglieder", "Local access", "Lokaler Zugriff", count, "review", "warn", "Several accounts appear to have Docker group access. Only the count is shown, not names. Review during maintenance.", "Mehrere Konten scheinen Docker-Gruppenzugriff zu haben. Es wird nur die Anzahl angezeigt, keine Namen. Prüfe das bei Wartung.")
    return _entry("Docker group members", "Docker-Gruppenmitglieder", "Local access", "Lokaler Zugriff", count, "present", "ok", "Docker group access count looks small. Names are intentionally not shown.", "Die Anzahl der Docker-Gruppenzugriffe wirkt klein. Namen werden absichtlich nicht angezeigt.")


def _check_sensitive_file_permissions(config):
    checked = 0
    suspicious = 0
    unreadable = 0
    for raw_path, bad_mask in SENSITIVE_PERMISSION_TARGETS:
        path = Path(raw_path)
        if not path.exists():
            continue
        checked += 1
        try:
            mode = path.stat().st_mode & 0o777
        except Exception:
            unreadable += 1
            continue
        if mode & bad_mask:
            suspicious += 1
    if suspicious:
        return _entry("Sensitive file permissions", "Sensible Datei-Rechte", "Integrity", "Integrität", f"{suspicious}/{checked}", "critical", "critical", "One or more sensitive files appear group- or world-writable. Review permissions manually. No file was changed.", "Eine oder mehrere sensible Dateien wirken gruppen- oder weltweit schreibbar. Prüfe die Rechte manuell. Es wurde keine Datei verändert.")
    if unreadable:
        return _entry("Sensitive file permissions", "Sensible Datei-Rechte", "Integrity", "Integrität", f"unreadable {unreadable}/{checked}", "unknown", "unknown", "Some sensitive file permissions could not be read without extra permissions.", "Einige sensible Datei-Rechte konnten ohne zusätzliche Rechte nicht gelesen werden.")
    if checked == 0:
        return _entry("Sensitive file permissions", "Sensible Datei-Rechte", "Integrity", "Integrität", "not found", "optional", "ok", "No configured sensitive permission targets were found at common paths.", "Keine konfigurierten sensiblen Rechte-Ziele wurden an den üblichen Pfaden gefunden.")
    return _entry("Sensitive file permissions", "Sensible Datei-Rechte", "Integrity", "Integrität", f"{checked} checked", "calm", "ok", "Basic permission check for common sensitive files looks calm. File contents were not read or displayed.", "Die einfache Rechteprüfung für übliche sensible Dateien wirkt ruhig. Dateiinhalte wurden nicht gelesen oder angezeigt.")


def _check_hostname():
    try:
        value = socket.gethostname()
    except Exception:
        value = "unknown"
    return _entry("Host identity", "Host-Identität", "Context", "Kontext", value, "ok", "ok", "Local hostname context for this static snapshot.", "Lokaler Hostname-Kontext für diesen statischen Schnappschuss.")


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
    if bool(config.get("security_check_reboot_required", True)):
        entries.append(_check_reboot_required(config))
    if bool(config.get("security_check_firewall_visibility", True)):
        entries.append(_check_firewall_visibility(config))
    if bool(config.get("security_check_ssh_config", True)):
        entries.append(_check_ssh_config(config))
    if bool(config.get("security_check_docker_group", True)):
        entries.append(_check_docker_group(config))
    if bool(config.get("security_check_sensitive_file_permissions", True)):
        entries.append(_check_sensitive_file_permissions(config))
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
    return f"<div class='card {html.escape(css_class)}'><span>{l10n_text(label_en, label_de)}</span><strong>{html.escape(str(value))}</strong><small class='state state-{html.escape(state)}'>{html.escape(state.upper())}</small></div>"


def _summary_cards(entries):
    counts = _summary_counts(entries)
    return "\n".join([
        _card("card-total", "Signals", "Signale", counts["total"], "ok" if counts["total"] else "unknown"),
        _card("card-ok", "OK", "OK", counts["ok"], "ok"),
        _card("card-warn", "Review", "Prüfen", counts["warn"], "warn" if counts["warn"] else "ok"),
        _card("card-critical", "Critical", "Kritisch", counts["critical"], "critical" if counts["critical"] else "ok"),
        _card("card-unknown", "Unknown", "Unbekannt", counts["unknown"], "unknown" if counts["unknown"] else "ok"),
    ])


def _overall_recommendation(overall):
    if overall == "critical":
        return l10n_text("Security Pulse found a critical review signal. Inspect the critical row first. No automatic change was made.", "Security Pulse hat ein kritisches Prüfsignal gefunden. Prüfe zuerst die kritische Zeile. Es wurde nichts automatisch geändert.")
    if overall == "warn":
        return l10n_text("Some local security signals should be reviewed. This does not prove a problem; it highlights where to look.", "Einige lokale Sicherheitssignale sollten geprüft werden. Das beweist kein Problem; es zeigt nur, wo du hinschauen solltest.")
    if overall == "unknown":
        return l10n_text("Some security signals could not be read without extra permissions or tools. Review manually if needed.", "Einige Sicherheitssignale konnten ohne zusätzliche Rechte oder Tools nicht gelesen werden. Prüfe bei Bedarf manuell.")
    return l10n_text("Basic local security signals look calm. Security Pulse did not change anything.", "Die einfachen lokalen Sicherheitssignale wirken ruhig. Security Pulse hat nichts geändert.")


def _entry_row(entry):
    return f"<tr><td><strong>{entry.name}</strong></td><td>{entry.area}</td><td><code>{html.escape(entry.value)}</code></td><td>{entry.state}</td><td><span class='sev-badge sev-{html.escape(entry.severity)}'>{html.escape(entry.severity.upper())}</span></td><td>{entry.note}</td></tr>"


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
            <tbody>{rows}</tbody>
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


def generate_security_pulse(output_path="security.html", template_path="security_template.html", config_path=None, state_path=".security_pulse_state.json"):
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
            html_text = html_text.replace(f"<p>{l10n_text('No security refresh warnings.', 'Keine Sicherheits-Aktualisierungswarnungen.')}</p>", f"<p>{error}</p>")
            path.write_text(html_text, encoding="utf-8")
        return False
