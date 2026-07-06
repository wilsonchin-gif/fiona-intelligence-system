# Fiona Scheduler Delivery Audit

版本：Phase 0A  
状态：Completed  
负责人：Wilson / Codex  
更新时间：2026-07-04

## 1. Scope

本审计验证 Production Scheduler 是否存在任务漏执行风险。

本阶段没有修改 scheduler，没有修改 Railway，没有修改 Telegram。

## 2. Current Scheduler Contract

Railway entry:

```text
python3 -m app.fiona_runtime --send run-scheduler
```

Runtime:

- File: `app/fiona_runtime.py`
- Scheduler loop: `run_scheduler()`
- Interval: `scheduler_interval_minutes()`
- Due detection: `due_brief_kinds()`
- Timezone arg: `--timezone`, default `FIONA_TIMEZONE`, `WILSON_TIMEZONE`, then `Asia/Manila`

Current interval priority:

1. `WILSON_INTERVAL_MINUTES`
2. `FIONA_RUNTIME_INTERVAL_MINUTES`
3. `FIONA_ALERT_INTERVAL_MINUTES`
4. default `15`

Known production setting:

```text
WILSON_INTERVAL_MINUTES=240
```

Due window:

```text
tolerance_minutes = 15
```

Due detection:

```text
abs(current_time - scheduled_time) <= 15 minutes
```

## 3. Existing 5 Scheduled Tasks

| Task | Time | Code |
|---|---:|---|
| Fiona Market News | 00:00 | `FionaBriefKind.MARKET_NEWS` |
| Fiona Morning | 07:30 | `FionaBriefKind.MORNING` |
| Fiona Evening | 20:30 | `FionaBriefKind.EVENING` |
| Fiona Daily | 22:30 | `FionaBriefKind.DAILY` |
| Fiona Weekly | Sunday 21:00 | `FionaBriefKind.WEEKLY` |

## 4. Delivery Matrix

Simulation uses current code:

- `due_brief_kinds()`
- 240-minute interval
- Asia/Manila timezone
- Sunday `2026-07-05` for weekly visibility

| Scenario | Market News 00:00 | Morning 07:30 | Evening 20:30 | Daily 22:30 | Weekly Sun 21:00 | Result |
|---|---|---|---|---|---|---|
| A. Process starts 00:00 | Guaranteed | Missed | Missed | Missed | Missed | High miss risk |
| B. Process starts 00:07 | Guaranteed | Missed | Missed | Missed | Missed | High miss risk |
| C. Process starts 01:00 | Missed | Missed | Missed | Missed | Guaranteed on Sunday | High miss risk |
| D. Process starts 06:02 | Missed | Missed | Missed | Missed | Missed | High miss risk |
| E. Process starts 07:20 | Missed | Guaranteed | Missed | Missed | Missed | High miss risk |
| F. Process starts 07:40 | Missed | Guaranteed | Missed | Missed | Missed | High miss risk |
| G. Process restarts 20:25 | Missed | Missed | Guaranteed | Missed | Missed | High miss risk |
| H. Process restarts 20:50 | Missed | Missed | Missed | Missed | Guaranteed on Sunday | High miss risk |
| I. Downtime spans scheduled task | Unknown | Missed | Missed | Missed | Missed | No catch-up |
| J. Continuous 7 days from Sunday 00:00 | Guaranteed daily | Missed | Missed | Missed | Missed | Non-midnight tasks missed |

## 5. Findings

### Finding 1: Scheduler is process start-time dependent

With 240-minute polling, the process only checks due windows every 4 hours.

If the process starts at 00:00, checks occur around:

```text
00:00, 04:00, 08:00, 12:00, 16:00, 20:00, 00:00
```

That misses:

- 07:30 Morning
- 20:30 Evening
- 22:30 Daily
- Sunday 21:00 Weekly

### Finding 2: No last-run state

There is no persistent last-run record for scheduled briefs.

Current memory tracks events/narratives/decisions, not schedule delivery.

### Finding 3: No missed-run recovery

If Railway is down during a due window, the task is not automatically recovered.

### Finding 4: Duplicate prevention is not scheduler-level

