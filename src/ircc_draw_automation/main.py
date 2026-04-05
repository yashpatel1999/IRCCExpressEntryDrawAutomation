import argparse
import json

from ircc_draw_automation.fetcher import DEFAULT_SOURCE_URL
from ircc_draw_automation.scheduler import run_check


def build_parser():
    parser = argparse.ArgumentParser(prog="ircc_draw_automation")
    subparsers = parser.add_subparsers(dest="command")

    check_parser = subparsers.add_parser("check_latest_draw")
    check_parser.add_argument("--source-url", default=DEFAULT_SOURCE_URL)
    check_parser.add_argument("--state-file", default=None)
    check_parser.add_argument("--dry-run", action="store_true")
    check_parser.add_argument("--use-browser", action="store_true")
    check_parser.add_argument("--browser-rows-file", default=None)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    command = args.command or "check_latest_draw"

    try:
        if command != "check_latest_draw":
            raise ValueError("Unsupported command: %s" % command)

        result = run_check(
            source_url=args.source_url,
            state_file=args.state_file,
            dry_run=args.dry_run,
            use_browser=args.use_browser,
            browser_rows_file=args.browser_rows_file,
        )
        payload = result.to_dict()
    except Exception as exc:
        payload = {
            "changed": False,
            "reason": "run_failed",
            "error": str(exc),
        }

    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
