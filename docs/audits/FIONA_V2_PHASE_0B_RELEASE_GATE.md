# Fiona V2 Phase 0B Release Gate Review

版本：Phase 0B Release Gate  
状态：APPROVE WITH CONDITIONS  
负责人：Wilson / Codex  
更新时间：2026-07-06  

## 1. Executive Verdict

Phase 0B Scheduler Reliability V2 is directionally correct and materially improves the previous scheduler model, but it is not safe to deploy without conditions.

Release verdict:

```text
APPROVE WITH CONDITIONS
```

Deploy must wait until the required items in this report are resolved or explicitly accepted by Wilson.

Key blockers:

1. Production Railway may still have `WILSON_INTERVAL_MINUTES=240`, which overrides the new 5-minute default.
2. README and config examples still recommend `WILSON_INTERVAL_MINUTES=240`.
3. First startup 24h lookback creates several expired ledger records and can send stale-but-within-window briefs.
4. Catch-up can cause short-window double pushes, especially Evening + Daily at 22:30.
5. `unknown_delivery_state` is only partially safe; it cannot guarantee no duplicate after ledger write loss.
6. Multi-replica Railway deployment would still be duplicate-prone because the ledger is local JSON.

## 2. Repository State Freeze

Repository:

```text
/Users/mac/Desktop/Wilson AI Lab/Fiona Intelligence Platform/03_Development/fiona-intelligence-system
```

Git root:

```text
/Users/mac/Desktop/Wilson AI Lab/Fiona Intelligence Platform/03_Development/fiona-intelligence-system
```

Origin:

```text
https://github.com/wilsonchin-gif/fiona-intelligence-system.git
```

Branch:

```text
main
```

HEAD:

```text
2295e01b8918efca5f1b9250ae3d40e96c85d2dd
```

origin/main and remote main:

```text
32c5a31fb81f490304231e402a30d0104e0fa559
```

Status:

```text
main...origin/main [ahead 1]
tracked modified:
  app/fiona_runtime.py
  tests/test_fiona_phase4.py

untracked:
  app/fiona_contracts.py
  app/fiona_scheduler.py
  docs/PRODUCT_STATUS.md
  docs/RELEASE_HISTORY.md
  docs/ROADMAP.md
  docs/SYSTEM_ARCHITECTURE.md
  docs/VERSION_MATRIX.md
  docs/audits/FIONA_SCHEDULER_DELIVERY_AUDIT.md
  docs/audits/FIONA_V2_TECHNICAL_FEASIBILITY_AUDIT.md
  docs/decision/README.md
  docs/fiona_project_memo.docx
  docs/release/README.md
  docs/v2/FIONA_SCHEDULER_RELIABILITY_V2.md
  docs/v2/FIONA_V2_CONTRACTS.md
  docs/v2/FIONA_V2_PHASE_0A_REPORT.md
  docs/v2/FIONA_V2_PHASE_0B_PRESTATE.md
  docs/v2/FIONA_V2_PHASE_0B_REPORT.md
  tests/test_fiona_phase0a_contracts.py
  tests/test_fiona_scheduler_reliability.py
```

Current tracked diff:

```text
app/fiona_runtime.py       | 141 ++++++++++++++++++++++++++++++++++++++++++---
tests/test_fiona_phase4.py |   3 +-
```

## 3. origin/main Already Contains

origin/main is `32c5a31 Initialize Fiona documentation system`.

It does not contain:

- local ahead commit `2295e01`
- Phase 0A untracked files
- Phase 0B scheduler files
- Phase 0B release gate report

## 4. Local Ahead Commit 2295e01

Commit:

```text
2295e01 Migrate Fiona workspace paths and documentation
```

Purpose:

Workspace path and documentation migration.

Files:

