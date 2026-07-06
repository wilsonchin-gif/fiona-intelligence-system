# Fiona V2 Phase 0B Report

版本：Phase 0B  
状态：Implemented locally, not committed  
负责人：Wilson / Codex  
更新时间：2026-07-04

## 1. Goal

Fix Production Scheduler Delivery Risk without changing:

- five scheduled task times
- Telegram user-visible text
- brief templates
- Railway command
- Telegram secrets
- Alert state

## 2. Decisions

### Decision 1: Add isolated scheduler module

New module:

```text
app/fiona_scheduler.py
```

Why:

Scheduler reliability logic now includes occurrence detection, ledger state, catch-up, retry, and idempotency. Keeping it outside `app/fiona_runtime.py` reduces runtime complexity.

### Decision 2: Default polling interval is 5 minutes

Why:

5-minute polling ensures every fixed-time task is detected during normal continuous operation.

### Decision 3: Remove Alert interval from brief scheduler precedence

Why:

`FIONA_ALERT_INTERVAL_MINUTES` belongs to Alert polling semantics and should not control the brief scheduler.

### Decision 4: Use local JSON ledger for Phase 0B

Why:

Phase 0B explicitly forbids PostgreSQL, Redis, Celery, and external queues. JSON ledger is acceptable as a best-effort scheduler reliability layer.

### Decision 5: Weekly catch-up max age is 240 minutes

Why:

This prevents Monday 02:00 from sending a stale Sunday Weekly.

## 3. New Scheduler Behavior

Scheduler flow:

```text
run_scheduler
↓
run_scheduler_cycle
↓
load SchedulerLedger
↓
due_occurrences(last_check_at, now)
↓
execute_scheduled_occurrence
↓
run_once(brief=<explicit kind>)
↓
Telegram success boundary
↓
ledger status update
```

## 4. Backward Compatibility

Maintained:

- Railway start command remains unchanged.
- CLI `run-scheduler` remains unchanged.
- `run_once()` remains unchanged for manual generation.
- `due_brief_kinds()` remains available for older tests and manual `brief=auto` behavior.
- five task times remain unchanged.

## 5. Restart Recovery

Supported when ledger file survives:

- process starts 07:40: catches Morning
- process restarts 20:50: catches Evening
- process restarts 23:10: catches Daily
- Sunday 21:20 restart: catches Weekly
- Monday 02:00: Weekly expired, not sent

## 6. Assumptions

- Production Railway should run a single scheduler instance.
- Telegram push success means `brief_push.ok` and non-empty `message_ids`.
- Local JSON state is best-effort, not durable.
- Catch-up should prioritize timely value over completeness.

## 7. Unresolved Questions

- Should V2.1 move scheduler ledger to a durable database after Fiona introduces a DB for Knowledge Intelligence?
- Should failed delivery retries be visible in a separate operations dashboard?
- Should `unknown_delivery_state` trigger an operator alert instead of staying local-only?

## 8. Tests

New test file:

```text
tests/test_fiona_scheduler_reliability.py
```

Coverage includes:

- five normal due detections
- first startup catch-up
- first startup expired skip
- restart recovery
- Sunday weekly behavior
- midnight boundary
- duplicate prevention
- failed bounded retry
- max attempts
- stale running
- malformed ledger
- missing ledger
- ledger write failure after Telegram success
- Telegram success and failure boundaries
- invalid interval values
- 7-day continuous simulation
- multi-route contract unaffected
- five task times unchanged

## 9. Validation

```text
Python compile check: passed
Unit tests: passed
```

## 10. Production Impact

Changed:

- scheduler reliability internals
- default scheduler polling interval
- scheduler execution now uses explicit occurrence-based brief execution

Not changed:

- Telegram user-visible content
- brief templates
- Alert state
- Railway command
- secrets
- task times

## 11. Known Limits

Current guarantee:

```text
best-effort restart recovery within surviving filesystem state
```

Not guaranteed:

```text
exactly-once delivery across Railway redeploy / filesystem loss
multi-replica duplicate prevention
```

## 12. Next Recommendation

Phase 0B Review:

1. Wilson reviews scheduler reliability behavior.
2. If accepted, commit locally.
3. Push and allow Railway deploy.
4. Observe production logs for one full day.

Phase 0C candidate:

- durable scheduler ledger decision
- operator alert for `unknown_delivery_state`
- runtime health dashboard in docs or reports

