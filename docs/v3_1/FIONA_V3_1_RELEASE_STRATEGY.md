# Fiona V3.1 Release Strategy

Version: V3.1-alpha.2
Status: Gate 2 Implemented / Shadow Candidate; Gate 3 LOCKED
Owner: Wilson / Codex
Updated: 2026-09-03

## 1. Release Objective

Release **Fiona V3.1 - Global 4H Intelligence Feed** without destabilizing the
V3.0.0 production scheduler, image renderer, Telegram delivery, or current
briefs before their approved replacement is ready.

V3.1 is one external product release implemented through independent internal
milestones:

| Version | Scope | Production meaning |
|---|---|---|
| `V3.1-alpha.1` | Native Photo + `en-US` | production validated; Gate 1 closed |
| `V3.1-alpha.2` | Global Coverage Engine | Shadow only initially |
| `V3.1-beta` | six-slot cadence + 4H Delta | simulation and controlled beta |
| `V3.1-RC` | integrated system | release-candidate validation |
| `V3.1.0 GA` | complete Global 4H product | production |

## 2. Release Principles

1. No big-bang cutover.
2. Legacy behavior is the code default until a wave passes review.
3. One feature flag changes one operational contract.
4. Unknown Telegram delivery never triggers an automatic second send.
5. Regional allocation runs in Shadow before publication.
6. Global cadence does not activate before durable state is healthy.
7. Every wave has its own release boundary and rollback.
8. No `git add .`, force push, uncontrolled deployment, or untracked-file
   cleanup.
9. Every wave starts with a Previous Wave Retrospective and ends with a Wave
   Completion Review and stop.

## 3. Feature Flag Contract

### 3.1 `FIONA_TELEGRAM_MEDIA_MODE`

| Value | Behavior |
|---|---|
| `document` | current image document with caption |
| `photo` | native photo with short caption |

- Default during initial deployment: `document`.
- Definite photo failure: one text fallback.
- Automatic photo -> document -> text fallback is prohibited.
- Unknown photo result: no retry/fallback; record terminal unknown state.
- Rollback: set `document`; no scheduler change.

### 3.2 `FIONA_OUTPUT_LOCALE`

| Value | Behavior |
|---|---|
| `zh-CN` | current legacy language behavior |
| `en-US` | deterministic American English user layer |

- Default during initial deployment: `zh-CN`.
- Failed source normalization: use an English safe fallback or withhold the
  unresolved item; never leak Chinese into the user payload.
- Preserve original language/title/content in provenance where supported.
- Do not add a separate translation API in Wave 1 unless technical evidence and
  a new Product approval require it.
- Rollback: `zh-CN`.

### 3.3 `FIONA_COVERAGE_PROFILE`

| Value | Behavior |
|---|---|
| `legacy` | current source/ranking authority plus Gate 2 Shadow evaluation |
| `global_631` | reserved activation profile; alpha.2 still enforces legacy authority |

- Default: `legacy`.
- New behavior first runs in Shadow with candidate/selection comparison.
- Invalid profile: warning + `legacy`. Ranking failures cannot affect legacy delivery.
- The registry is release-validated; it is the sole production source list.
- Alpha.2 never publishes Shadow selections, even if `global_631` is supplied.
- No additional observability flag, scheduler, Telegram sender, or ledger is added.

### 3.4 `FIONA_CADENCE_MODE`

| Value | Behavior |
|---|---|
| `legacy` | current five named schedules |
| `global_4h` | six Global 4H editions plus Weekly |

- Default: `legacy`.
- Activation requires a cutover timestamp and durable schedule profile journal.
- Rollback must prevent discovery of both profiles for the same period.
- Production timezone: `Asia/Hong_Kong` / UTC+8.
- Every scheduled slot produces an edition; no material change is reported
  explicitly with reduced density rather than an invented narrative.

### 3.5 `FIONA_4H_DELTA_MODE`

| Value | Behavior |
|---|---|
| `off` | no Delta comparison |
| `shadow` | compute/store/validate; do not publish |
| `on` | publish validated Delta |

- Default: `off`.
- Missing or unhealthy state returns explicit baseline-unavailable status.
- Rollback is independent of cadence.
- Approved persistence: dedicated Railway Volume state, atomic/versioned
  snapshots, and 14-day retention. PostgreSQL is deferred.

No separate resolution flag is recommended. The 1440 x 1800 render profile is
part of native photo mode.

