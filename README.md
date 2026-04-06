# IRCC Express Entry Notifier

This project monitors two IRCC pages and sends iPhone push notifications through `ntfy`:

- Express Entry draw updates  
  `https://www.canada.ca/en/immigration-refugees-citizenship/corporate/mandate/policies-operational-instructions-agreements/ministerial-instructions/express-entry-rounds.html`
- CRS pool distribution updates  
  `https://www.canada.ca/en/immigration-refugees-citizenship/services/immigrate-canada/express-entry/rounds-invitations.html`

The production path is:
- GitHub Actions scheduler
- HTTP-first parsing
- MCP/Playwright browser fallback when HTTP parsing fails
- JSON state persisted on the `scheduler-state` branch
- `ntfy` push notifications to iPhone

## Architecture

```text
GitHub Actions Scheduler
  -> HTTP fetcher
  -> deterministic parser
  -> validator
  -> MCP browser fallback when needed
  -> state store
  -> ntfy notifier
  -> JSON logs + run summaries
```

There are two independent monitors in the same run:
- draw monitor
- CRS pool distribution monitor

Each has its own state key, change detection, and notification result.

## Repo Layout

- `src/ircc_draw_automation/fetcher.py`
  - HTTP source providers and source URLs.
- `src/ircc_draw_automation/parser.py`
  - Draw parser and CRS pool distribution parser from HTML or browser rows.
- `src/ircc_draw_automation/validator.py`
  - Draw validation and confidence checks.
- `src/ircc_draw_automation/browser_source.py`
  - Browser row normalization for draw and pool tables.
- `src/ircc_draw_automation/mcp_client.py`
  - Python MCP client that spawns the Playwright MCP server.
- `mcp/playwright_server.mjs`
  - Playwright MCP server used for live browser fallback.
- `src/ircc_draw_automation/scheduler.py`
  - Main orchestration, state update, notifier calls, summaries, heartbeat.
- `src/ircc_draw_automation/state_store.py`
  - JSON state, event log, latest summary, run history.
- `src/ircc_draw_automation/notifier.py`
  - `ntfy`, dry-run, and optional Twilio notifier support.
- `src/ircc_draw_automation/enricher.py`
  - Notification message formatting.
- `src/ircc_draw_automation/main.py`
  - CLI entrypoint.

## CLI

Set:

```powershell
$env:PYTHONPATH='src'
```

Run the normal check:

```powershell
python -m ircc_draw_automation.main check_latest_draw
```

Dry run:

```powershell
python -m ircc_draw_automation.main check_latest_draw --dry-run
```

Force browser path for draw debugging:

```powershell
python -m ircc_draw_automation.main check_latest_draw --use-browser --browser-rows-file tests/fixtures/browser_rows_fixture.json --dry-run
```

Use local HTML fixtures for manual testing:

```powershell
python -m ircc_draw_automation.main check_latest_draw --draw-html-file "C:\path\to\draw_test.html" --pool-html-file "C:\path\to\pool_test.html" --state-file "state\manual-test-state.json"
```

Send a standalone test notification:

```powershell
python -m ircc_draw_automation.main send_test_notification --message "IRCC ntfy test alert"
```

Force notifications even if state is unchanged:

```powershell
python -m ircc_draw_automation.main check_latest_draw --force-notify
```

`--force-notify` is intended for manual testing only.

## Notification Setup

Recommended notifier: `ntfy`

Local `.env` keys:

```env
NTFY_SERVER_URL=https://ntfy.sh
NTFY_TOPIC=your-topic
NTFY_TITLE=IRCC Express Entry Alert
NTFY_DRAW_TITLE=IRCC Draw Alert
NTFY_POOL_TITLE=IRCC Pool Distribution Alert
NTFY_USERNAME=
NTFY_PASSWORD=
NTFY_TOKEN=
```

Notes:
- `NTFY_DRAW_TITLE` overrides the draw notification title.
- `NTFY_POOL_TITLE` overrides the pool distribution title.
- If `ntfy` is not configured, the app falls back to dry-run behavior.

