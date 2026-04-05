# IRCC Express Entry Draw Notifier

This project is a starter architecture for monitoring the IRCC Express Entry rounds page and notifying you by SMS or WhatsApp when a **new draw** is published.

Target page:
- https://www.canada.ca/en/immigration-refugees-citizenship/corporate/mandate/policies-operational-instructions-agreements/ministerial-instructions/express-entry-rounds.html

## 1) High-level architecture

```text
┌────────────────────┐
│ Scheduler          │  (cron / GitHub Actions / Cloud Scheduler)
└─────────┬──────────┘
          │ triggers every X minutes
┌─────────▼──────────┐
│ Fetcher            │  (HTTP GET page + normalization)
└─────────┬──────────┘
          │ html
┌─────────▼──────────┐
│ Parser             │  (extract latest draw ID/date/program/CRS)
└─────────┬──────────┘
          │ structured draw object
┌─────────▼──────────┐
│ State Store        │  (last_draw_id + hash + sent_at)
│ (SQLite/Redis/S3)  │
└──────┬─────┬───────┘
       │new? │duplicate?
       │yes  │no action
┌──────▼─────────────┐
│ AI Enricher        │  (optional summary, confidence check)
└─────────┬──────────┘
          │ message
┌─────────▼──────────┐
│ Notifier           │  (Twilio SMS/WhatsApp)
└─────────┬──────────┘
          │ send result
┌─────────▼──────────┐
│ Observability      │  (logs, retries, alerts)
└────────────────────┘
```

## 2) Suggested modules

- `src/fetch_ircc_page.py`
  - Download page and save normalized HTML.
- `src/parse_latest_draw.py`
  - Parse the newest draw row/card and output JSON.
- `src/state_store.py`
  - Read/write `last_seen_draw_key` and idempotency metadata.
- `src/notify.py`
  - Send SMS/WhatsApp via Twilio (or equivalent).
- `src/main.py`
  - Orchestrate fetch → parse → compare → notify.

## 3) Data model (minimal)

## 2.1) Current scaffold

The initial implementation scaffold now lives under:

- `src/ircc_draw_automation/fetcher.py`
  - Fetches and normalizes the IRCC rounds page through the HTTP provider.
- `src/ircc_draw_automation/browser_source.py`
  - Legacy browser-row loader used by the MCP browser adapter.
- `src/ircc_draw_automation/mcp_browser_source.py`
  - MCP-branded browser fallback provider for rendered table rows.
- `src/ircc_draw_automation/parser.py`
  - Extracts the latest draw payload from HTML or normalized row data.
- `src/ircc_draw_automation/validator.py`
  - Rejects stale, incomplete, or implausible parsed draws.
- `src/ircc_draw_automation/scheduler.py`
  - Runs HTTP-first checks with MCP browser fallback and persisted state.
- `src/ircc_draw_automation/state_store.py`
  - Stores `last_seen_draw_key` and related run metadata in a local JSON file.
- `src/ircc_draw_automation/main.py`
  - CLI entrypoint for `check_latest_draw`.
- `tests/test_parser.py`
  - Parser tests with HTML and browser-row fixtures.

## 2.2) Current CLI

Run the default check:

```powershell
$env:PYTHONPATH='src'
python -m ircc_draw_automation.main check_latest_draw
```

Force the browser-backed fixture path:

```powershell
$env:PYTHONPATH='src'
python -m ircc_draw_automation.main check_latest_draw --use-browser --browser-rows-file tests/fixtures/browser_rows_fixture.json --dry-run
```

Live MCP browser path:

```powershell
npm install
npx playwright install chromium
$env:PYTHONPATH='src'
python -m ircc_draw_automation.main check_latest_draw --dry-run
```

When HTTP parsing is stale or broken, the app now spawns the local MCP browser server in `mcp/playwright_server.mjs`, opens the live IRCC page in Playwright, and extracts the rendered rows.

```json
{
  "draw_key": "2026-03-20_341",
  "draw_number": 341,
  "draw_date": "2026-03-20",
  "program": "Canadian Experience Class",
  "invitations": 7500,
  "crs_cutoff": 515,
  "tie_breaking": "2026-02-15T14:25:00Z",
  "source_url": "https://www.canada.ca/.../express-entry-rounds.html",
  "fetched_at": "2026-04-04T18:30:00Z",
  "content_hash": "sha256:..."
}
```

`draw_key` should be deterministic and stable. A common strategy:
- `draw_key = "{draw_date}_{draw_number}"`

## 4) Detection strategy (robust)

Use **2 checks together**:
1. Primary key check: newest `draw_key` differs from stored value.
2. Content hash check: normalized latest-draw block hash differs.

This prevents false positives from whitespace/page template changes.

## 5) Notification channels

### SMS
- Provider: Twilio Programmable SMS
- Destination: your verified number

### WhatsApp
- Provider: Twilio WhatsApp (sandbox for dev, approved sender in prod)
- Message template example:
  - `New IRCC Draw #341 (2026-03-20) | Program: CEC | ITAs: 7,500 | CRS: 515`

## 6) Where MCP server fits

You can place your automation behind an MCP server so AI tools can call your pipeline safely and consistently.

### MCP role in this project

Expose actions as MCP tools:
- `check_latest_draw`
- `get_last_seen_draw`
- `set_last_seen_draw`
- `send_test_notification`
- `run_full_check`

This gives you:
- Standardized tool interface for local/remote agents.
- Reusable automation from IDE agents, CLI agents, and chat assistants.
- Easier policy control (what tools can send notifications vs read-only).

### Example MCP tool contract

- `check_latest_draw() -> { latest_draw, changed, reason }`
- `run_full_check({ dry_run: boolean }) -> { changed, notified, message_id }`

Keep side-effect operations (`notify`) separate from read-only operations for safety.

## 7) Where AI helps (practical, optional)

AI is not required for basic detection, but useful for:
- **Message enrichment**: convert raw fields into clean human summary.
- **Parser resilience**: fallback extraction if page layout changes.
- **Change triage**: determine whether detected change is meaningful draw data.
- **Explainability**: “Why did I get this alert?” text.

### Recommended pattern

- Rule-based parser first (deterministic, cheap).
- AI fallback only if parser confidence is low or schema mismatch occurs.
- Always store parser confidence and raw snippet for audit.

## 8) Reliability checklist

- Idempotent notifications (never alert twice for same `draw_key`).
- Retry on transient HTTP / provider failures with backoff.
- Timeout budget (e.g., 8s fetch, 5s notify).
- Alerting if checks fail N consecutive times.
- Persist run history for debugging.
- Unit tests for parser with frozen HTML fixtures.

## 9) Security checklist

- Secrets in env vars / secret manager (`TWILIO_AUTH_TOKEN`, etc.).
- No secrets in logs.
- Validate outbound destination numbers.
- Signed webhook verification if you later add inbound callbacks.

## 10) Deployment options

- **Fastest**: GitHub Actions on schedule + small state file in artifact or external KV.
- **Production**: Docker container + Cloud Run / ECS + managed DB (SQLite -> Postgres).
- **Low-cost**: VPS with cron + SQLite.

## 11) MVP implementation plan

1. Build deterministic parser + test fixtures.
2. Add state store and duplicate-protection.
3. Integrate Twilio SMS first.
4. Add WhatsApp channel.
5. Add observability and retries.
6. Add MCP server wrapper around existing functions.
7. Add optional AI summarization/fallback parsing.

## 12) Success criteria

- Detects a newly posted draw within scheduled interval.
- Sends exactly one message per unique draw.
- Can run in `dry_run` for safe testing.
- Handles temporary website/provider failures without losing state.