```text
M README.md
M app/desktop_export.py
M docs/architecture/deployment.md
M docs/changelog/CHANGELOG.md
M docs/decisions/decision_log.md
M docs/deployment/production.md
M docs/export/Architecture.docx
M docs/export/Decision Log.docx
M docs/export/Deployment Guide.docx
M docs/export/PRD.docx
M docs/export/Release Notes.docx
M docs/export/Roadmap.docx
M docs/fiona_phase4.md
M docs/fiona_phase5.md
A docs/releases/Release_v1.0.1.md
M docs/roadmap/roadmap.md
M scripts/run_fiona_once.sh
```

Production behavior impact:

- Low direct runtime impact.
- Contains path/documentation/script changes.
- Must be reviewed before pushing because it is already ahead of origin/main and would deploy before Phase 0A/0B if pushed as-is.

## 5. Phase 0A Boundary Review

Phase 0A files are currently untracked:

```text
app/fiona_contracts.py
tests/test_fiona_phase0a_contracts.py
docs/v2/FIONA_V2_CONTRACTS.md
docs/audits/FIONA_V2_TECHNICAL_FEASIBILITY_AUDIT.md
docs/audits/FIONA_SCHEDULER_DELIVERY_AUDIT.md
docs/v2/FIONA_V2_PHASE_0A_REPORT.md
```

Status:

- Not in origin/main.
- Not in local HEAD.
- No tracked conflict.
- `docs/audits/FIONA_SCHEDULER_DELIVERY_AUDIT.md` was created in Phase 0A and appended in Phase 0B.

No naming conflict observed.

## 6. Phase 0B Boundary Review

Phase 0B new files:

```text
app/fiona_scheduler.py
tests/test_fiona_scheduler_reliability.py
docs/v2/FIONA_SCHEDULER_RELIABILITY_V2.md
docs/v2/FIONA_V2_PHASE_0B_PRESTATE.md
docs/v2/FIONA_V2_PHASE_0B_REPORT.md
```

Phase 0B modified tracked files:

```text
app/fiona_runtime.py
tests/test_fiona_phase4.py
```

Phase 0B modified untracked Phase 0A doc:

```text
docs/audits/FIONA_SCHEDULER_DELIVERY_AUDIT.md
```

This Release Gate adds only:

```text
docs/audits/FIONA_V2_PHASE_0B_RELEASE_GATE.md
```

## 7. Real Scheduler Call Chain

Railway command:

```text
python3 -m app.fiona_runtime --send run-scheduler
```

Call chain:

```text
app.fiona_runtime.main
-> parse_args
-> resolve_send
-> run_scheduler
-> scheduler_interval_minutes
-> run_scheduler_cycle
-> SchedulerLedger.load
-> due_occurrences
-> scheduled_points_between
-> execute_scheduled_occurrence
-> can_execute_occurrence
-> run_once(brief=<explicit brief_name>)
-> build_payload
-> write_payload
-> push_text when send=true
-> telegram_service.send_message
-> Telegram Bot API
-> delivery_succeeded
-> SchedulerLedger.mark_success / mark_failed / mark_unknown_delivery_state
-> SchedulerLedger.save
-> sleep(interval * 60)
```

Critical branches:

- `run_scheduler()` is a long-running `while True` loop.
- `scheduler_interval_minutes()` delegates to `app.fiona_scheduler.scheduler_interval_minutes()`.
- `due_occurrences()` detects occurrences in `(last_check_at, now]`.
- `can_execute_occurrence()` prevents resend after `success`, blocks `unknown_delivery_state`, retries `failed`, and retries stale `running`.
- `delivery_succeeded()` treats dry-run `send=false` as successful if runtime status is ok.
- With `send=true`, delivery success requires `brief_push.ok` and non-empty `message_ids`.

## 8. Unknown Delivery State Review

Question answers:

