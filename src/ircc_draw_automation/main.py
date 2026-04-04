import json

from ircc_draw_automation.scheduler import run_check


def main():
    try:
        result = run_check()
        payload = {
            "changed": result.changed,
            "reason": result.reason,
            "latest_draw": result.latest_draw.to_dict(),
        }
    except Exception as exc:
        payload = {
            "changed": False,
            "reason": "run_failed",
            "error": str(exc),
        }

    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
