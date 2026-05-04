import html
import json
import socket
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from i18n_static import l10n_text

DEFAULT_SERVICES_CONFIG = {
    "refresh_seconds": 60,
    "service_check_timeout_seconds": 2.0,
    "service_allow_external_urls": False,
    "service_checks": [],
}

SEVERITY_RANK = {"ok": 0, "unknown": 1, "warn": 2, "critical": 3}
SEVERITY_SORT = {"critical": 0, "warn": 1, "unknown": 2, "ok": 3}

LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


@dataclass(frozen=True)
class ServiceEntry:
    name: str
    check_type: str
    target: str
    state: str
    severity: str
    latency_ms: float | None
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
    config = dict(DEFAULT_SERVICES_CONFIG)
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
    if not isinstance(config.get("service_checks"), list):
        config["service_checks"] = []
    return config


def _overall(entries):
    if not entries:
        return "unknown"
    return max((entry.severity for entry in entries), key=lambda item: SEVERITY_RANK.get(item, 0))


def _is_local_url(url):
    try:
        parsed = urlparse(url)
    except Exception:
        return False
    host = parsed.hostname or ""
    return host in LOCAL_HOSTS or host.startswith("127.")


def _target_from_check(check):
    check_type = str(check.get("type", "")).lower().strip()
    if check_type in {"url", "http"}:
        return str(check.get("url") or "")
    if check_type == "tcp":
        host = str(check.get("host") or "localhost")
        port = str(check.get("port") or "")
        return f"{host}:{port}" if port else host
    if check_type in {"heartbeat", "file_age"}:
        return str(check.get("path") or "")
    return str(check.get("target") or "-")


def _entry_unknown(name, check_type, target, message_en, message_de):
    return ServiceEntry(
        name=name,
        check_type=check_type or "unknown",
        target=target or "-",
        state="unknown",
        severity="unknown",
        latency_ms=None,
        note=l10n_text(message_en, message_de),
    )


def _check_url(check, config):
    name = str(check.get("name") or check.get("url") or "HTTP check")
    url = str(check.get("url") or "")
    timeout = float(check.get("timeout_seconds", config.get("service_check_timeout_seconds", 2.0)))
    allow_external = bool(check.get("allow_external", config.get("service_allow_external_urls", False)))
    expected_status = int(check.get("expected_status", 200))

    if not url:
        return _entry_unknown(name, "url", "-", "No URL configured.", "Keine URL konfiguriert.")
    if not allow_external and not _is_local_url(url):
        return _entry_unknown(
            name,
            "url",
            url,
            "External URL checks are disabled by default. Set allow_external true for this check if intended.",
            "Externe URL-Checks sind standardmäßig deaktiviert. Setze allow_external true für diesen Check, wenn das beabsichtigt ist.",
        )

    request = urllib.request.Request(url, method="GET", headers={"User-Agent": "ServicesPulse/1.0"})
    start = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            latency_ms = (time.monotonic() - start) * 1000.0
            status = int(response.getcode())
    except urllib.error.HTTPError as exc:
        latency_ms = (time.monotonic() - start) * 1000.0
        status = int(exc.code)
    except Exception as exc:
        return ServiceEntry(
            name=name,
            check_type="url",
            target=url,
            state="down",
            severity="critical",
            latency_ms=None,
            note=l10n_text(
                f"URL did not respond successfully: {exc}",
                f"URL hat nicht erfolgreich geantwortet: {exc}",
            ),
        )

    if status == expected_status:
        return ServiceEntry(
            name=name,
            check_type="url",
            target=url,
            state="up",
            severity="ok",
            latency_ms=latency_ms,
            note=l10n_text(
                f"HTTP responded with expected status {status}.",
                f"HTTP antwortete mit erwartetem Status {status}.",
            ),
        )
    return ServiceEntry(
        name=name,
        check_type="url",
        target=url,
        state="review",
        severity="warn",
        latency_ms=latency_ms,
        note=l10n_text(
            f"HTTP responded with status {status}; expected {expected_status}.",
            f"HTTP antwortete mit Status {status}; erwartet war {expected_status}.",
        ),
    )


