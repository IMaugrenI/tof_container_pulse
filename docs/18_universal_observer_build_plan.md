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

## Implementierungsstand (30.10.2026, erste Integration auf main)

| Paket | Tatsächlicher Entwicklungsstand | Noch offen vor Freeze |
| --- | --- | --- |
| B1 | Explizite Compose-Korrelation, Warnbelege, hostbezogene Sicherheitsgrenzen; doppelte Host-Aliase werden blockiert | Weitere Quellenverträge/Qualitätsanzeige |
| B2 | Anwendungsergebnisse der bereits konfigurierten Services-Checks auf der Hauptseite; HTTP-Redirect- und Datenminimierungshärtung | Breitere Service-Metriken nur nach nachweisbarem Bedarf |
| B3 | Explizite App-Check → Docker-Compose-Zuordnungen mit UNKNOWN/NOT_OBSERVED/NOT_COLLECTED sowie eine zeitlich sortierte Docker-/Incident-Zeitachse aus vorhandener opt-in Historie | Historische Application-Checks und Plattform-Telemetrie bleiben außerhalb der bisherigen Persistenz und werden nicht erfunden |
| B4 | Konservative Anomaliehinweise aus vorhandenen zeitlich plausiblen CPU-/RAM-Samples | Kalibrierung der Schwellen anhand echten Betriebs; keine Vorhersagebehauptung |
| B5 | Anonymisierte statistische Hinweise im manuellen Report sowie evidenzbasierte regelgesteuerte Diagnosehinweise | Optionaler, bewusst autorisierter lokaler Erkläradapter; kein LLM aktiviert |
| B6 | Browserseitige Host-/Statusfilter der bestehenden Containerübersicht; bestehende Plattformadapter unverändert | Erweiterte Navigations- und Plattformnachweise |

Die erste Entwicklungsintegration wurde nach bestandener CI und plattformübergreifenden Smoke-Jobs am 30.10.2026 durch [PR #38](https://github.com/IMaugrenI/tof_container_pulse/pull/38) nach `main` gemergt (Merge-Commit `34dd0e5`). **Das ist keine Produktfreigabe und kein GO.** Offene Punkte B1–B6 bleiben vor dem Feature-Freeze zu entwickeln und zu bewerten. Die Betreiber-Gesamtabnahme beginnt erst nach dem vollständigen Ausbau.

## Weiterbau B3 / B5 (30.10.2026)

- **B3:** Einheitliche Infrastruktur-Zeitachse aus vorhandenen erfolgreichen Docker-Listings, gespeicherten Änderungsereignissen und Incident-Lifecycle. Ereigniszeitpunkte sind ausschließlich Beobachtungszeitpunkte und keine bestätigten Beginn-/Endzeitpunkte eines Ausfalls. Keine nachträgliche Erfindung historischer Application-Probes.
- **B5:** Die vorhandene ausdrücklich konfigurierte Check-zu-Compose-Zuordnung erhält deterministische **manuelle** Diagnosehinweise für widersprüchliche Zustände, fehlerhafte oder nicht durchgeführte Erfassung, abweichende Replikatzustände und gleichzeitige Warnungen. Kein Root-Cause-Urteil, kein automatisches Repair und kein LLM-Aufruf.
- **Main-Strategie:** Abgeschlossene Bauabschnitte dürfen nach erfolgreichen gezielten GitHub-Prüfungen von DOMs ausdrücklicher Freigabe nach `main` gelangen. Das ist Entwicklungsintegration, **keine** Gesamtabnahme. Die offene B1–B6-Bauliste bleibt maßgeblich.

## B5 – Manueller lokaler LLM-Erkläradapter (separater Bauabschnitt)

Der vorhandene CLI-Einstieg `run.py` bekommt eine **ausdrücklich manuell** aufrufbare Funktion:

```bash
python run.py --config config.yaml --explain-incidents --explain-model llama3.2:3b
```

Voraussetzungen: `history_enabled: true`, `local_explanation_enabled: true`, eine bereits eingerichtete lokale Ollama-Instanz mit dem angegebenen Modell auf **127.0.0.1:11434**. Ohne manuelle CLI-Aktion wird kein LLM angesprochen; der `--watch`-Pfad ruft keinen Modelladapter auf.

Der Adapter erhält **nur** aus `pulse_reports.build_report` nochmals explizit whitelisted, anonymisierte Host-Aliase und aggregierte Incident-/Ressourcenzahlen. Keine Rohlogs, Config-Werte, Container-/Image-Namen, Benutzerinformationen, Netzwerktopologie oder Kommandos. Er verwendet eine feste Loopback-Adresse, deaktiviert Proxy und HTTP-Redirects, begrenzt Anfrage/Antwort, Laufzeit und Ausgabetokens und fordert eine vorsichtige, als unbestätigt gekennzeichnete Erklärung. Weder Werkzeuge noch Reparaturen oder persistierte LLM-Antworten werden angeboten. Keine Modellinstallation und keine Cloud- oder Fallback-Provider.

**Status:** Code im Entwicklungsbranch; Funktionstests/CI sind keine Betreiberabnahme. Ein lokales Modell benötigt eigene ausreichende Ressourcen und Betreiberentscheidung.
