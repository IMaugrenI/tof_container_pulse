# tof_container_pulse

<p align="center">
  <img src="https://raw.githubusercontent.com/IMaugrenI/IMaugrenI/main/assets/banner/tof_container_pulse_banner_clean.png" alt="tof_container_pulse banner" width="100%" />
</p>

**Local Docker host status at a glance**

Generate a simple static status page from Docker CLI data — read-only, local-first, no database, no cloud.

*A real local host view showing container health, warning thresholds, and critical states in one page.*

---

One host. One page. One glance.

`tof_container_pulse` is a small local dashboard for Docker hosts.
It generates a static `pulse.html` file so you can answer one question fast:

> Is everything okay right now?

## What this repo is

This repository is the public Observe repo in the product line.

## Who it is for

This repo is for self-hosters, local operators, and small teams who want simple Docker host visibility without adopting a larger monitoring stack.

## What it is not

This repo is not a control plane, not a cloud service, and not a hidden automation layer.

## Where to go next

- `tof-showcase` — public architecture and product-line overview
- `tof_local_knowledge` — grounded local knowledge workflows
- `tof_local_builder` — controlled local build workflows

## Role in the public product line

Observe (system state visibility)

### Works standalone
Yes.

### Integration
None (observe-only)

### Not intended for
- controlling or triggering other tools
- becoming part of an automated pipeline

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

or

```bash
./scripts/linux/start_here.sh
```

### macOS

```bash
python3 run.py --once
```

or

```bash
./scripts/macos/start_here.command
```

### Windows (PowerShell)

```powershell
py run.py --once
```

or

```powershell
./scripts/windows/start_here.ps1
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

## Local path and safety note

Container Pulse is a local read-only observer, but it can write output and state files to custom paths.
If you change `--output`, `--state-file`, `--template`, or `--config`, use only paths you understand and control.

For safe examples and path guidance, see:
- `docs/10_safe_paths_and_local_usage.md`

## Notes

- single-host by default
- optional multi-host via Docker contexts
- read-only by design
- no time-series history
- no container restart or control actions
