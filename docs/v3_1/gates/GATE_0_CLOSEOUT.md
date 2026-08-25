# Fiona V3.1 Gate 0 Closeout

Version: V3.1.0 Phase 0
Gate: 0
Name: Retrospective & Technical Audit
Verdict: PASS WITH CONDITIONS -> CLOSED
Owner: Wilson / Codex
Closed at: 2026-08-25
Production baseline: Fiona V3.0.0 (`a8678b0`)

## 1. Objectives

Gate 0 reviewed Fiona V1-V3, audited V3.1 technical feasibility, and froze the
product contract for Fiona Global 4H Intelligence. It did not authorize or
implement Gate 1.

## 2. Work Performed

- Confirmed the repository, branch, production baseline, and remote identity.
- Audited the V1-V3 architecture, scheduler, delivery, sources, language,
  persistence, rendering, tests, and release controls.
- Compared the V3.1 product target with current production capabilities.
- Recorded implementation blockers, migration boundaries, reversible flags,
  and the phased release strategy.
- Ran Python compile and the complete unit suite without production side effects.
- Completed Product Review and froze the approved decisions in repository docs.

## 3. Previous Wave Retrospective

- V1 established Railway, Telegram, fixed briefs, and unattended operation.
- V2 established scheduler reliability, occurrence arbitration, delivery
  safety, image shadow validation, and production image delivery.
- V3.0 established judgment-first visual hierarchy, reusable design tokens and
  components, and a stable 1080 x 1350 Intelligence Card.
- V3.1 must extend the stable platform incrementally. A rewrite and a big-bang
  cadence cutover are rejected.

## 4. Audit Findings

- The current architecture supports a gradual V3.1 upgrade; a rewrite is not
  required or recommended.
- Native `sendPhoto` is not yet equivalent to the current production document
  transport and needs an isolated Gate 1 delivery contract.
- User-visible strings and synthesis currently mix Chinese and English.
- Production source provenance is collapsed and Europe/Rest-of-World coverage
  is insufficient for a defensible global 6:3:1 claim.
- The current scheduler model cannot directly express six editions of the same
  product kind, and existing collision windows need explicit redesign.
- Scheduler ledger and intelligence memory are not durable across Railway
  replacement without a mounted persistent medium.
- There is no dedicated previous-edition state for deterministic 4H Delta.

## 5. Approved Product Decisions

1. Product name: Fiona Global 4H Intelligence.
2. Delivery target: native Telegram photo with a short caption, iOS first,
   rendered directly by Pillow at 1440 x 1800 without upscaling.
3. Transport flag: `FIONA_TELEGRAM_MEDIA_MODE=document|photo`.
4. Definite photo failure falls directly back to text. The chain
   photo -> document -> text is prohibited.
5. Unknown Telegram delivery is never automatically retried.
6. User-visible output locale is `en-US`.
7. Language flow is original source -> normalized facts/events -> English
   synthesis -> deterministic `en-US` validation.
8. Wave 1 does not add a separate translation API unless implementation proves
   it necessary and Product approves it.
9. Original source language, title, content, and provenance are preserved when
   supported.
10. Editorial coverage uses a dynamic 6:3:1 target: US/Europe 60%, Greater China
    30%, Rest of World 10%. Material events may override the target.
11. Future cadence is 00:00, 04:00, 08:00, 12:00, 16:00, and 20:00 UTC+8 using
    `Asia/Hong_Kong`.
12. Morning merges into 08:00, Evening into 20:00, and Daily into the 00:00
    Extended Edition. Weekly remains Sunday 21:00. Alert remains Material Change
    Only.
13. The 00:00 Extended Edition uses the new calendar date, reviews the just-ended
    market cycle/previous 24 hours, and defines Watch Next for the new cycle.
14. Every 4H edition is produced. If there is no material change, it states so
    explicitly, reduces density, and does not invent a narrative.
15. Dedicated 4H Intelligence State uses Railway Volume, atomic and versioned
    snapshots, and 14-day retention. PostgreSQL is deferred pending architecture
    review.

## 6. Frozen Feature Flags

