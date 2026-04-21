# tof_container_pulse

**Local Docker host status at a glance**

Generate a simple static status page from Docker CLI data — read-only, local-first, no database, no cloud.

![Container Pulse dashboard](assets/screenshots/pulse-main-1.png)

*A real local host view showing container health, warning thresholds, and critical states in one page.*

---

One host. One page. One glance.

`tof_container_pulse` is a small local dashboard for Docker hosts.
It generates a static `pulse.html` file so you can answer one question fast:

> Is everything okay right now?

## Features

- Linux, macOS, Windows
- read-only Docker CLI access
- no Docker SDK required
- configurable warning thresholds
- optional watch loop
- optional multi-host view via Docker contexts
- static HTML output
- no database
- no cloud

## Requirements

- Python 3.9+
- Docker CLI in `PATH`
- Docker daemon or Docker Desktop running

## Quick start

`--once` generates `pulse.html` and opens it automatically in your default browser.
Use `--no-open` if you only want to generate the file.

### Linux

```bash
python3 run.py --once
```

### macOS

```bash
python3 run.py --once
```

### Windows (PowerShell)

```powershell
py run.py --once
```

## Watch mode

### Linux / macOS

```bash
python3 run.py --watch 60
```

### Windows (PowerShell)

```powershell
py run.py --watch 60
```

## Config

Defaults are built in.

Copy `config.example.yaml` to `config.yaml` if you want custom thresholds.
YAML loading is optional and uses `PyYAML` from `requirements.txt`.

Install optional YAML support:

```bash
pip install -r requirements.txt
```

Use a config file:

```bash
python run.py --once --config config.yaml
```

Write to another output path:

```bash
python run.py --once --output pulse.html
```

## Multi-host mode

Multi-host is optional.
If you do nothing, the tool stays in normal single-host mode.

A neutral template is included:

```text
multi_host.example.yaml
```

Use it only if you actually want a combined view across multiple Docker contexts.

### How to use it

1. copy `multi_host.example.yaml` to `multi_host.yaml`
2. fill in your real Docker contexts
3. run:

```bash
python run.py --once --config multi_host.yaml
```

### Example

```yaml
hosts:
  - name: local
    docker_context: default
  - name: nas
    docker_context: nas
```

In multi-host mode, the page keeps the same logic and style, but adds a `Host` column and merges all configured hosts into one page.

## Severity model

- `ok` = running and within thresholds
- `warn` = running but above CPU or RAM threshold
- `critical` = container state is not healthy
- `unknown` = state or live stats could not be determined cleanly

## Notes

- single-host by default
- optional multi-host via Docker contexts
- read-only by design
- no time-series history
- no container restart or control actions
