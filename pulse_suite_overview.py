"""Bounded cross-page collection overview, not an inferred health verdict.

Uses the six existing static page generators and their boolean return values.
No extra collection, state access, subprocess or network request.
"""
from __future__ import annotations

import html
from pathlib import Path

from i18n_static import l10n_text

PAGES = ("containers", "hardware", "ports", "storage", "services", "security")


def collection_quality(name: str, result: object, docker: dict | None = None,
                       services: list[dict] | None = None) -> tuple[str, str, str]:
    """Collection evidence, never system health or a causal assertion."""
    if result is False:
        return "unavailable", "collection failed", "Erfassung fehlgeschlagen"
    if result is not True:
        return "unconfirmed", "not confirmed", "nicht bestätigt"
    if name == "containers" and docker is not None and "successful_hosts" in docker:
        good = len(docker.get("successful_hosts") or [])
        failed = len(docker.get("failed_hosts") or [])
        if not good:
            return "unavailable", "no Docker hosts collected", "keine Docker-Hosts erfasst"
        if failed:
            return "partial", "partial Docker collection", "Docker-Erfassung teilweise"
    if name == "services" and services is not None:
        if not services:
            return "not_configured", "no checks configured", "keine Prüfungen konfiguriert"
        recognized = {"ok", "warn", "critical"}
        if not any(item.get("severity") in recognized for item in services):
            return "unavailable", "no evaluable check results", "keine auswertbaren Prüfergebnisse"
        if any(item.get("severity") == "unknown" for item in services):
            return "partial", "checks include unknown results", "Prüfungen mit unbekannten Ergebnissen"
    return "collected", "refreshed", "aktualisiert"