def _check_tcp(check, config):
    name = str(check.get("name") or "TCP check")
    host = str(check.get("host") or "localhost")
    port = check.get("port")
    timeout = float(check.get("timeout_seconds", config.get("service_check_timeout_seconds", 2.0)))
    try:
        port_int = int(port)
    except Exception:
        return _entry_unknown(name, "tcp", f"{host}:{port}", "No valid TCP port configured.", "Kein gültiger TCP-Port konfiguriert.")

    start = time.monotonic()
    try:
        with socket.create_connection((host, port_int), timeout=timeout):
            latency_ms = (time.monotonic() - start) * 1000.0
    except Exception as exc:
        return ServiceEntry(
            name=name,
            check_type="tcp",
            target=f"{host}:{port_int}",
            state="closed",
            severity="critical",
            latency_ms=None,
            note=l10n_text(
                f"TCP connection failed: {exc}",
                f"TCP-Verbindung fehlgeschlagen: {exc}",
            ),
        )

    return ServiceEntry(
        name=name,
        check_type="tcp",
        target=f"{host}:{port_int}",
        state="open",
        severity="ok",
        latency_ms=latency_ms,
        note=l10n_text(
            "TCP port accepted a connection.",
            "TCP-Port hat eine Verbindung angenommen.",
        ),
    )


def _check_heartbeat(check, config):
    name = str(check.get("name") or "Heartbeat file")
    raw_path = str(check.get("path") or "").strip()
    max_age_seconds = float(check.get("max_age_seconds", 300))
    if not raw_path:
        return _entry_unknown(name, "heartbeat", "-", "No heartbeat file path configured.", "Kein Heartbeat-Dateipfad konfiguriert.")
    path = Path(raw_path)
    if not path.exists():
        return ServiceEntry(
            name=name,
            check_type="heartbeat",
            target=str(path),
            state="missing",
            severity="critical",
            latency_ms=None,
            note=l10n_text(
                "Heartbeat file does not exist. The service may not be writing its heartbeat.",
                "Heartbeat-Datei existiert nicht. Der Dienst schreibt seinen Heartbeat möglicherweise nicht.",
            ),
        )
    try:
        age_seconds = max(0.0, time.time() - path.stat().st_mtime)
    except Exception as exc:
        return _entry_unknown(
            name,
            "heartbeat",
            str(path),
            f"Heartbeat file age could not be read: {exc}",
            f"Alter der Heartbeat-Datei konnte nicht gelesen werden: {exc}",
        )

    if age_seconds <= max_age_seconds:
        return ServiceEntry(
            name=name,
            check_type="heartbeat",
            target=str(path),
            state="fresh",
            severity="ok",
            latency_ms=None,
            note=l10n_text(
                f"Heartbeat is fresh: {age_seconds:.0f}s old.",
                f"Heartbeat ist frisch: {age_seconds:.0f}s alt.",
            ),
        )
    return ServiceEntry(
        name=name,
        check_type="heartbeat",
        target=str(path),
        state="stale",
        severity="warn",
        latency_ms=None,
        note=l10n_text(
            f"Heartbeat is stale: {age_seconds:.0f}s old; expected under {max_age_seconds:.0f}s.",
            f"Heartbeat ist alt: {age_seconds:.0f}s; erwartet unter {max_age_seconds:.0f}s.",
        ),
    )


def _collect_services(config):
    entries = []
    for raw in config.get("service_checks") or []:
        if not isinstance(raw, dict):
            continue
        check_type = str(raw.get("type", "")).lower().strip()
        if check_type in {"url", "http"}:
            entries.append(_check_url(raw, config))
        elif check_type == "tcp":
            entries.append(_check_tcp(raw, config))
        elif check_type in {"heartbeat", "file_age"}:
            entries.append(_check_heartbeat(raw, config))
        else:
            entries.append(
                _entry_unknown(
                    str(raw.get("name") or "Unknown check"),
                    check_type or "unknown",
                    _target_from_check(raw),
                    "Unsupported service check type.",
                    "Nicht unterstützter Dienst-Check-Typ.",
                )
            )
    entries.sort(key=lambda item: (SEVERITY_SORT.get(item.severity, 9), item.name.lower()))
    return entries


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
            _card("card-total", "Checks", "Checks", counts["total"], "ok" if counts["total"] else "unknown"),
            _card("card-ok", "OK", "OK", counts["ok"], "ok"),
            _card("card-warn", "Review", "Prüfen", counts["warn"], "warn" if counts["warn"] else "ok"),
            _card("card-critical", "Critical", "Kritisch", counts["critical"], "critical" if counts["critical"] else "ok"),
            _card("card-unknown", "Unknown", "Unbekannt", counts["unknown"], "unknown" if counts["unknown"] else "ok"),
        ]
    )


