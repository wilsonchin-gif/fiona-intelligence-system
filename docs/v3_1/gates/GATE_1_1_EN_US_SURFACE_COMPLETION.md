# Fiona V3.1 Gate 1.1 - American English Surface Completion

- Internal version: V3.1-alpha.1.1
- Gate: Gate 1.1
- Status: Production Validated; merged into closed Gate 1
- Owner: Wilson / Fiona Engineering
- Updated: 2026-09-03
- Production baseline: `d0ea66931bdedf0cacbf3df451379ddbd327ea67`
- Implementation commit: `87d046884375fe0fc64fe8e35e009f04dad77c46`

## Objective

Complete the existing `en-US` boundary for every active Telegram surface while
preserving product logic, source provenance, schedules, alert thresholds,
delivery semantics, ledger behavior, and Gate 2 isolation.

## Previous Wave Retrospective

Gate 1 successfully delivered native Telegram photo transport and an American
English Market News surface. Production acceptance confirmed a 1440 x 1800
photo, successful validation and cleanup, no text duplicate, and no Market News
CJK leakage. The production flags are `photo + en-US`.

The actual miss was narrower but material: runtime read
`FIONA_OUTPUT_LOCALE` only inside the Market News branch. Morning, Evening,
Daily, Weekly, Alert, and the generic fallback continued to use Chinese or
mixed-language presentation resources. Gate 1.1 closes that implementation
gap. It does not minimize or reinterpret it as a source-data issue.

## Root Cause

```text
Scheduler
  -> run_once
     -> build_payload using legacy default language
        -> Morning / Evening / Daily / Weekly render_text (zh-CN)
        -> render_alert (zh-CN)
     -> locale read only when brief == Market News
```

The locale architecture existed, but its runtime boundary was scoped to one
product instead of the complete Telegram presentation layer.

## Implementation

- Runtime resolves `FIONA_OUTPUT_LOCALE` once before payload construction.
- The selected locale is passed through brief builders and Alert rendering.
- `app/fiona_locale.py` remains the single source for terminology, editorial
  resources, timestamps, Alert severity names, deterministic event projection,
  and CJK validation.
- Chinese source facts remain in the event and provenance structures. The
  English surface uses conservative category-aware synthesis and does not call
  an external translator.
- The final `push_text` boundary validates en-US text before Telegram. Known
  deterministic labels are repaired once; unresolved leakage uses one safe
  English fallback. Mixed-language output is never silently sent.

## Surfaces Migrated

| Surface | Result | Notes |
|---|---|---|
| Market News | Regression PASS | Existing native photo/card/caption path retained |
| Morning | Migrated | Existing sections and product purpose retained |
| Evening | Migrated | Existing night-risk structure retained |
| Daily | Migrated | Existing standalone legacy cadence retained |
| Weekly | Migrated | Existing narrative and scenario structure retained |
| Alert | Migrated | Thresholds/lifecycle unchanged; severity is now deterministic English |
| Missing data | Migrated | Repeated missing states collapse to one English summary |
| Generic fallback | Migrated | Safe English output even when snapshot creation fails |
| Timestamp | Standardized | `SEP 02 · 20:00 UTC+8` |
| Disclaimer | Standardized | `For informational purposes only. Not investment advice.` |

## Leakage Failure Policy

1. Repair a known deterministic resource or punctuation mismatch once.
2. Use the existing deterministic English event projection where supported.
3. Replace the unsafe payload with one safe English fallback.
4. Fail delivery only if the fallback itself violates the language contract.

There is no open-ended regeneration loop and no automatic CJK allowlist.

## Validation

- Focused Gate 1.1 tests: 43 PASS.
- Baseline full suite: 234 PASS before implementation.
- Updated full suite: 277 PASS.
- Production-safe validator: all six active surfaces report `cjk=false`.
- Telegram API calls: 0.
- Ledger mutations: 0.
- Scheduler mutations: 0.
- Formal occurrences created: 0.
- Full/Missing and Alert fixtures are generated under ignored `reports/`.

## Production Impact

Production currently has `FIONA_OUTPUT_LOCALE=en-US`, so deployment of this
change is an immediate language rollout for the remaining active surfaces.
Market News photo transport remains unchanged. Scheduler, occurrence logic,
ledger, arbitration, coverage, cadence, delta, Telegram API semantics, and
Railway variables are unchanged.

## Known Risks

1. Source wording may be withheld when it cannot be represented safely by the
   deterministic English projection; this is deliberate and preferable to a
   fabricated translation.
2. Daily and Weekly passed deterministic production-safe validation; later
   natural occurrences remain part of normal operational observation.
3. Legacy non-production reports and historical files may remain Chinese; they
   are outside the active Telegram boundary.

## Rollback

Preferred rollback is `git revert <Gate-1.1-commit>` followed by the normal
Railway auto-deploy. `FIONA_OUTPUT_LOCALE=zh-CN` is reserved for an urgent
operational isolation only. No scheduler or ledger rollback is required.

## Gate Verdict

**Production verdict: PASS.**

Real Morning, Evening, and naturally occurring Alert deliveries succeeded in
`en-US`; production runtime remained healthy; Daily and Weekly production-safe
validation passed; Wilson accepted real iPhone output and production CJK
leakage. Gate 1.1 is complete and the parent Gate 1 is closed. Gate 2 remains
locked and has not started.