def collection_summary(results: dict[str, object], docker_evidence: dict | None = None,
                       service_entries: list[dict] | None = None,
                       completed_at: dict[str, str] | None = None) -> str:
    """Display per-collector provenance without inventing platform or host health."""
    rows = []
    successful = 0
    unknown = 0
    for name in PAGES:
        result = results.get(name)
        quality, en, de = collection_quality(name, result, docker_evidence, service_entries)
        if quality in ("collected", "partial"):
            successful += 1
        elif quality == "unconfirmed":
            unknown += 1
        scope_en, scope_de = (
            ("configured Docker hosts", "konfigurierte Docker-Hosts") if name == "containers"
            else ("configured checks from this computer", "konfigurierte Prüfungen dieses Rechners") if name == "services"
            else ("this computer", "dieser Rechner")
        )
        evidence = ""
        if name == "containers" and docker_evidence is not None and "successful_hosts" in docker_evidence:
            good = len(docker_evidence.get("successful_hosts") or [])
            failed = len(docker_evidence.get("failed_hosts") or [])
            evidence = l10n_text(f"{good} hosts collected, {failed} unavailable",
                                 f"{good} Hosts erfasst, {failed} nicht verfügbar")
        elif name == "services" and service_entries is not None:
            unknown_checks = sum(1 for item in service_entries if item.get("severity") == "unknown")
            evidence = l10n_text(f"{len(service_entries)} configured results; {unknown_checks} unknown",
                                 f"{len(service_entries)} Prüfergebnisse; {unknown_checks} unbekannt")
        stamp = str((completed_at or {}).get(name, ""))[:48]
        rows.append("<tr><td>" + html.escape(name.title()) + "</td><td>" +
                    l10n_text(en, de) + "</td><td>" +
                    l10n_text(scope_en, scope_de) + "</td><td>" +
                    html.escape(evidence or "-") + "</td><td>" +
                    html.escape(stamp or "-") + "</td></tr>")
    lead = l10n_text(
        f"{successful} of 6 collectors completed; {unknown} unconfirmed.",
        f"{successful} von 6 Datenerfassungen abgeschlossen; {unknown} nicht bestätigt."
    )
    return (
        '<section id="pulse-suite-summary" class="pulse-suite-summary" aria-label="Pulse Suite collection results" '
        'style="margin-top:24px;padding:16px;border:1px solid var(--panel-line);'
        'border-radius:var(--radius-lg)">'
        '<section class="table-title"><h2>' +
        l10n_text("Suite collection overview", "Übergreifender Erfassungsstatus") +
        '</h2><span>' + lead + '</span></section>'
        '<p>' + l10n_text(
            "Collection status is not system health. An unavailable page does not prove an outage, "
            "and different warnings do not establish a common cause. Timestamps are collection completion times in UTC, "
            "not individual metric sampling times.",
            "Der Erfassungsstatus ist kein Systemgesundheitsurteil. Eine nicht verfügbare Seite "
            "beweist keinen Ausfall und gleichzeitige Warnungen keine gemeinsame Ursache. Zeitstempel zeigen den "
            "Abschluss der Erfassung in UTC, nicht die Messzeit einzelner Werte."
        ) + '</p><div class="table-shell"><table><thead><tr><th>' +
        l10n_text("Area", "Bereich") + '</th><th>' + l10n_text("Quality", "Erfassungsqualität") +
        '</th><th>' + l10n_text("Scope", "Geltungsbereich") + '</th><th>' +
        l10n_text("Evidence", "Nachweis") + '</th><th>' +
        l10n_text("Completed UTC", "Abgeschlossen UTC") +
        '</th></tr></thead><tbody>' + "".join(rows) + '</tbody></table></div></section>'
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
    return ('<section id="pulse-app-summary" class="pulse-app-summary" aria-label="Application check results" '
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
    return ('<section id="pulse-declared-links" class="pulse-declared-links" aria-label="Declared application links" '
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


def application_history_summary(snapshots: list[dict] | None, issue: str | None = None) -> str:
    """Trend in opt-in local-check samples only; no remote-host attribution."""
    if snapshots is None and issue is None:
        return ""
    esc = lambda value: html.escape(str(value), quote=True)
    if issue:
        body = "<p>" + l10n_text(
            "Application history unavailable; prior observations are not evidence of current health.",
            "Anwendungshistorie nicht verfügbar; alte Daten beweisen keine aktuelle Verfügbarkeit.") + "</p>"
    elif not snapshots:
        body = "<p>" + l10n_text(
            "No application history saved yet. History is opt-in.",
            "Noch keine Anwendungshistorie gespeichert. Historie benötigt Zustimmung.") + "</p>"
    else:
        by_check = {}
        for snapshot in snapshots[-60:]:
            if not isinstance(snapshot, dict) or snapshot.get("scope") != "suite_local":
                continue
            stamp = str(snapshot.get("at", ""))[:48]
            for item in (snapshot.get("checks") or [])[:100]:
                if not isinstance(item, dict):
                    continue
                name = str(item.get("name", ""))[:120]
                if name:
                    by_check.setdefault(name, []).append((stamp, item))
        rows = []
        for name in sorted(by_check)[:30]:
            points = by_check[name]
            latest_at, latest = points[-1]
            severity = str(latest.get("severity", "unknown"))
            if severity not in ("ok", "warn", "critical", "unknown"):
                severity = "unknown"
            latency_values = [(stamp, value) for stamp, item in points
                              for value in [item.get("latency_ms")]
                              if isinstance(value, (int, float)) and not isinstance(value, bool)
                              and 0 <= value <= 120000]
            latency_label = "-"
            if latency_values:
                latency_label = f"{latency_values[-1][1]:.0f} ms"
                if len(latency_values) >= 3:
                    change = latency_values[-1][1] - latency_values[0][1]
                    latency_label += f" ({change:+.0f} ms vs first retained sample)"
            rows.append("<tr><td>" + esc(name) + "</td><td>" +
                        esc(len(points)) + "</td><td>" + esc(latest_at) +
                        "</td><td>" + esc(severity.upper()) +
                        "</td><td>" + esc(latency_label) + "</td></tr>")
        body = (
            '<div class="table-shell"><table><thead><tr><th>' +
            l10n_text("Check", "Check") + "</th><th>" +
            l10n_text("Samples", "Messungen") + "</th><th>" +
            l10n_text("Last collection UTC", "Letzte Erfassung UTC") + "</th><th>" +
            l10n_text("Last observed", "Zuletzt beobachtet") +
            "</th><th>" + l10n_text("Latency and retained delta", "Latenz und gespeicherte Änderung") +
            "</th></tr></thead><tbody>" + "".join(rows) +
            "</tbody></table></div>" if rows else "<p>" +
            l10n_text("No valid local application samples.", "Keine gültigen lokalen Anwendungsmessungen.") + "</p>"
        )
    return ('<section id="pulse-app-history" class="pulse-app-history" aria-label="Opt-in application history" '
            'style="margin-top:24px;padding:16px;border:1px solid var(--panel-line);'
            'border-radius:var(--radius-lg)"><section class="table-title"><h2>' +
            l10n_text("Application history", "Anwendungshistorie") +
            '</h2></section><p>' +
            l10n_text("Explicitly configured local checks only. Completion timestamps are not exact probe times. "
                      "Missing samples are not healthy, down or zero latency. No remote Docker-host inference.",
                      "Nur ausdrücklich konfigurierte lokale Checks. Abschlusszeiten sind keine genauen Prüfzeitpunkte. "
                      "Fehlende Messungen bedeuten weder gesund noch ausgefallen oder Null-Latenz. Keine Zuordnung zu Remote-Docker-Hosts.") +
            "</p>" + body + "</section>")


def infrastructure_matrix(docker_evidence: dict | None, application_links: object,
                          entries: list[dict] | None, app_collected: bool) -> str:
    """One bounded shared view: Docker Compose graph plus explicitly mapped checks."""
    docker = docker_evidence or {}
    groups = docker.get("projects") or []
    failed = docker.get("failed_hosts") or []
    if not groups and not failed:
        return ""
    esc = lambda x: html.escape(str(x), quote=True)
    known = {}
    for item in entries or []:
        known.setdefault(item.get("name"), []).append(item)
    declared = application_links if isinstance(application_links, list) and len(application_links) <= 50 else []
    sections = []
    for group in groups[:20]:
        host = str(group.get("host", ""))[:120]
        project = str(group.get("project", ""))[:120]
        services = group.get("services") or []
        edges = group.get("edges") or []
        rows = []
        for service in services[:60]:
            name = str(service.get("service", ""))[:120]
            severity = {str(x) for x in service.get("severities", [])}
            if not severity or severity - {"ok", "warn", "critical", "unknown"}:
                state = "unknown"
            else:
                state = next(iter(severity)) if len(severity) == 1 else "mixed"
            outgoing = [str(edge.get("to", ""))[:120] +
                        (" (observed)" if edge.get("present") is True else " (not observed)")
                        for edge in edges[:100] if edge.get("from") == name]
            checks = []
            for link in declared:
                if not isinstance(link, dict):
                    continue
                if link.get("host") == host and link.get("project") == project and link.get("service") == name:
                    label = str(link.get("check", ""))[:120]
                    match = known.get(label, []) if app_collected else []
                    status = match[0].get("severity", "unknown") if len(match) == 1 else "unknown"
                    if status not in ("ok", "warn", "critical", "unknown"):
                        status = "unknown"
                    checks.append(label + " (" + status.upper() + ")")
            rows.append("<tr><td>" + esc(name) + "</td><td>" + esc(state.upper()) +
                        "</td><td>" + esc("; ".join(outgoing) or "-") +
                        "</td><td>" + esc("; ".join(checks) or "-") + "</td></tr>")
        sections.append('<h3>' + esc(host) + " / " + esc(project) + '</h3><div class="table-shell"><table>'
                        '<thead><tr><th>Compose service</th><th>Docker</th><th>Explicit depends_on</th>'
                        '<th>Declared application check</th></tr></thead><tbody>' +
                        "".join(rows) + "</tbody></table></div>")
    if failed:
        sections.append("<p>" +
                        l10n_text("Docker hosts not collected: ", "Docker-Hosts nicht erfasst: ") +
                        esc(", ".join(str(h)[:120] for h in failed[:20])) +
                        ". " + l10n_text("State unknown, no outage proven.",
                                         "Zustand unbekannt, kein Ausfall bewiesen.") + "</p>")
    return ('<section id="pulse-infrastructure-matrix" class="pulse-infrastructure-matrix" aria-label="Combined infrastructure evidence" '
            'style="margin-top:24px;padding:16px;border:1px solid var(--panel-line);'
            'border-radius:var(--radius-lg)"><div class="table-title"><h2>' +
            l10n_text("Infrastructure and application evidence", "Infrastruktur- und Anwendungsnachweise") +
            '</h2></div><p>' + l10n_text(
                "Docker relationships come only from explicit Compose depends_on labels; application links only from operator declarations. "
                "Checks run on this computer, not necessarily on the Docker host. These are independent states, never causal proof.",
                "Docker-Beziehungen stammen nur aus Compose-depends_on-Labels; App-Zuordnungen nur aus Betreiberdeklarationen. "
                "Checks laufen auf diesem Rechner, nicht zwingend auf dem Docker-Host. Unabhängige Zustände, kein Ursachenbeweis.") +
            "</p>" + "".join(sections) + "</section>")


def diagnosis_queue(docker: dict | None, app_entries: list[dict] | None,
                    statuses: dict[str, object], limit: int = 12) -> list[dict]:
    """Deterministic manual queue from independent, already collected evidence."""
    docker = docker or {}
    rows = []
    for host in (docker.get("failed_hosts") or [])[:80]:
        rows.append({"source": "docker", "scope": str(host)[:120],
                     "signal": "collection_unavailable", "priority": "unknown",
                     "action": "Verify Docker context connectivity and permissions manually."})
    for item in (docker.get("containers") or [])[:1500]:
        severity = str(item.get("severity", "unknown"))
        if severity not in ("critical", "warn"):
            continue
        scope = str(item.get("host", ""))[:120] + " / " + str(item.get("project", ""))[:120] + " / " + str(item.get("service", ""))[:120]
        rows.append({"source": "docker", "scope": scope,
                     "signal": severity + "_container_observation", "priority": severity,
                     "action": "Review the individual container evidence and metrics manually."})
    if statuses.get("services") is True and app_entries is not None:
        for item in app_entries[:100]:
            severity = str(item.get("severity", "unknown"))
            if severity not in ("critical", "warn", "unknown"):
                continue
            rows.append({"source": "services", "scope": "suite_local / " + str(item.get("name", ""))[:120],
                         "signal": severity + "_configured_check", "priority": severity,
                         "action": "Review the explicitly configured check independently; this is not a Docker-host assertion."})
    elif statuses.get("services") is not True:
        rows.append({"source": "services", "scope": "suite_local", "signal": "collection_unavailable",
                     "priority": "unknown", "action": "Review Services collection before interpreting application state."})
    order = {"critical": 0, "warn": 1, "unknown": 2}
    rows.sort(key=lambda item: (order.get(item["priority"], 3), item["source"], item["scope"], item["signal"]))
    return rows[:max(0, min(limit, 12))]


def render_diagnosis_queue(docker: dict | None, app_entries: list[dict] | None,
                           statuses: dict[str, object]) -> str:
    """Rule-only triage, with uncertainty visible. No LLM or action dispatch."""
    rows = diagnosis_queue(docker, app_entries, statuses)
    esc = lambda value: html.escape(str(value), quote=True)
    if not rows:
        body = '<p>' + l10n_text(
            "No independent review signals selected. This does not prove system health.",
            "Keine einzelnen Prüfsignale ausgewählt. Dies beweist keine Systemgesundheit.") + '</p>'
    else:
        body = ('<div class="table-shell"><table><thead><tr><th>' +
                l10n_text("Priority", "Priorität") + '</th><th>' +
                l10n_text("Source / scope", "Quelle / Bereich") +
                '</th><th>' + l10n_text("Observed signal", "Beobachtetes Signal") +
                '</th><th>' + l10n_text("Manual next check", "Nächste manuelle Prüfung") +
                '</th></tr></thead><tbody>' + "".join(
                    '<tr><td>' + esc(item["priority"].upper()) + '</td><td>' +
                    esc(item["source"]) + ' / ' + esc(item["scope"]) +
                    '</td><td>' + esc(item["signal"]) + '</td><td>' +
                    esc(item["action"]) + '</td></tr>' for item in rows
                ) + '</tbody></table></div>')
    return ('<section id="pulse-triage-queue" class="pulse-triage-queue" '
            'aria-label="Evidence-based manual diagnostics" '
            'style="margin-top:24px;padding:16px;border:1px solid var(--panel-line);'
            'border-radius:var(--radius-lg)"><div class="table-title"><h2>' +
            l10n_text("Manual diagnostic queue", "Manuelle Diagnoseliste") +
            '</h2></div><p>' +
            l10n_text("Independent source observations only, capped at 12; never causal proof. "
                      "The optional local LLM requires a separate explicit CLI action.",
                      "Nur unabhängige Quellbeobachtungen, maximal 12; kein Ursachenbeweis. "
                      "Das optionale lokale LLM erfordert einen getrennten ausdrücklichen CLI-Aufruf.") +
            '</p>' + body + '</section>')


def evidence_navigation(active: set[str] | None = None) -> str:
    """Keyboard-friendly links to present sections and the six original pages."""
    active = active or set()
    targets = (
        ("pulse-suite-summary", "Collection quality", "Erfassungsqualität"),
        ("pulse-triage-queue", "Manual diagnosis", "Manuelle Diagnose"),
        ("pulse-app-summary", "Applications", "Anwendungen"),
        ("pulse-app-history", "Application history", "Anwendungshistorie"),
        ("pulse-infrastructure-matrix", "Infrastructure", "Infrastruktur"),
        ("pulse-declared-links", "Explicit links", "Explizite Zuordnungen"),
    )
    links = ['<a href="#' + target + '">' + l10n_text(en, de) + '</a>'
             for target, en, de in targets if target in active]
    pages = (("pulse.html", "Containers", "Container"), ("hardware.html", "Hardware", "Hardware"),
             ("ports.html", "Ports", "Ports"), ("storage.html", "Storage", "Speicher"),
             ("services.html", "Services", "Dienste"), ("security.html", "Security", "Sicherheit"))
    links += ['<a href="' + filename + '">' + l10n_text(en, de) + '</a>'
              for filename, en, de in pages]
    return ('<nav class="pulse-evidence-index" aria-label="Pulse evidence navigation" '
            'style="display:flex;flex-wrap:wrap;gap:10px;margin:18px 0;">' +
            ''.join(links) + '</nav>')


def table_filter_controls(target: str) -> str:
    """One accessible in-page filter; only known static target selectors."""
    if target not in ("pulse-triage-queue", "pulse-app-summary", "pulse-infrastructure-matrix"):
        return ""
    return ('<div class="pulse-evidence-filter" data-filter-target="' + target +
            '" style="margin:10px 0;"><label>' +
            l10n_text("Show evidence", "Nachweise anzeigen") +
            ' <select aria-label="Filter evidence by severity">'
            '<option value="">' + l10n_text("All states", "Alle Zustände") + '</option>'
            '<option value="critical">CRITICAL</option><option value="warn">WARN</option>'
            '<option value="unknown">UNKNOWN</option><option value="ok">OK</option>'
            '<option value="mixed">MIXED</option></select></label> '
            '<output aria-live="polite"></output></div>')


_FILTER_SCRIPT = """
<script>
(function () {
  'use strict';
  const groups = document.querySelectorAll('.pulse-evidence-filter[data-filter-target]');
  const allowed = {
    'pulse-triage-queue': 0,
    'pulse-app-summary': 3,
    'pulse-infrastructure-matrix': 1
  };
  groups.forEach(function (group) {
    const target = group.getAttribute('data-filter-target');
    if (!Object.prototype.hasOwnProperty.call(allowed, target)) return;
    const panel = document.getElementById(target);
    const select = group.querySelector('select');
    const output = group.querySelector('output');
    if (!panel || !select || !output) return;
    const rows = Array.from(panel.querySelectorAll('tbody tr'));
    function applyFilter() {
      let visible = 0;
      rows.forEach(function (row) {
        const cell = row.cells[allowed[target]];
        const state = cell ? cell.textContent.trim().toLowerCase() : '';
        const match = !select.value || state === select.value;
        row.hidden = !match;
        if (match) visible += 1;
      });
      output.textContent = visible + ' / ' + rows.length;
    }
    select.addEventListener('change', applyFilter);
    applyFilter();
  });
}());
</script>
"""



def add_suite_summary(output_path: str | Path, results: dict[str, object],
                      service_entries: list[dict] | None = None, docker_evidence: dict | None = None,
                      application_links: object = None, completed_at: dict[str, str] | None = None,
                      application_history: list[dict] | None = None,
                      application_history_issue: str | None = None) -> bool:
    """Modify only the existing generated Container Pulse output; idempotent."""
    path = Path(output_path)
    if not path.is_file():
        return False
    source = path.read_text(encoding="utf-8")
    marker = '<section class="feature-strip" aria-label="Design principles">'
    if marker not in source or 'class="pulse-suite-summary"' in source:
        return False
    summary = collection_summary(results, docker_evidence, service_entries, completed_at)
    triage = render_diagnosis_queue(docker_evidence, service_entries, results)
    apps = application_checks_summary(service_entries, results.get("services") is True)
    history = application_history_summary(application_history, application_history_issue)
    matrix = infrastructure_matrix(docker_evidence, application_links, service_entries,
                                   results.get("services") is True)
    declared = declared_link_summary(application_links, docker_evidence, service_entries,
                                     results.get("services") is True)
    chunks = [summary, triage, apps, history, matrix, declared]
    active = {name for name in ("pulse-suite-summary", "pulse-triage-queue",
              "pulse-app-summary", "pulse-app-history", "pulse-infrastructure-matrix",
              "pulse-declared-links")
              if any('id="' + name + '"' in chunk for chunk in chunks)}
    nav = evidence_navigation(active)
    source = source.replace(marker,
                            nav + summary + table_filter_controls("pulse-triage-queue") +
                            triage + table_filter_controls("pulse-app-summary") +
                            apps + history +
                            (table_filter_controls("pulse-infrastructure-matrix") if matrix else "") +
                            matrix + declared + "\n" + marker, 1)
    if "</body>" in source:
        source = source.replace("</body>", _FILTER_SCRIPT + "\n</body>", 1)
    path.write_text(source, encoding="utf-8")
    return True
