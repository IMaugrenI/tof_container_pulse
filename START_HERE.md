# Start here

This is the shortest path to see `tof_container_pulse` working.

> German version: [START_HERE_DE.md](START_HERE_DE.md)

## What it does

Pulse Suite reads local status signals and generates six static HTML pages:

- `pulse.html` — Docker/container overview
- `hardware.html` — hardware overview
- `ports.html` — local listening-port orientation
- `storage.html` — storage overview
- `services.html` — configured service checks
- `security.html` — local security orientation

It is read-only and does not restart, repair, or change the host.

## Requirements

- Python 3.10+
- a browser
- Docker CLI + running Docker daemon/Desktop only if you want live container data

The non-Docker pages can still render when Docker is unavailable.

## First run

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

Or run it directly:

```bash
python3 run.py --once
```

On Windows:

```powershell
py run.py --once
```

The default one-shot run generates the pages and opens `pulse.html`.

## What success looks like

After the run, the repository directory should contain the six HTML files. Open `pulse.html` and use the navigation between pages.

Unavailable signals should appear as unavailable/unknown/N/A rather than crashing the suite.

## Continuous refresh

If you want the files regenerated every 60 seconds:

```bash
python3 run.py --watch 60
```

Stop watch mode with `Ctrl+C`.

## If the first run fails

Run the built-in smoke check. It uses the same generation path without opening a browser and verifies that all six HTML pages were actually rendered.

Linux/macOS:

```bash
python3 scripts/smoke_check.py
```

Windows PowerShell:

```powershell
py scripts/smoke_check.py
```

If that fails, the first error printed by the smoke check is the useful starting point. Docker being unavailable should not prevent the non-Docker pages from rendering.

## Quality check

The same smoke path is exercised in GitHub Actions across Linux, macOS, and Windows.

## Privacy

Generated pages can reveal hostnames, container names, ports, paths, and local infrastructure details.

Do not publish generated HTML or screenshots from a private host without reviewing them first. See [SECURITY.md](SECURITY.md).

## More detail

- [Platform support](PLATFORM_SUPPORT.md)
- [Quality](QUALITY.md)
- [Security](SECURITY.md)
- [Safe local paths](docs/10_safe_paths_and_local_usage.md)
