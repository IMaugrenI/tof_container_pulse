import argparse
import time
import webbrowser
from pathlib import Path

from hardware_xplat import generate_hardware_pulse
from ports_xplat import generate_port_pulse
from pulse import generate_pulse
from security_xplat import generate_security_pulse
from services import generate_services_pulse
from storage_xplat import generate_storage_pulse
from ui_overrides import (
    apply_active_ports_navigation,
    apply_active_security_navigation,
    apply_active_services_navigation,
    apply_active_storage_navigation,
    apply_container_suite_navigation,
    apply_generated_l10n,
    apply_platform_badges,
    apply_soft_light_mode_overrides,
)


def open_output_in_browser(output_path: str) -> None:
    try:
        file_url = Path(output_path).resolve().as_uri()
        webbrowser.open(file_url)
    except Exception:
        pass


def generate_suite(args) -> None:
    """Generate the static Pulse Suite pages.

    Each page generator is responsible for bounded, read-only collection work.
    Hardware, Ports, Storage, and Security use cross-platform wrappers that
    keep the existing Linux collectors and add macOS/Windows fallback paths.
    """

    generate_pulse(
        output_path=args.output,
        template_path=args.template,
        config_path=args.config,
        state_path=args.state_file,
    )
    generate_hardware_pulse(
        output_path=args.hardware_output,
        template_path=args.hardware_template,
        config_path=args.config,
        state_path=args.hardware_state_file,
    )
    generate_port_pulse(
        output_path=args.ports_output,
        template_path=args.ports_template,
        config_path=args.config,
        state_path=args.ports_state_file,
    )
    generate_storage_pulse(
        output_path=args.storage_output,
        template_path=args.storage_template,
        config_path=args.config,
        state_path=args.storage_state_file,
    )
    generate_services_pulse(
        output_path=args.services_output,
        template_path=args.services_template,
        config_path=args.config,
        state_path=args.services_state_file,
    )
    generate_security_pulse(
        output_path=args.security_output,
        template_path=args.security_template,
        config_path=args.config,
        state_path=args.security_state_file,
    )
    apply_soft_light_mode_overrides(args.output)
    apply_soft_light_mode_overrides(args.hardware_output)
    apply_soft_light_mode_overrides(args.ports_output)
    apply_soft_light_mode_overrides(args.storage_output)
    apply_soft_light_mode_overrides(args.services_output)
    apply_soft_light_mode_overrides(args.security_output)
    apply_container_suite_navigation(args.output)
    apply_active_ports_navigation(args.hardware_output)
    apply_active_storage_navigation(args.output)
    apply_active_storage_navigation(args.hardware_output)
    apply_active_storage_navigation(args.ports_output)
    apply_active_services_navigation(args.output)
    apply_active_services_navigation(args.hardware_output)
    apply_active_services_navigation(args.ports_output)
    apply_active_services_navigation(args.storage_output)
    apply_active_security_navigation(args.output)
    apply_active_security_navigation(args.hardware_output)
    apply_active_security_navigation(args.ports_output)
    apply_active_security_navigation(args.storage_output)
    apply_active_security_navigation(args.services_output)
    apply_platform_badges(args.output, "container")
    apply_platform_badges(args.hardware_output, "hardware")
    apply_platform_badges(args.ports_output, "ports")
    apply_platform_badges(args.storage_output, "storage")
    apply_platform_badges(args.services_output, "services")
    apply_platform_badges(args.security_output, "security")
    apply_generated_l10n(args.output)
    apply_generated_l10n(args.hardware_output)
    apply_generated_l10n(args.ports_output)
    apply_generated_l10n(args.storage_output)
    apply_generated_l10n(args.services_output)
    apply_generated_l10n(args.security_output)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate local static Pulse Suite pages.")
    parser.add_argument("--once", action="store_true", help="Generate static Pulse pages once and exit.")
    parser.add_argument("--watch", type=int, default=None, help="Regenerate every N seconds.")
    parser.add_argument("--output", default="pulse.html", help="Where to write the generated Container Pulse HTML file.")
    parser.add_argument("--template", default="template.html", help="Path to the Container Pulse HTML template file.")
    parser.add_argument("--hardware-output", default="hardware.html", help="Where to write the generated Hardware Pulse HTML file.")
    parser.add_argument("--hardware-template", default="hardware_template.html", help="Path to the Hardware Pulse HTML template file.")
    parser.add_argument("--ports-output", default="ports.html", help="Where to write the generated Port Pulse HTML file.")
    parser.add_argument("--ports-template", default="ports_template.html", help="Path to the Port Pulse HTML template file.")
    parser.add_argument("--storage-output", default="storage.html", help="Where to write the generated Storage Pulse HTML file.")
    parser.add_argument("--storage-template", default="storage_template.html", help="Path to the Storage Pulse HTML template file.")
    parser.add_argument("--services-output", default="services.html", help="Where to write the generated Services Pulse HTML file.")
    parser.add_argument("--services-template", default="services_template.html", help="Path to the Services Pulse HTML template file.")
    parser.add_argument("--security-output", default="security.html", help="Where to write the generated Security Pulse HTML file.")
    parser.add_argument("--security-template", default="security_template.html", help="Path to the Security Pulse HTML template file.")
    parser.add_argument("--config", default=None, help="Optional path to a YAML config file.")
    parser.add_argument("--state-file", default=".pulse_state.json", help="Path to the local Container Pulse state file.")
    parser.add_argument("--hardware-state-file", default=".hardware_pulse_state.json", help="Path to the local Hardware Pulse state file.")
    parser.add_argument("--ports-state-file", default=".port_pulse_state.json", help="Path to the local Port Pulse state file.")
    parser.add_argument("--storage-state-file", default=".storage_pulse_state.json", help="Path to the local Storage Pulse state file.")
    parser.add_argument("--services-state-file", default=".services_pulse_state.json", help="Path to the local Services Pulse state file.")
    parser.add_argument("--security-state-file", default=".security_pulse_state.json", help="Path to the local Security Pulse state file.")
    parser.add_argument(
        "--no-open",
        action="store_true",
        help="Do not open the generated Container Pulse file in the browser after a one-shot run.",
    )
    args = parser.parse_args()

    if args.once or args.watch is None:
        generate_suite(args)
        if not args.no_open:
            open_output_in_browser(args.output)
        return 0

    if args.watch <= 0:
        parser.error("--watch must be greater than zero.")

    while True:
        try:
            generate_suite(args)
        except Exception:
            pass
        time.sleep(args.watch)


if __name__ == "__main__":
    raise SystemExit(main())
