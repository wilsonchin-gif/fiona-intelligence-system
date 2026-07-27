# Fiona Market News Card Specification V1

- Version: V1.0
- Phase: Fiona V2 Phase 2A.1
- Status: Product Design Review
- Owner: Fiona Product / Design
- Updated: 2026-07-24
- Parent Standard: [Fiona Visual System V1](./FIONA_VISUAL_SYSTEM_V1.md)

## 1. Component Tree

```text
FionaMarketNewsCard
├── Header
│   ├── FionaWordmark
│   ├── ProductTitle
│   ├── GeneratedAt
│   └── DataQualityBadge
├── FionaView
│   ├── MarketState
│   ├── DominantDriver
│   ├── Judgment
│   └── NextConfirmation
├── MarketHeatMap
│   ├── USMarketTile
│   ├── ChinaMarketTile
│   ├── CryptoMarketTile
│   └── RWAMarketTile
├── WhatChanged
│   └── Observation × 0–3
│       ├── Category
│       ├── VerificationState
│       ├── WhatHappened
│       ├── WhyItMatters
│       └── WhatToWatch
├── KeyMarkets
│   ├── BTC
│   ├── SPX
│   ├── US10Y
│   ├── Gold
│   └── DynamicMarket
├── NarrativeContext
│   ├── Narrative × 0–2
│   └── TopicTag × 0–4
└── Footer
    ├── Disclaimer
    └── ProductSignature
```

## 2. Layout

Canvas: 1080×1350.

| Component | Y Range | Height | Grid |
| --- | ---: | ---: | --- |
| Header | 0–122 | 122 px | Full width |
| FionaView | 122–338 | 216 px | Full width |
| MarketHeatMap | 338–608 | 270 px | 2 columns × 2 rows |
| WhatChanged | 608–986 | 378 px | 1 column, up to 3 observations |
| KeyMarkets | 986–1162 | 176 px | 5 equal anchors |
| NarrativeContext | 1162–1270 | 108 px | 2 narratives + tags |
| Footer | 1270–1350 | 80 px | Full width |

Global layout requirements:

- Horizontal margin: 48 px.
- Section gap: 24–32 px.
- Card padding: 24–28 px.
- Card radius: 8 px.
- No nested decorative cards.
- Stable section dimensions in Full, Partial, and Degraded states.

## 3. Required Fields

### Header

| Field | Type | Required | Rule |
| --- | --- | --- | --- |
| `product_name` | Text | Yes | Always `Fiona Market News` |
| `generated_at` | Datetime | Yes | UTC+8 display |
| `data_quality` | Enum | Yes | Full / Partial / Degraded |

### FionaView

| Field | Type | Required | Rule |
| --- | --- | --- | --- |
| `market_state` | Text | Yes | One state only |
| `dominant_driver` | Text | Yes | One primary driver |
| `judgment` | Text | Yes | Evidence-aware, non-predictive |
| `next_confirmation` | Text | Yes | One observable condition |

### HeatMapTile

| Field | Type | Required | Missing behavior |
| --- | --- | --- | --- |
| `market` | Enum | Yes | Fixed slot |
| `score` | Integer 0–100 | Conditional | `—` |
| `direction` | Enum | Conditional | Awaiting |
| `key_metric` | Text | Conditional | Data unavailable |
| `risk_state` | Enum | Yes | Unknown |
| `freshness` | Datetime / State | Yes | Stale or unavailable state |

### Observation

| Field | Type | Required | Rule |
| --- | --- | --- | --- |
| `what_happened` | Text | Yes | Material change only |
| `why_it_matters` | Text | Yes | Impact on market understanding |
| `what_to_watch` | Text | Yes | Specific and verifiable |

### KeyMarket

| Field | Type | Required | Rule |
| --- | --- | --- | --- |
| `label` | Text | Yes | Short market name |
| `value` | Number / Text | Conditional | `—` when missing |
| `change` | Number | Conditional | Not shown as zero when missing |
| `freshness` | State | Yes | Current / Stale / Unavailable |

### Narrative

| Field | Type | Required | Rule |
| --- | --- | --- | --- |
| `name` | Text | Yes | Controlled narrative name |
| `direction` | Enum | Yes | Separate from Heat Map state |
| `confidence` | Integer 0–100 | Conditional | Hide when unsupported |

## 4. Optional Fields

