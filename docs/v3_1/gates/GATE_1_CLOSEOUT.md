# Fiona V3.1 Gate 1 Closeout

- Gate: 1
- Name: Native Telegram Photo + en-US
- Internal milestone: V3.1-alpha.1
- Final status: CLOSED
- Owner: Wilson / Fiona Engineering
- Closed: 2026-09-03
- Production source before closeout: `87d046884375fe0fc64fe8e35e009f04dad77c46`

## 1. Objective

Deliver a native, iOS-readable Telegram photo and a consistent American-English
presentation layer without changing Fiona's source coverage, scheduler,
occurrence ledger, routing, Alert thresholds, cadence, or Delta behavior.

## 2. Gate 0 Dependency

Gate 0 froze the V3.1 product boundary and established the V3.0 production
baseline. It required reversible feature flags, explicit Telegram delivery
states, deterministic language validation, real-device QA, and a separate
approval before each later Gate. Gate 0 was closed by commit `fd012c8` before
Gate 1 implementation began.

## 3. Gate 1 Journey

Gate 1 was completed in two bounded phases:

1. Commit `d0ea66931bdedf0cacbf3df451379ddbd327ea67` implemented native
   Telegram photo delivery and the `en-US` Market News path.
2. Commit `87d046884375fe0fc64fe8e35e009f04dad77c46` extended the same
   locale boundary to Morning, Evening, Daily, Weekly, Alert, missing-data
   states, and safe fallback text.

The second phase was necessary because the first implementation migrated the
primary Market News path but did not cover every production-reachable
user-visible surface.

## 4. Native Photo and Delivery Semantics

- `FIONA_TELEGRAM_MEDIA_MODE=photo` selects Telegram `sendPhoto`.
- A successful photo occurrence sends one photo and no duplicate text message.
- An explicit, definite photo failure permits one safe text fallback.
- An unknown Telegram delivery result is terminal for that occurrence: no
  automatic retry and no fallback that could create a duplicate.
- Delivery success requires a valid Telegram `message_id`.

## 5. Renderer

The production Market News artifact is rendered directly by Pillow at
1440 x 1800 pixels. It is not an enlarged 1080 x 1350 image. The renderer
preserves the approved Design System, safe margins, fixed typography, RGB PNG
validation, and bounded file size.

## 6. en-US Architecture

```text
Original-language source and provenance
  -> existing normalized event and product logic
  -> centralized OutputLocale boundary
  -> deterministic American-English presentation
  -> final CJK leakage guard
  -> Telegram payload
```

Original source language remains available internally. In `en-US` mode Fiona
does not silently expose Chinese or bilingual text. The failure sequence is
bounded: one known deterministic repair, one safe English projection, one safe
English fallback, then delivery failure if no safe output exists.

## 7. Gate 1.1 Language Completion

Gate 1.1 brought Market News, Morning, Evening, Daily, Weekly, Alert, generic
fallback, missing-data copy, headings, timestamps, severity labels,
confirmation language, Fiona's View, and disclaimers under one locale contract.
Alert thresholds and lifecycle semantics were not changed.

## 8. Production Validation

- Railway deployed commit `87d046884375fe0fc64fe8e35e009f04dad77c46`
  successfully with one running replica.
- Start command remained `python3 -m app.fiona_runtime --send run-scheduler`.
- Scheduler cycles remained `ok=true`, with `ledger_load_error=null` and no
  runtime errors.
- Native Market News photo delivery and Market News `en-US` were validated in
  production before Gate 1.1 closeout.
- Real Evening delivery succeeded with message ID `2422`.
- Three naturally occurring Alert deliveries succeeded with message IDs
  `2419`, `2420`, and `2421`.
- Real Morning delivery succeeded at the 2026-09-03 07:30 slot with message ID
  `2425`, one successful chunk, no fallback, no duplicate, and no errors.
- Daily and Weekly passed production-safe deterministic validation.
- Production CJK leakage acceptance passed.

## 9. Real iOS Acceptance

Wilson completed real iPhone Telegram acceptance on 2026-09-03:

