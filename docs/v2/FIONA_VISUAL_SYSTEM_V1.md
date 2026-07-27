# Fiona Visual System V1

- Version: V1.0
- Phase: Fiona V2 Phase 2A.1
- Status: Product Design Review
- Product: Fiona Intelligence System
- Owner: Fiona Product / Design
- Updated: 2026-07-24

## 1. Brand Philosophy

Fiona is an AI Market Intelligence Officer. She helps users understand what happened, why it matters, what to watch, and how the current market state should be interpreted.

Fiona should feel:

- Warm: calm human language, never cold data dumping.
- Calm: no alarmist composition, flashing colors, or exaggerated claims.
- Professional: evidence first, clear hierarchy, disciplined terminology.
- Restrained: fewer elements, fewer colors, fewer conclusions.
- Trustworthy: missing and uncertain data are visible, never silently substituted.
- Information-dense: every visible element must improve understanding.

Fiona is not a news robot, price ticker, trading signal, casino interface, marketing poster, or TradingView screenshot.

The closest reference family is Bloomberg Terminal, Glassnode, Kaiko, Messari Research, and institutional research reports. Fiona borrows their discipline and density, but adds a warmer editorial voice through Fiona's View.

## 2. Design Principles

### 2.1 Judgment before inventory

The card should not begin with a list of everything available. It should begin with the current state and Fiona's judgment.

### 2.2 One card, one market state

Every card communicates one coherent reading of the current period. Conflicting signals are explained, not hidden.

### 2.3 Evidence has visible status

Full, Partial, Degraded, Stale, and Unavailable are first-class visual states. Missing data must never be converted into zero, Neutral, or a neighboring market's value.

### 2.4 Color is semantic

Market identity colors and market direction colors are separate systems. China red does not mean Bearish; RWA green does not mean Bullish.

### 2.5 Mobile size is the source of truth

The 1080×1350 source is designed for a phone, not merely scaled down from a desktop dashboard. Information is removed before typography is reduced.

### 2.6 Calm density

Dense information is acceptable when hierarchy is strong. Crowding, repeated labels, and equal visual emphasis are not.

## 3. Information Hierarchy

The first five seconds must answer:

1. What is the current market state?
2. What is the largest influencing factor?
3. What does Fiona think it means?

The next five seconds must answer:

1. Which markets confirm or contradict the judgment?
2. What changed during the latest period?
3. Is deeper reading worthwhile?

Reading order:

```text
Brand / Time / Data Quality
    ↓
Fiona's View
    ↓
Market Heat Map
    ↓
What Changed
    ↓
Key Markets
    ↓
Narrative / Tags
    ↓
Disclaimer
```

Fiona's View moves above the Heat Map because it is the product's interpretation layer. The Heat Map then provides evidence for that judgment.

## 4. Card Layout

Canvas: 1080×1350, portrait 4:5.

| Region | Y Range | Height | Share | Content | Purpose |
| --- | ---: | ---: | ---: | --- | --- |
| Header | 0–122 | 122 px | 9% | Fiona wordmark, title, timestamp, data quality | Establish identity, freshness, and trust |
| Fiona's View | 122–338 | 216 px | 16% | Market state, dominant driver, Fiona judgment | Deliver the five-second answer |
| Market Heat Map | 338–608 | 270 px | 20% | US, China, Crypto, RWA in a 2×2 heat map | Show cross-market confirmation |
| What Changed | 608–986 | 378 px | 28% | Up to three research observations | Explain material changes |
| Key Markets | 986–1162 | 176 px | 13% | Five market anchors | Supply compact verification data |
| Narrative / Tags | 1162–1270 | 108 px | 8% | Up to two narratives and four visible tags | Connect current context to future knowledge |
| Footer | 1270–1350 | 80 px | 6% | Disclaimer and product signature | Close with compliance and identity |

Layout rules:

- Outer horizontal margin: 48 px.
- No card may sit inside another decorative card.
- Section titles align to one left edge.
- The Header and Footer are unframed.
- Fiona's View receives the strongest non-numeric emphasis.
- Key Markets must not use bright white cards that dominate the page.

## 5. Fiona View Specification

### Position

Immediately below the Header.

Why:

- The product differentiator is interpretation, not data collection.
- Telegram users should understand Fiona's judgment before deciding to inspect supporting data.
- Placing it near the top makes the card useful even when viewed as a small preview.

### Structure

1. Market State: one short label, such as `Neutral / Fragmented`.
2. Dominant Driver: one concise factor.
3. Fiona's View: one evidence-aware judgment.
4. Next Confirmation: one observable condition.

Example:

> 资金仍未形成一致方向。宏观利率压制风险偏好，但 RWA 保持相对稳定。下一轮等待 ETF 流向与美元走势是否形成同向确认。

### Text limits

- Ideal: 60–90 Chinese characters.
- Hard maximum: 110 Chinese characters.
- Maximum: three lines of body text.
- One judgment only.
- One confirmation condition only.

