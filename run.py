import argparse
import time

from pulse import generate_pulse


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a local static Docker host pulse page.")
    parser.add_argument("--once", action="store_true", help="Generate pulse.html once and exit.")
    parser.add_argument("--watch", type=int, default=None, help="Regenerate every N seconds.")
    parser.add_argument("--output", default="pulse.html", help="Where to write the generated HTML file.")
    parser.add_argument("--template", default="template.html", help="Path to the HTML template file.")
    parser.add_argument("--config", default=None, help="Optional path to a YAML config file.")
    parser.add_argument("--state-file", default=".pulse_state.json", help="Path to the local state file.")
    args = parser.parse_args()

    if args.once or args.watch is None:
        generate_pulse(
            output_path=args.output,
            template_path=args.template,
            config_path=args.config,
            state_path=args.state_file,
        )
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
