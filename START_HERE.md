# Start here

This is the shortest path from a fresh clone to a useful local overview of your computer.

> German version: [START_HERE_DE.md](START_HERE_DE.md)

## What this product is for

Pulse gives you six local pages that answer simple questions:

- **Containers** — what is running and what needs attention?
- **Hardware** — does the computer look healthy?
- **Connections** — which local connections are open?
- **Storage** — is there enough space and does anything stand out?
- **Services** — are the services you care about reachable?
- **Security** — which local settings may deserve a closer look?

Pulse only observes. It does not restart, repair, delete or change anything.

## What you need

- Python 3.10+
- a browser
- Docker/Docker Desktop only if you want live container information

The other pages still render when Docker is unavailable.

## First start

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

The normal one-time run creates the pages and opens the container overview.

## What success looks like

Look first at the summary cards:

- **Running / OK** means nothing currently stands out
- **Check** means something is worth reviewing
- **Needs attention** means an important signal should be looked at
- **Unknown / N/A** means Pulse could not determine that value cleanly

Use the navigation to move through the six pages. Each page includes a short recommendation or explanation of what the state means.

## If something is unavailable

Unavailable information is not automatically a failure.

For example, Docker may be stopped while hardware or storage information can still be shown.

If the pages are not generated at all, run:

### Linux/macOS

```bash
python3 scripts/smoke_check.py
```

### Windows

```powershell
py scripts/smoke_check.py
```

The first reported error is the useful starting point.

## Continuous refresh

If you want Pulse to recreate the pages every 60 seconds:

```bash
python3 run.py --watch 60
```

Stop with `Ctrl+C`.

## Privacy and trust

Pulse is local and read-only, but the generated pages can contain hostnames, container names, ports, paths and local infrastructure details.

Review generated HTML and screenshots before sharing them publicly.

See [SECURITY.md](SECURITY.md).

## Stop and come back later

A one-time run ends after generating the pages.

Watch mode stops with `Ctrl+C`.

Later, run the same start command again. Pulse does not require a server or account to keep working.

## Real-life example

See [docs/USER_JOURNEY.md](docs/USER_JOURNEY.md) for a complete “something needs attention” journey.

## More detail

- [Platform support](PLATFORM_SUPPORT.md)
- [Quality](QUALITY.md)
- [Security](SECURITY.md)
- [Safe local paths](docs/10_safe_paths_and_local_usage.md)
