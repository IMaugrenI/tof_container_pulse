"""Static Pulse Suite page registry.

This module intentionally has no runtime side effects.
It does not collect system data, call Docker, inspect hardware, scan ports,
inspect storage, inspect services, inspect security signals, or write files.

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
        summary="Docker container status, severity, CPU, memory, image, and notes. Works anywhere Docker CLI is available.",
    ),
    PulsePage(
        key="hardware",
        title="Hardware Pulse",
        output_path="hardware.html",
        collector_module="hardware_xplat",
        status="active",
        summary="Cross-platform host CPU, RAM, swap, load, uptime, disk, and platform-dependent sensor hints.",
    ),
    PulsePage(
        key="ports",
        title="Port Pulse",
        output_path="ports.html",
        collector_module="ports_xplat",
        status="active",
        summary="Cross-platform local listening-port overview with Linux, macOS, and Windows read-only adapters.",
    ),
    PulsePage(
        key="storage",
        title="Storage Pulse",
        output_path="storage.html",
        collector_module="storage_xplat",
        status="active",
        summary="Cross-platform local volume usage with Linux deep details and macOS/Windows baseline volume adapters.",
    ),
    PulsePage(
        key="services",
        title="Services Pulse",
        output_path="services.html",
        collector_module="services",
        status="active",
        summary="Explicitly configured local service checks, HTTP checks, TCP checks, and heartbeat-file freshness.",
    ),
    PulsePage(
        key="security",
        title="Security Pulse",
        output_path="security.html",
        collector_module="security_xplat",
        status="active",
        summary="Cross-platform local safety orientation with Linux deep details and macOS/Windows baseline security adapters.",
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
