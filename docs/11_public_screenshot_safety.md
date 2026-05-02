# Public screenshot safety

`tof_container_pulse` can produce screenshots that look useful but still reveal private infrastructure details.

Use this checklist before placing screenshots in the README, release notes, issues, or public docs.

## Safe screenshot checklist

Before publishing, confirm that the screenshot does not show:

- private hostnames
- private Docker context names
- customer names
- private project names
- secret or sensitive container names
- private registry names
- internal URLs
- tokens, keys, passwords, or `.env` values
- local filesystem paths you do not want public

## Preferred public screenshot style

A good public screenshot should show:

- the generated static dashboard
- neutral or public-safe container names
- useful status columns
- severity states such as ok, warn, critical, or unknown
- no secrets and no private operational context

## When to redact

If the screenshot is technically useful but contains private names, redact or crop before publishing.

If heavy redaction makes the screenshot hard to trust, prefer a fresh local demo run using neutral container names.

## Issue reports

When reporting bugs, avoid attaching full private screenshots.

Prefer:

- a cropped screenshot
- copied error text with private names removed
- a minimal synthetic reproduction
- neutral example config files