Optional Twilio fallback is still supported through:
- `TWILIO_ACCOUNT_SID`
- `TWILIO_AUTH_TOKEN`
- `TWILIO_FROM_NUMBER`
- `TWILIO_TO_NUMBER`

## GitHub Actions Production Setup

Workflow:
- `.github/workflows/ircc-draw-scheduler.yml`

Current production behavior:
- scheduled on weekdays only
- checked every 30 minutes
- only processes during Toronto business hours
- manual runs are allowed any time

Current scheduled trigger:
- `*/30 * * * 1-5`

Runtime gate:
- Monday to Friday
- `09:00` to `17:59` in `America/Toronto`

GitHub repository secrets required for real iPhone notifications:
- `NTFY_SERVER_URL`
- `NTFY_TOPIC`
- `NTFY_TITLE`
- `NTFY_DRAW_TITLE`
- `NTFY_POOL_TITLE`

Optional if your ntfy server needs auth:
- `NTFY_USERNAME`
- `NTFY_PASSWORD`
- `NTFY_TOKEN`

Important:
- Create each of these as a separate repository secret.
- Do not combine them into one multi-line secret.

## MCP Fallback

Both monitors use the same pattern:
- try HTTP first
- if parse fails or data is incomplete, use MCP browser fallback

The MCP server:
- is implemented in `mcp/playwright_server.mjs`
- is launched by the Python scheduler during the run
- runs inside GitHub Actions for production

Current fallback behavior:
- draw monitor: HTTP first, MCP fallback
- pool distribution monitor: HTTP first, MCP fallback

## State and Logs

Runtime state is not stored on `main`. It is stored on the `scheduler-state` branch.

Files:
- `state/ircc_draw_state.json`
  - persisted scheduler state
- `state/ircc_draw.log.jsonl`
  - detailed event log, appended across runs
- `state/latest_run_summary.json`
  - one readable summary for the latest run
- `state/run_history.jsonl`
  - one summary line per run, appended across runs

Artifacts:
- GitHub Actions also uploads these files as `ircc-scheduler-state`

## What Gets Logged

Examples of event log entries:
- `run_started`
- `http_parse_valid`
- `http_failed`
- `browser_fallback_used`
- `draw_comparison_complete`
- `notification_sent`
- `notification_skipped`
- `pool_distribution_checked`
- `pool_distribution_notification_sent`
- `workflow_run_outcome`

`run_started` also logs notifier diagnostics, including:
- selected provider
- whether ntfy is configured
- whether the ntfy topic is present

## Heartbeat

Each run summary includes:
- `expected_interval_minutes`
- `previous_checked_at`
- `observed_gap_minutes`
- `missed_schedule_suspected`

This helps detect delayed or skipped GitHub scheduled runs.

## Manual End-to-End Test in GitHub

1. Add the repository secrets listed above.
2. Open `Actions` -> `IRCC Draw Scheduler`.
3. Click `Run workflow`.
4. Set:
   - `delay_seconds = 0`
   - `force_notify = true`
5. Start the run.

Expected:
- draw notification is sent even if draw state is unchanged
- pool notification is sent even if pool state is unchanged
- logs and summaries are updated in `scheduler-state`

## Pool Distribution Notification Format

Pool notifications include row highlights, for example:

```text
IRCC CRS pool distribution updated (date unavailable) | Total candidates: unknown | 601-1200: 351 | 501-600: 11648 | 451-500: 73445
```

If the browser fallback cannot recover the table date or total, the row details are still included.

## Reliability Notes

- Notifications are idempotent by state key unless `--force-notify` is used.
- Draw and pool distribution state are tracked independently.
- Notification failures do not destroy state.
- Historical run files are restored before each GitHub run so logs and summaries accumulate.

## Current Status

The current implementation supports:
- real ntfy notifications from GitHub Actions
- MCP fallback in production
- business-hours weekday scheduling
- force-notify manual tests
- persisted state and historical summaries
- local HTML fixture testing
