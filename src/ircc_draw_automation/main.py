import argparse
import json

from ircc_draw_automation.config import load_dotenv_file
from ircc_draw_automation.fetcher import DEFAULT_SOURCE_URL
from ircc_draw_automation.notifier import build_default_notifier
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

    notify_parser = subparsers.add_parser("send_test_notification")
    notify_parser.add_argument("--message", default="IRCC notifier test message")
    notify_parser.add_argument("--dry-run", action="store_true")

    return parser


def main(argv=None):
    load_dotenv_file()
    parser = build_parser()
    args = parser.parse_args(argv)
    command = args.command or "check_latest_draw"

    try:
        if command == "check_latest_draw":
            result = run_check(
                source_url=args.source_url,
            state_file=args.state_file,
            dry_run=args.dry_run,
            use_browser=args.use_browser,
            browser_rows_file=args.browser_rows_file,
        )
            payload = result.to_dict()
        elif command == "send_test_notification":
            notifier = build_default_notifier(dry_run=args.dry_run)
            notification_result = notifier.send(args.message)
            payload = {
                "sent": notification_result.sent,
                "provider": notification_result.provider,
                "message": notification_result.message,
                "message_id": notification_result.message_id,
                "reason": notification_result.reason,
            }
        else:
            raise ValueError("Unsupported command: %s" % command)
    except Exception as exc:
        payload = {
            "changed": False,
            "reason": "run_failed",
            "error": str(exc),
        }

    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