| Check | Result |
|---|---|
| Native photo displayed inline | PASS |
| Attachment filename absent | PASS |
| Full card visible | PASS |
| Body readable | PASS |
| Fiona's View readable | PASS |
| No material clipping | PASS |
| English natural | PASS |
| Caption appropriately short | PASS |
| No visible duplicate | PASS |

## 10. Tests

- Gate 1 implementation suite: 234 tests PASS.
- Gate 1.1 focused suite: 43 tests PASS.
- Gate 1.1 complete suite: 277 tests PASS.
- Python compile: PASS.
- Production-safe surface validation: all six active surfaces report
  `cjk=false` and `all_user_surfaces_en_us=true`.
- Validation side effects: zero Telegram calls, ledger mutations, scheduler
  mutations, and formal occurrences.

## 11. Commits

| Commit | Purpose |
|---|---|
| `fd012c8` | Close Gate 0 product and technical audit |
| `d0ea66931bdedf0cacbf3df451379ddbd327ea67` | Implement native photo and Market News en-US |
| `87d046884375fe0fc64fe8e35e009f04dad77c46` | Complete all active en-US user-facing surfaces |

## 12. Railway Deployment History

Both Gate 1 implementation commits reached `main` through normal pushes and
Railway auto-deployment. The final Gate 1.1 production deployment was
`d80d7796-c9da-46e6-b988-02d70c7e98f7`, reported `SUCCESS`, ran source commit
`87d0468`, and remained healthy during natural scheduled occurrences.

## 13. Production Feature Flags

| Contract | Effective production state |
|---|---|
| Telegram media | `photo` |
| Output locale | `en-US` |
| Coverage | `legacy` default |
| Cadence | `legacy` default |
| 4H Delta | `off` default |

The code defaults remain reversible. Gate 1 did not activate global coverage,
global cadence, or Delta.

## 14. Rollback

The preferred code rollback is `git revert` of the relevant Gate 1 commit,
followed by normal Railway auto-deployment. Operational isolation can set media
to `document`; a severe language incident can temporarily set locale to
`zh-CN`. Neither rollback requires a scheduler or ledger migration.

## 15. Remaining Technical Debt

- Coverage remains the legacy source/ranking profile.
- Cadence remains the five existing scheduled products.
- 4H Delta and durable Delta state remain off.
- Upstream source provenance is incomplete for some events.
- Daily and Weekly have deterministic production-safe acceptance; their later
  natural occurrences should continue to be observed operationally.
- Historical reports and internal source provenance may retain original-language
  text by design.

## 16. Product and Engineering Retrospective

### What worked well

The feature-flag boundary, explicit Telegram outcome model, direct iOS renderer,
safe validators, precise commits, and natural-occurrence production checks made
the rollout reversible and observable.

### What did not work initially

Gate 1 localized the primary Market News path but treated it as representative
of the whole product. Production-reachable legacy Brief and Alert surfaces were
not included in the first language boundary.

### What Gate 1.1 revealed

A feature is not complete merely because its primary path is migrated. Future
locale and product changes must audit the entire user-visible surface matrix
before production activation.

### Mandatory process change

Every presentation-layer release must include a production surface inventory,
final-payload validation, missing/fallback coverage, and real-device QA. Real
iPhone QA remains mandatory for Telegram image and layout changes.

## 17. Product Lessons Learned

The strongest release evidence came from combining deterministic validation
with natural production occurrences and human client review. Automated tests
can prove contracts and prevent leakage; they cannot independently prove the
actual mobile reading experience.

## 18. Next Gate

The next planned Gate is **Gate 2 - Global Coverage Engine 6:3:1**. It requires
its own retrospective, repository gate, scope approval, implementation wave,
validation, and explicit Wilson authorization.

## 19. Final Declaration

**Gate 1 is CLOSED.**

**Gate 2 has NOT started.**

This closeout marks `V3.1-alpha.1` as **Production Validated**. It does not mark
Fiona V3.1 as GA and does not activate Global 6:3:1, Global 4H cadence, or 4H
Delta.
