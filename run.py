import argparse
import time

from pulse import generate_pulse


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--watch", type=int, default=None)
    parser.add_argument("--output", default="pulse.html")
    parser.add_argument("--template", default="template.html")
    args = parser.parse_args()

    if args.once or args.watch is None:
        generate_pulse(output_path=args.output, template_path=args.template)
        return 0

    while True:
        try:
            generate_pulse(output_path=args.output, template_path=args.template)
        except Exception:
            pass
        time.sleep(args.watch)


if __name__ == "__main__":
    raise SystemExit(main())
