# Fiona V3.1-alpha.2 Release Notes

- Release: Global Coverage Engine 6:3:1
- Status: Implemented / Shadow Candidate
- Date: 2026-09-03
- Production authority: Legacy coverage

## Highlights

- One canonical registry for all legacy and Gate 2 sources.
- Tier 1-first official source expansion across US/Europe, Greater China, and
  Rest of World.
- Original provenance, event-region semantics, source independence, bounded
  clustering, freshness, deterministic materiality, and dynamic 6:3:1 ranking.
- Failure-isolated Shadow evaluation with per-edition and rolling 24h/7d metrics.
- Production-safe registry and global coverage validators.

## Compatibility

The exact seven legacy feeds remain the user-visible input in their existing
order. Native Photo, `en-US`, Telegram transport, Scheduler, five task times,
ledger, arbitration, cadence, Delta, and Alert behavior are unchanged.

## Validation

- 82 focused Gate 2 tests pass.
- Full regression suite: 359 tests pass.
- Python compile passes.
- Validator reports zero Telegram calls, zero scheduler-ledger mutations, and
  zero formal occurrences.

## Known Limitations

- `global_631` is not production-activated.
- The 14-day / 100-qualified-cluster evidence window remains open.
- ECB source health requires Railway CA verification.
- RBA and other documented official families remain approved gaps.
- Observation JSON is ephemeral on Railway without a Volume.

## Rollback

Keep `FIONA_COVERAGE_PROFILE=legacy`. Revert the bounded release commit if the
Shadow evaluator affects production health. Do not change Scheduler or Telegram.

## Next Gate

Gate 3 remains locked until Product reviews the Gate 2 observation evidence.