There is no per-brief date/time delivery ledger.

Short polling may create duplicate risk unless a last-run ledger is added.

## 6. Repair Options

### Option A: Short Polling Interval

Set scheduler polling to 5-15 minutes.

| Dimension | Assessment |
|---|---|
| Reliability | Medium-high |
| Complexity | Low |
| Railway compatibility | High |
| Duplicate risk | Medium without ledger |
| Restart recovery | Low |
| Migration risk | Low |

Pros:

- Minimal code change or env-only if interval already configurable.
- Due window works as intended.

Cons:

- Still no catch-up if downtime spans schedule.
- Duplicate prevention still needs ledger.

### Option B: Next-Run Scheduling

Scheduler computes next exact due time and sleeps until then.

| Dimension | Assessment |
|---|---|
| Reliability | High while process is alive |
| Complexity | Medium |
| Railway compatibility | High |
| Duplicate risk | Low |
| Restart recovery | Medium |
| Migration risk | Medium |

Pros:

- No dependence on arbitrary process start phase.
- Efficient.

Cons:

- Needs careful timezone and weekly handling.
- Still needs startup catch-up rules.

### Option C: Persistent Last-Run + Catch-Up

Maintain a schedule ledger:

```text
brief_kind
scheduled_for
delivered_at
status
```

On startup and each loop:

- find due or missed-but-recoverable tasks
- deliver once
- record ledger

| Dimension | Assessment |
|---|---|
| Reliability | Highest |
| Complexity | Medium-high |
| Railway compatibility | Medium with JSON, high with DB |
| Duplicate risk | Low |
| Restart recovery | High |
| Migration risk | Medium |

Pros:

- Handles downtime.
- Prevents duplicates.
- Auditable.

Cons:

- JSON ledger on Railway remains ephemeral.
- Needs careful no-user-visible-change rollout.

## 7. Recommendation

Recommended path:

### Phase 0B

Use Option A as immediate safety improvement:

- Set polling interval to 15 minutes or less.
- Do not alter brief templates.
- Do not alter Telegram content.

### Phase 1

Implement Option C with a schedule ledger:

- `scheduled_for`
- `brief_kind`
- `delivered_at`
- `status`
- `message_ids`

For V1/V2 transition, JSON ledger is acceptable.

### Later

Move schedule ledger to PostgreSQL only when Fiona has a durable DB for Knowledge Graph.

## 8. Contract Test Added

Test file:

```text
tests/test_fiona_phase0a_contracts.py
```

Scheduler tests confirm:

- 240-minute polling from midnight misses non-midnight tasks.
- Delivery depends on process start time.

## 9. Production Impact

No scheduler code changed in Phase 0A.

This document records risk only.

## 10. Phase 0B Update

Phase 0B implemented a local scheduler reliability layer to address the confirmed delivery risk.

New module:

```text
app/fiona_scheduler.py
```

Runtime integration:

```text
app/fiona_runtime.py
```

The original failure record above remains valid for the previous scheduler model.

### New Model

```text
5-minute default polling
+
stable occurrence_id
+
due detection between last_check_at and now
+
bounded catch-up
+
execution ledger
+
idempotency
+
restart recovery
```

### Final Interval Variable Priority

1. explicit CLI `--interval-minutes`
2. `WILSON_INTERVAL_MINUTES`
3. `FIONA_RUNTIME_INTERVAL_MINUTES`
4. default `5`

`FIONA_ALERT_INTERVAL_MINUTES` is intentionally excluded from the brief scheduler interval.

### Catch-up Windows

| Task | Catch-up Max Age |
|---|---:|
| Market News | 60 minutes |
| Morning | 120 minutes |
| Evening | 120 minutes |
| Daily | 180 minutes |
| Weekly | 240 minutes |

### Phase 0B Validation

```text
Python compile check: passed
Unit tests: passed
```

### Remaining Limitation

The JSON scheduler ledger is still an ephemeral Railway filesystem record.

Current guarantee:

```text
best-effort restart recovery within surviving filesystem state
```

Not guaranteed:

```text
exactly-once delivery across Railway redeploy / filesystem loss
multi-replica duplicate prevention
```
