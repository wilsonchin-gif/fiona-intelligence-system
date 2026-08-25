# Fiona V3.1 Product Freeze

Version: V3.1 Phase 0
Status: APPROVED - Gate 0 closed
Owner: Wilson
Technical owner: Codex
Updated: 2026-08-25

## 1. Product Identity

External product name:

**Fiona Global 4H Intelligence**

Fiona is an AI Market Intelligence Product. It is not a dashboard, a news bot,
or a trading signal service. Each edition must help the reader understand:

1. the current market state;
2. what materially changed;
3. why the change matters;
4. what evidence supports the judgment; and
5. what observable variable should confirm or challenge the judgment next.

Fiona does not provide price targets, deterministic forecasts, or trading
instructions.

## 2. Frozen Product Decisions

### P0-1: Telegram-Native Photo

- Delivery experience: `sendPhoto` with a short caption.
- Primary client: Telegram on iOS.
- Production image: 1440 x 1800 PNG, 4:5.
- The image is the product; the caption is a secondary summary.
- Important content must remain visible without attachment-style file chrome.
- The release must preserve duplicate protection and unknown-delivery handling.
- Automatic fallback is `photo -> text` for a definite failure.
- `photo -> document -> text` is prohibited.
- An unknown delivery state is not retried automatically.
- Existing unknown and partial-delivery protections remain mandatory.

### P0-2: American English

- Output locale: `en-US`.
- All user-visible card, caption, brief, alert, fallback, missing-data,
  disclaimer, hashtag, and safe-error copy must use American English.
- American spelling is required, including `analyze`, `behavior`, `center`,
  `color`, and `organization`.
- Original source language and original source text remain internal provenance
  whenever the collector provides them.
- An LLM instruction alone is not an acceptable language guarantee.
- Approved Wave 1 architecture:

```text
Original-language source
  -> normalized facts/events
  -> English intelligence synthesis
  -> deterministic en-US output validation
```

- Wave 1 does not introduce a separate translation API unless implementation
  proves it is technically necessary and Product approves it.

### P0-3: Dynamic Global Coverage 6:3:1

Long-run editorial target:

| Region | Target share |
|---|---:|
| US & Europe | 60% |
| Greater China | 30% |
| Rest of World | 10% |

This is a dynamic editorial target, not a hard quota. A material event overrides
regional allocation. The ranking layer must consider materiality, cross-market
impact, source quality, source independence, freshness, market relevance,
narrative relevance, and confirmation strength.

Region definitions:

- **US & Europe:** United States, Eurozone, United Kingdom, Switzerland, and
  materially relevant European markets.
- **Greater China:** Mainland China, Hong Kong, and Taiwan.
- **Rest of World:** Japan, Korea, India, Southeast Asia, Middle East,
  Australia/New Zealand, Latin America, Canada when separately classified, and
  other material markets.

### P0-4: Global 4H Cadence

All times are UTC+8.

| Time | Edition responsibility |
|---|---|
| 00:00 | Extended Global 4H Intelligence; absorbs Daily responsibilities |
| 04:00 | Global 4H Intelligence |
| 08:00 | Global 4H Intelligence; absorbs Morning responsibilities |
| 12:00 | Global 4H Intelligence |
| 16:00 | Global 4H Intelligence |
| 20:00 | Global 4H Intelligence; absorbs Evening responsibilities |
| Sunday 21:00 | Fiona Weekly remains separate |

Consolidation rules:

- Fiona Market News becomes six Global 4H Intelligence editions.
- Fiona Morning is removed as a separate notification and merged into 08:00.
- Fiona Evening is removed as a separate notification and merged into 20:00.
- Fiona Daily is removed as a separate notification and merged into the 00:00
  Extended Edition.
- Fiona Weekly remains.
- Fiona Alert remains available only for a material change.

There must be no separate Daily notification in addition to the 00:00 Extended
Edition.

The 00:00 Extended Edition is published under the new calendar date. It
primarily reviews the market cycle and previous 24 hours that have just ended,
then establishes Watch Next variables for the new cycle. It is not a separate
Daily Brief.

Every scheduled edition is produced even when there is no material change. In
that case Fiona must explicitly state **No material change** or equivalent
English language, must not invent a narrative, and may use reduced information
density to preserve continuity and comparability.

### P0-5: Deterministic 4H Delta

Each edition must answer: **What changed since the previous scheduled 4H
edition?**