### Expression rules

Allowed:

- Current state
- Observed driver
- Conditional interpretation
- Verifiable confirmation point

Forbidden:

- Price predictions
- Trading advice
- Target prices
- Guaranteed outcomes
- Emotional urgency

### Visual emphasis

- Dark elevated surface with restrained Fiona Gold accent.
- Market state label: 22–24 px.
- Main judgment: 26–28 px.
- No robot icon, speech bubble, or cartoon treatment.

## 6. Heat Map Specification

The Heat Map is a 2×2 matrix, not a horizontal table.

Fixed order:

```text
US       China
Crypto   RWA
```

Each market tile contains:

1. Market name
2. Score, 0–100
3. Direction: Bullish / Neutral / Bearish
4. One key metric
5. Risk state: Low / Medium / High / Unknown

### Heat behavior

- All tiles use the same neutral base surface.
- Direction applies a low-opacity color wash.
- Color intensity increases with the distance of the score from 50.
- Score remains the primary quantitative signal.
- Risk state is independent from direction.

### Color separation

Market identity accents:

- US: Fiona Blue
- China: Muted Rose
- Crypto: Fiona Gold
- RWA: Institutional Teal

Direction colors:

- Bullish: Muted Positive
- Neutral: Warm Neutral
- Bearish: Muted Negative
- Unknown: Data Gray

Market identity appears only as a small label marker or 4 px edge. It must never determine the tile's direction color.

### Missing state

```text
Score: —
Direction: Awaiting
Key metric: Data unavailable
Risk: Unknown
```

The tile remains in its original position.

## 7. What Changed Specification

What Changed is a research observation component, not a news list.

Maximum: three observations.

Each observation contains:

1. What happened
2. Why it matters
3. What to watch
4. Optional category
5. Optional verification state

Recommended format:

```text
MACRO · CONFIRMED
美债收益率抬升，科技与加密风险偏好同步降温
Why: 利率重新定价正在影响高估值资产
Watch: 美元与美债是否继续同向上行
```

Rules:

- Rank by intelligence value, not recency alone.
- Do not show ranking numbers unless the items are explicitly ranked.
- Do not repeat the same event in different words.
- If only one event is material, show one event.
- If nothing changed, show one calm empty state: `暂无新增高价值变化。`
- Events dependent on missing sources must be suppressed or marked `Developing / Partial`.

## 8. Key Markets Specification

V1 displays a maximum of five market anchors.

Four structural anchors:

1. BTC — Crypto risk appetite
2. S&P 500 — US risk assets
3. US10Y — Macro liquidity
4. Gold — Defensive demand

One dynamic slot:

- ETH
- Nasdaq
- HSI / CSI500
- RWA TVL
- DXY

The dynamic asset is selected by the highest-value current event or narrative.

Each item contains:

- Symbol or short label
- Current value
- Period change
- Freshness state when not current

Rules:

- No more than five items.
- No unnecessary decimals.
- Missing assets keep their intended meaning; they are not replaced by unrelated values.
- Key Markets is supporting evidence and must have lower visual contrast than Fiona's View.

## 9. Typography

Primary CJK family:

- Noto Sans CJK SC
- PingFang SC as local fallback

Primary Latin and figures:

- Inter
- Helvetica Neue as fallback

| Role | Size | Weight | Line Height |
| --- | ---: | ---: | ---: |
| Product title | 44–48 px | 700 | 1.10 |
| Section title | 22–24 px | 700 | 1.20 |
| Fiona View state | 22–24 px | 600 | 1.25 |
| Fiona View body | 26–28 px | 600 | 1.35 |
| Event headline | 24–26 px | 600–700 | 1.30 |
| Body / Why / Watch | 22–24 px | 400–600 | 1.35 |
| Core score | 40–48 px | 700 | 1.00 |
| Key market value | 30–36 px | 700 | 1.10 |
| Labels / metadata | 20–22 px | 500–600 | 1.25 |
| Disclaimer | 16–18 px | 400 | 1.30 |

Rules:

- No informational body text below 20 px.
- Do not reduce type size to solve overflow.
- Use at most three font weights per card.
- Letter spacing is 0 for body text.
- English asset names must not split across lines.

## 10. Color System

### Core palette

| Token | Value | Use |
| --- | --- | --- |
| Fiona Background | `#08131F` | Page background |
| Fiona Surface | `#101F2B` | Standard sections |
| Fiona Elevated | `#162836` | Fiona's View and high-priority surfaces |
| Fiona Border | `#294154` | Dividers and card edges |
| Primary Text | `#F4F7F9` | Titles and core content |
| Secondary Text | `#A9B7C2` | Explanation |
| Muted Text | `#718594` | Metadata |
| Fiona Gold | `#D8AD4A` | Brand and controlled emphasis |
| Positive | `#4FA989` | Bullish / improving |
| Negative | `#C96A72` | Bearish / deteriorating |
| Neutral | `#B59B63` | Neutral / waiting |
| Risk | `#D08A5B` | Elevated risk |
| Data Gray | `#687C8C` | Missing / stale / unknown |

