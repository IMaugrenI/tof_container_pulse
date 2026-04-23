# Safe paths and local usage

> English is the primary text in this document.

This page explains the local path behavior of `tof_container_pulse` and how to use custom paths without accidentally overwriting files you care about.

## Why this page exists

`tof_container_pulse` is a local read-only observer, but it still writes local files.

The tool can write:
- the generated HTML output
- the local state file that remembers the last successful run

It can also read:
- the HTML template
- an optional YAML config file

That means the tool itself is small and local, but you should still understand which paths you are giving it.

## The simple rule

Only use paths you understand and control.

If you are unsure, stay with the defaults first.

## Default local files

When you run the tool in the normal simple way, these defaults apply:

- `--output` → `pulse.html`
- `--template` → `template.html`
- `--config` → not used unless you pass it
- `--state-file` → `.pulse_state.json`

In the default case, these files live in or near your current project folder.

That is the safest beginner path.

## What each path does

### `--output`

This is the path where the generated HTML dashboard is written.

Example:

```bash
python3 run.py --once --output pulse.html
```

What it means:
- the tool builds the dashboard
- the result is written to `pulse.html`
- if a file with that exact name already exists in that path, it will be replaced

Safe beginner advice:
- keep the output in the project folder first
- use a simple filename you recognize
- do not point this at a file you care about

### `--state-file`

This is the small JSON file that stores the timestamp of the last successful run.

Example:

```bash
python3 run.py --once --state-file .pulse_state.json
```

What it means:
- the tool writes a tiny local state file
- the file is updated after successful refreshes
- this is normal and expected

Safe beginner advice:
- leave this in the project folder first
- do not point it at unrelated JSON files
- do not reuse the same file path for other tools

### `--template`

This tells the tool which HTML template it should use when building the page.

Example:

```bash
python3 run.py --once --template template.html
```

What it means:
- the tool reads that template file
- if the path is wrong, the HTML build can fail or produce no useful output

Safe beginner advice:
- keep the default template first
- only change this if you intentionally maintain your own template
- do not move the template path casually without testing

### `--config`

This is the optional YAML config file.

Example:

```bash
python3 run.py --once --config config.yaml
```

What it means:
- the tool reads your YAML file
- thresholds, refresh values, overrides, or host settings can change
- if the file path is wrong, missing, or malformed, the run can fail or fall back to an error message in the generated HTML

Safe beginner advice:
- start without config first
- when you add config, copy from `config.example.yaml`
- do not experiment with multi-host before you understand the single-host default

## Safe first-time pattern

If you want the safest first-time path, do this:

1. clone the repository
2. enter the project folder
3. run the default one-shot command
4. let the tool write `pulse.html` and `.pulse_state.json` in the local project context

Example:

```bash
git clone https://github.com/IMaugrenI/tof_container_pulse.git
cd tof_container_pulse
python3 run.py --once
```

This is the calm path.
You do not need custom output paths on day one.

## Good and bad path habits

### Good habits

- use the project folder first
- use filenames you clearly recognize
- make one change at a time
- test the result after each change
- keep your first runs simple

### Bad habits

- using random absolute paths without checking them
- writing output into important folders you do not normally touch
- pointing `--state-file` at unrelated JSON files
- changing output, config, template, and watch mode all at once
- trying multi-host before the single-host path works cleanly

## A few safe examples

### Example 1 — safest beginner run

```bash
python3 run.py --once
```

This keeps the default behavior.

### Example 2 — custom output inside the project folder

```bash
python3 run.py --once --output my-pulse.html
```

This is usually fine because the new file is still easy to see and understand.

### Example 3 — custom config after the default path already works

```bash
python3 run.py --once --config config.yaml
```

This is safe if `config.yaml` is your own file derived from `config.example.yaml`.

## What this tool does not do

To avoid confusion, `tof_container_pulse` does not:
- open a network port for other users
- create a cloud account
- set up a database
- restart containers for you
- silently manage your Docker host

It reads local Docker information and writes a local HTML file.

That is why the main risk is usually not remote attack surface, but careless local path usage.

## Practical conclusion

If you stay with the defaults first, the risk stays small and understandable.

The clean beginner path is:
- use the repo folder
- run `--once`
- open `pulse.html`
- only then start changing paths or config

If a custom path feels unclear, do not use it yet.
Stay with the defaults until the local flow feels obvious.
