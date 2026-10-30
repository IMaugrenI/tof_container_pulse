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



def operator_diagnostic_hint(app_status: str, docker_status: str) -> tuple[str, str]:
    """Deterministic human guidance; never an autonomous action or diagnosis."""
    if docker_status == "not_collected":
        return ("Docker listing unavailable; host state is unknown. Check collection access manually.",
                "Docker-Abfrage nicht verfügbar; Hostzustand unbekannt. Erfassungszugang manuell prüfen.")
    if docker_status == "not_observed":
        return ("No matching Compose service observed. Verify the declared project/service; outage not confirmed.",
                "Kein passender Compose-Dienst beobachtet. Projekt/Dienstzuordnung prüfen; Ausfall nicht bestätigt.")
    if docker_status == "mixed":
        return ("Mixed container replica states; inspect instances separately.",
                "Unterschiedliche Containerzustände; Instanzen einzeln prüfen.")
    if app_status == "unknown":
        return ("Application check unavailable or ambiguous; verify the declared check.",
                "Anwendungscheck fehlt oder ist uneindeutig; Checkzuordnung prüfen.")
    if app_status in ("critical", "warn") and docker_status in ("critical", "warn"):
        return ("Both checks show issues. Review each independently; no common cause established.",
                "Beide Prüfungen zeigen Probleme. Unabhängig prüfen; gemeinsame Ursache nicht belegt.")
    if app_status in ("critical", "warn") and docker_status == "ok":
        return ("Application check reports a problem despite Docker OK. Review endpoint and app behavior manually.",
                "Anwendungscheck meldet Problem trotz Docker OK. Endpunkt und Anwendung manuell prüfen.")
    if app_status == "ok" and docker_status in ("critical", "warn"):
        return ("Probe succeeds despite container warning. Verify the declared association and all replicas.",
                "Probe erfolgreich trotz Containerwarnung. Zuordnung und Replikate prüfen.")
    return ("Observed checks show no conflict; one snapshot does not prove ongoing health.",
            "Beobachtete Checks widersprechen sich nicht; Momentaufnahme beweist keine Dauerverfügbarkeit.")


def declared_link_summary(links: object, docker: dict | None,
                          app_entries: list[dict] | None, app_collected: bool) -> str:
    """Operator-declared observation links only; no inferred relationship or causality."""
    if not links:
        return ""
    if not isinstance(links, list) or len(links) > 50:
        return ("<p>" + l10n_text(
            "Application links ignored: expected at most 50 explicit declarations.",
            "Anwendungsverknüpfungen ignoriert: maximal 50 ausdrückliche Zuordnungen erlaubt.") + "</p>")
    docker = docker or {}
    observed_hosts = set(docker.get("successful_hosts") or [])
    docker_rows = docker.get("containers") or []
    apps_by_name: dict[str, list[dict]] = {}
    for entry in (app_entries or []):
        apps_by_name.setdefault(str(entry.get("name", "")), []).append(entry)
    rows = []
    for link in links:
        if not isinstance(link, dict):
            continue
        check = str(link.get("check", ""))[:120]
        host = str(link.get("host", ""))[:120]
        project = str(link.get("project", ""))[:120]
        service = str(link.get("service", ""))[:120]
        if not all((check, host, project, service)):
            continue
        app_matches = apps_by_name.get(check, []) if app_collected else []
        app_status = str(app_matches[0].get("severity", "unknown")) if len(app_matches) == 1 else "unknown"
        if app_status not in ("ok", "warn", "critical", "unknown"):
            app_status = "unknown"
        docker_matches = [
            item for item in docker_rows
            if item.get("host") == host and item.get("project") == project and item.get("service") == service
        ] if host in observed_hosts else []
        if host not in observed_hosts:
            container_status = "not_collected"
        elif not docker_matches:
            container_status = "not_observed"
        else:
            statuses = {str(item.get("severity", "unknown")) for item in docker_matches}
            container_status = next(iter(statuses)) if len(statuses) == 1 else "mixed"
        recommendation = l10n_text(*operator_diagnostic_hint(app_status, container_status))
        rows.append("<tr><td>" + html.escape(check) + "</td><td>" +
                    html.escape(host) + " / " + html.escape(project) + " / " +
                    html.escape(service) + "</td><td>" +
                    html.escape(app_status.upper()) + "</td><td>" +
                    html.escape(container_status.upper()) + "</td><td>" +
                    recommendation + "</td></tr>")
    if not rows:
        return ""
    return ('<section class="pulse-declared-links" aria-label="Declared application links" '
            'style="margin-top:24px;padding:16px;border:1px solid var(--panel-line);'
            'border-radius:var(--radius-lg)"><section class="table-title"><h2>' +
            l10n_text("Declared infrastructure links", "Deklarierte Infrastrukturverknüpfungen") +
            '</h2></section><p>' + l10n_text(
                "Only links explicitly declared by the operator. States are independent observations, not dependency or causal proof. "
                "NOT OBSERVED is not DOWN; NOT COLLECTED is unknown.",
                "Nur ausdrücklich vom Betreiber deklarierte Zuordnungen. Zustände sind unabhängige Beobachtungen, kein Abhängigkeits- oder Ursachenbeweis. "
                "NICHT BEOBACHTET ist kein Ausfall; NICHT ERFASST ist unbekannt.") +
            '</p><div class="table-shell"><table><thead><tr><th>' +
            l10n_text("Check", "Check") + '</th><th>Host / Compose</th><th>' +
            l10n_text("Application", "Anwendung") + '</th><th>Docker</th><th>' +
            l10n_text("Manual diagnostic hint", "Manueller Diagnosehinweis") +
            '</th></tr></thead><tbody>' +
            "".join(rows) + '</tbody></table></div></section>')


def add_suite_summary(output_path: str | Path, results: dict[str, object],
                      service_entries: list[dict] | None = None, docker_evidence: dict | None = None,
                      application_links: object = None) -> bool:
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
        declared_link_summary(application_links, docker_evidence, service_entries,
                              results.get("services") is True) +
        "\n" + marker, 1)
    path.write_text(source, encoding="utf-8")
    return True