def _format_latency(value):
    if value is None:
        return "-"
    return f"{value:.0f} ms"


def _type_label(check_type):
    labels = {
        "url": ("HTTP URL", "HTTP-URL"),
        "http": ("HTTP URL", "HTTP-URL"),
        "tcp": ("TCP port", "TCP-Port"),
        "heartbeat": ("heartbeat file", "Heartbeat-Datei"),
        "file_age": ("heartbeat file", "Heartbeat-Datei"),
        "unknown": ("unknown", "unbekannt"),
    }
    return l10n_text(*labels.get(check_type, (check_type, check_type)))


def _state_label(state):
    labels = {
        "up": ("up", "erreichbar"),
        "down": ("down", "nicht erreichbar"),
        "review": ("review", "prüfen"),
        "open": ("open", "offen"),
        "closed": ("closed", "geschlossen"),
        "fresh": ("fresh", "frisch"),
        "stale": ("stale", "alt"),
        "missing": ("missing", "fehlt"),
        "unknown": ("unknown", "unbekannt"),
    }
    return l10n_text(*labels.get(state, (state, state)))


def _entry_row(entry):
    target = html.escape(entry.target)
    return (
        "<tr>"
        f"<td><strong>{html.escape(entry.name)}</strong></td>"
        f"<td>{_type_label(entry.check_type)}</td>"
        f"<td><code title='{target}'>{target}</code></td>"
        f"<td>{_state_label(entry.state)}</td>"
        f"<td>{html.escape(_format_latency(entry.latency_ms))}</td>"
        f"<td><span class='sev-badge sev-{html.escape(entry.severity)}'>{html.escape(entry.severity.upper())}</span></td>"
        f"<td>{entry.note}</td>"
        "</tr>"
    )


def _overall_recommendation(overall, entries):
    if not entries:
        return l10n_text(
            "No service checks are configured yet. Add explicit checks in config.example.yaml or your own config file.",
            "Noch keine Dienst-Checks konfiguriert. Ergänze gezielte Checks in config.example.yaml oder deiner eigenen Config-Datei.",
        )
    if overall == "critical":
        return l10n_text(
            "At least one service check failed. Review the critical rows first. Services Pulse only observes; it does not restart anything.",
            "Mindestens ein Dienst-Check ist fehlgeschlagen. Prüfe zuerst die kritischen Zeilen. Services Pulse beobachtet nur; es startet nichts neu.",
        )
    if overall == "warn":
        return l10n_text(
            "Some service checks need review, but no automatic action was taken.",
            "Einige Dienst-Checks müssen geprüft werden, aber es wurde keine automatische Aktion ausgeführt.",
        )
    if overall == "unknown":
        return l10n_text(
            "Some checks could not be evaluated. Review their configuration.",
            "Einige Checks konnten nicht bewertet werden. Prüfe deren Konfiguration.",
        )
    return l10n_text(
        "Configured service checks look healthy.",
        "Die konfigurierten Dienst-Checks sehen gesund aus.",
    )


