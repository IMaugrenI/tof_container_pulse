# Multi-host build and implementation plan

## Goal

Extend `tof_container_pulse` from **one host, one page** to **multiple hosts, one page** without breaking the original philosophy.

The product should remain:

- local-first
- read-only
- static HTML
- no database
- no control actions
- one-glance operational visibility

## Scope decision

This implementation round focuses on **horizontal scaling only**:

- more hosts
- same logic
- same severity model
- same output style

Two other directions remain intentionally out of scope for now:

### Later option 1 — time scaling
- snapshots over time
- simple history
- trend visibility
- more memory

### Later option 2 — UX / distribution scaling
- easier startup
- Docker image
- one-command launchers
- broader accessibility

## Smallest honest implementation

The smallest honest version is:

1. keep single-host behavior working by default
2. allow an optional `hosts:` list in YAML config
3. query each host via Docker context
4. merge all container rows into one static page
5. add a `Host` column to the table
6. keep one severity model across all hosts
7. keep watch mode and one-shot mode unchanged in spirit

## Config shape

```yaml
refresh_seconds: 60
cpu_warn_percent: 50
memory_warn_mb: 1024
docker_timeout_seconds: 8

hosts:
  - name: local
    docker_context: default
  - name: nas
    docker_context: nas-prod
```

Rules:

- if `hosts:` is missing, behave like the old single-host version
- each host entry may define a display `name`
- each host entry may define a Docker `docker_context`
- contexts are read-only from the tool perspective; the tool only calls `docker ps` and `docker stats`

## Runtime behavior

For each configured host:

1. run `docker --context <context> ps -a --format {{json .}}`
2. run `docker --context <context> stats --no-stream --format {{json .}}`
3. classify container severities with the existing rules
4. append rows into one combined HTML table
5. include host name in each row

## Output changes

The page keeps its current structure, but now shows:

- a combined summary across all hosts
- a `Host` column in the table
- warning messages per host if a context fails or live stats are unavailable

## Guardrails

This change must not:

- introduce a database
- introduce remote control actions
- introduce hidden background daemons
- require a web server
- break the current one-host quick start

## Acceptance

The implementation is successful when:

1. `python3 run.py --once` still works for one host
2. config with multiple Docker contexts produces one combined page
3. rows visibly show which host they belong to
4. failures on one host do not destroy the full page
5. the page remains readable at a glance
