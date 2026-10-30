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
