# Fiona V3.1-alpha.1.1 Release Notes

- Release: American English Surface Completion
- Status: Release candidate; production observation pending
- Date: 2026-09-02
- Owner: Wilson / Fiona Engineering

## Highlights

- Extends the approved `en-US` output boundary from Market News to Morning,
  Evening, Daily, Weekly, Alert, missing-data copy, and runtime fallback.
- Standardizes American English terminology, UTC+8 display time, concise
  disclaimer, Alert severity, and category-aware market language.
- Adds a final CJK leakage guard to every active text payload before Telegram.
- Preserves original-language source facts and available provenance.

## Architecture

The scheduler still invokes the same runtime, the same five tasks, the same
Alert engine, and the same Telegram service. The only functional extension is
the user-facing locale propagated through the existing presentation path.

## Safety

- No scheduler, ledger, arbitration, cadence, coverage, delta, source, or
  Telegram transport change.
- No external translation provider or LLM dependency.
- One bounded repair/fallback pass; no regeneration loop.
- Safe validator creates no Telegram call, ledger mutation, scheduler mutation,
  or formal occurrence.

## Validation

- Baseline: 234 tests PASS.
- Gate 1.1 focused suite: 43 tests PASS.
- Full suite after implementation: 277 tests PASS.
- Compile: PASS.
- All active en-US surfaces: CJK false.

## Known Limitations

- Production observation is still required for natural Morning, Evening, and
  Alert deliveries after Railway deploy.
- Daily and Weekly pass deterministic validation but await their next scheduled
  production occurrences.
- Historical reports and source-language provenance may remain non-English by
  design.

## Rollback

Revert the Gate 1.1 implementation commit and allow Railway to auto-deploy.
Use `FIONA_OUTPUT_LOCALE=zh-CN` only for urgent operational isolation.

## Deferred

Global 6:3:1 coverage, source expansion, global 4H cadence, product merging,
4H Delta, Railway Volume, Alert redesign, and Scheduler redesign remain outside
this release. Gate 2 is not started.
