"""Bounded cross-page collection overview, not an inferred health verdict.

Uses the six existing static page generators and their boolean return values.
No extra collection, state access, subprocess or network request.
"""
from __future__ import annotations

import html
from pathlib import Path

from i18n_static import l10n_text

PAGES = ("containers", "hardware", "ports", "storage", "services", "security")


def collection_summary(results: dict[str, object]) -> str:
    rows = []
    successful = 0
    unknown = 0
    for name in PAGES:
        result = results.get(name)
        if result is True:
            successful += 1
            en, de = "refreshed", "aktualisiert"
        elif result is False:
            en, de = "collection failed", "Erfassung fehlgeschlagen"
        else:
            unknown += 1
            en, de = "not confirmed", "nicht bestätigt"
        rows.append("<tr><td>" + html.escape(name.title()) + "</td><td>" +
                    l10n_text(en, de) + "</td></tr>")
    lead = l10n_text(
        f"{successful} of 6 collectors completed; {unknown} unconfirmed.",
        f"{successful} von 6 Datenerfassungen abgeschlossen; {unknown} nicht bestätigt."
    )
    return (
        '<section class="pulse-suite-summary" aria-label="Pulse Suite collection results" '
        'style="margin-top:24px;padding:16px;border:1px solid var(--panel-line);'
        'border-radius:var(--radius-lg)">'
        '<section class="table-title"><h2>' +
        l10n_text("Suite collection overview", "Übergreifender Erfassungsstatus") +
        '</h2><span>' + lead + '</span></section>'
        '<p>' + l10n_text(
            "Collection status is not system health. An unavailable page does not prove an outage, "
            "and different warnings do not establish a common cause.",
            "Der Erfassungsstatus ist kein Systemgesundheitsurteil. Eine nicht verfügbare Seite "
            "beweist keinen Ausfall und gleichzeitige Warnungen keine gemeinsame Ursache."
        ) + '</p><div class="table-shell"><table><thead><tr><th>Area</th><th>Status</th>'
        '</tr></thead><tbody>' + "".join(rows) + '</tbody></table></div></section>'
    )



def application_checks_summary(entries: list[dict] | None, collected: bool) -> str:
    """Existing configured checks only, collected locally by Services Pulse."""
    if not collected or entries is None:
        body = "<p>" + l10n_text(
            "Service collection unavailable. Application health is unknown.",
            "Dienst-Erfassung nicht verfügbar. Anwendungszustand unbekannt.") + "</p>"
    elif not entries:
        body = "<p>" + l10n_text(
            "No application checks configured. This is not proof of healthy applications.",
            "Keine Anwendungschecks konfiguriert. Das beweist keine gesunden Anwendungen.") + "</p>"
    else:
        rows = []
        for entry in entries[:100]:
            severity = str(entry.get("severity", "unknown"))
            if severity not in ("ok", "warn", "critical", "unknown"):
                severity = "unknown"
            latency = entry.get("latency_ms")
            latency_text = "-" if not isinstance(latency, (int, float)) or not (0 <= latency < 1_000_000) else f"{latency:.0f} ms"
            rows.append("<tr><td>" + html.escape(str(entry.get("name", "-"))[:120]) +
                        "</td><td>" + html.escape(str(entry.get("type", "unknown"))[:30]) +
                        "</td><td>" + html.escape(str(entry.get("state", "unknown"))[:30]) +
                        "</td><td>" + html.escape(severity.upper()) +
                        "</td><td>" + html.escape(latency_text) + "</td></tr>")
        body = ("<p>" + l10n_text(
            "Only explicitly configured checks from this computer. No automatic association with remote Docker contexts, and no root-cause claim.",
            "Nur ausdrücklich konfigurierte Checks von diesem Rechner. Keine automatische Zuordnung zu entfernten Docker-Contexts und keine Ursachenbehauptung.") +
            "</p><div class='table-shell'><table><thead><tr><th>" +
            l10n_text("Application", "Anwendung") + "</th><th>" +
            l10n_text("Check", "Prüfung") + "</th><th>" +
            l10n_text("State", "Zustand") + "</th><th>Status</th><th>" +
            l10n_text("Latency", "Latenz") + "</th></tr></thead><tbody>" +
            "".join(rows) + "</tbody></table></div>")
    return ('<section class="pulse-app-summary" aria-label="Application check results" '
            'style="margin-top:24px;padding:16px;border:1px solid var(--panel-line);'
            'border-radius:var(--radius-lg)"><section class="table-title"><h2>' +
            l10n_text("Application checks", "Anwendungschecks") +
            '</h2></section>' + body + '</section>')


def add_suite_summary(output_path: str | Path, results: dict[str, object],
                      service_entries: list[dict] | None = None) -> bool:
    """Modify only the existing generated Container Pulse output; idempotent."""
    path = Path(output_path)
    if not path.is_file():
        return False
    source = path.read_text(encoding="utf-8")
    marker = '<section class="feature-strip" aria-label="Design principles">'
    if marker not in source or 'class="pulse-suite-summary"' in source:
        return False
    source = source.replace(
        marker,
        collection_summary(results) +
        application_checks_summary(service_entries, results.get("services") is True) +
        "\n" + marker, 1)
    path.write_text(source, encoding="utf-8")
    return True
