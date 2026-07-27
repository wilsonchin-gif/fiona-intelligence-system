# Fiona Phase 2B.5 Product Refinement

- Version: V2 Phase 2B.5
- Status: Local prototype, pending Wilson review
- Owner: Fiona Product / Engineering
- Updated: 2026-07-26
- Scope: Market News Intelligence Card only

## 1. Product Positioning

Fiona is an AI Market Intelligence Officer. The card is designed to help a
reader understand the current market state, why it matters, Fiona's current
judgment, and the next observable variables. It does not provide trading
signals, price predictions, or investment advice.

## 2. New Components

### Market Regime

Supported states:

- Risk On
- Risk Off
- Neutral
- Transition
- Unknown

The state is derived deterministically from available Heat Map scores and
directions. Fewer than three valid markets produces `Unknown`. Mixed
Bullish/Bearish evidence or a wide score spread produces `Transition`.

### Evidence Level

Supported levels:

- Verified
- Strong
- Moderate
- Limited

The level uses:

1. Unique source identifiers attached to the current events or snapshot.
2. Coverage across four Heat Map fields and five Key Market fields.
3. Missing critical indicators: US Market, Crypto Market, BTC, SPX, and US10Y.

No random values or inferred source counts are used.

### Watch Next

Up to three deduplicated, observable variables are selected from current
event watch conditions. Long conditions are normalized into compact,
verifiable labels such as:

- US10Y / DXY direction
- ETF Flow / Stablecoin supply
- RWA TVL / Usage

These are observation variables, not forecasts or recommendations.

### Historical Context

Phase 2B.5 uses a clearly labeled rule-based reference. Supported starting
patterns include:

- Liquidity: previous liquidity tightening cycle
- ETF Flow: previous ETF inflow period
- Rates: historical Fed tightening phase
- RWA: previous institutional adoption phase

The card explicitly states that a historical reference does not mean the same
scenario will repeat.

## 3. Design Principles

- Interpretation precedes data inventory.
- Evidence quality is visible and deterministic.
- Missing data reduces certainty instead of creating a synthetic conclusion.
- Typography remains fixed; content is selected and cropped before layout.
- Market identity color remains separate from market direction color.
- Historical context is a reference, not a prediction.

## 4. Generation Rules

```text
MarketNewsViewModel
    ├── Heat Map ───────────────> Market Regime
    ├── Source IDs
    ├── Missing core fields ────> Evidence Level
    ├── Event watch conditions ─> Watch Next
    └── Events / tags / narrative
                                 └> Historical Context
```

All four derivations are deterministic pure functions in the renderer module.
The production runtime does not import or execute them in this phase.

## 5. Information Priority Audit

### Three-second layer

- Market Regime is immediately below the Header.
- Evidence Level is visible beside the title.
- Fiona's View remains the largest interpretation block.

Result: the reader can identify the state, evidence quality, and Fiona's
judgment without reading the data grid.

### Ten-second layer

- Dominant Driver explains why the state matters.
- What Changed is limited to two material observations.
- Watch Next exposes up to three concrete verification variables.

Result: the reader understands the cause and the next confirmation points
without processing every market value.

### Thirty-second layer

- Heat Map shows cross-market confirmation or divergence.
- Key Markets provide five structural anchors.
- Narrative Context and Historical Context connect the snapshot to a broader
  market pattern.

Result: deeper reading adds context without changing the top-level judgment.

## 6. Data Density Audit

- Canvas remains fixed at 1080 x 1350.
- No component reduces font size dynamically.
- Fiona's View is capped at two lines.
- What Changed is capped at two observations.
- Key Markets remains capped at five anchors.
- Narrative Context is capped at two narratives.
- Watch Next is capped at three compact variables.
- Historical Context is capped at one rule-based reference.
- Visible tags are capped at three.
- Pixel-aware wrapping preserves compound market terms.
- Semantic cropping prefers complete clauses and uses at most one ellipsis.
- Component regions are validated for overlap and canvas overflow before
  rendering.

## 7. Knowledge Graph Integration

`HistoricalContextAssessment` provides a small future-facing interface:

- `topic`
- `reference`

The rule engine can later be replaced by Knowledge Graph retrieval without
changing the visual component contract. No database is introduced in this
phase.

## 8. Reuse Across Briefs

- Morning can reuse Market Regime and Watch Next for pre-market orientation.
- Daily can reuse Evidence Level and Historical Context for the daily judgment.
- Weekly can reuse Historical Context as an entry point to longer narrative
  timelines.

Reuse is a product direction only. Morning, Daily, and Weekly are not modified
in Phase 2B.5.

## 9. Production Isolation

This phase does not modify or connect:

- Scheduler
- Runtime
- Telegram delivery
- Ledger
- Arbitration
- Morning
- Evening
- Daily
- Weekly
- Alert Engine
- Railway configuration

Production integration remains blocked pending Wilson review.
