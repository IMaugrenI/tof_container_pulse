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
4. verify that generated HTML files look rendered and do not contain real template placeholders
5. verify that platform/collector/read-only badges are present in every generated page

Expected outputs:

- `pulse.html`
- `hardware.html`
- `ports.html`
- `storage.html`
- `services.html`
- `security.html`

Expected generated UI markers:

- `Platform`
- `Collector`
- `Read-only`

## GitHub Actions

The workflow `.github/workflows/smoke.yml` runs the same smoke check on:

- Ubuntu latest
- macOS latest
- Windows latest

Python versions:

- 3.11
- 3.12

## What the smoke check proves

The smoke check proves that the suite can generate all six static pages on the tested operating systems and Python versions.

It catches:

- Python syntax errors
- generator crashes
- missing generated pages
- very small or malformed generated HTML files
- real unreplaced template placeholders such as `{{TITLE}}`
- missing platform/collector/read-only badges

## What it does not prove

The smoke check is not a full browser visual test.

It does not prove:

- pixel-perfect layout
- mobile layout quality
- JavaScript language toggle behavior in a real browser
- Light/Dark visual quality
- deep OS signal availability on every real user machine

Those require manual review or a later optional browser/screenshot test.

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
