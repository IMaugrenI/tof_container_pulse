# Pulse Suite quality checks

Pulse Suite uses a small cross-platform smoke check to make sure the static dashboard generator stays healthy on Linux, macOS, and Windows.

## Local smoke check

Run:

```bash
python scripts/smoke_check.py
```

The check performs only read-only validation:

1. compile all Python files
2. run `python run.py --once --no-open`
3. verify that all expected static HTML files exist
4. verify that generated HTML files look rendered and do not contain template placeholders

Expected outputs:

- `pulse.html`
- `hardware.html`
- `ports.html`
- `storage.html`
- `services.html`
- `security.html`

## GitHub Actions

The workflow `.github/workflows/smoke.yml` runs the same smoke check on:

- Ubuntu latest
- macOS latest
- Windows latest

Python versions:

- 3.11
- 3.12

## Boundaries

The smoke check does not require Docker to be running.

It does not:

- run sudo/admin elevation
- change Docker
- change firewall rules
- change SSH settings
- change users or groups
- change services
- change storage mounts
- run external scans
- auto-fix anything

If a platform cannot provide a specific signal, the dashboard should still render and show optional, unknown, or N/A instead of crashing.
