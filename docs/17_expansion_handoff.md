# ToF Container Pulse – Entwicklungsausbau A1–A8

Stand: 2026-10-25. Gültig für den Entwicklungs-PR #36, nicht für main.

## Funktionspakete

| Paket | Im Entwicklungsbranch |
| --- | --- |
| A1 | Opt-in lokale Snapshots und Zustandsänderungen |
| A2 | Explizite Compose-Topologie, regelbasierte read-only Hinweise |
| A3 | Historische CPU-/Speicherdaten und statische Trends |
| A4 | Incident-Eröffnung, Wiederherstellung, Dauer und explizite CLI-Bestätigung |
| A5 | Image-/Portänderungen, eindeutige Neuerstellung erkannt |
| A6 | Status der sechs **Datenerfassungen**, keine kausale Subsystem-Diagnose |
| A7 | Manuell exportierter anonymisierter Report, optionale lokale Hinweisablage |
| A8 | Erfolgreiche Multi-Host-Beobachtungen und vorsichtige Speichertrend-Hinweise |

## Beibehaltene Grenzen

- Nur Docker-/Host-Beobachtung. Keine Restart-/Repair-/Port-/Firewall-Aktion.
- Vorhandenes run.py sowie bestehender Docker- und Compose-Startpfad.
- Keine neue Datenbank, kein Daemon, keine Cloud oder unbeauftragte Netzverbindung.
- Historie, Hinweisablage und Incident-Report erfolgen nur mit explizitem Opt-in.
- Sparse Metriken bleiben unbekannt; die Kapazitätsrechnung ist keine Prognose.
- Aus Docker-Labels und Einzelbeobachtungen darf keine Sicherheits- oder
  kausale Ursachenbewertung abgeleitet werden.
- Benachrichtigungen sind derzeit eine lokale Inbox, kein OS-, E-Mail- oder Messenger-Push.

## Nachweislage und Restbedarf

- GitHub Actions: bestehende CI, Docker-Build und plattformübergreifende
  Smoke-Jobs auf Entwicklungscommits durchgeführt.
- Einzelne Entwicklungsfehler wurden im Bauabschnitt korrigiert und CI wiederholt.
- **Nicht durchgeführt:** Installation, echter Langzeitbetrieb, Verbindung zu
  Betreiberhosts, Endgeräteprüfung und Gesamtabnahme.
- P2/Optionen für DOM: native Meldungswege, tiefere Services/Ports/Storage-Korrelation,
  Docker-Inspect-basierte Restart-/Config-Daten (neue Datengrenzen erforderlich),
  Kapazitätsmodelle für längere Messperioden.
- Vor Feature-Freeze: offene P2-Optionen bewerten; für Gesamtfreigabe muss DOM
  erst die verbindliche Abnahmeliste am Zielsystem durchführen.

Entwicklungs-PR bleibt Draft und main unverändert. Keine eigenmächtige
Releasefreigabe, kein GO aus GitHub-CI ableitbar.