## 4. Gate Model

### 4.1 Repository Gate

- correct repository and `main` branch;
- local HEAD, `origin/main`, and GitHub remote identified;
- ahead/behind reported;
- all pre-existing tracked/untracked files recorded;
- no unrelated file enters the release boundary.

### 4.2 Production Gate

- current production commit and mode recorded;
- scheduler, runtime, Telegram, and state health recorded;
- no production variable changed before approval;
- rollback command/variable sequence written before cutover.

### 4.3 Quality Gate

- Python compile passes;
- full test suite passes;
- wave-focused tests pass;
- static language/security/source checks pass;
- Telegram calls = 0 in automated local validation;
- production scheduler ledger mutations = 0 in renderer/locale/source validators;
- generated media passes dimensions, bytes, format, and layout checks.

### 4.4 Release Boundary Gate

Before commit, show explicit file list, staged diff, and staged diff statistics.
Exclude reports, PNG prototypes, caches, local `.env`, logs, temporary state,
experiments, and unrelated documentation.

### 4.5 Documentation Gate

- CHANGELOG;
- Version Matrix;
- Release Notes;
- Release Manifest;
- Architecture Snapshot;
- deployment/environment guide;
- ADR for an accepted decision;
- Previous Wave Retrospective;
- Wave Completion Review;
- milestone update where appropriate.

## 5. Wave Release Boundaries

### Alpha 1 Boundary

Includes only:

- Telegram native-photo transport and delivery coordination;
- 1440 x 1800 token/renderer profile;
- localization/output-language boundary;
- related tests and documentation.

Excludes sources, regional ranking, scheduler, Delta, and production variables.

### Alpha 2 Boundary

Includes only:

- canonical source registry and approved adapters;
- provenance, region, tier, independence, dedup/clustering;
- 6:3:1 ranking and Shadow observability;
- related tests and documentation.

Excludes scheduler and Delta activation.

### Beta Boundary

Includes only:

- schedule profiles and six edition slots;
- merged edition responsibilities;
- durable state adapter;
- Delta contract/store/comparator;
- Weekly/Alert arbitration compatibility;
- migration, tests, and documentation.

Excludes production activation until the RC gate.

### RC Boundary

Contains only integration changes needed to join already approved wave outputs.
No opportunistic refactor or new product feature is permitted.

## 6. Shadow and Validation Strategy

### Native Photo

- Production uses native `photo` delivery with a short `en-US` caption.
- The production card is rendered directly at 1440 x 1800 from the same
  ViewModel; the legacy document path remains available for rollback.
- Image, caption, safe area, file size, render duration, Telegram processing,
  and real iPhone presentation have passed Gate 1 acceptance.
- A successful occurrence sends one photo only. Explicit failure permits one
  text fallback; unknown delivery permits no retry or second send.

### American English

- Generate every brief, Alert, missing-data, fallback, and image fixture.
- Run deterministic no-CJK and American-spelling checks.
- Review translated source meaning against original provenance.
- Do not activate if any unresolved source text can leak to users.

### Global Coverage

- Reuse the exact legacy candidates and add official Shadow-only candidates.
- Publish legacy only.
- Record 24-hour/seven-day regional share, tier share, diversity, duplicates,
  confirmation, overrides, and reviewer judgments.
- Activation gate: at least 14 days and 100 distinct qualified event clusters.
- The count unions overlapping event membership across observations, so repeat
  evaluations and new confirmations do not inflate progress.
- Without a Railway Volume, local Shadow JSON is ephemeral. A redeploy may reset
  observation progress; exported production metrics are needed to establish a
  continuous review window. Gate 2 does not introduce persistence infrastructure.

### 4H Delta

- Store snapshots and compute Delta in Shadow while cadence is still legacy.
- Simulate synthetic six-slot snapshots to verify exact previous-slot lookup.
- Test missing baseline, restart, redeploy, partial source data, schema change,
  retention, and corruption.

### Global Cadence

- Simulate seven days at five-minute polling.
- Include process start/restart around all six slots.
- Include Sunday 20:00, Weekly 21:00, and Monday 00:00.
- Include Alert collision, network timeout, unknown Telegram state, and state
  unavailability.
- Rehearse cutover and rollback using copied production-shaped ledger data.
- Confirm the 00:00 Extended Edition uses the new calendar date, reviews the
  completed 24-hour cycle, and establishes new-cycle confirmation variables.

