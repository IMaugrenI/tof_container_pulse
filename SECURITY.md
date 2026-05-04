# Security policy

`tof_container_pulse` is a local, static, read-only Pulse Suite.

It generates local HTML pages for Docker/container, hardware, ports, storage, services, and security orientation.
It does not open a network service, create a database, expose a remote dashboard, or control the host.

Still, generated pages and local status output can reveal private infrastructure details.

## Please do not post private data

When opening issues, discussions, pull requests, or public screenshots, do not include:

- private hostnames
- private Docker context names
- customer names
- internal project names
- secret container names
- local usernames
- private IP addresses if they identify your environment
- tokens, passwords, API keys, or `.env` values
- private `config.yaml` or `multi_host.yaml` contents
- generated Pulse Suite HTML files from sensitive hosts
- raw logs from sensitive hosts

Generated files can include local machine context. Treat these as private unless you intentionally sanitized them:

- `pulse.html`
- `hardware.html`
- `ports.html`
- `storage.html`
- `services.html`
- `security.html`

Prefer reproductions with neutral container names, synthetic examples, and screenshots that hide private host details.

## Reporting security issues

If you believe you found a security problem, avoid posting sensitive details publicly.

Use GitHub security reporting when available, or open a minimal public issue that says a private security report is needed without disclosing secrets, hostnames, logs, screenshots, or private infrastructure details.

## Project boundary

This project is designed to:

- read local Docker CLI status data when Docker is available
- read local host visibility signals where the operating system exposes them
- generate local static HTML pages
- optionally repeat that generation in watch mode
- explain unavailable platform data calmly as optional, unknown, or N/A

This project is not designed to:

- restart containers
- modify Docker state
- change firewall rules
- change SSH settings
- change users or groups
- change services
- clean, repair, or remount storage
- run external scans
- expose a remote dashboard
- collect metrics into a database
- sync data to a cloud service
- auto-fix anything

## Platform notes

Linux has the deepest collectors.
macOS and Windows use baseline read-only adapters for platform-specific signals.

If a platform cannot provide a specific signal without extra permissions, Pulse Suite should still render and show optional, unknown, or N/A instead of crashing.