### Market identity accents

| Market | Accent |
| --- | --- |
| US | `#5B8FD9` |
| China | `#C9787E` |
| Crypto | `#D8AD4A` |
| RWA | `#4D9A7F` |

Color rules:

- Avoid saturated red and green backgrounds.
- Never communicate direction using color alone; always include a text label.
- Target at least 4.5:1 contrast for normal informational text.
- White surfaces are not used as large blocks on the dark card.

## 11. Spacing System

Base unit: 8 px.

| Token | Value |
| --- | ---: |
| Outer margin | 48 px |
| Section gap | 24–32 px |
| Card gap | 16–20 px |
| Card padding | 24–28 px |
| Title-to-body gap | 12–16 px |
| Body line gap | 8–12 px |
| Divider inset | 24 px |
| Corner radius | 8 px |

Rules:

- Use whitespace to separate ideas, not extra borders.
- Keep stable card dimensions across full and missing states.
- Do not nest visual cards.
- Horizontal alignment must be shared across all sections.

## 12. Brand Identity

### Logo

V1 uses a text wordmark: `FIONA`.

A complex logo is not required. A future monogram may be explored, but the wordmark remains the primary identity.

### Telegram avatar

Recommended:

- Deep navy background
- Fiona Gold `F` or `FIONA`
- No face, robot, mascot, candlestick, coin, or chart arrow

### Signature

`Fiona's View` is the permanent editorial signature.

### AI identity

Use `AI Market Intelligence Officer` as quiet metadata. Do not make “AI” the dominant headline; the product should be trusted for its judgment, not promoted as a novelty.

## 13. Data Density Rules

| Component | Maximum |
| --- | ---: |
| Core judgment | 1 |
| Heat Map markets | 4 |
| Key metric per market | 1 |
| What Changed observations | 3 |
| Key Markets | 5 |
| Current Narratives | 2 |
| Visible card tags | 4 |
| Telegram caption tags | 8 |
| Fiona View confirmation points | 1 |

Additional rules:

- No Top Gainers / Top Losers in the Market News card.
- No more than one percentage and one absolute value per market item.
- Do not repeat the same number in Heat Map and Key Markets unless it is essential to the judgment.
- When limits are exceeded, move detail to the Caption or future Knowledge layer.

## 14. Missing Data Rules

Missing data is a trust state, not an empty decoration.

### Display states

- `Awaiting update`: expected source has not returned.
- `Data unavailable`: source failed or returned no usable data.
- `Stale · HH:mm`: value exists but is outside freshness policy.
- `Partial`: some required sources are unavailable.
- `Degraded`: the card cannot support a normal-strength judgment.

### Rules

- Preserve the market's fixed position.
- Display `—`, never `0`.
- Do not classify missing data as Neutral.
- Do not copy data from another market or positional fallback.
- Do not hide the card without explaining the gap.
- Reduce judgment confidence when material sources are missing.
- Mark affected observations `Developing / Partial`, or suppress them.
- Place the overall data quality state in the Header.

## 15. Long Text Rules

Overflow is solved by editorial compression, not smaller fonts.

### Character limits

| Field | Ideal | Hard Maximum |
| --- | ---: | ---: |
| Fiona View | 60–90 | 110 Chinese characters |
| What happened | 18–28 | 36 Chinese characters |
| Why it matters | 24–36 | 48 Chinese characters |
| What to watch | 18–30 | 40 Chinese characters |
| Narrative name | 6–12 | 16 Chinese characters |
| Key metric label | 6–12 | 16 characters |

### Truncation policy

1. Remove repetition and background detail.
2. Keep the conclusion, evidence, and next confirmation.
3. Truncate at sentence or clause boundaries.
4. Preserve locked terms such as `RWA`, `BTC ETF`, `US10Y`, and institution names.
5. Use a single ellipsis only when unavoidable.
6. Move extended detail to the Telegram Caption.

Forbidden:

- Mid-word breaks such as `R / WA`
- Multiple ellipses
- Incomplete conclusions
- Font shrinking
- Hidden overflow

## 16. Telegram Adaptation

Output:

- Canvas: 1080×1350
- Ratio: 4:5
- Format: PNG
- Target file size: below 1.5 MB
- Delivery target: `sendDocument + caption`

Telegram reading order:

1. Caption: 5–20 second summary
2. Image preview: title, Fiona's View, market state
3. Opened image: full supporting structure
4. Hashtags: future topic retrieval

Caption guidance:

- Ideal: 120–220 Chinese characters
- Hard maximum: 280 Chinese characters
- Maximum eight hashtags

Phase 2B device validation must include:

- Telegram iOS
- Telegram Android
- Document thumbnail
- Opened full image
- Light and dark chat themes
- No pinch zoom required for normal body reading

The card is not production-ready until the full, missing, and long-text states all pass mobile validation.