1. Telegram success is judged by `delivery_succeeded(status, send)`.
2. For `send=true`, it requires `status["brief_push"]["ok"]` and non-empty `status["brief_push"]["message_ids"]`.
3. Telegram `message_id` comes from `response["result"]["message_id"]` via `telegram_message_id()`.
4. Ledger success write happens in `execute_scheduled_occurrence()` after `ledger.mark_success()` and `ledger.save()`.
5. Write failure is caught in the `except Exception` branch after final delivery.
6. `unknown_delivery_state` is written into the in-memory ledger entry and then a second `ledger.save()` is attempted.
7. If the second save fails, the exception is swallowed and the returned result is `unknown_delivery_state`, but the state is not durable.
8. If the file retained the prior `running` state, next cycles block resend until stale running exceeds 30 minutes.
9. After 30 minutes and within catch-up window, stale running can retry, creating duplicate risk after Telegram success.
10. After process restart, if unknown state was not persisted, behavior depends on the last durable ledger state.

Verdict:

```text
Partially Safe
```

Reason:

The implementation detects the dangerous condition, but without durable storage it cannot reliably persist the unknown state. Duplicate resend remains possible after stale-running recovery if the success write fails after Telegram delivered.

Additional issue:

`push_text()` marks `brief_push.ok = true` if any chunk has a message id. If a multi-chunk message partially succeeds and later chunks fail, scheduler may mark the whole occurrence `success`.

## 9. Ledger Atomicity Review

Ledger file:

```text
reports/fiona/fiona_scheduler_ledger.json
```

Atomicity:

- Uses temp file plus `os.replace()`.
- Safer than direct overwrite.
- Process crash before replace leaves old ledger intact and a `.tmp` file.
- Process crash after replace leaves new ledger.

Malformed JSON:

- `SchedulerLedger.load()` catches exceptions and returns empty ledger with `load_error`.
- This prevents crash but may allow duplicate sends because prior success state is lost.

Empty file:

- Treated as malformed JSON, returns empty ledger with load error.

Concurrent write:

- No file lock.
- Same-process scheduler loop is sequential, so normal same-process overlap is unlikely.
- Multi-replica or overlapping processes can race and overwrite each other.

Filesystem failure:

- Permission failure and disk full surface as save exceptions.
- Pre-send ledger write failure prevents send.
- Post-send save failure can create unknown delivery state risk.

Verdict:

```text
Partially Safe
```

It is acceptable as best-effort local JSON state, not as exactly-once production delivery storage.

## 10. First Startup 24h Lookback Review

Dry-run first startup simulation, no ledger:

| Startup Time | Discovered | Sent | Catch-up Sent | Skipped Expired | Ledger Records |
|---|---|---|---|---|---:|
| 00:05 | morning, evening, daily, market_news | daily, market_news | daily, market_news | morning, evening | 4 |
| 07:40 | evening, daily, market_news, morning | morning | morning | evening, daily, market_news | 4 |
| 14:00 | evening, daily, market_news, morning | none | none | evening, daily, market_news, morning | 4 |
| 20:35 | daily, market_news, morning, evening | evening | evening | daily, market_news, morning | 4 |
| 23:10 | market_news, morning, evening, daily | daily | daily | market_news, morning, evening | 4 |
| Monday 02:00 | morning, evening, weekly, daily, market_news | none | none | all five | 5 |

Findings:

- 24h startup lookback creates multiple expired records on each first startup.
- Ledger loss means the same expired records can be recreated.
- Ledger growth is bounded by task frequency, but noisy.
- Weekly boundary is acceptable at Monday 02:00 because Weekly is expired at that time.
- However Monday 01:00 still sends Weekly, Daily, and Market News.

Verdict:

```text
Reduce / Per-task lookback recommended
```

Recommended future change:

Use per-task lookback equal to catch-up max age and do not create expired ledger entries for occurrences outside the task's catch-up window.

## 11. Catch-up Semantics Review

Current windows:

| Task | Window |
|---|---:|
| Market News | 60m |
| Morning | 120m |
| Evening | 120m |
| Daily | 180m |
| Weekly | 240m |

