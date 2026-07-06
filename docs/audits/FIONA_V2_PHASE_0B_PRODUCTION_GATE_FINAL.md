# Fiona V2 Phase 0B.1 Production Gate Finalization

版本：Phase 0B.1 Production Gate  
状态：Ready for Wilson review, not committed  
负责人：Wilson / Codex  
更新时间：2026-07-06

## 1. Production Ground Truth

Wilson manually confirmed the following Railway production state through Console screenshots:

| Item | Production Ground Truth |
|---|---|
| Production variable | `WILSON_INTERVAL_MINUTES=240` |
| Runtime model | Long-running Railway service |
| Custom start command | `python3 -m app.fiona_runtime --send run-scheduler` |
| Cron schedule | None / empty |
| Serverless | Off |
| Scale | 1 replica |
| Region | US West, California, USA |
| GitHub production branch | `main` |
| Auto deploy on GitHub push | Enabled |
| Restart policy | On Failure |
| Restart retries | 10 |
| Builder | Nixpacks, deprecated |

Nixpacks deprecation is non-blocking for this release. Builder migration is explicitly out of scope.

## 2. Repository State

Repository:

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

Current HEAD:

```text
2295e01b8918efca5f1b9250ae3d40e96c85d2dd
```

origin/main:

```text
32c5a31fb81f490304231e402a30d0104e0fa559
```

Ahead / behind:

```text
behind 0, ahead 1
```

Current tracked diff:

```text
README.md
app/fiona_runtime.py
config/fiona.env.example
tests/test_fiona_phase4.py
```

There are untracked Phase 0A / Phase 0B / Phase 0B.1 files plus pre-existing untracked docs. These must be committed with explicit file paths only.

## 3. Interval Analysis

Current Phase 0B.1 code resolves scheduler interval as:

```text
CLI --interval-minutes
-> WILSON_INTERVAL_MINUTES
-> FIONA_RUNTIME_INTERVAL_MINUTES
-> default 5
```

Required production interval:

```text
WILSON_INTERVAL_MINUTES=5
```

or remove `WILSON_INTERVAL_MINUTES` so the runtime default `5` applies.

Current Railway ground truth:

```text
WILSON_INTERVAL_MINUTES=240
```

Therefore, if new code is deployed while Railway still has `240`, effective interval remains `240`.

## 4. Production Config Simulation

Simulation period:

```text
2026-07-06 00:00 Asia/Manila through 2026-07-13 00:00 Asia/Manila
```

Results:

| Config | Effective Interval | 7-day Occurrence Counts |
|---|---:|---|
| `WILSON_INTERVAL_MINUTES=240` | 240m | evening 8, weekly 2, daily 8, market_news 8, morning 7 |
| `WILSON_INTERVAL_MINUTES=5` | 5m | market_news 8, morning 7, evening 7, daily 7, weekly 1 |
| no interval override | 5m | market_news 8, morning 7, evening 7, daily 7, weekly 1 |

Interpretation:

- New code with `240` no longer behaves like old due-window-only scheduler, because it can discover occurrences between `last_check_at` and `now`.
- However, `240` still creates delayed catch-up behavior and can cluster occurrences into large recovery windows.
- `240` is therefore a release risk, not the intended production mode.
- `5` is the required production setting.

## 5. Old Code / New Env Risk

If Railway env is changed from `240` to `5` while old production code is still running:

- old runtime wakes every 5 minutes
- old due detection still uses `due_brief_kinds(now, ±15 minutes)`
- same due window may be hit repeatedly
- duplicate Telegram pushes become more likely

Therefore, do not change Railway env to `5` before the code cutover is controlled.

## 6. Safe Cutover Sequence

Because Auto Deploy is enabled, pushing `main` triggers production deploy.

Recommended sequence:

1. Keep current Railway env at `WILSON_INTERVAL_MINUTES=240` while preparing commits.
2. Commit locally in clear boundaries.
3. Push during an agreed quiet window.
4. Immediately after Railway starts deploying the new code, update Railway Variables:
   ```text
   WILSON_INTERVAL_MINUTES=5
   ```
   or remove the variable to use default `5`.
5. Confirm Railway deploy succeeds.
6. Confirm a single running instance.
7. Confirm logs show:
   ```text
   interval_minutes: 5
   ```
8. Observe at least one scheduled boundary.
9. Monitor Telegram for duplicate or catch-up burst behavior.

Alternative safer sequence if Wilson wants zero ambiguity:

1. Temporarily set `WILSON_SEND=0`.
2. Push code and let Railway deploy.
3. Set `WILSON_INTERVAL_MINUTES=5`.
4. Verify logs.
5. Set `WILSON_SEND=1`.

This reduces duplicate-send risk during cutover, but causes a short push pause.

