# Gate 2.3 — Production State Continuity & Release Consolidation

Version: V3.1 Gate 2.3 | Date: 2026-10-09 | Owner: Wilson / Fiona Engineering
Status: Local validation PASS; production acceptance pending
Parent: Gate 2 OPEN / HOLD; Gate 3 LOCKED; global_631 inactive.

## Repository and local-change boundary

Initial HEAD / origin/main / GitHub main: `e6cdb7a135266149c6281b93725de820fe5b7744`,
main, ahead 0 / behind 0. Correct Desktop Wilson AI Lab development repository.

Category A, reviewed Gate 2.2 follow-ups: `app/fiona_global_coverage.py`,
`tests/test_fiona_gate2_2.py`, `docs/VERSION_MATRIX.md`, `docs/changelog/CHANGELOG.md`,
`docs/v3_1/FIONA_V3_1_IMPLEMENTATION_ROADMAP.md`, and Gate 2.2 remediation report.
The rate-context fix is included with financial-rate and hospitality regression
cases; post-deploy findings remain visible, not erased by the new release.

Category B, unrelated pre-existing work (excluded): modified
`docs/decisions/decision_log.md`; untracked PRODUCT_STATUS, RELEASE_HISTORY,
ROADMAP, SYSTEM_ARCHITECTURE, FIONA_PRODUCTION_PIPELINE_AUDIT, decision/README,
ADR_005, release/README, IMAGE_CAPTION_RC_RELEASE_REPORT,
V3_VISUAL_EXPERIENCE_RELEASE_NOTES, four V3 visual documents and four prototype
generation scripts. Category C: untracked `docs/fiona_project_memo.docx`, generated
document, excluded. Category D: none added to release. All retained unchanged.

## Current versus target infrastructure — recorded BEFORE changes

| Property | Current verified | Approved target |
|---|---|---|
| Service | fiona-intelligence-system, production | Same service/environment |
| Running instance | One, c895503a-8ffa-4cfc-98e1-32f92e5120e9 | One; no multi-instance coordination |
| Volumes | Project volumes edges=[] | One dedicated attached Volume |
| Mount | None | `/data`, NOT `/app` or repository source |
| Runtime command | python3 -m app.fiona_runtime --send run-scheduler | Unchanged |
| State root | Ephemeral `/app/reports/fiona` | `/data/fiona` via automatic RAILWAY_VOLUME_MOUNT_PATH |
| Optional config | None | FIONA_STATE_DIR may override only inside Volume; not required |
| Product flags | photo / en-US / image / legacy / legacy / off | Unchanged |
| Cadence/Alert thresholds | Existing | Unchanged |

