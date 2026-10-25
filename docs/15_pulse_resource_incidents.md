# Pulse A3/A4 – Bounded resource timelines and incident lifecycle

These features continue the original read-only, local static Pulse model.

## Opt in

Set the existing config values:

\`\`\`yaml
history_enabled: true
history_path: .pulse_history.json
history_max_snapshots: 120
\`\`\`

Then run the existing entrypoint (\`python3 run.py --config config.yaml --once\`
or \`--watch 60\`). No new service, Docker permissions, or daemon are required.

- A3 records CPU %, memory used MiB and memory percent with each valid host
  snapshot. Unavailable metrics are null, never zero. The current page charts
  the last 24 observations. Older A1 snapshots without metrics remain readable.
- A4 records first-observed incident time, current and highest observed
  severity, last observation, recovery time and acknowledgement metadata.
  An incident is opened when severity becomes warn or critical, or when a
  container previously present disappears on a *successfully* queried host.
- A host that fails collection may neither start a disappearance event nor
  close an incident. Missing stats alone are UNKNOWN, not a confirmed outage.
- Durations are observation-derived, not guaranteed actual failure durations.
- Manual acknowledgement: \`python3 run.py --config config.yaml --ack-incident INC-ID\`.
  No Docker command runs during acknowledgement. This is an operator note,
  not an authentication system.
- Snapshot file writes are atomic, private (0600 on newly written files),
  bounded by the existing 2 MB storage ceiling and configured snapshot cap.
  Closed older incidents may be retired before open incidents to stay bounded.
- No sensitive Docker settings, env values, inspected secrets, or log data
  are captured. No container state is ever modified.

**Scope:** GitHub development code. Runtime validation and overall acceptance
remain postponed until the end of the expansion phase.


## PULSE-A6/A7 – Übergreifender Erfassungsstatus und anonymisierter Bericht

Die bereits vorhandenen sechs Seiten-Generatoren melden nur ihre **Erfassungs-**
Ergebnisse an eine Übersicht auf der bestehenden Container-Pulse-HTML-Seite.
Diese Übersicht trifft kein Urteil über den tatsächlichen Betriebszustand und
stellt keine Kausalbeziehung zwischen verschiedenen Systembereichen her.

Ein Report wird ausschließlich auf expliziten Betreiberwunsch erzeugt:

    python run.py --config config.yaml --export-incident-report incident.json

Voraussetzung: \`history_enabled: true\` und gespeicherte lokale Historie.
Der Bericht nutzt ausschließlich vorhandene Snapshots und Incidents:
keine erneute Docker-Abfrage, keine zusätzlichen Subsystemprüfungen,
keine Containersteuerung oder Remote-Dienste.

Datensparsamkeit: Er enthält Host-Aliase statt Hostnamen und keine
Containernamen, Images, Ports, Systempfade oder Originalfehlermeldungen.
Mehrere offene Incidents plus auffällige Containerressourcen desselben Hosts
werden als **Koinzidenz**, nicht als Ursachenerklärung, ausgegeben.
Ein bereits vorhandener Dateipfad wird niemals überschrieben; das
Zielverzeichnis muss vorher existieren. Die neu erzeugte Datei erhält
private Schreibrechte, soweit das Betriebssystem sie unterstützt.

Dies ist ein Entwicklungsnachweis in GitHub Actions und ausdrücklich keine
Gesamt- oder Laufzeitabnahme auf Betreibergeräten.
