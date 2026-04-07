# Runtime Flow

This file shows the actual code path for the scheduler, parser, MCP fallback, state updates, and notifications.

## Main Entry

```mermaid
sequenceDiagram
    participant GH as GitHub Actions / CLI
    participant Main as main.py
    participant Scheduler as scheduler.run_check
    participant Store as JsonStateStore
    participant Notifier as build_default_notifier

    GH->>Main: python -m ircc_draw_automation.main check_latest_draw
    Main->>Main: load_dotenv_file()
    Main->>Scheduler: run_check(...)
    Scheduler->>Notifier: build_default_notifier(dry_run)
    Scheduler->>Store: read_state()
    Scheduler->>Scheduler: log_event("run_started")
```

## Draw Flow

```mermaid
sequenceDiagram
    participant Scheduler as scheduler.run_check
    participant HTTP as fetch_http_source
    participant Parser as parse_latest_draw_from_html
    participant Validator as validate_draw_record
    participant MCP as fetch_browser_source
    participant BrowserParser as parse_latest_draw_from_rows
    participant Store as JsonStateStore
    participant Notify as notifier.send

    Scheduler->>HTTP: http_provider(url=source_url)
    HTTP-->>Scheduler: SourcePayload(html=...)
    Scheduler->>Parser: parse_latest_draw_from_html(html, source_url)
    Parser-->>Scheduler: DrawRecord
    Scheduler->>Validator: validate_draw_record(draw)
    Validator-->>Scheduler: ValidationResult

    alt HTTP parse valid
        Scheduler->>Scheduler: reason = http_primary_success
    else HTTP fetch/parse/validation failed
        Scheduler->>Scheduler: log_event("http_failed" or "http_parse_invalid")
        Scheduler->>MCP: browser_provider(url, fixture_path)
        MCP-->>Scheduler: SourcePayload(rows=...)
        Scheduler->>BrowserParser: parse_latest_draw_from_rows(rows, source_url)
        BrowserParser-->>Scheduler: DrawRecord
        Scheduler->>Validator: validate_draw_record(draw)
        Validator-->>Scheduler: ValidationResult
        Scheduler->>Scheduler: reason = http_failed_browser_used / http_parse_low_confidence_browser_used
    end

    Scheduler->>Scheduler: compare draw_key with state.last_seen_draw_key
    alt dry_run == false
        Scheduler->>Store: write_state(...)
        Scheduler->>Scheduler: log_event("state_updated")
    end

    alt should notify
        Scheduler->>Notify: send(draw_message, title=draw title)
        Notify-->>Scheduler: NotificationResult
        alt notification sent
            Scheduler->>Store: append_notification(...)
            Scheduler->>Store: write_state(last_notified_draw_key=draw_key)
        end
    else notification skipped
        Scheduler->>Scheduler: log_event("notification_skipped")
    end
```

## Pool Distribution Flow

```mermaid
sequenceDiagram
    participant Scheduler as _run_pool_distribution_check
    participant HTTP as fetch_http_source
    participant Parser as parse_pool_distribution_from_html
    participant MCP as fetch_pool_distribution_browser_source
    participant BrowserParser as parse_pool_distribution_from_rows
    participant Store as JsonStateStore
    participant Notify as notifier.send

    Scheduler->>HTTP: pool_distribution_provider(url=pool_distribution_url)
    HTTP-->>Scheduler: SourcePayload(html=...)
    Scheduler->>Parser: parse_pool_distribution_from_html(html, source_url)
    Parser-->>Scheduler: PoolDistributionRecord

    alt HTTP parse failed
        Scheduler->>Scheduler: log_event("pool_distribution_http_failed")
        Scheduler->>MCP: pool_distribution_browser_provider(url)
        MCP-->>Scheduler: SourcePayload(rows=...)
        Scheduler->>BrowserParser: parse_pool_distribution_from_rows(rows, source_url)
        BrowserParser-->>Scheduler: PoolDistributionRecord
        Scheduler->>Scheduler: log_event("pool_distribution_browser_fallback_used")
    end

    Scheduler->>Scheduler: compare distribution_key with state.pool_distribution.last_seen_key
    alt dry_run == false
        Scheduler->>Store: write_state(pool_distribution=...)
    end

    alt should notify
        Scheduler->>Notify: send(pool_message, title=pool title)
        Notify-->>Scheduler: NotificationResult
        alt notification sent
            Scheduler->>Store: write_state(pool_distribution.last_notified_key=distribution_key)
        end
    else notification skipped
        Scheduler->>Scheduler: log_event("pool_distribution_notification_skipped")
    end
```

## Summary And History

```mermaid
flowchart TD
    A[run_check completes draw flow] --> B[_run_pool_distribution_check]
    B --> C[_build_heartbeat]
    C --> D[summary dict]
    D --> E[JsonStateStore.write_latest_run_summary]
    D --> F[JsonStateStore.append_run_history]
    D --> G[return SchedulerRunResult]
```

## Method Order

Typical production run:

1. `main.main()`
2. `load_dotenv_file()`
3. `scheduler.run_check()`
4. `build_default_notifier()`
5. `JsonStateStore.read_state()`
6. `log_event("run_started")`
7. Draw branch:
   - `fetch_http_source()` or injected provider
   - `parse_latest_draw_from_html()`
   - `validate_draw_record()`
   - optional fallback:
     - `fetch_browser_source()`
     - `parse_latest_draw_from_rows()`
8. Draw change detection and optional notification
9. `_run_pool_distribution_check()`
10. Pool branch:
   - `fetch_http_source()` or injected provider
   - `parse_pool_distribution_from_html()`
   - optional fallback:
     - `fetch_pool_distribution_browser_source()`
     - `parse_pool_distribution_from_rows()`
11. Pool change detection and optional notification
12. `_build_heartbeat()`
13. `JsonStateStore.write_latest_run_summary()`
14. `JsonStateStore.append_run_history()`
15. return `SchedulerRunResult`

## Important Files

- `src/ircc_draw_automation/main.py`
- `src/ircc_draw_automation/scheduler.py`
- `src/ircc_draw_automation/fetcher.py`
- `src/ircc_draw_automation/parser.py`
- `src/ircc_draw_automation/browser_source.py`
- `src/ircc_draw_automation/mcp_client.py`
- `mcp/playwright_server.mjs`
- `src/ircc_draw_automation/state_store.py`
- `src/ircc_draw_automation/notifier.py`