Railway Volume documentation: [reference](https://docs.railway.com/volumes/reference),
[mount lifecycle](https://docs.railway.com/volumes). Volumes attach at startup,
not pre-deploy. A Volume service has one active deployment and brief redeploy
downtime; volume-backed data persists across deployment replacement. Actual
mount/writability must still be checked inside the container.

## State inventory

| Store | Old path under /app/reports/fiona | Target under /data/fiona | Retention / duplicate protection |
|---|---|---|---|
| Scheduler ledger | fiona_scheduler_ledger.json | scheduler/ledger.json | No pruning; required |
| Unknown delivery journal | fiona_scheduler_delivery_uncertain.log | scheduler/delivery_uncertain.log | No pruning; reload IDs; required |
| Shared runtime Alert/event/narrative/decision memory | fiona_memory.json | alerts/runtime_memory.json | Existing record retention; required for cooldown/lifecycle |
| Standalone Alert memory | alerts/fiona_alert_memory.json if used | alerts/standalone_memory.json | Existing retention; standalone entry not production scheduler |
| Shadow history | fiona_coverage_shadow_history.json | coverage/shadow_history.json | Existing 21 days; not a delivery authority |
| Generated latest/archive, logs, fetch cache | latest/, archive/, push logs / cache | Remain ephemeral outputs | Not delivery authorities; diagnostic loss remains possible |
| Initialization manifest | None | state_manifest.json | Required; versioned; written last |

Old files survived process-only restarts on same filesystem, not redeploy or
instance replacement. New Volume files support all three in single-instance scope.
Future Gate 3 Delta is a separate namespace, NOT implemented here.

## Architecture and safety contract

`RuntimeStatePaths` is the only path resolver. Production requires actual mount
and root inside it. Initialization is explicit; manifest and all critical stores
must validate. Missing/corrupt initialized state fails closed, preserves evidence,
does not auto-create a blank ledger or invoke legacy fallback. Operator restore
or audited safe boundary is required; future task eligibility resumes afterwards.

Atomic writes: unique temp in same directory, restrictive permissions, flush,
file fsync, atomic replace, directory fsync on supported systems; old authority
survives pre-rename failure. Partial temp never authoritative. Memory adds schema
1.0 and accepts valid pre-version legacy memory. Alert lifecycle decisions remain
unchanged; standalone intent is now persisted before external send.

## Migration and controlled deployment order

1. Full scoped tests, security and release boundary review.
2. Private read-only backup of authoritative ledger, memory, any uncertain journal
   and Shadow history; record hashes/counts, never commit state snapshots.
3. One precise commit + normal push. Auto-deployed protection blocks delivery until
   a real initialized Volume is available; do not mount while old unsafe code runs.
4. Attach dedicated `/data` Volume to the same service. No product variable change.
5. Upload private bundle outside source path. Run `python3 -m app.fiona_state_migration`
   with bundle/root/aware activation boundary. Copies known entries and Alert memory;
   raises last_check_at to boundary to suppress uncertain elapsed backlog, without
   invented success records. Refuses overwriting existing state. Manifest written last.
6. Verify mount, file hashes/entries, writable filesystem, healthy cycles and flags.
7. Safe normal process restart: retain successful entries and Alert memory; observe
   healthy subsequent cycles, no duplicate replay. Never create synthetic occurrence.

Recovery is explicit: back up/quarantine damaged authority, restore verified backup
or initialize an audited new namespace with boundary and preserved available memory.
Do not reset cooldown silently. No unattended recovery promises for corrupted disk.

## Validation / release gate

- Final local full suite: 480 PASS; focused state tests 36 PASS; Gate 2.2 63 PASS.
- Compile and diff whitespace check PASS.
- Memory write failure blocks both Alert delivery and legacy text fallback; no
  durable-state bypass through the existing fallback generator.
- OS-process simulation: Evening once, replacement no second send, next Daily once;
  fake runner only; no Telegram/network/database side effects.
- Legacy/global bridge renders 1440x1800 PNG, English captions, no CJK, cleanup
  success, Telegram 0 / production ledger 0 / formal occurrences 0.
- Read-only network coverage validator: 322 candidates, 59 qualified, 10 selected;
  sources degraded individually (including local TLS/response failures), no fatal
  whole-engine crash; not full production-source acceptance or coverage activation.
- Region precedence, Ukraine bias, admin down-ranking, quality floor, bounded
  regional weights, bridge fallback/isolation and bounded logs tested unchanged.
- Known editorial items (e.g. commentary/Nobel headline) still need later product
  review; do not redesign ranking or close Gate 2 here.

## Release boundary

New: app/fiona_state.py, app/fiona_state_migration.py, tests/test_fiona_gate2_3.py,
this Gate document and incident record.
Modified: runtime, scheduler persistence helpers, memory, standalone Alert runtime,
coverage state path/writer, reviewed global rate-context fix, Gate 2.2 tests,
env example comments, README/deployment/architecture/roadmap/changelog/version docs.
Excluded: pre-existing decision log, all unrelated untracked files, raw logs,
state backups, credentials, reports, PNGs and caches. No git add .

## Acceptance status

Local tests are not live acceptance. Commit / push / Volume / restart results will
be recorded below only after actual verification. PASS requires persistent storage,
retained actual successful occurrence, no restart duplicate and unchanged flags.
Until then: PASS WITH CONDITIONS, production release readiness pending.
