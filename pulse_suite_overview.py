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


def add_suite_summary(output_path: str | Path, results: dict[str, object]) -> bool:
    """Modify only the existing generated Container Pulse output; idempotent."""
    path = Path(output_path)
    if not path.is_file():
        return False
    source = path.read_text(encoding="utf-8")
    marker = '<section class="feature-strip" aria-label="Design principles">'
    if marker not in source or 'class="pulse-suite-summary"' in source:
        return False
    source = source.replace(marker, collection_summary(results) + "\n" + marker, 1)
    path.write_text(source, encoding="utf-8")
    return True