## 7. Rollback Plan

Rollback triggers:

- duplicate Telegram delivery
- scheduler crash loop
- unexpected catch-up burst
- arbitration malfunction
- partial delivery anomaly

### 7.1 Code Rollback

Use Railway rollback to the previous known-good deploy, or revert the scheduler hardening commit and push a rollback commit.

Because Auto Deploy is enabled, any rollback push will deploy automatically.

### 7.2 Env Rollback

If rolling back to old production code:

```text
WILSON_INTERVAL_MINUTES=240
```

must be restored because old code with `5` can repeatedly hit the ±15 minute due window.

### 7.3 Telegram Safety During Rollback

If duplicate delivery or burst risk is active:

```text
WILSON_SEND=0
```

temporarily pauses Telegram sends during rollback.

After the previous stable deploy is restored and interval is back to `240`, set:

```text
WILSON_SEND=1
```

### 7.4 Avoiding Rollback-induced Duplicate Sends

Before re-enabling sends:

- inspect latest Railway logs
- check scheduler ledger status if available
- wait until outside any immediate due/catch-up collision window when possible
- re-enable sends only once the runtime version and interval are aligned

## 8. Release Boundary Plan

Do not use `git add .`.

### Commit A: Existing workspace migration

Already exists:

```text
2295e01 Migrate Fiona workspace paths and documentation
```

Do not rewrite history unless Wilson explicitly asks.

Files in existing commit:

```text
README.md
app/desktop_export.py
docs/architecture/deployment.md
docs/changelog/CHANGELOG.md
docs/decisions/decision_log.md
docs/deployment/production.md
docs/export/Architecture.docx
docs/export/Decision Log.docx
docs/export/Deployment Guide.docx
docs/export/PRD.docx
docs/export/Release Notes.docx
docs/export/Roadmap.docx
docs/fiona_phase4.md
docs/fiona_phase5.md
docs/releases/Release_v1.0.1.md
docs/roadmap/roadmap.md
scripts/run_fiona_once.sh
```

### Commit B: Phase 0A contracts and audits

Exact add paths:

```bash
git add app/fiona_contracts.py
git add tests/test_fiona_phase0a_contracts.py
git add docs/v2/FIONA_V2_CONTRACTS.md
git add docs/v2/FIONA_V2_PHASE_0A_REPORT.md
git add docs/audits/FIONA_V2_TECHNICAL_FEASIBILITY_AUDIT.md
```

`docs/audits/FIONA_SCHEDULER_DELIVERY_AUDIT.md` is shared between Phase 0A and Phase 0B updates. Include it in Commit C to keep the final scheduler audit state with the scheduler hardening release.

### Commit C: Phase 0B + Phase 0B.1 scheduler reliability and production gate

Exact add paths:

```bash
git add README.md
git add app/fiona_runtime.py
git add app/fiona_scheduler.py
git add config/fiona.env.example
git add tests/test_fiona_phase4.py
git add tests/test_fiona_scheduler_reliability.py
git add docs/audits/FIONA_SCHEDULER_DELIVERY_AUDIT.md
git add docs/audits/FIONA_V2_PHASE_0B_RELEASE_GATE.md
git add docs/audits/FIONA_V2_PHASE_0B_PRODUCTION_GATE_FINAL.md
git add docs/v2/FIONA_SCHEDULER_RELIABILITY_V2.md
git add docs/v2/FIONA_DELIVERY_ARBITRATION_POLICY.md
git add docs/v2/FIONA_V2_PHASE_0B_PRESTATE.md
git add docs/v2/FIONA_V2_PHASE_0B_REPORT.md
git add docs/v2/FIONA_V2_PHASE_0B1_PRESTATE.md
git add docs/v2/FIONA_V2_PHASE_0B1_HARDENING_REPORT.md
```

Do not include in Commit C unless separately approved:

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

## 9. Validation

Full unit tests:

```text
103 tests passed
```

Python compile check:

```text
34 Python files compile OK
```

Targeted scheduler hardening tests:

```text
8 targeted tests passed
```

Covered:

- Evening + Daily collision
- Monday triple collision
- partial delivery semantics
- unknown delivery state semantics
- stale running semantics
- top-level scheduler exception guard
- per-task startup lookback
- 7-day simulation

## 10. Production Gate Verdict

Verdict:

```text
APPROVE FOR CONTROLLED CUTOVER AFTER RAILWAY ENV UPDATE PLAN IS READY
```

No new code blocker was found.

Remaining operational requirements before deploy:

- coordinate push timing because Auto Deploy is enabled
- update Railway `WILSON_INTERVAL_MINUTES` from `240` to `5` during cutover
- verify logs show effective interval `5`
- observe production after deploy

