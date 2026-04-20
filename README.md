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

## Requirements

- Python 3.9+
- Docker CLI in `PATH`
- Docker daemon or Docker Desktop running

## Quick start

Generate once:

```bash
python run.py --once
```

Watch mode:

```bash
python run.py --watch 60
```

## Config

Defaults are built in.

Copy `config.example.yaml` to `config.yaml` if you want custom thresholds.
YAML loading is optional and uses `PyYAML` from `requirements.txt`.

## Notes

- single-host by design
- read-only by design
- no database
- no cloud
- no time-series history
