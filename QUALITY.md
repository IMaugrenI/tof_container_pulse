# Pulse Suite quality checks

Pulse Suite uses two quality layers:

1. targeted unit tests for stable parser and classification helpers
2. a cross-platform smoke check to make sure the static dashboard generator stays healthy on Linux, macOS, and Windows

## Unit tests

Run:

```bash
pytest
```

Current unit tests cover stable helper behavior for:

- platform parsing helpers
- percentage and byte formatting helpers
- port bind parsing and exposure classification
- netstat listener parsing
- storage threshold classification
- security signal severity aggregation

These tests intentionally avoid live host state. They should stay deterministic and should not require Docker, special system privileges, network access, or platform-specific services.

## Local smoke check

Run:

```bash
python scripts/smoke_check.py
```

The check performs local validation:

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

The workflow `.github/workflows/ci.yml` runs:

- Ruff advisory check
- Python compilation
- unit tests through `pytest`
- Docker image build check

The workflow `.github/workflows/smoke.yml` runs the smoke check on:

- Ubuntu latest
- macOS latest
- Windows latest

Python versions:

- 3.11
- 3.12

## What the checks prove

The unit tests prove that selected pure parser/classification helpers keep their expected behavior.

The smoke check proves that the suite can generate all six static pages on the tested operating systems and Python versions.

Together they catch:

- Python syntax errors
- generator crashes
- selected parser/classification regressions
- missing generated pages
- very small or malformed generated HTML files
- real unreplaced template placeholders such as `{{TITLE}}`
- missing platform/collector/read-only badges

## What they do not prove

These checks are not full browser visual tests.

They do not prove:

- pixel-perfect layout
- mobile layout quality
- JavaScript language toggle behavior in a real browser
- Light/Dark visual quality
- deep OS signal availability on every real user machine

Those require manual review or a later optional browser/screenshot test.

## Boundaries

The tests and smoke check do not require Docker to be running.

They do not perform host-changing operations. They only compile code, run deterministic helper tests, generate local static HTML, and validate generated file structure.

If a platform cannot provide a specific signal, the dashboard should still render and show optional, unknown, or N/A instead of crashing.