def _services_table(entries):
    if not entries:
        return f"""
      <section class="health-panel" aria-label="Service checks notice">
        <div class="health-head">
          <h2>{l10n_text('Configured Service Checks', 'Konfigurierte Dienst-Checks')}</h2>
          <span class="pill">{l10n_text('No checks configured', 'Keine Checks konfiguriert')}</span>
        </div>
        <section class="messages" aria-label="Service setup help">
          <p><strong>{l10n_text('Plain meaning', 'Einfache Bedeutung')}</strong>: {l10n_text('Services Pulse does not guess your important services. You explicitly configure what should be checked.', 'Services Pulse rät nicht, welche Dienste wichtig sind. Du konfigurierst ausdrücklich, was geprüft werden soll.')}</p>
          <p>{l10n_text('Supported first checks: local HTTP URL, TCP port, and heartbeat file age.', 'Erste unterstützte Checks: lokale HTTP-URL, TCP-Port und Alter einer Heartbeat-Datei.')}</p>
        </section>
      </section>
""".rstrip()

    rows = "\n".join(_entry_row(entry) for entry in entries)
    counts = _summary_counts(entries)
    return f"""
      <section class="health-panel" aria-label="Service check details">
        <div class="health-head">
          <h2>{l10n_text('Configured Service Checks', 'Konfigurierte Dienst-Checks')}</h2>
          <span class="pill">{l10n_text('Read-only checks', 'Nur lesende Checks')}</span>
        </div>
        <section class="messages" aria-label="Service plain summary">
          <p><strong>{l10n_text('Plain meaning', 'Einfache Bedeutung')}</strong>: {l10n_text('Services Pulse checks only targets you explicitly configure. It does not restart, stop, or change services.', 'Services Pulse prüft nur Ziele, die du ausdrücklich konfigurierst. Es startet, stoppt oder verändert keine Dienste.')}</p>
          <p>{l10n_text('Summary', 'Zusammenfassung')}: {counts['total']} Checks · OK {counts['ok']} · WARN {counts['warn']} · CRITICAL {counts['critical']} · UNKNOWN {counts['unknown']}</p>
        </section>
        <section class="table-shell" aria-label="Service checks table">
          <table>
            <thead>
              <tr>
                <th>{l10n_text('Name', 'Name')}</th>
                <th>{l10n_text('Type', 'Typ')}</th>
                <th>{l10n_text('Target', 'Ziel')}</th>
                <th>{l10n_text('State', 'Zustand')}</th>
                <th>{l10n_text('Latency', 'Latenz')}</th>
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
        "{{TITLE}}": "SERVICES PULSE",
        "{{REFRESH_SECONDS}}": str(int(config.get("refresh_seconds", 60))),
        "{{GENERATED_AT}}": html.escape(generated_at),
        "{{LAST_SUCCESS_AT}}": html.escape(previous_last_success),
        "{{OVERALL}}": html.escape(overall.upper()),
        "{{OVERALL_CLASS}}": html.escape(overall),
        "{{RECOMMENDATION}}": _overall_recommendation(overall, entries),
        "{{SUMMARY_CARDS}}": _summary_cards(entries),
        "{{SERVICES_TABLE}}": _services_table(entries),
        "{{MESSAGES}}": f"<p>{l10n_text('No service refresh warnings.', 'Keine Dienst-Aktualisierungswarnungen.')}</p>",
    }
    html_text = template
    for key, value in replacements.items():
        html_text = html_text.replace(key, value)
    Path(output_path).write_text(html_text, encoding="utf-8")


def generate_services_pulse(
    output_path="services.html",
    template_path="services_template.html",
    config_path=None,
    state_path=".services_pulse_state.json",
):
    generated_at = _now()
    previous_last_success = _read_last_success(state_path)
    config = dict(DEFAULT_SERVICES_CONFIG)
    try:
        config = _load_config(config_path)
        entries = _collect_services(config)
        _render(template_path, output_path, generated_at, previous_last_success, config, entries)
        _write_last_success(state_path, generated_at)
        return True
    except Exception as exc:
        _render(template_path, output_path, generated_at, previous_last_success, config, [])
        path = Path(output_path)
        if path.exists():
            html_text = path.read_text(encoding="utf-8")
            error = l10n_text(f"Services refresh failed: {exc}", f"Dienst-Aktualisierung fehlgeschlagen: {exc}")
            html_text = html_text.replace(
                f"<p>{l10n_text('No service refresh warnings.', 'Keine Dienst-Aktualisierungswarnungen.')}</p>",
                f"<p>{error}</p>",
            )
            path.write_text(html_text, encoding="utf-8")
        return False
