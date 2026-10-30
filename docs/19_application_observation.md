"""Optional Services Pulse application evidence – read-only contract.

The Suite's application panel reuses the in-process results of the *existing*
configured Services Pulse checks. No new service collection or network requests
are introduced by the panel.

Security rules:
- HTTP(S) endpoints must be explicitly configured; external URLs remain
  disabled by default.
- HTTP redirects are not followed. A redirect response is a review signal,
  not permission to contact another target.
- URL userinfo is rejected; query and path are not echoed into HTML.
- At most 100 configured checks per refresh; each network check has a bounded
  0.1-30 second timeout.
- Missing or failed collection shows UNKNOWN, not healthy or down.
- Observations belong to the machine *running* Services Pulse, and are not
  automatically attributed to any remote Docker Context/Host.
- The existing static HTML pages are retained; no DB, daemon, action API,
  or second start path is created.

Readiness: development-only, CI evidence; no operator/runtime acceptance.

## B3 – Explicit infrastructure associations (development)

The operator may optionally declare an `application_links` list in the existing YAML config. Each item contains:

- `check`: unique configured `service_checks[].name`;
- `host`: the displayed Docker host alias (or local hostname without a hosts list);
- `project`: exact Compose project name;
- `service`: exact Compose service name.

The Suite joins only the **current in-process observations** from Docker and Services Pulse. No second probe, inspect call, local DB, new startup command, or persistence is introduced. The static link table displays both independent statuses; it cannot infer service-to-container identity, an actual dependency, an outage from a missing container, or causal direction. Failed hosts display `NOT_COLLECTED`; absent containers on successfully queried hosts display `NOT_OBSERVED`. A duplicate application check name yields `UNKNOWN` and duplicate Docker host aliases are rejected to prevent cross-context mixing. At most 50 declared links are accepted.

The feature remains development-only until the final project-wide acceptance.

## B4 – Resource-deviation hints (development)

When the already existing `history_enabled` opt-in is active, the existing resource-trend section can additionally show unusually high CPU/memory deviations for an individual container, scoped by host alias and container ID. No new collection, persistence, daemon, external telemetry, or intervention is added.

Quality gates: current host successfully observed; at least eight valid prior measurements within the retained last 48 observations; at least five minutes between earliest and latest baseline sample; most recent prior sample at most one hour old; non-monotonic or excessive time gaps rejected; missing and invalid values ignored rather than treated as zero. A robust median and median absolute deviation plus a minimum absolute and relative increase are used. Results are capped at 12 and mean **statistical review hints only**; no memory-leak diagnosis, guarantee of future capacity, or causal proof. No hint is shown when evidence is insufficient.
