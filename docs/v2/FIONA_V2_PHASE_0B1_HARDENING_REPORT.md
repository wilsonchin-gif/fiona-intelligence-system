# Fiona V2 Phase 0B.1 Hardening Report

版本：Phase 0B.1  
状态：Implemented locally, not committed  
负责人：Wilson / Codex  
更新时间：2026-07-06

## 1. Scope

This patch addresses the Phase 0B Release Gate blockers before production deploy.

It does not:

- change brief templates
- change Telegram user-visible text
- enable Alert
- modify Railway secrets
- introduce DB / Redis / queue / distributed lock

## 2. Interval Safety

Production recommendation is now:

```text
WILSON_INTERVAL_MINUTES=5
```

Updated:

```text
README.md
config/fiona.env.example
```

Production Railway env verification is still required before deploy.

## 3. Delivery Arbitration

Implemented:

```text
SEND
SUPPRESS
DEFER
```

Collision window:

```text
180 minutes
```

Suppressed occurrence ledger status:

```text
suppressed_collision
```

Deferred occurrence ledger status:

```text
deferred_collision
```

## 4. Telegram Partial Delivery

`push_text()` now returns:

```text
delivery_status = success | partial_delivery | failed
successful_chunks
failed_chunks
message_ids
errors
```

Occurrence `success` requires all chunks to succeed.

`partial_delivery` is not retried automatically to avoid repeating already-delivered chunks.

## 5. Per-task Startup Lookback

Unified 24h startup lookback was removed.

Startup discovery is now bounded by each task's catch-up window:

| Brief | Startup Discovery / Catch-up |
|---|---:|
| Market News | 60m |
| Morning | 120m |
| Evening | 150m |
| Daily | 180m |
| Weekly | 240m |

Expired occurrences outside these windows are ignored and do not create ledger flood.

## 6. Top-level Scheduler Guard

Unexpected scheduler-cycle exceptions are caught in `run_scheduler()`.

Behavior:

- print cycle error status
- keep process alive
- sleep with bounded backoff
- continue next cycle

## 7. Unknown Delivery Hardening

Retained:

```text
unknown_delivery_state
```

Added:

```text
fiona_scheduler_delivery_uncertain.log
```

and in-process uncertain occurrence memory.

Limit:

Railway filesystem remains ephemeral. This does not provide exactly-once delivery across redeploy or filesystem loss.

## 8. Stale Running Hardening

Stale running retry is blocked if:

- occurrence is known uncertain
- occurrence is `partial_delivery`
- occurrence is `suppressed_collision`
- occurrence is expired
- max attempts reached

## 9. Validation

```text
Python compile check: passed
Unit tests: 102 passed
```

## 10. Remaining Deployment Gates

Required before deploy:

- verify Railway service type is long-running service
- verify Railway replicas = 1
- verify Railway Variables use `WILSON_INTERVAL_MINUTES=5` or no interval override

