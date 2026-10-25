# PULSE-A2 – Topology and diagnostics (development feature)

Container Pulse adds two panels to the existing **Container Pulse** static page,
without another process, endpoint, database, or control command.

- **Compose overview**: groups containers using only explicitly present
  \`com.docker.compose.project\` and \`com.docker.compose.service\` labels.
- **Dependency arrows** appear only for services named in an explicit
  \`com.docker.compose.depends_on\` label on the same host and project.
  If the dependency container is not present in that observation, the arrow
  reads “target not observed”; that is not proof of a fault.
- **Diagnostic hints**: conservative read-only messages for stopped containers,
  existing configured resource warnings, missing metrics, or failed host queries.
  They are not automated diagnoses or repair recommendations.

Both panels are controlled using \`topology_enabled\` and
\`diagnostics_enabled\` in the optional YAML configuration (default: enabled).
They reuse the current \`docker ps\` observation; they do not make extra calls.

No Docker modifications, host operations, full label dumps, secret gathering,
external scans, or network services are introduced.

Retain PULSE-A1 opt-in history; this package does not change retention behavior.
This is an expansion-phase implementation, not the system's final acceptance.
