import argparse
import time
import webbrowser
from pathlib import Path

from hardware import generate_hardware_pulse
from pulse import generate_pulse


def open_output_in_browser(output_path: str) -> None:
    try:
        file_url = Path(output_path).resolve().as_uri()
        webbrowser.open(file_url)
    except Exception:
        pass


def generate_suite(args) -> None:
    """Generate the currently implemented static Pulse Suite pages.

    Keep this explicit and small. Each page generator is responsible for its
    own bounded, read-only collection work.
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate local static Pulse Suite pages.")
    parser.add_argument("--once", action="store_true", help="Generate static Pulse pages once and exit.")
    parser.add_argument("--watch", type=int, default=None, help="Regenerate every N seconds.")
    parser.add_argument("--output", default="pulse.html", help="Where to write the generated Container Pulse HTML file.")
    parser.add_argument("--template", default="template.html", help="Path to the Container Pulse HTML template file.")
    parser.add_argument("--hardware-output", default="hardware.html", help="Where to write the generated Hardware Pulse HTML file.")
    parser.add_argument("--hardware-template", default="hardware_template.html", help="Path to the Hardware Pulse HTML template file.")
    parser.add_argument("--config", default=None, help="Optional path to a YAML config file.")
    parser.add_argument("--state-file", default=".pulse_state.json", help="Path to the local Container Pulse state file.")
    parser.add_argument("--hardware-state-file", default=".hardware_pulse_state.json", help="Path to the local Hardware Pulse state file.")
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
