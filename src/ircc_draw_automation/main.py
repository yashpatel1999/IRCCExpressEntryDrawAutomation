import argparse
import json
import os
import sys

from ircc_draw_automation.config import load_dotenv_file
from ircc_draw_automation.fetcher import DEFAULT_SOURCE_URL
from ircc_draw_automation.models import SourcePayload, utc_now_iso
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
    check_parser.add_argument("--draw-html-file", default=None)
    check_parser.add_argument("--pool-html-file", default=None)
    check_parser.add_argument("--force-notify", action="store_true")

    notify_parser = subparsers.add_parser("send_test_notification")
    notify_parser.add_argument("--message", default="IRCC notifier test message")
    notify_parser.add_argument("--dry-run", action="store_true")

    return parser


def main(argv=None):
    load_dotenv_file()
    parser = build_parser()
    args = parser.parse_args(argv)
    command = args.command or "check_latest_draw"
    exit_code = 0

    try:
        if command == "check_latest_draw":
            http_provider = _build_html_file_provider(args.draw_html_file) if args.draw_html_file else None
            pool_distribution_provider = _build_html_file_provider(args.pool_html_file) if args.pool_html_file else None
            result = run_check(
                source_url=args.source_url,
                state_file=args.state_file,
                dry_run=args.dry_run,
                use_browser=args.use_browser,
                browser_rows_file=args.browser_rows_file,
                force_notify=args.force_notify,
                http_provider=http_provider,
                pool_distribution_provider=pool_distribution_provider,
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
            "error_type": type(exc).__name__,
            "error": str(exc),
        }
        exit_code = 1

    print(json.dumps(payload, indent=2))
    return exit_code

def _build_html_file_provider(path):
    absolute_path = os.path.abspath(path)

    def _provider(url):
        with open(absolute_path, "r", encoding="utf-8") as handle:
            html = handle.read()
        return SourcePayload(
            source_kind="http",
            source_url="file://%s" % absolute_path.replace("\\", "/"),
            fetched_at=utc_now_iso(),
            html=html,
            rows=None,
            diagnostics={"status_code": 200, "fixture_path": absolute_path},
        )

    return _provider


if __name__ == "__main__":
    sys.exit(main())
