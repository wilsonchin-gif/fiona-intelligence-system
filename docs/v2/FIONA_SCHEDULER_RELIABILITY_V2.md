# Fiona Scheduler Reliability V2

版本：Phase 0B  
状态：Implemented locally, not committed  
负责人：Wilson / Codex  
更新时间：2026-07-04

## 1. Previous Failure Mode

Production V1 scheduler relied on:

```text
polling interval + due_brief_kinds(now, ±15 minutes)
```

With `WILSON_INTERVAL_MINUTES=240`, a process starting at midnight checked roughly:

```text
00:00, 04:00, 08:00, 12:00, 16:00, 20:00
```

This missed:

- 07:30 Fiona Morning
- 20:30 Fiona Evening
- 22:30 Fiona Daily
- Sunday 21:00 Fiona Weekly

The old scheduler had no execution ledger, no bounded catch-up, and no scheduler-level idempotency.

## 2. New Scheduling Model

Phase 0B introduces:

```text
Frequent Polling
+
Due Detection
+
Execution Ledger
+
Bounded Catch-up
+
Idempotency
+
Restart Recovery
```

The scheduler now detects scheduled occurrences between:

```text
(last_check_at, current_time]
```

On first startup, it uses a bounded startup lookback window instead of scanning unlimited history.

## 3. Polling Interval

Default scheduler polling interval:

```text
5 minutes
```

Effective variable precedence:

1. explicit CLI `--interval-minutes`
2. `WILSON_INTERVAL_MINUTES`
3. `FIONA_RUNTIME_INTERVAL_MINUTES`
4. default `5`

`FIONA_ALERT_INTERVAL_MINUTES` is intentionally not used for brief scheduler polling, so Alert polling cannot be confused with the production brief scheduler.

Invalid values fall back to `5`:

- `0`
- negative values
- malformed strings

Minimum accepted configured value:

```text
1 minute
```

## 4. Occurrence Identity

Every scheduled run receives a deterministic occurrence ID:

```text
{brief_name}:{scheduled_local_datetime}
```

Examples:

```text
morning:2026-07-04T07:30:00+08:00
weekly:2026-07-05T21:00:00+08:00
```

Properties:

- timezone-aware
- stable across restart
- independent from process start time
- independent from random UUIDs

## 5. Catch-up Policy

| Task | Scheduled Time | Catch-up Max Age |
|---|---:|---:|
| Market News | 00:00 | 60 minutes |
| Morning | 07:30 | 120 minutes |
| Evening | 20:30 | 150 minutes |
| Daily | 22:30 | 180 minutes |
| Weekly | Sunday 21:00 | 240 minutes |

Weekly uses `240 minutes`, not `360 minutes`, so Monday 02:00 does not send a stale Sunday Weekly. This matches the product requirement that old Weekly briefings should not be pushed after they lose timing value.

Expired occurrences are recorded as:

```text
skipped_expired
```

## 6. Execution Ledger

Local ledger file:

```text
reports/fiona/fiona_scheduler_ledger.json
```

Schema fields:

```text
occurrence_id
task_name
brief_name
scheduled_at
detected_at
started_at
finished_at
status
attempt_count
catch_up
error_summary
updated_at
```

Statuses:

```text
pending
running
success
failed
skipped_expired
unknown_delivery_state
```

## 7. Idempotency Semantics

Same `occurrence_id` behavior:

- `success`: never send again
- `running`: block retry until stale
- `failed`: retry only while within catch-up window and below max attempts
- `skipped_expired`: never send
- `unknown_delivery_state`: never auto-resend

Retry policy:

```text
max_attempts = 3
stale_running_after = 30 minutes
retry must remain inside catch-up max age
```

## 8. Telegram Boundary

Production `send=true` success requires:

```text
status["brief_push"]["ok"] == true
and
message_ids is non-empty
```

For dry-run `send=false`, scheduler tests may mark runtime success without Telegram delivery because no real user delivery is attempted.

No Telegram user-visible content is changed in Phase 0B.

## 9. Dangerous Delivery State

Dangerous state:

```text
Telegram send success
+
ledger success write failure
```

Phase 0B handles it by marking:

```text
unknown_delivery_state
```

If the filesystem write itself is unavailable, the process cannot guarantee exactly-once delivery after restart. The in-process state prevents another send during the same process lifetime, but a filesystem loss can still create duplicate risk.

## 10. Persistence Limitations

Current ledger persistence class:

```text
EPHEMERAL
```

Current guarantee:

```text
best-effort restart recovery within surviving filesystem state
```

Not guaranteed:

```text
exactly-once delivery across Railway redeploy / filesystem loss
```

## 11. Phase 0B.1 Hardening

Phase 0B.1 adds:

- delivery arbitration for same-cycle collisions
- `suppressed_collision` and `deferred_collision` ledger states
- chunk-level Telegram delivery status
- `partial_delivery` stop-retry semantics
- per-task startup lookback instead of 24h startup scan
- top-level scheduler-cycle exception guard
- secondary uncertain delivery journal

Updated catch-up windows:

| Task | Catch-up Max Age |
|---|---:|
| Market News | 60 minutes |
| Morning | 120 minutes |
| Evening | 150 minutes |
| Daily | 180 minutes |
| Weekly | 240 minutes |

## 12. Railway Limitations

Railway filesystem state may not survive all redeploys or platform moves.

If Railway runs more than one replica, local JSON ledger cannot prevent cross-replica duplicate sends. Phase 0B does not introduce distributed locking, Redis, PostgreSQL, Celery, or an external queue.

## 13. Rollback Plan

Rollback code path:

1. revert Phase 0B scheduler module and runtime scheduler integration
2. restore old `run_scheduler()` loop calling `run_once(brief="auto")`
3. keep Railway command unchanged

Rollback risk:

The old scheduler is already known to miss tasks under 240-minute polling and has no catch-up.