| Flag | Values | Gate 0 purpose |
|---|---|---|
| `FIONA_TELEGRAM_MEDIA_MODE` | `document`, `photo` | Reversible Telegram transport |
| `FIONA_OUTPUT_LOCALE` | `zh-CN`, `en-US` | Reversible user-visible locale |
| `FIONA_COVERAGE_PROFILE` | `legacy`, `global_631` | Reversible source allocation |
| `FIONA_CADENCE_MODE` | `legacy`, `global_4h` | Reversible scheduler profile |
| `FIONA_4H_DELTA_MODE` | `off`, `shadow`, `on` | Reversible temporal delta |

Legacy behavior remains the default until each gate authorizes its replacement.

## 7. Technical Blockers

- Production-safe `sendPhoto` behavior, caption validation, and unknown-delivery
  handling must be proven before transport activation.
- Source identity, region, tier, independence, materiality, clustering, and
  coverage telemetry do not yet form one production contract.
- Six-slot scheduling requires collision-safe discovery, arbitration, catch-up,
  and rollback semantics.
- Atomic durable 4H state is required before Delta or global cadence activation.
- Deterministic `en-US` validation and provenance preservation are not yet wired
  through every user-visible output surface.

## 8. Deferred Technical Debt

- `app/wilson.py` has broad responsibilities but is outside the Gate 0 boundary.
- Source metadata and active source configuration are not yet one source of truth.
- Europe and Rest-of-World production coverage are not yet available.
- Ledger and memory durability depend on Railway filesystem configuration.
- 4H Delta state and material-change thresholds are not implemented.
- PostgreSQL, multi-instance redesign, Knowledge Graph, and unrelated refactors
  are explicitly deferred.

## 9. Files Created

- `docs/audits/FIONA_V3_1_GLOBAL_4H_TECHNICAL_AUDIT.md`
- `docs/v3_1/FIONA_V3_1_PRODUCT_FREEZE.md`
- `docs/v3_1/FIONA_V3_1_IMPLEMENTATION_ROADMAP.md`
- `docs/v3_1/FIONA_V3_1_RELEASE_STRATEGY.md`
- `docs/v3_1/gates/GATE_0_CLOSEOUT.md`

Direct documentation consistency corrections were made to `README.md`,
`docs/VERSION_MATRIX.md`, and `docs/changelog/CHANGELOG.md`.

## 10. Production Impact

- Production code changed: No.
- Railway configuration or service changed: No.
- Production variables changed: No.
- Telegram messages sent: No.
- Scheduler, runtime, ledger, arbitration, renderer, and delivery behavior
  changed: No.

## 11. Tests

- Repository identity: confirmed.
- Production baseline: V3.0.0 at `a8678b0`.
- Python compile under the project Python 3.12 runtime: PASS.
- Full unit suite: 206 tests PASS.
- Telegram calls: 0.
- Railway, Scheduler, runtime, environment variables, and production code: no
  changes during Gate 0.

## 12. Product Review Decision

Product Review accepts the technical audit with explicit conditions carried
into later gates: source-provider licensing/onboarding details, quantitative
material-change thresholds, isolated Telegram photo validation, durable state,
and per-gate rollback evidence.

**Verdict: PASS WITH CONDITIONS -> CLOSED.**

## 13. Next Gate

**Gate 1 - Native Telegram Photo + en-US.**

## 14. Gate 1 Entry Conditions

Gate 1 may begin only after explicit Wilson authorization. It must start with a
Previous Wave Retrospective, preserve legacy defaults, keep delivery changes
reversible, and pass isolated Telegram plus deterministic locale validation.

## 15. Closeout Verdict

**Gate 0: CLOSED.**
**Gate 1: NOT STARTED.**
**Production impact: NONE.**

Authoritative supporting documents:

- `docs/v3_1/FIONA_V3_1_PRODUCT_FREEZE.md`
- `docs/v3_1/FIONA_V3_1_IMPLEMENTATION_ROADMAP.md`
- `docs/v3_1/FIONA_V3_1_RELEASE_STRATEGY.md`
- `docs/audits/FIONA_V3_1_GLOBAL_4H_TECHNICAL_AUDIT.md`