## 7. Production Activation Plan

1. Approve the wave release commit and exact manifest.
2. Push normally to `main`; no force push.
3. Confirm local HEAD, `origin/main`, and GitHub remote are identical.
4. Allow Railway auto-deploy with all new flags on legacy defaults.
5. Confirm deploy source SHA, runtime start, scheduler cycle, and existing output.
6. Run production-safe validators with no Telegram calls and no ledger mutation.
7. Activate one approved flag at a time.
8. Record the variable change time and previous value.
9. Observe the specified cycles before the next flag.
10. Stop immediately on a release-gate failure and execute the documented
    rollback; do not improvise a second send.

Recommended production sequence:

```text
Legacy defaults
  -> en-US/native-photo validated in isolated chat
  -> controlled en-US + photo activation
  -> global coverage Shadow
  -> global coverage active
  -> durable state healthy
  -> Delta Shadow
  -> global cadence cutover + Delta on
  -> full seven-day observation
  -> V3.1.0 GA
```

## 8. Observability Requirements

### Delivery

- requested/effective media mode;
- occurrence ID and payload hash;
- render success, width, height, bytes, duration;
- caption length and locale;
- Telegram outcome category and message ID;
- fallback and cleanup state;
- no token, caption body, or private user data.

### Locale

- output locale;
- source original language;
- normalization method/status;
- CJK leakage count;
- withheld item count.

### Coverage

- candidate/selected/published regional shares;
- source tier/diversity/concentration;
- independent-source count;
- override, duplicate, stale, and rejected counts.

### Scheduler

- schedule profile and edition slot;
- scheduled/detected/started/finished timestamps;
- catch-up age;
- arbitration action/reason;
- delivery terminal state;
- state-store health and schema.

### Delta

- current and baseline edition IDs;
- comparison status by field;
- missing/stale/not-comparable count;
- state write/read/checksum/retention health.

## 9. Rollback Matrix

| Failure | Immediate action | Data action | User-facing result |
|---|---|---|---|
| Photo rendering/upload definite failure | text fallback for that occurrence; set media mode to document if systemic | retain logs and payload hash | one text update |
| Photo outcome unknown | no retry/fallback | mark occurrence unknown for reconciliation | possible single photo; no duplicate |
| `en-US` leakage/meaning error | return locale to `zh-CN` | retain source/normalized pair for review | legacy language resumes |
| Coverage quality failure | set profile to legacy | retain Shadow metrics | legacy ranking resumes |
| Delta store failure | set Delta off | preserve last valid snapshot; do not overwrite | edition states baseline unavailable or no Delta |
| Global cadence failure | coordinated profile rollback | preserve cutoff and all occurrence history | legacy schedule resumes without same-period duplication |
| Code regression | revert only approved release commit | no destructive state migration | Railway deploys prior code |

## 10. Stop Conditions

Stop activation immediately if any of the following occurs:

- local/origin/GitHub commit mismatch;
- unreviewed file inside the release boundary;
- compile or any required test failure;
- Telegram token or private payload in logs;
- CJK leakage in user-visible `en-US` output;
- photo delivery without reliable unknown-state handling;
- image crop/overflow or unreadable iOS typography;
- unlicensed source use;
- material event suppressed by regional weighting;
- ledger or Delta state is not durable;
- duplicate scheduled delivery;
- legacy and global schedules run simultaneously;
- Weekly or Alert is unintentionally suppressed;
- Railway crash loop or validator mutation of production ledger.

## 11. GA Declaration

V3.1.0 may be marked Production only after:

- all five wave reviews are approved;
- exact GA commit and release manifest are recorded;
- local, origin, and GitHub commits match;
- Railway reports the GA source commit;
- all six edition slots and Sunday Weekly have been observed;
- native photo, `en-US`, coverage, and Delta metrics meet their gates;
- rollback has been rehearsed;
- CHANGELOG, Version Matrix, Release Notes, Architecture Snapshot, ADRs, and
  milestones are synchronized.

## 12. Current Authorization

Gate 0 and Gate 1 are closed. `V3.1-alpha.1` is production validated with
`photo + en-US`. Wilson authorized Gate 2 implementation and its normal release
behind legacy selection. Coverage and cadence must remain `legacy`; Delta stays
off. Gate 2 global selection activation, Gate 3, new Volumes, and schedule changes
are not authorized. Production verification and observation remain distinct from
the local implementation verdict.