Product checks:

- 01:00 Market News: still within 60m, likely acceptable.
- 09:30 Morning: exactly 120m, currently sends because expiry uses `>`, not `>=`; acceptable but edge-heavy.
- 22:30 Evening: exactly 120m after 20:30, currently sends Evening catch-up and Daily normal in the same cycle.
- 01:30 Daily: exactly 180m, currently sends; may be acceptable for daily summary but late.
- Monday 01:00 Weekly: exactly 240m, currently sends Weekly plus Daily plus Market News on first startup; likely too dense.

Verdict:

```text
Blocking Risk before deploy
```

Reason:

The current catch-up logic can create short-window double or triple pushes after first startup or ledger loss.

## 12. Retry Semantics Review

Current retry policy:

```text
max_attempts = 3
retry while inside catch-up window
retry failed every scheduler cycle
```

Findings:

- A failed attempt can retry every 5 minutes until attempt 3 or expiry.
- `attempt_count` increments in `mark_running()`.
- Telegram 4xx, 5xx, timeout, and malformed response are all treated the same by `push_text()` as errors.
- Permanent failures can consume 3 attempts.
- Retry cannot cross catch-up expiry because `can_execute_occurrence()` checks expiry before status.

Verdict:

```text
Accept with monitoring
```

Risk:

No distinction between permanent and transient Telegram errors.

## 13. Stale Running Review

Current policy:

```text
running > 30m -> stale -> retry
```

Findings:

- 30m is hard-coded.
- Long fetches over 30m do not overlap in the same process because scheduler loop is sequential.
- If process dies or freezes after Telegram delivery but before success finalization, stale retry can duplicate.
- Stale retry is bounded by attempt count and catch-up expiry.

Verdict:

```text
Partially Safe
```

## 14. Railway Runtime Model Review

Repo evidence:

```toml
[deploy]
startCommand = "python3 -m app.fiona_runtime --send run-scheduler"
restartPolicyType = "ON_FAILURE"
```

Runtime:

- `run-scheduler` enters `run_scheduler()`.
- `run_scheduler()` is a long-running loop.
- Each loop sleeps `interval * 60`.
- It exits only on `max_cycles` or unhandled exception.
- `run_once()` catches most generation and Telegram exceptions.
- `run_scheduler_cycle()` catches final ledger save failure.
- There is no top-level `try/except` around the entire scheduler cycle.

Railway service type:

```text
Unknown — requires Railway console verification
```

Historical "No running instances":

```text
Unknown — requires Railway console verification
```

Verdict:

```text
Partially Safe
```

Reason:

The repo defines a long-running service command, but actual Railway service/cron semantics cannot be confirmed from the repository alone.

## 15. Production Interval Env Review

Code precedence:

```text
CLI --interval-minutes
WILSON_INTERVAL_MINUTES
FIONA_RUNTIME_INTERVAL_MINUTES
default 5
```

Critical finding:

README still recommends:

```text
WILSON_INTERVAL_MINUTES=240
```

`config/fiona.env.example` still sets:

```text
WILSON_INTERVAL_MINUTES=240
```

`docs/deployment/environment.md` still documents:

```text
WILSON_INTERVAL_MINUTES=240
```

If Railway Variables still include `WILSON_INTERVAL_MINUTES=240`, the effective interval remains 240 and the new 5-minute default does not apply.

Actual Railway env:

```text
Unknown — production env verification required
```

Verdict:

```text
BLOCKER before deploy
```

Required:

Set Railway `WILSON_INTERVAL_MINUTES=5` or remove it to use default 5.

## 16. Scheduler Exception Boundary Review

Findings:

