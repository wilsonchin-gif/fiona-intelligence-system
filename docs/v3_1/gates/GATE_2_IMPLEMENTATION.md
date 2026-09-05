# Fiona V3.1 Gate 2 Implementation

- Internal version: V3.1-alpha.2
- Status: Implemented / Shadow Candidate
- Verdict: PASS WITH CONDITIONS
- Owner: Wilson / Fiona Engineering
- Updated: 2026-09-05

## Gate 2.1 Observability Addendum

Production Shadow ran successfully on September 4 and 5 with legacy-selected
photo/en-US output. Cumulative distinct qualified clusters: 159. Official
observation start: 2026-09-04 00:02:09.964920 UTC+8; 14 days remain mandatory.
The aggregate-only history could not support selected-story editorial review.
[Gate 2.1](GATE_2_1_SHADOW_EDITORIAL_OBSERVABILITY.md) adds bounded selected-event
audit records, existing score/provenance visibility and compact occurrence-bound
logs. Ranking and aggregate metrics are unchanged. HKMA remains WATCH after one
success and one timeout. Single-source confirmation remains an observation,
not a clustering fix. Parent Gate 2 remains PASS WITH CONDITIONS; Gate 3 LOCKED.

## Objective

Build trustworthy source identity, provenance, event clustering, materiality,
dynamic 6:3:1 ranking, and Shadow observability without changing production
selection, cadence, Telegram, Scheduler, ledger, arbitration, or Alerts.

## Previous Gate Retrospective

Gate 1 is closed in the signed-off repository record. Those records confirm native Telegram Photo,
1440 x 1800 rendering, and all active `en-US` surfaces were production
validated, including Wilson's real iPhone QA. The last verified production
baseline is photo + en-US, legacy coverage/cadence, and Delta off. The current
Gate 2 session has not yet revalidated live Railway: both available browsers
require sign-in, and the Railway GitHub login page is handed to Wilson. No
contradiction with Gate 1 was observed, but historical acceptance is not a
substitute for current production evidence. Gate 3 has not started.

## Source Audit and Additions

Before Gate 2, seven hard-coded production feeds competed with a stale
`config/sources.json`. The new registry preserves those exact seven names,
order, endpoints, buckets, and weights. Eight additional active Shadow adapters
cover SEC, ECB, Bank of England, HKMA, HKEX, BOJ, RBI, and Bank of Korea. RBA is
registered but disabled as an approved access gap. Other unavailable official
families remain explicit gaps.

## Architecture

- `app/fiona_source_registry.py`: typed source identity, regions, tiers,
  eligibility, profile parsing, and validation.
- `app/fiona_global_coverage.py`: bounded collectors, provenance, region/category
  inference, freshness, materiality, clustering, deduplication, ranking, metrics.
- `app/fiona_coverage_runtime.py`: legacy-safe Shadow execution, source health,
  24h/7d summaries, ephemeral observation history, and safe validator.
- `app/wilson.py`: legacy collectors now derive from the canonical registry and
  retain source provenance for Shadow.
- `app/fiona_runtime.py`: Market News invokes the failure-isolated Shadow path;
  legacy remains authoritative.

## Event, Clustering, and Ranking

The normalized event contract preserves original evidence while adding stable
IDs, event region, tier, independence, freshness, entities, markets,
materiality, cross-market impact, and normalized facts. Clustering separates
duplicate/syndicated reports from independent confirmation. Ranking uses a
quality floor, material override, and soft regional deficit rather than slot
quotas.

## Shadow Safety

Shadow runs only for Market News. It cannot send Telegram, mutate the scheduler
ledger, create a formal occurrence, change Alerts, or alter a brief. Expanded
source failures produce source-health records and cannot fail legacy delivery.
`FIONA_COVERAGE_PROFILE=legacy` remains the production requirement.

## Validation

- Gate 2 focused suite: 82 tests passed (66 required scenarios plus 16 evidence safety regressions).
- Full suite: 359 tests passed on 2026-09-03 with the bundled Python runtime.
- Registry validation: 16 records, 7 legacy, 15 Shadow-eligible, no metadata
  errors or warnings.
- Production-safe source run (2026-09-03 11:36 UTC): 491 candidates, 145 qualified
  clusters, 10 Shadow selections; US/EU 50%, Greater China 30%, ROW 20%.
  Tier 1 30%, Tier 2 70%; 14 source identities, 13 owner groups; 15 duplicate
  rejections and 292 stale-cluster rejections. No Telegram, ledger, or occurrence
  side effects. ECB TLS-chain health failure remained explicit. This is one
  local sample, not a production compliance claim.
