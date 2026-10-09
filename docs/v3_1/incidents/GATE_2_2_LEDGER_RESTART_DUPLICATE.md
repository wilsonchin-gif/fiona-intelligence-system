# Gate 2.2 Ledger Restart Duplicate

Date: 2026-10-09 | Owner: Wilson / Fiona Engineering | Status: Remediation in progress

## Incident and evidence

Gate 2.2 code commit `e6cdb7a135266149c6281b93725de820fe5b7744` auto-deployed successfully as
`7dcc76ac-19b2-445a-8056-33945208e69a`. Coverage stayed legacy, photo/en-US/image unchanged.
This is an application state-continuity incident, NOT a Telegram API duplicate.

| UTC+8 | Deployment / action | Occurrence / result |
|---|---|---|
| 20:33:45.343621 | Old `9b81af84-9e74-4e5b-abcd-95175533c928`, cycle 9847 detects Evening | `evening:2026-10-09T20:30:00+08:00`; catch-up true; arbitration send / single_due_occurrence |
| 20:34:09.966219 log | Evening succeeds | Telegram 2655; no Alert selected in this run |
| 21:20:26.882090 | New instance `c895503a-8ffa-4cfc-98e1-32f92e5120e9`, cycle 1 detects same occurrence | Same ID; catch-up true; arbitration send / single_due_occurrence |
| 21:20:53.417171 | Runtime Alert 1 sendMessage succeeds | 2656, US macro family |
| 21:20:54.088805 | Runtime Alert 2 sendMessage succeeds | 2657, RWA family |
| 21:20:54.718960 | Evening sendMessage succeeds again | 2658 |
| 21:20:54 | Current ledger finishes successfully | attempt_count=1 in new ledger, not attempt 2 against old ledger |

Old ledger bytes before/after 2655 were not retained. Old structured logs prove
successful delivery; they do not expose the entire historical ledger or old Alert
evidence. New ledger retained the Evening success only, and new memory first_seen
times start at the restart. Private evidence lives outside Git; no state snapshots,
raw article text or credentials are committed.

## Proven root cause

- Ledger `/app/reports/fiona/fiona_scheduler_ledger.json` and shared Alert memory
  `/app/reports/fiona/fiona_memory.json` were on ephemeral application filesystem.
- Railway project had zero Volumes; one production instance.
- Replacement container did not retain old filesystem. Missing ledger loaded with
  `last_check_at=None`, `entries={}`, `load_error=None`.
- Startup lookback permitted the 20:30 Evening within its 150-minute catch-up
  window. `can_execute_occurrence` found no success entry and returned new.
- Arbitration chooses among current candidates, not historical Telegram messages.
  It cannot deduplicate an absent ledger.
- Atomic replace alone protects process crashes, not replacement of storage.

## Alert 2656 / 2657 conclusion

These were runtime Alerts emitted during the duplicate Evening run, not a second
dispatcher. Saved events identify US market macro and RWA institutional-adoption
families with `send_now`; replacement memory treats both as first observations.
The old Evening had Alert count=0. This proves cooldown/lifecycle continuity was
lost and explains first-seen reclassification. It does NOT prove these exact texts
were previously sent, or exclude all real material change: old memory/source
snapshot is unavailable. Classification: restart-related continuity risk (C),
not certified new material-change Alerts, nor proven identical-content duplicates.
Alert thresholds and lifecycle scoring remain unchanged.

## Remediation

Dedicated `/data` Railway Volume, root `/data/fiona`; scheduler ledger and uncertain
journal in `scheduler/`; runtime/standalone Alert memory in `alerts/`; audit history
in `coverage/`. Explicit initialization manifest; no automatic blank production
install. Missing mount, missing initialized state or corruption blocks delivery,
not old catch-up replay. Versioned atomic JSON writes use temp/flush/fsync/replace.

The latest genuine state is exported privately before replacement and migrated.
A documented cutover boundary suppresses elapsed unknown backlog without inventing
success records. Future schedules stay unchanged. Production state loss requires
audited restore/recovery, not automatic reset; future tasks resume after recovery.

## Tests and acceptance

36 focused restart/persistence tests; 63 editorial regressions; 480 total unit tests
and compile pass at initial release preparation. OS-process recreation simulation
sends Evening once through a mock, then Daily once through a mock. Validation itself
has zero real Telegram API calls, production ledger mutations or formal occurrences.
Live Volume / restart acceptance is recorded in the Gate 2.3 document separately;
test success alone is not production acceptance.

## Rollback / prevention

Do not blindly revert to the ephemeral e6c runtime while sending is enabled.
Preserve Volume, manifest, ledger, journals and memories. If new startup fails,
keep delivery blocked, restore known-good state with backup and explicit boundary,
then resume the durable runtime. Removing the Volume is not rollback.
Single-instance contract only: a crash between external delivery and recording
its outcome is not distributed exactly-once. Unknown/partial outcomes remain
suppressed under existing semantics; stale running retries remain a known limitation.
Release readiness must include state continuity, not only a healthy new process.