- Single source / fetch failure is generally caught by `run_once()`.
- Telegram failure is caught by `push_text()` and does not kill the scheduler.
- Malformed source response should generally be caught inside `run_once()`.
- Ledger pre-send write failure prevents send and returns an occurrence result.
- Ledger final save failure is captured in scheduler cycle status.
- One normal brief failure should not prevent later due tasks in the same cycle if it is contained in `run_once()`.
- If `runner()` raises unexpectedly, `execute_scheduled_occurrence()` does not catch it.
- If `due_occurrences()` or timezone conversion raises, `run_scheduler()` has no top-level guard.

Verdict:

```text
Partially Safe
```

## 17. 7-Day Simulation Validation

Observed:

```text
Market News: 8
Morning: 7
Evening: 7
Daily: 7
Weekly: 1
```

Why Market News is 8:

The simulation window is inclusive from Monday 00:00 through next Monday 00:00. That includes both boundary midnights:

- 2026-07-06 00:00
- 2026-07-13 00:00

Production semantics:

This is a test-window artifact, not a duplicate production occurrence. Each occurrence_id is unique by scheduled local datetime.

Verdict:

```text
Accept
```

## 18. Test Quality Review

Current result:

```text
79 tests passed
Python compile check passed
```

New scheduler tests:

- 31 deterministic unit/simulation tests.
- Runtime integration is tested through `run_scheduler_cycle()` with fake runner.
- Telegram is mocked via fake runner.
- Filesystem failure is mocked for ledger write failure.
- Malformed ledger is tested.
- Missing ledger is tested.
- Restart with surviving ledger is tested.
- Env precedence is tested.
- `WILSON_INTERVAL_MINUTES=240` override is tested in `tests/test_fiona_phase4.py`.

False confidence risks:

- No real Railway process/service test.
- No real Telegram API test.
- No test for first-startup 22:30 Evening + Daily collision.
- No test for Monday 01:00 Weekly + Daily + Market News collision.
- No multi-replica test.
- No real file permission/disk-full integration test.
- Multi-chunk partial Telegram success is not tested.

Verdict:

```text
Good unit coverage, incomplete production confidence
```

## 19. Git Release Boundary Plan

Do not use `git add .`.

### Commit A — Existing workspace/path migration

Purpose:

Preserve current ahead commit as the first release boundary, or push it separately after review.

Already committed locally:

```text
2295e01 Migrate Fiona workspace paths and documentation
```

Files:

```bash
git add README.md
git add app/desktop_export.py
git add docs/architecture/deployment.md
git add docs/changelog/CHANGELOG.md
git add docs/decisions/decision_log.md
git add docs/deployment/production.md
git add docs/export/Architecture.docx
git add "docs/export/Decision Log.docx"
git add "docs/export/Deployment Guide.docx"
git add docs/export/PRD.docx
git add "docs/export/Release Notes.docx"
git add docs/export/Roadmap.docx
git add docs/fiona_phase4.md
git add docs/fiona_phase5.md
git add docs/releases/Release_v1.0.1.md
git add docs/roadmap/roadmap.md
git add scripts/run_fiona_once.sh
```

Production behavior change:

- Mostly documentation/path scripts.
- Review path-sensitive script changes before push.

Rollback:

- Revert `2295e01`.

### Commit B — Fiona V2 Phase 0A contracts and audits

Purpose:

Add V2 contract module, deterministic contract tests, and audit docs.

Files:

```bash
git add app/fiona_contracts.py
git add tests/test_fiona_phase0a_contracts.py
git add docs/v2/FIONA_V2_CONTRACTS.md
git add docs/audits/FIONA_V2_TECHNICAL_FEASIBILITY_AUDIT.md
git add docs/audits/FIONA_SCHEDULER_DELIVERY_AUDIT.md
git add docs/v2/FIONA_V2_PHASE_0A_REPORT.md
```

Production behavior change:

- No production runtime path change, unless imported elsewhere later.

Rollback:

- Remove the new contract/audit files.

### Commit C — Scheduler Reliability V2

Purpose:

Add occurrence-based scheduler, ledger, bounded catch-up, idempotency, and tests.

Files:

