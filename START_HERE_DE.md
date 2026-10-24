# Hier starten

Das ist der kürzeste Weg, um `tof_container_pulse` laufen zu sehen.

> English version: [START_HERE.md](START_HERE.md)

## Was das Tool macht

Pulse Suite liest lokale Statussignale und erzeugt sechs statische HTML-Seiten:

- `pulse.html` — Docker-/Container-Übersicht
- `hardware.html` — Hardware
- `ports.html` — lokale Port-Orientierung
- `storage.html` — Speicher
- `services.html` — konfigurierte Dienstprüfungen
- `security.html` — lokale Sicherheitsorientierung

Das Tool arbeitet read-only und startet, repariert oder verändert nichts automatisch.

## Voraussetzungen

- Python 3.10+
- ein Browser
- Docker CLI + laufender Docker-Daemon/Docker Desktop nur für Live-Containerdaten

Die anderen Seiten können auch ohne Docker gerendert werden.

## Erster Lauf

### Linux

```bash
git clone https://github.com/IMaugrenI/tof_container_pulse.git
cd tof_container_pulse
./scripts/linux/start_here.sh
```

### macOS

```bash
git clone https://github.com/IMaugrenI/tof_container_pulse.git
cd tof_container_pulse
./scripts/macos/start_here.command
```

### Windows PowerShell

```powershell
git clone https://github.com/IMaugrenI/tof_container_pulse.git
cd tof_container_pulse
./scripts/windows/start_here.ps1
```

Oder direkt:

```bash
python3 run.py --once
```

Unter Windows:

```powershell
py run.py --once
```

Der normale Einmallauf erzeugt die Seiten und öffnet `pulse.html`.

## Erfolgszustand

Nach dem Lauf sollten im Repository die sechs HTML-Dateien liegen. Öffne `pulse.html` und nutze die Navigation zwischen den Seiten.

Nicht verfügbare Signale sollen ruhig als unbekannt/nicht verfügbar/N/A erscheinen statt das Tool abstürzen zu lassen.

## Automatisch aktualisieren

Für eine Neugenerierung alle 60 Sekunden:

```bash
python3 run.py --watch 60
```

Beenden mit `Ctrl+C`.

## Qualitätsprüfung

```bash
python scripts/smoke_check.py
```

Derselbe Smoke-Pfad läuft in GitHub Actions auf Linux, macOS und Windows.

## Datenschutz

Die erzeugten Seiten können Hostnamen, Container-Namen, Ports, Pfade und lokale Infrastrukturdetails zeigen.

Veröffentliche keine HTML-Ausgaben oder Screenshots eines privaten Hosts, ohne sie vorher zu prüfen. Siehe [SECURITY.md](SECURITY.md).

## Mehr Details

- [Plattform-Support](PLATFORM_SUPPORT.md)
- [Qualität](QUALITY.md)
- [Security](SECURITY.md)
- [Sichere lokale Pfade](docs/10_safe_paths_and_local_usage.md)