| Component | Optional field | Display rule |
| --- | --- | --- |
| Header | `intelligence_value` | Only when data-supported |
| FionaView | `confidence` | Only when methodology is supported |
| HeatMapTile | `secondary_metric` | Not used in V1 default |
| Observation | `category` | Recommended |
| Observation | `verification_state` | Required for Partial/Developing evidence |
| Observation | `affected_assets` | Maximum three; Caption preferred |
| KeyMarket | `micro_trend` | Maximum one highlighted market |
| Narrative | `momentum` | Future extension |
| NarrativeContext | `tags` | Maximum four visible |

Optional fields must never create empty labels or decorative placeholders.

## 5. Character Limits

| Field | Ideal | Hard Maximum | Overflow action |
| --- | ---: | ---: | --- |
| Market state | 8 | 14 characters | Use controlled vocabulary |
| Dominant driver | 18 | 28 Chinese characters | Compress to one factor |
| Fiona judgment | 60–90 | 110 Chinese characters | Sentence-level summary |
| Next confirmation | 18–30 | 40 Chinese characters | Keep one condition |
| Heat key metric | 8–12 | 16 characters | Abbreviate units |
| What happened | 18–28 | 36 Chinese characters | Remove background detail |
| Why it matters | 24–36 | 48 Chinese characters | Keep causal explanation |
| What to watch | 18–30 | 40 Chinese characters | Keep verifiable condition |
| Narrative name | 6–12 | 16 Chinese characters | Controlled short name |
| Market label | 3–10 | 12 characters | Use standard abbreviation |
| Topic tag | 3–12 | 16 characters | Use canonical display name |

No component may reduce its font below the Visual System minimum to fit additional text.

## 6. Visual Priority

Priority 1:

- Fiona judgment
- Market state
- Heat Map scores

Priority 2:

- What Changed headlines
- Dominant driver
- Key market values

Priority 3:

- Why it matters
- What to watch
- Narrative context

Priority 4:

- Metadata
- Tags
- Disclaimer

Contrast must follow this order. Key Markets must not visually overpower Fiona's View or What Changed.

## 7. State Variants

### Full

- All four Heat Map tiles contain supported data.
- Data Quality badge: Full.
- Fiona judgment may use normal confidence language.

### Partial

- Missing tiles remain in their fixed positions.
- Data Quality badge: Partial.
- Affected observations are marked Developing / Partial or suppressed.
- Fiona judgment explicitly describes the evidence gap.

### Degraded

- Data Quality badge: Degraded.
- Unsupported score and direction values are not displayed.
- Fiona judgment becomes a data-status interpretation, not a market-direction conclusion.
- What Changed may collapse to a single status observation.

### Long Text

- Content is summarized before layout.
- Locked asset terms do not split.
- One ellipsis maximum.
- Extended detail moves to Telegram Caption.

## 8. Content Selection Rules

### Heat Map

- Exactly four fixed market slots.
- One score, one direction, one metric, one risk state per tile.

### What Changed

- Zero to three items.
- Select by intelligence value and material change.
- Do not fill empty capacity with low-value news.

### Key Markets

- Five items maximum.
- BTC, SPX, US10Y, and Gold are structural anchors.
- The fifth slot follows the dominant event or narrative.

### Narrative Context

- Two narratives maximum.
- Show direction and supported confidence.
- Four visible tags maximum.

## 9. Visual Semantics

### Market identity

Market identity appears as a small accent only:

- US: blue
- China: muted rose
- Crypto: gold
- RWA: teal

### Direction

Direction uses a shared semantic system:

- Bullish: muted positive
- Neutral: warm neutral
- Bearish: muted negative
- Unknown: data gray

### Risk

Risk is independent from direction:

- Low
- Medium
- High
- Unknown

No state relies on color alone.

## 10. Acceptance Criteria

The card passes product design review only when:

1. A user can identify market state and Fiona's View within five seconds.
2. All normal body text is readable on a phone without pinch zoom.
3. Missing market data never shifts, duplicates, or borrows another market's value.
4. No asset or institution name breaks mid-word.
5. Long text ends on a complete clause.
6. Fiona's View remains visually stronger than Key Markets.
7. Market identity color cannot be mistaken for market direction.
8. Full, Partial, and Degraded states preserve the same reading order.
9. The PNG remains 1080×1350 and below the agreed file-size target.
10. The card contains no prediction, trading instruction, or marketing language.
