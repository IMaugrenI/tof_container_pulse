"""Read-only Compose-label topology and human-reviewed diagnostic hints.

Only standard Docker Compose labels from the existing docker ps listing are used.
Presence in the same project does NOT establish dependency. A directed
relationship appears only if its source includes an explicit depends_on label.
No environment variables, inspected configurations, ports or secrets are read.
"""
from __future__ import annotations

import html
import re
from collections import defaultdict

from i18n_static import l10n_text

# Whitelist standard labels, not arbitrary user-configurable secrets.
_LABEL = re.compile(r"(?:^|,)com\.docker\.compose\.(project|service|depends_on)=")


def compose_labels(raw: object) -> dict[str, str]:
    if isinstance(raw, dict):
        return {
            key: str(raw.get("com.docker.compose." + key, ""))[:160]
            for key in ("project", "service", "depends_on")
        }
    value = str(raw or "")[:4096]
    matches = list(_LABEL.finditer(value))
    result = {}
    for index, match in enumerate(matches):
        ending = matches[index + 1].start() if index + 1 < len(matches) else len(value)
        content = value[match.end():ending].strip(", ")
        result[match.group(1)] = content[:160]
    return result


def _dependency_names(value: str) -> list[str]:
    """Compose metadata format: db:service_started:false,cache:service_healthy:false."""
    names = []
    for part in value.split(","):
        name = part.partition(":")[0].strip()
        if name and re.fullmatch(r"[a-zA-Z0-9_.-]{1,80}", name) and name not in names:
            names.append(name)
    return names[:20]


def topology_data(observations: list[dict]) -> dict[str, object]:
    """Return bounded project/service groups and explicit relationship edges."""
    projects: dict[tuple[str, str], dict[str, object]] = {}
    standalone = 0
    for item in observations[:1500]:
        labels = compose_labels(item.get("labels", {}))
        host = str(item.get("host", ""))[:120]
        project = labels.get("project", "")
        service = labels.get("service", "")
        if not project or not service:
            standalone += 1
            continue
        key = (host, project)
        group = projects.setdefault(key, {"host": host, "project": project, "services": {}, "edges": []})
        services = group["services"]
        if len(services) >= 150 and service not in services:
            continue
        instances = services.setdefault(service, [])
        if len(instances) < 40:
            instances.append({
                "name": str(item.get("name", ""))[:120],
                "state": str(item.get("state", "unknown"))[:40],
                "severity": str(item.get("severity", "unknown"))[:40],
                "depends_on": _dependency_names(labels.get("depends_on", "")),
            })

    result = []
    for group in projects.values():
        names = set(group["services"])
        edges = set()
        for service, instances in group["services"].items():
            for instance in instances:
                for target in instance["depends_on"]:
                    if target != service:
                        edges.add((service, target, target in names))
        group["edges"] = [
            {"from": source, "to": target, "present": present}
            for source, target, present in sorted(edges)
        ][:200]
        result.append(group)
    return {"projects": sorted(result, key=lambda p: (p["host"], p["project"]))[:80],
            "standalone": standalone, "truncated": len(result) > 80 or len(observations) > 1500}


def render_topology(observations: list[dict]) -> str:
    data = topology_data(observations)
    groups = []
    for item in data["projects"]:
        groups.append("<section class='pulse-topology-group'><h3>" +
                      html.escape(item["host"]) + " / " + html.escape(item["project"]) + "</h3>")
        members = []
        for service, instances in sorted(item["services"].items()):
            states = ", ".join(inst["state"] for inst in instances[:6])
            members.append("<li><strong>" + html.escape(service) + "</strong> " +
                           html.escape(states) + "</li>")
        groups.append("<ul>" + "".join(members) + "</ul>")
        if item["edges"]:
            relations = []
            for edge in item["edges"]:
                detail = (l10n_text("present", "vorhanden") if edge["present"]
                          else l10n_text("target not observed", "Ziel nicht beobachtet"))
                relations.append("<li>" + html.escape(edge["from"]) + " → " +
                                 html.escape(edge["to"]) + " (" + detail + ")</li>")
            groups.append("<p>" + l10n_text("Explicit Compose depends_on labels only:",
                                            "Nur ausdrücklich vorhandene Compose-depends_on-Labels:") +
                          "</p><ul>" + "".join(relations) + "</ul>")
        groups.append("</section>")
    if not groups:
        groups.append("<p>" + l10n_text(
            "No Compose project labels observed. Standalone containers are still included in diagnostics.",
            "Keine Compose-Projektlabels beobachtet. Einzelcontainer bleiben in der Diagnose enthalten."
        ) + "</p>")
    intro = l10n_text(
        f"{len(data['projects'])} Compose groups · {data['standalone']} ungrouped containers. "
        "Shared group membership does not prove dependency.",
        f"{len(data['projects'])} Compose-Gruppen · {data['standalone']} nicht gruppierte Container. "
        "Gemeinsame Gruppenzugehörigkeit beweist keine Abhängigkeit."
    )
    return ("<section class='pulse-topology' aria-label='Compose topology'>"
            "<div class='table-title'><h2>" +
            l10n_text("Compose topology", "Compose-Übersicht") + "</h2><span>" + intro +
            "</span></div>" + "".join(groups) + "</section>")


def render_diagnostics(observations: list[dict], failed_hosts: list[str] | None = None) -> str:
    rows = []
    for host in (failed_hosts or [])[:15]:
        rows.append("<li><strong>" + html.escape(str(host)) + "</strong>: " +
                    l10n_text("Docker listing failed; no container conclusions can be drawn.",
                              "Docker-Abfrage fehlgeschlagen; keine Aussagen zu Containern möglich.") +
                    "</li>")
    for item in observations:
        severity = str(item.get("severity", "unknown"))
        if severity == "ok" or len(rows) >= 25:
            continue
        if severity == "critical":
            advice = l10n_text("Container not running. Check whether the stopped state is intentional.",
                               "Container läuft nicht. Prüfen, ob der Stillstand beabsichtigt ist.")
        elif severity == "warn":
            advice = l10n_text("Configured resource threshold exceeded. Inspect the metrics and workload.",
                               "Konfigurierter Ressourcengrenzwert überschritten. Metriken und Last prüfen.")
        else:
            advice = l10n_text("Live metrics unavailable or uncertain. No failure is confirmed.",
                               "Live-Metriken fehlen oder sind unklar. Ein Ausfall ist nicht bestätigt.")
        rows.append("<li><strong>" + html.escape(str(item.get("host", ""))) + " / " +
                    html.escape(str(item.get("name", ""))) + "</strong> (" +
                    html.escape(severity) + "): " + advice + "</li>")
    if not rows:
        rows.append("<li>" + l10n_text("No items need manual review in this observation.",
                                       "In dieser Beobachtung ist keine manuelle Prüfung angezeigt.") + "</li>")
    return ("<section class='pulse-diagnostics' aria-label='Read-only diagnostics'>"
            "<div class='table-title'><h2>" + l10n_text("Diagnostic hints", "Diagnosehinweise") +
            "</h2><span>" + l10n_text("Rules, not automatic repairs or root-cause proof.",
                                       "Regeln, keine Reparaturen oder Ursachenbeweise.") +
            "</span></div><ul>" + "".join(rows) + "</ul></section>")
