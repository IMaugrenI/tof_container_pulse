# Universal Pulse – Ausbauplan B1–B6

Stand: 2026-10-30 · Status: DEVELOPMENT · Keine Gesamt-Abnahme

## Ziel und Produktgrenze

ToF Container Pulse wird aus dem vorhandenen read-only Docker-/Host-Observer zum universellen lokalen Infrastruktur-Beobachtungssystem erweitert. Beobachtung umfasst Host, Betriebssystem, Docker/Compose, Anwendungen/Services und explizit konfigurierte lokale Netzwerkziele. Eine spätere optionale Diagnosehilfe erklärt belegte Beobachtungen; sie führt niemals Reparaturen aus.

**Nicht-Ziele:** Remote-Steuerung, Restart/Repair, Firewall-/Portänderungen, allgemeine Netzwerkscans, ungefragte Provider-Aufrufe, Cloud-Pflicht, Datenbankpflicht, autonomes LLM-Handeln, zweite Startmechanik.

## Architektur-Iststand

- Kanonischer Einstieg: `run.py` (`--once`, `--watch`); sechs statische HTML-Seiten.
- Bestehende Collector-Module: Docker in `pulse.py`, Hardware, Ports, Storage, Services und Security in ihren bestehenden Modulen und Cross-Platform-Adaptern.
- A1–A8 in `main` (Merge #36): optionale bounded JSON-Snapshots, Incident-Lifecycle, Compose-Labels, Trends, Drift, lokale Inbox, Multi-Host-Tabelle, konservative Capacity-Hinweise.
- Grenzen: Docker-Context-Multi-Host ist keine vollständige Remote-Host-Telemetrie. Suite-Status ist Erfassungsstatus, kein Systemgesundheits- oder Kausalitätsbeweis. Collector-Daten unterschiedlicher Hosts dürfen nicht implizit demselben Host zugeordnet werden.
- Bestand: keine DB, standardmäßig keine Persistenz von Historie oder Benachrichtigungen, kein neuer Dienst, kein Eingriff in fremden State.

## Datenschnittstellen und Invarianten

1. Beobachtungen tragen mindestens `source`, `scope` (Host/Context), `observed_at`, `status`, `evidence_refs` und `quality` (observed, unavailable, stale, unknown). Verträge werden zu vorhandenen Collector-Ergebnissen **adaptiert**, nicht als Parallelcollector aufgebaut.
2. Ein fehlgeschlagener Collector liefert `unknown`; er beweist keinen Host-/Anwendungsausfall. Keine vermischten Host-Scope-Zuordnungen.
3. Korrelation bedeutet zunächst Gleichzeitigkeit oder explizit deklarierte Abhängigkeit. Keine automatische Kausalitätsbehauptung oder Sicherheitsfreigabe aus Labels, ähnlichen Namen oder Zeitnähe.
4. Opt-in-Persistenz wird begrenzt, atomar geschrieben und führt keine Secret-, Env-, Raw-Log- oder vollständigen Inspect-Dumps.
5. Bestehende sechs Seiten und `run.py` bleiben kanonisch. Neue Auswertungen sind ergänzende Sektionen/Module im Repository; keine zusätzlichen Container oder Startdienste.
6. Systemänderungen und automatisierte Reaktionen bleiben ausgeschlossen. Ein optionales LLM erhält nur minimierte, freigegebene Diagnosedaten, keine Docker-/Host-Aktionswerkzeuge.
7. DEV-/CI-Nachweise sind keine Runtime- oder Betreiberabnahme. P0/P1 vor abhängigem Weiterbau beheben, P2 gesammelt zum Freeze bewerten.

## Baufolge (zusammenhängende Pakete)

| Phase | Ziel | Geplante Umsetzung | Nachweis während Bau |
| --- | --- | --- | --- |
| B1 – Beobachtungsvertrag & Korrelation | vorhandene Beobachtungen sicher verbinden | Normalisierte read-only Incident-/Topologie-Ansicht, explizite Evidenz, Scope-/Qualitätsregeln, begrenzte Warnungsgruppen in vorhandener HTML-Seite | Gezielt: keine Cross-Host-Mischung, unknown != outage, XSS-escaping, deterministic limits |
| B2 – Dienst-/Anwendungssicht | Funktionsfähigkeit statt nur Prozessstatus | vorhandene `services.py`-Checks und Container-Kontext verbinden; explizite HTTP/TCP/Heartbeat-Signale, Messalter und Timeout im bestehenden Konfigurationsmodell; keine automatischen Discovery-Scans | Isolierte Checks ohne externe Ziele, Fail-Closed |
| B3 – Infrastrukturgraph & Zeitachse | Host-/Compose-/Service-Abhängigkeiten nachvollziehen | bestehende Compose-Kanten, deklarierte Dienstbeziehungen, Incidents, Drift und Zeitreihen visualisieren; fehlende Kanten als unbekannt ausweisen | Gezielte Kanten-/Zeitfensterprüfung |
| B4 – Ressourcenintelligenz | Anomalien und Kapazitätsrisiken | vorhandene Trends/Capacity erweitert um konfigurierbare Normalbereiche, ausreichende Stichproben, robuste Ausreißerbehandlung und explizite Prognosegrenzen | Sparse/missing/outlier-Negativfälle |
| B5 – Lokale Diagnostik & Berichte | Betreiber bei Fehlersuche unterstützen | evidenzbasierte Diagnosekarten; vorhandene Report-/Inbox-Pfade erweitern; optionale lokale LLM-Erklärung als rein lesender Adapter, kein LLM erforderlich | Deterministische Fallbacks; keine neuen Netzwege ohne Opt-in |
| B6 – universelle UX & Plattformen | einheitliche Host-/Dienstansicht | sechs bestehende Seiten konsolidiert navigierbar, Host- und Quellenfilter, klare Erfassungsqualität; vorhandene Linux/macOS/Windows-Adapter gezielt erweitern | gezielte Cross-Platform-CI, Accessibility und Darstellung |

## Freeze und spätere Gesamtabnahme

Erst nach B1–B6: Feature-Freeze, Dokumentationsabgleich, P2-Entscheidungen, vollständige zentrale Abnahmeliste. Wiederverwendung bestandener CI-Nachweise; getrennte Betreiber-Nachweise auf Zielhosts zu Docker/Compose, verschiedenen Collector-Ausfällen, opt-in State, Sicherheit/Datensparsamkeit, Runtime-Startweg und ggf. optionalem LLM. Kein GO aus CI oder Merge allein.

## Entscheidungen (für diesen Ausbau festgelegt)

- Produktziel: universeller lokaler read-only Infrastruktur-Observer, einschließlich Anwendungsgesundheit über explizite Prüfungen.
- Bestehendes Repository und bestehende Runtime-/Startwege bleiben Autorität.
- Kein zweiter Datenstore, Collector-Daemon oder Remote-Agent als Default.
- Keine selbständigen Reparaturen oder Host-/Docker-Steuerung.
- B1 beginnt mit tatsächlichen Evidenz- und Korrelationsverträgen; Features müssen am vorhandenen Datenfluss hängen, nicht als ungenutzte Parallelmodule entstehen.
