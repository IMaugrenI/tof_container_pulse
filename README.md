# tof_container_pulse

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
- static HTML output
- no database
- no cloud

## Requirements

- Python 3.9+
- Docker CLI in `PATH`
- Docker daemon or Docker Desktop running

## Quick start

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

## Severity model

- `ok` = running and within thresholds
- `warn` = running but above CPU or RAM threshold
- `critical` = container state is not healthy
- `unknown` = state or live stats could not be determined cleanly

## Notes

- single-host by design
- read-only by design
- no time-series history
- no container restart or control actions
