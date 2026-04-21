import argparse
import time
import webbrowser
from pathlib import Path

from pulse import generate_pulse


def open_output_in_browser(output_path: str) -> None:
    try:
        file_url = Path(output_path).resolve().as_uri()
        webbrowser.open(file_url)
    except Exception:
        pass


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a local static Docker host pulse page.")
    parser.add_argument("--once", action="store_true", help="Generate pulse.html once and exit.")
    parser.add_argument("--watch", type=int, default=None, help="Regenerate every N seconds.")
    parser.add_argument("--output", default="pulse.html", help="Where to write the generated HTML file.")
    parser.add_argument("--template", default="template.html", help="Path to the HTML template file.")
    parser.add_argument("--config", default=None, help="Optional path to a YAML config file.")
    parser.add_argument("--state-file", default=".pulse_state.json", help="Path to the local state file.")
    parser.add_argument(
        "--no-open",
        action="store_true",
        help="Do not open the generated HTML file in the browser after a one-shot run.",
    )
    args = parser.parse_args()

    if args.once or args.watch is None:
        generate_pulse(
            output_path=args.output,
            template_path=args.template,
            config_path=args.config,
            state_path=args.state_file,
        )
        if not args.no_open:
            open_output_in_browser(args.output)
        return 0

    if args.watch <= 0:
        parser.error("--watch must be greater than zero.")

    while True:
        try:
            generate_pulse(
                output_path=args.output,
                template_path=args.template,
                config_path=args.config,
                state_path=args.state_file,
            )
        except Exception:
            pass
        time.sleep(args.watch)


if __name__ == "__main__":
    raise SystemExit(main())
