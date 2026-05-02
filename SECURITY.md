# Security policy

`tof_container_pulse` is a local read-only Docker observer.
It does not open a network service, create a database, or control containers.

Still, Docker status output can reveal private infrastructure details.

## Please do not post private data

When opening issues, discussions, pull requests, or public screenshots, do not include:

- private hostnames
- private Docker context names
- customer names
- internal project names
- secret container names
- tokens, passwords, API keys, or `.env` values
- private `config.yaml` or `multi_host.yaml` contents
- generated `pulse.html` files from sensitive hosts

Prefer reproductions with neutral container names and synthetic examples.

## Reporting security issues

If you believe you found a security problem, avoid posting sensitive details publicly.

Use GitHub security reporting when available, or open a minimal public issue that says a private security report is needed without disclosing secrets, hostnames, or private infrastructure details.

## Project boundary

This project is designed to:

- read Docker CLI status data
- generate a local static HTML page
- optionally repeat that generation in watch mode

This project is not designed to:

- restart containers
- modify Docker state
- expose a remote dashboard
- collect metrics into a database
- sync data to a cloud service