```bash
git add app/fiona_scheduler.py
git add app/fiona_runtime.py
git add tests/test_fiona_phase4.py
git add tests/test_fiona_scheduler_reliability.py
git add docs/v2/FIONA_SCHEDULER_RELIABILITY_V2.md
git add docs/v2/FIONA_V2_PHASE_0B_PRESTATE.md
git add docs/v2/FIONA_V2_PHASE_0B_REPORT.md
git add docs/audits/FIONA_V2_PHASE_0B_RELEASE_GATE.md
```

Production behavior change:

- Yes. Scheduler delivery behavior changes.

Rollback:

- Revert Commit C.
- Risk: rollback returns to the old scheduler that can miss tasks under 240-minute polling.

### Pre-existing Untracked Docs

These should be handled separately, not bundled into scheduler release unless Wilson confirms:

```text
docs/PRODUCT_STATUS.md
docs/RELEASE_HISTORY.md
docs/ROADMAP.md
docs/SYSTEM_ARCHITECTURE.md
docs/VERSION_MATRIX.md
docs/decision/README.md
docs/fiona_project_memo.docx
docs/release/README.md
```

## 20. Deploy Gate Checklist

### BLOCKER

- Verify Railway service type in Railway console.
- Verify actual Railway Variables. If `WILSON_INTERVAL_MINUTES=240`, change to `5` or remove it before deploy.
- Resolve or explicitly accept catch-up collision risk: 22:30 Evening + Daily and Monday 01:00 Weekly + Daily + Market News.
- Decide how to handle multi-chunk partial Telegram success before considering the occurrence fully successful.

### REQUIRED BEFORE DEPLOY

- Update README/config/env docs away from `WILSON_INTERVAL_MINUTES=240`.
- Confirm Railway replica count is 1.
- Confirm `reports/fiona/fiona_scheduler_ledger.json` path is acceptable as ephemeral state.
- Confirm rollback command/process.
- Keep commits separated; do not use `git add .`.

### RECOMMENDED

- Reduce startup lookback to per-task catch-up window.
- Avoid recording expired occurrences outside catch-up windows.
- Add tests for Evening + Daily collision and Monday 01:00 triple catch-up.
- Add top-level scheduler loop exception guard.
- Add operator-visible warning for `unknown_delivery_state`.

### NON-BLOCKING

- Move ledger to DB later when Fiona introduces persistent Knowledge Intelligence storage.
- Add Railway log dashboard.
- Add file lock only if multi-process local deployment becomes realistic.

## 21. Final Release Gate Verdict

```text
APPROVE WITH CONDITIONS
```

The scheduler reliability implementation is structurally sound but not deploy-ready until Railway interval configuration and catch-up collision semantics are resolved or explicitly accepted.

No code, tests, Railway config, Telegram config, or environment variables were modified during this Release Gate Review.

## 22. Phase 0B.1 Remediation Status

Status:

```text
Implemented locally, not committed
```

Remediated:

- README and config example now recommend `WILSON_INTERVAL_MINUTES=5`.
- Delivery arbitration implemented with `SEND`, `SUPPRESS`, and `DEFER`.
- Suppressed occurrences are auditable in the ledger as `suppressed_collision`.
- Telegram delivery now distinguishes `success`, `partial_delivery`, and `failed`.
- `partial_delivery` is not retried automatically.
- First startup now uses per-task bounded lookback instead of unified 24h scan.
- Scheduler loop has a top-level guard for unexpected cycle exceptions.
- Unknown delivery state now attempts a secondary local uncertain delivery journal.

Still required before deploy:

- Verify Railway production env actually uses `WILSON_INTERVAL_MINUTES=5` or removes the override.
- Verify Railway service type is a long-running service, not cron.
- Verify Railway replicas = 1.

Updated release verdict:

```text
APPROVE WITH CONDITIONS
```

The remaining conditions are operational verification gates, not known code blockers.
