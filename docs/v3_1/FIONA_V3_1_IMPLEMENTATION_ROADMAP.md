# Fiona V3.1 Implementation Roadmap

Version: V3.1-alpha.2
Status: Gate 2 Implemented / Shadow Candidate; Gate 3 LOCKED
Owner: Wilson / Codex
Updated: 2026-09-03

## 1. Delivery Model

Fiona V3.1 is developed in five reversible Gates/Waves and released externally as one
coherent product generation: **Fiona V3.1 - Global 4H Intelligence Feed**.

Every wave follows the same mandatory lifecycle:

```text
Previous Wave Retrospective
  -> Repository Gate
  -> Product/Contract Gate
  -> One bounded implementation wave
  -> Compile
  -> Focused tests
  -> Full test suite
  -> Production-safe validation
  -> Documentation Sync
  -> Release Boundary Review
  -> Wave Completion Review
  -> STOP for Wilson/Product Review
```

No wave automatically starts the next one.

## 2. Gate 0 - Audit and Product Freeze

### Goal

Establish the verified V3.0 baseline, freeze V3.1 intent, identify affected
contracts, and define a release plan without changing production.

### Scope

- V1-V3 retrospective;
- production architecture and workflow audit;
- Telegram/iOS and 1440 x 1800 feasibility;
- `en-US` language surface audit;
- source inventory and regional coverage estimate;
- 6:3:1 feasibility;
- scheduler, merge, Weekly, Alert, and Delta audit;
- feature flag, risk, testing, and release strategy.

### Deliverables

- `docs/audits/FIONA_V3_1_GLOBAL_4H_TECHNICAL_AUDIT.md`
- `docs/v3_1/FIONA_V3_1_PRODUCT_FREEZE.md`
- `docs/v3_1/FIONA_V3_1_IMPLEMENTATION_ROADMAP.md`
- `docs/v3_1/FIONA_V3_1_RELEASE_STRATEGY.md`

### Exit Gate

- Wilson approved the Product Freeze with the conditions recorded in the Gate 0
  Closeout.
- No production code, variable, commit, push, or deploy occurred.
- Verdict: **PASS WITH CONDITIONS -> CLOSED**.

## 3. Gate/Wave 1 - Native Delivery and en-US

Internal version: `V3.1-alpha.1`

### Previous Wave Retrospective

Before implementation, verify Phase 0 intent, documents, test evidence, open
decisions, and worktree boundary. Record whether the Product Freeze is still
valid.

### Goal

Deliver the approved Telegram-native photo experience and deterministic
American English user layer without changing sources or cadence.

### Scope

- production-grade `sendPhoto` with short caption;
- classified definite/unknown Telegram outcomes;
- 1440 x 1800 direct Pillow render profile;
- iOS safe-area and photo-processing validation;
- centralized `OutputLocale` and static string resources;
- `en-US` timestamp, number, currency, percentage, and punctuation formatting;
- source-language provenance fields and normalization status;
- English-only fallback and CJK leakage guard;
- caption de-duplication against the image;
- `FIONA_TELEGRAM_MEDIA_MODE` and `FIONA_OUTPUT_LOCALE`.

Approved language flow:

```text
Original-language source
  -> normalized facts/events
  -> English intelligence synthesis
  -> deterministic en-US output validation
```

Wave 1 must not add a separate translation API unless implementation proves it
technically necessary and Product approves the change.

### Explicit Non-Scope

- source expansion;
- 6:3:1 ranking;
- scheduler changes;
- Delta storage;
- Alert behavior changes.

### Likely Files

- `app/telegram_service.py`
- `app/fiona_market_news_delivery.py`
- `app/fiona_market_news_image.py`
- `app/fiona_card_renderer.py`
- `app/fiona_card_components.py`
- `app/design_tokens.py`
- `app/fiona_briefing.py`
- `app/fiona_classifier.py`
- `app/fiona_runtime.py` only for locale/media wiring, not scheduler behavior
- new locale/output-contract module(s)
- focused tests and V3.1 documentation

### Required Tests

- photo multipart and caption;
- 1440 x 1800 dimensions and file bounds;
- no post-render scaling;
- iOS safe-area geometry;
- timeout/5xx/malformed response unknown state;
- no duplicate fallback after unknown state;
- one text fallback after definite failure;
- all user-visible products pass `en-US` and no-CJK lint;
- original source text remains internal;
- Telegram calls = 0 in local validation;
- scheduler and ledger regression tests unchanged.

### Risk and Rollback

Risk: Medium.
Rollback: `FIONA_TELEGRAM_MEDIA_MODE=document` and
`FIONA_OUTPUT_LOCALE=zh-CN`. A definite photo failure falls back once to text;
an unknown result is not retried. Code deploys with legacy defaults.

### Wave Completion Review

Review iOS screenshots, Telegram-returned media metadata, language leakage,
fallback behavior, full tests, documentation, and exact release boundary. Stop.

### Current Result

- Native `sendPhoto`, direct 1440 x 1800 render, media flag, centralized locale,
  fallback matrix, leakage guard, and validator are complete and production
  validated.
