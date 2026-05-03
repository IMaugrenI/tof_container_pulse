# Pulse Suite roadmap

`tof_container_pulse` started as a focused static Docker container dashboard.
The next product direction is a small local read-only **Pulse Suite**.

The repository name can remain `tof_container_pulse` for the current public baseline.
The public product wording can gradually introduce "Pulse Suite" once more than one page is validated locally.

## Boundary

Every Pulse page must stay inside the same safety boundary:

- local-first
- read-only
- static HTML output
- no cloud service
- no database requirement
- no automatic repair actions
- no reboot, shutdown, firewall, update, prune, or restart buttons
- no external port scanning
- no private hostnames or sensitive service names in public screenshots

The suite may recommend checks or maintenance windows, but it must not execute corrective actions.

## Planned pages

### 1. Container Pulse

Current page.

Purpose:
- Docker container overview
- state and severity
- CPU and memory per container
- Docker image and notes
- optional Docker context multi-host view

Default output:

```text
pulse.html
```

### 2. Hardware Pulse

Purpose:
- host hardware health at a glance
- CPU, RAM, swap, load average, uptime
- disk usage summary
- local IP addresses
- optional GPU/VRAM, temperature, fan RPM, UPS, Wi-Fi, NTP, and sensor checks when available

Default output:

```text
hardware.html
```

### 3. Port Pulse

Purpose:
- local host port exposure overview
- listening ports
- bind address classification: local-only vs public-bound
- process/service when available
- Docker-published ports when available
- allowed/review/critical status

Boundary:
- local read-only port inspection only
- no external network scanning

Default output:

```text
ports.html
```

### 4. Storage Pulse

Purpose:
- storage health and capacity pressure
- mount usage
- inode usage
- Docker log size
- Docker orphaned volumes
- database and backup file size checks when configured
- S.M.A.R.T. status when safely available

Default output:

```text
storage.html
```

### 5. Service Pulse

Purpose:
- configured local service checks
- HTTP health endpoints
- bot heartbeat files
- cron/script status files
- tunnel status files
- DNS check when configured
- SSL certificate expiry when configured

Boundary:
- only explicit configured checks
- no broad discovery scans

Default output:

```text
services.html
```

### 6. Security Pulse

Purpose:
- local operational hygiene checks
- SSH failed login count when available
- active SSH sessions
- fail2ban ban count when available
- privileged Docker containers
- host-network Docker containers
- Docker socket mounts
- config drift checks when configured
- risky permission checks when explicitly configured

Boundary:
- advisory only
- no automatic remediation

Default output:

```text
security.html
```

## Implementation principles

### Resource-friendly collection

Collectors should be cheap by default.

- avoid heavy scans in the default path
- prefer bounded commands with short timeouts
- cache or rate-limit expensive checks
- make slow checks opt-in
- never block generation of all pages because one collector fails
- show `unknown` or `unavailable` when data cannot be collected safely

### Lazy and optional checks

The suite should not collect everything on every run.

Recommended approach:

```text
required cheap checks:
  run every generation

optional medium checks:
  run only when enabled in config

expensive checks:
  run only on explicit interval or dedicated page generation
```

Examples:

- CPU/RAM/load/uptime: cheap
- local listening ports: medium
- S.M.A.R.T.: optional
- Docker image update checks: optional/expensive
- broken-link checks: optional/expensive
- inter-node bandwidth tests: explicit/manual only

### Collector isolation

Each page should have its own collector module.

Suggested future structure:

```text
run.py
pulse.py                  # current Container Pulse collector/generator
hardware.py               # Hardware Pulse collector/generator
ports.py                  # Port Pulse collector/generator
storage.py                # Storage Pulse collector/generator
services.py               # Service Pulse collector/generator
security.py               # Security Pulse collector/generator
```

A later refactor may extract common rendering helpers after at least two pages exist.
Do not over-abstract before the second real page is validated.

### Static outputs

Default one-shot generation should eventually produce:

```text
pulse.html
hardware.html
ports.html
storage.html
services.html
security.html
```

Watch mode should refresh the enabled pages at the configured interval.

### Page navigation

All pages should share compact navigation pills:

```text
Container | Hardware | Ports | Storage | Services | Security
```

All pages should also keep:

- Deutsch/English toggle
- dark/light toggle
- `localStorage` persistence
- clear read-only footer

## Suggested release path

```text
v0.1.x  Container Pulse public demo baseline
v0.2.0  Hardware Pulse
v0.3.0  Port Pulse
v0.4.0  Storage Pulse
v0.5.0  Service Pulse
v0.6.0  Security Pulse
```

## Public screenshot rule

Only publish screenshots with neutral names and public-safe data.

Avoid:

- real hostnames
- private Docker context names
- customer names
- private service names
- public IPs that should not be public
- tokens, `.env` values, SSH keys, or secrets
- sensitive logs or paths

Use synthetic or redacted local demo data for public evidence.
