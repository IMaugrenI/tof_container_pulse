# Hier starten

Das ist der kürzeste Weg vom frischen Klon bis zu einer nützlichen lokalen Übersicht über deinen Rechner.

> English version: [START_HERE.md](START_HERE.md)

## Wofür dieses Produkt gedacht ist

Pulse gibt dir sechs lokale Seiten für einfache Fragen:

- **Container** — was läuft und was braucht Aufmerksamkeit?
- **Hardware** — wirkt der Rechner unauffällig?
- **Verbindungen** — welche lokalen Verbindungen sind offen?
- **Speicher** — ist genug Platz frei und fällt etwas auf?
- **Dienste** — sind die Dienste erreichbar, die dir wichtig sind?
- **Sicherheit** — welche lokalen Einstellungen solltest du dir genauer ansehen?

Pulse schaut nur nach. Es startet, repariert, löscht oder verändert nichts.

## Was du brauchst

- Python 3.10+
- einen Browser
- Docker/Docker Desktop nur dann, wenn du Live-Containerinformationen sehen möchtest

Die anderen Seiten können auch ohne Docker angezeigt werden.

## Erster Start

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

Der normale Einmallauf erzeugt die Seiten und öffnet die Containerübersicht.

## Woran du erkennst, was wichtig ist

Schau zuerst auf die Übersichtskarten:

- **Läuft / OK** — aktuell fällt nichts auf
- **Prüfen** — etwas ist einen Blick wert
- **Braucht Aufmerksamkeit** — ein wichtiges Signal sollte geprüft werden
- **Unbekannt / N/A** — Pulse konnte diesen Wert nicht sauber bestimmen

Über die Navigation wechselst du zwischen den sechs Seiten. Jede Seite zeigt eine kurze Einordnung oder Empfehlung zum aktuellen Zustand.

## Wenn etwas nicht verfügbar ist

Fehlende Informationen sind nicht automatisch ein Fehler.

Docker kann zum Beispiel gestoppt sein, während Hardware- oder Speicherinformationen trotzdem angezeigt werden.

Wenn gar keine Seiten erzeugt werden, nutze:

### Linux/macOS

```bash
python3 scripts/smoke_check.py
```

### Windows

```powershell
py scripts/smoke_check.py
```

Der erste gemeldete Fehler ist der sinnvolle Ausgangspunkt.

## Automatisch aktualisieren

Wenn Pulse die Seiten alle 60 Sekunden neu erzeugen soll:

```bash
python3 run.py --watch 60
```

Beenden mit `Ctrl+C`.

## Datenschutz und Vertrauen

Pulse arbeitet lokal und verändert nichts. Die erzeugten Seiten können aber Hostnamen, Container-Namen, Ports, Pfade und lokale Infrastrukturdetails enthalten.

Prüfe HTML-Ausgaben und Screenshots, bevor du sie öffentlich teilst.

Siehe [SECURITY.md](SECURITY.md).

## Stoppen und später weitermachen

Ein Einmallauf endet nach dem Erzeugen der Seiten.

Den Watch-Modus beendest du mit `Ctrl+C`.

Später startest du einfach denselben Befehl erneut. Pulse braucht keinen Server und kein Benutzerkonto, um weiterzuarbeiten.

## Beispiel aus echter Nutzung

[docs/USER_JOURNEY_DE.md](docs/USER_JOURNEY_DE.md) zeigt einen kompletten Ablauf für den Fall „Etwas braucht Aufmerksamkeit“.

## Mehr Details

- [Plattform-Support](PLATFORM_SUPPORT.md)
- [Qualität](QUALITY.md)
- [Security](SECURITY.md)
- [Sichere lokale Pfade](docs/10_safe_paths_and_local_usage.md)
