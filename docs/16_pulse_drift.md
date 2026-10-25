# PULSE-A5 – Image-, Port- und Recreation-Drift

Opt-in Verlauf (history_enabled) nutzt die vorhandene erfolgreiche Docker-PS-Abfrage.

- Begrenzt gespeicherte veröffentlichte Zielport-Nummern/Protokolle (keine Bind-IP)
- Compose-Projekt und -Service als eingeschränkte Metadaten
- Vergleiche je Host; zuerst Container-ID, ersatzweise nur eindeutige Projekt/Service-Kombination oder Name
- Alte Snapshots ohne Portdaten erzeugen keinen künstlichen Portdrift
- Keine Containeraktionen, keine zusätzlichen Docker-Inspect-Aufrufe und keine automatischen Eingriffe
- Docker-Neustartzähler und vollständiger Konfigurationsdrift sind ausdrücklich nicht nachgewiesen

Konfiguration: \`drift_enabled: true\` (hat ohne \`history_enabled\` keine Wirkung).
Entwicklungsstand, keine Gesamtabnahme.
