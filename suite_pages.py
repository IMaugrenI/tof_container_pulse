"""Static Pulse Suite page registry.

This module intentionally has no runtime side effects.
It does not collect system data, call Docker, inspect hardware, scan ports,
or write files.

The registry is a small planning primitive for the multi-page Pulse Suite.
Future collectors and templates can import it without triggering expensive work.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PulsePage:
    """Metadata for one static Pulse Suite page."""

    key: str
    title: str
    output_path: str
    collector_module: str
    status: str
    summary: str


PULSE_PAGES: tuple[PulsePage, ...] = (
    PulsePage(
        key="container",
        title="Container Pulse",
        output_path="pulse.html",
        collector_module="pulse",
        status="active",
        summary="Docker container status, severity, CPU, memory, image, and notes.",
    ),
    PulsePage(
        key="hardware",
        title="Hardware Pulse",
        output_path="hardware.html",
        collector_module="hardware",
        status="planned",
        summary="Host CPU, RAM, swap, load, uptime, disk summary, and optional sensors.",
    ),
    PulsePage(
        key="ports",
        title="Port Pulse",
        output_path="ports.html",
        collector_module="ports",
        status="planned",
        summary="Local listening ports, bind addresses, Docker-published ports, and exposure status.",
    ),
    PulsePage(
        key="storage",
        title="Storage Pulse",
        output_path="storage.html",
        collector_module="storage",
        status="planned",
        summary="Mount usage, inode pressure, Docker logs, volumes, backups, and optional S.M.A.R.T. signals.",
    ),
    PulsePage(
        key="services",
        title="Service Pulse",
        output_path="services.html",
        collector_module="services",
        status="planned",
        summary="Configured health URLs, bot heartbeats, cron/script status, tunnel checks, and DNS/SSL signals.",
    ),
    PulsePage(
        key="security",
        title="Security Pulse",
        output_path="security.html",
        collector_module="security",
        status="planned",
        summary="SSH/fail2ban signals, Docker operational hygiene, config drift, and advisory-only safety checks.",
    ),
)


def get_page(key: str) -> PulsePage:
    """Return page metadata by key.

    Raises:
        KeyError: if the page key is not known.
    """

    for page in PULSE_PAGES:
        if page.key == key:
            return page
    raise KeyError(f"Unknown Pulse page: {key}")


def active_pages() -> tuple[PulsePage, ...]:
    """Return pages that currently have implemented collectors."""

    return tuple(page for page in PULSE_PAGES if page.status == "active")


def planned_pages() -> tuple[PulsePage, ...]:
    """Return pages that are intentionally documented but not implemented yet."""

    return tuple(page for page in PULSE_PAGES if page.status == "planned")


def navigation_items(include_planned: bool = True) -> tuple[PulsePage, ...]:
    """Return ordered pages for future UI navigation.

    By default this includes planned pages so the UI can expose the suite
    direction without implying that every collector is already implemented.
    """

    if include_planned:
        return PULSE_PAGES
    return active_pages()