- Compile: passed.
- Native-photo production-model fixture: passed at 1440 x 1800, 265477 bytes;
  391-character en-US caption; CJK false; cleanup success; zero Telegram calls
  and ledger mutations. This was offline validation, not a live send.
- All active en-US surface validator: passed, no CJK leakage.
- Legacy content byte equality passed for Shadow success vs failure.

Expected failure-simulation logs appeared inside the regression suite; no test
failed. These are not production runtime errors.

## Production Impact

User-visible Telegram content is unchanged. Native Photo, `en-US`, five legacy
times, Alert behavior, cadence, Delta, Railway command, ledger, and arbitration
remain unchanged. Market News gains bounded synchronous Shadow source requests
and structured metrics; these may add latency, but not additional deliveries.

## Known Gaps and Technical Debt

- 14-day / 100-cluster observation is not yet complete.
- ECB must be rechecked in the Railway CA environment.
- Several desired official sources lack approved stable adapters.
- Rule-based region and clustering need reviewer-labeled false-positive and
  false-negative samples.
- Materiality/cross-market/narrative values are documented heuristics, not
  calibrated impact measurements or automatic truth confirmation.
- Railway history JSON is ephemeral without a Volume; Gate 2 intentionally does
  not add one.
- Current Railway authentication and post-deploy verification are pending.

## Observation Requirement

Start the evidence window after Railway deploy confirms the Shadow log event.
Do not enable `global_631` until at least 14 days and 100 distinct qualified
clusters are reviewed. Repeated evaluations and expanding confirmations are
unioned by event membership; they do not count as new events. A single
validation run is not compliance evidence. Redeploy without durable storage
resets local progress, so a continuous observation window must be independently
documented from production metrics.

## Rollback

Keep `FIONA_COVERAGE_PROFILE=legacy`. If background evaluation affects runtime
health, revert the bounded Gate 2 release commit. No Scheduler or Telegram
variable change is needed.

## Verdict

**PASS WITH CONDITIONS**: implementation is releaseable behind legacy authority;
production activation is blocked by the observation gate. Gate 3 remains locked.

## Repository and Release Boundary

Pre-release branch: `main`. HEAD, origin/main and GitHub main:
`15fef953e2d85f6e1b5cd2233c1e24d5e0fe89ee`; ahead/behind 0/0.

Only the following 22 files belong to this release (9 added, 13 modified):

```text
README.md
app/config.py
app/fiona_runtime.py
app/wilson.py
app/fiona_source_registry.py
app/fiona_global_coverage.py
app/fiona_coverage_runtime.py
config/sources.json
config/fiona.env.example
tests/test_fiona_v3_1_gate2.py
docs/VERSION_MATRIX.md
docs/changelog/CHANGELOG.md
docs/roadmap/roadmap.md
docs/releases/FIONA_MILESTONES.md
docs/releases/FIONA_V3_1_ALPHA_2_RELEASE_NOTES.md
docs/decisions/ADR_007_GLOBAL_EDITORIAL_COVERAGE_ARCHITECTURE.md
docs/v3/FIONA_ARCHITECTURE_SNAPSHOT_V3.md
docs/v3_1/FIONA_GLOBAL_SOURCE_REGISTRY.md
docs/v3_1/FIONA_GLOBAL_COVERAGE_ENGINE.md
docs/v3_1/FIONA_V3_1_IMPLEMENTATION_ROADMAP.md
docs/v3_1/FIONA_V3_1_RELEASE_STRATEGY.md
docs/v3_1/gates/GATE_2_IMPLEMENTATION.md
```

The pre-existing modified `docs/decisions/decision_log.md`, untracked workspace
summaries, historical drafts, DOCX, experimental scripts, reports, PNGs, caches,
and local environment files are excluded. No pre-existing work is overwritten.

## Production Acceptance Checklist

- Confirm Railway deploy source equals the Gate 2 commit.
- Keep photo, en-US, image delivery, legacy coverage/cadence, and Delta off.
- Confirm scheduler cycles `ok=true`, `ledger_load_error=null`, `errors=[]`.
- Read the next legitimate Market News `fionaGlobalCoverageShadow` log.
- Record observation start from that log, not from this document or validator.
- Confirm `selection_authority=legacy` and no coverage-created Telegram message,
  occurrence, or scheduler-ledger mutation.
- Recheck ECB TLS/source health in the actual Railway environment.
- Do not close Gate 2 or begin Gate 3 while 14-day evidence is incomplete.

At document creation, production observation start and production cluster count
are **not yet verified**. The 145 local qualified clusters must not be reported
as production observation progress.