- Gate 1.1 completed the `en-US` boundary for Market News, Morning, Evening,
  Daily, Weekly, Alert, missing-data states, and safe fallback text.
- Real Market News, Morning, Evening, Alert, iPhone presentation, and CJK
  leakage acceptance passed. Daily and Weekly passed production-safe validation.
- Implementation commits: `d0ea66931bdedf0cacbf3df451379ddbd327ea67`
  and `87d046884375fe0fc64fe8e35e009f04dad77c46`.
- Verdict: **CLOSED - PRODUCTION VALIDATED**.
- Gate 2: **NOT STARTED**.

## 4. Gate/Wave 2 - Global Coverage Engine

Internal version: `V3.1-alpha.2`

### Previous Wave Retrospective

Confirm Native Photo and `en-US` behavior, production impact, open risks, release
records, and whether Wave 1 genuinely passed. Do not begin source work if photo
or locale rollback remains unresolved.

### Goal

Create evidence-backed global candidate coverage and a measurable dynamic 6:3:1
editorial allocation.

### Scope

- canonical source registry as the single source of truth;
- source ID, tier, authority, language, region, independence group, and status;
- approved source adapters in Tier 1-first order;
- original and normalized source content;
- event-level geography and multi-region support;
- source-aware deduplication and clustering;
- materiality and cross-market override;
- deterministic regional-balance adjustment;
- 24-hour and seven-day coverage metrics;
- `FIONA_COVERAGE_PROFILE=legacy|global_631`;
- Shadow-only ranking and reviewer comparison first.

### Explicit Non-Scope

- six-edition scheduler;
- 4H Delta;
- production Alert expansion;
- hard regional quotas.

### Likely Files

- `config/sources.json` or a versioned replacement registry
- `app/wilson.py`, preferably through bounded source adapters rather than more
  unrelated helpers
- `app/fiona_contracts.py` or a backward-compatible source/evidence extension
- new source registry, region classifier, clustering, and coverage modules
- source, ranking, and observability tests
- source policy and architecture documents

### Required Data Gate

- approved licensing and redistribution terms;
- deterministic source identity and independent-source rules;
- minimum 14-day Shadow sample;
- at least 100 candidate clusters;
- reviewer-labeled false positives and missed material events;
- no claim of 6:3:1 compliance based only on feed count.

### Required Tests

- source registry validation;
- primary/official/source-tier behavior;
- syndicated duplicate detection;
- event region and multi-region classification;
- material override;
- soft allocation under candidate scarcity;
- source outage, timeout, rate-limit, stale, and malformed data;
- metric correctness and no private credential logging.

### Risk and Rollback

Risk: High.
Rollback: `FIONA_COVERAGE_PROFILE=legacy`; new adapters remain inactive. No
production activation before Shadow review.

### Wave Completion Review

Review source evidence quality, regional metrics, duplication, override cases,
licenses, data costs, and 14-day Shadow results. Stop.

## 5. Gate/Wave 3 - Global 4H Intelligence

Internal version: `V3.1-beta`

### Previous Wave Retrospective

Confirm global source quality, regional metrics, source failures, documentation,
and rollback. Do not change cadence if evidence provenance is incomplete.

### Goal

Introduce six reliable UTC+8 editions, consolidate existing brief roles, and add
deterministic 4H Delta with durable state.

### Scope

- versioned schedule profiles and six edition slots;
- UTC+8 scheduling through `Asia/Hong_Kong`;
- edition responsibilities for 00/04/08/12/16/20;
- Morning merge into 08:00;
- Evening merge into 20:00;
- Daily merge into 00:00 Extended;
- Weekly retained at Sunday 21:00;
- material Alert compatibility;
- durable occurrence ledger;
- dedicated 4H snapshot store;
- deterministic Delta comparison and missing-baseline states;
- a reduced-density but explicit No Material Change edition when applicable;
- legacy occurrence cutoff and additive ledger compatibility;
- `FIONA_CADENCE_MODE` and `FIONA_4H_DELTA_MODE`.

### Explicit Non-Scope

- new end-user product modules;
- dashboard/database analytics;
- vector search or Knowledge Graph;
- an Alert worker redesign beyond compatibility required for material changes.

### Likely Files

- `app/fiona_scheduler.py`
- `app/fiona_runtime.py`
- `app/fiona_briefing.py`
- new edition schedule/profile module
- new Delta contract/comparator/store module
- ledger/state migration utilities with dry-run support
- Railway/deployment documentation; a volume configuration only after approval
- extensive scheduler, storage, merge, and collision tests

### Required Storage Gate

Minimum recommendation:

- mounted Railway Volume;
- scheduler ledger and Delta store in separate namespaces;
- atomic write, lock, checksum, schema version, backup, retention, and restore;
- 14-day Delta snapshot retention;
- no production cadence activation while state health is unknown.

PostgreSQL is required only if deployment becomes multi-replica, concurrent
writers are introduced, or query/audit needs exceed the volume design.

### Required Tests