Candidate comparison dimensions:

- Market Regime
- Evidence Level
- rates and the US dollar
- equities
- BTC and ETH
- commodities
- liquidity
- leading narrative
- primary driver
- Watch Next
- event materiality

The Delta layer must compare validated values from two edition snapshots. It
must not manufacture a delta when the prior baseline, timestamp, unit, or source
is unavailable. Scheduler ledger data is not an intelligence database.

Approved V3.1 storage:

- dedicated 4H Intelligence State;
- Railway Volume for the single production instance;
- atomic, versioned snapshots;
- 14-day retention;
- PostgreSQL is deferred until a future multi-instance architecture review.

## 3. Information Contract

Every edition follows judgment-first hierarchy:

1. Fiona's current judgment
2. What changed in the last 4 hours
3. Supporting evidence
4. Regional and market context
5. Next confirmation
6. Source/evidence confidence

The caption must not duplicate the full card. It should contain only the edition
identity, one concise judgment, the most material delta or next confirmation,
safe hashtags, and the disclaimer.

## 4. Evidence and Safety

- Fact, inference, scenario, and opinion remain distinct.
- Unverified causal claims must not be presented as facts.
- Missing inputs remain unavailable; they are not converted to zero.
- A material regional event may override 6:3:1 allocation.
- No source is counted as independent merely because the same syndicated story
  appears under multiple URLs.
- Alert delivery is not a substitute for the six scheduled editions.
- Output must remain informational and non-predictive.

## 5. Release Constraints

V3.1 is delivered through independent, reversible waves. No big-bang cutover is
allowed. New behavior must be protected by feature flags with legacy-safe
defaults, observability, fallback, and rollback procedures.

Frozen feature flags:

| Flag | Values |
|---|---|
| `FIONA_TELEGRAM_MEDIA_MODE` | `document`, `photo` |
| `FIONA_OUTPUT_LOCALE` | `zh-CN`, `en-US` |
| `FIONA_COVERAGE_PROFILE` | `legacy`, `global_631` |
| `FIONA_CADENCE_MODE` | `legacy`, `global_4h` |
| `FIONA_4H_DELTA_MODE` | `off`, `shadow`, `on` |

Every implementation wave must begin with a **Previous Wave Retrospective** and
end with a **Wave Completion Review**. No wave starts automatically after the
previous one. Wilson/Product Review is required between waves.

## 6. Non-Goals

V3.1 does not authorize:

- trading signals or price predictions;
- a dashboard or web portal;
- Knowledge Graph implementation;
- Academy implementation;
- a vector database;
- a full architecture rewrite;
- an unreviewed production source expansion;
- removal of the existing scheduler reliability, ledger, arbitration, or
  unknown-delivery controls.

## 7. Product Acceptance Summary

V3.1 is product-complete only when:

- Telegram receives a native photo rather than an attachment-style document;
- the card is a directly rendered 1440 x 1800 PNG and passes iOS visual QA;
- all user-facing output is deterministic `en-US`;
- regional coverage is measurable and trends toward 6:3:1 without suppressing
  material events;
- six UTC+8 editions run with durable idempotency and tested catch-up behavior;
- Morning, Evening, and Daily are consolidated exactly as frozen;
- every edition has an auditable 4H Delta or explicitly reports an unavailable
  baseline;
- Weekly remains compatible;
- Alerts remain restricted to material changes; and
- each wave has passed compile, full tests, focused tests, production-safe
  validation, documentation sync, and rollback review.

## 8. Gate 0 Product Review

Product Review verdict: **PASS WITH CONDITIONS -> CLOSED**.

Approved in Gate 0:

- native photo delivery, 1440 x 1800 direct Pillow rendering, and photo-to-text
  fallback;
- deterministic `en-US` user output with original-language provenance;
- dynamic 6:3:1 regional allocation after source expansion;
- six UTC+8 editions in `Asia/Hong_Kong`;
- Morning, Evening, and Daily consolidation;
- Sunday 21:00 Weekly and Material Change Only Alert;
- explicit no-material-change editions;
- dedicated Railway Volume state with 14-day retention; and
- the five reversible feature flags above.

Conditions carried into later Gates:

- source licensing and exact Tier 1/Tier 2 providers require approval before
  production integration;
- Alert material-change thresholds require their own product/technical review;
- every implementation Gate must pass its retrospective, test, documentation,
  release, and rollback checks.

Gate 1 implementation has not started.