- six slots over seven days;
- exact occurrence IDs and schedule versioning;
- every startup/restart/catch-up boundary;
- Sunday 20:00/Weekly 21:00/Monday 00:00;
- Alert collision and edition dedup;
- old schedule cutoff and rollback;
- no standalone Morning/Evening/Daily in global mode;
- state persistence across simulated replacement;
- Delta units, stale/missing/partial/schema-change states;
- volume unavailable and corrupt snapshot recovery;
- no duplicate send under unknown Telegram state.

### Risk and Rollback

Risk: High.
Rollback: coordinated return to `FIONA_CADENCE_MODE=legacy` using the recorded
cutoff and schedule profile. Delta can independently return to `off` without
changing cadence.

### Wave Completion Review

Review seven-day simulation, cutover rehearsal, rollback rehearsal, state backup,
collision behavior, notification count, and all merged responsibilities. Stop.

## 6. Gate/Wave 4 - Integrated Release Candidate

Internal version: `V3.1-RC`

### Previous Wave Retrospective

Confirm the scheduler and Delta beta passed all reliability gates and no legacy
notification duplication occurred in simulation.

### Goal

Validate all V3.1 capabilities together without an uncontrolled production
switch.

### Scope

- native photo plus `en-US`;
- global 6:3:1 candidate ranking;
- six-edition schedule and merged responsibilities;
- 4H Delta;
- Weekly and Material Alert compatibility;
- production-safe telemetry and runbooks.

### Validation Matrix

- Full, Missing, Stress, and multilingual source fixtures;
- iOS light/dark mode screenshots;
- Telegram definite and unknown failure simulations;
- seven-day scheduler, restart, catch-up, collision, and duplicate simulations;
- source outage and regional scarcity;
- Delta baseline loss and schema evolution;
- 24-hour/7-day regional coverage;
- notification-density review;
- compile, full tests, focused tests, and validator;
- Telegram calls = 0 in automated local gates;
- production group remains untouched until approval.

### Risk and Rollback

Risk: Medium/High.
Rollback: each new flag returns independently to its legacy value. Integrated RC
does not change production variables automatically.

### Wave Completion Review

Product, engineering, data, iOS, and release sign-off. Stop before GA.

## 7. Gate/Wave 5 - Controlled Production Rollout

Internal version: `V3.1.0 GA`

### Previous Wave Retrospective

Confirm every RC gate, exact commit, documentation, rollback rehearsal, and
production variable plan.

### Goal

Activate V3.1 progressively with a traceable, reversible production cutover.

### Recommended Activation Order

1. Deploy code with all new flags at legacy defaults.
2. Run renderer, locale, source, and state validators.
3. Validate native photo and `en-US` in an isolated Telegram chat.
4. Activate `en-US` and native photo under the approved cutover plan.
5. Observe at least three scheduled legacy-cadence occurrences.
6. Enable global coverage Shadow and complete the approved observation period.
7. Enable `global_631` while cadence remains legacy.
8. Mount/verify durable state and enable Delta Shadow.
9. Rehearse cadence cutover and rollback against a copied ledger/state set.
10. Enable `global_4h` at the recorded cutoff.
11. Observe all six slots, Sunday Weekly, a restart, and a full seven-day cycle.
12. Mark V3.1.0 GA only after the completion report is approved.

### Production Success Criteria

- native `sendPhoto` returns a message ID;
- image is 1440 x 1800 and passes iOS QA;
- caption is short, non-duplicative, and `en-US`;
- no user-visible Chinese leakage;
- 6:3:1 metrics are visible and material override is preserved;
- each required edition has one terminal occurrence;
- no standalone Morning, Evening, or Daily delivery;
- Weekly remains separate;
- Delta uses the previous scheduled baseline or reports unavailable;
- no crash loop, source-failure cascade, duplicate delivery, or state corruption.

### Rollback

Rollback feature flags in reverse order. Cadence rollback uses the release
cutoff and profile journal. Unknown Telegram delivery is never automatically
resent. If code rollback is required, revert only the approved wave commit and
allow Railway to deploy the revert normally.

## 8. Cross-Wave Documentation Contract

Before each approved commit:

- update CHANGELOG;
- update Version Matrix;
- update Product/PRD and Architecture/Dataflow;
- update environment and deployment guides;
- add Release Notes and Release Manifest;
- add an ADR for accepted architecture/product decisions;
- update milestone history at significant production boundaries;
- record exact test count and production source SHA.

No documentation update is bundled opportunistically from an unrelated wave.

## 9. Roadmap Stop Condition

Gate 1 is closed. Wilson authorized Gate 2 source/provenance/clustering/ranking
implementation with legacy-safe Shadow observation. That implementation is
complete locally; the production observation gate remains open. See
[Gate 2 implementation](gates/GATE_2_IMPLEMENTATION.md).

Global 6:3:1 selection needs at least 14 days and 100 distinct qualified
clusters plus Product review before activation. No source-count or single-run
ratio claim substitutes for that evidence. Gate 3 remains locked: no cadence,
Delta, Volume, or brief-merger work is authorized by this wave.
