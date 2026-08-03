# Fiona Market News Caption System V1

- Version: V1.0 RC
- Status: Product Review
- Owner: Fiona Intelligence Platform
- Updated: 2026-08-03

## 1. Product Goal

Caption V1 lets a Telegram reader understand Fiona's current market judgment in 5–15 seconds. Fiona remains an AI Market Intelligence Officer: calm, evidence-aware, and explicit about uncertainty. The caption does not predict prices, recommend trades, or invent causes.

## 2. Caption Role

The image owns dense evidence, structured market data, and visual comparison. The caption owns the conclusion: current state, one or two material changes, Fiona's judgment, verifiable next checks, and topic entry points. It must not become a text copy of the card.

## 3. Caption Structure

1. Product name and UTC+8 update time
2. `Market Regime` and deterministic `Evidence`
3. `What Changed`, limited to one or two material changes
4. `Fiona’s View`, the primary decision layer
5. `Watch Next`, limited to three verifiable variables
6. Five to eight relevant hashtags
7. One-line disclaimer

## 4. Information Priority

The compression and product priority is: Fiona's View, Market Regime, material change, Watch Next, Evidence, hashtags, disclaimer. The view and regime must survive every compression pass. Lower-priority repetition is removed before Fiona's judgment is shortened.

## 5. Length Rules

- Chinese body target: 180–380 CJK characters
- Ideal range: 220–320 CJK characters
- Total caption safety limit: 760 characters
- Telegram's transport limit is not used as the product target; safety margin is intentional.
- Compression removes duplicated numbers, secondary changes, excess watch items, and excess tags in that order.
- Compression only keeps complete sentences or clauses. It does not cut asset codes, hashtags, or markup mid-token.

## 6. Market Regime Rules

Supported values are `Risk On`, `Risk Off`, `Neutral`, `Transition`, and `Unknown`. The caption reuses the deterministic rule in the card intelligence layer. Fewer than three valid market cards produces `Unknown`, followed by an explicit statement that no directional judgment is being formed.

## 7. Evidence Rules

Supported values are `Verified`, `Strong`, `Moderate`, and `Limited`. Evidence is derived from source count, core-field completeness, and critical missing fields. It is never random and is not selected by an LLM. `Limited` suppresses unverified causal language and forces a lower-certainty Fiona's View.

## 8. Fiona’s View Rules

Fiona's View uses one to three complete sentences, ideally 70–140 CJK characters. It states the current judgment, the evidence or driver behind it, and the variable that can confirm or invalidate it. It must not repeat the regime label as prose, use empty caution, issue a trade instruction, or claim a future price.

## 9. What Changed Compression

The caption keeps at most two changes. Each line combines the event and why it matters. The event-specific watch clause is removed from this section and consolidated under Watch Next. With Limited evidence, causal explanations are replaced by a statement that market impact still requires confirmation.

## 10. Watch Next Rules

Watch Next contains at most three observable and verifiable variables directly linked to Fiona's View. Generic entries such as “关注市场变化” are rejected. Unknown or Limited states prioritize data-coverage recovery. Absence of a high-confidence narrative adds a concrete narrative-confirmation check.

## 11. Hashtag Rules

Caption V1 selects at most eight hashtags in this order: core assets, narratives, institutions or policy, risks, and market categories. Canonical alias groups prevent pairs such as `#Bitcoin` / `#BTC`, `#FederalReserve` / `#Fed`, and `#Markets` / `#MarketSnapshot`. Internal tags remain separate from Telegram presentation tags.

## 12. Missing Data Rules

Missing data never produces placeholder prices or fabricated direction. If market coverage is inadequate, the regime is `Unknown`. If sources or core fields are inadequate, Evidence is `Limited`. The caption then states that evidence is insufficient, keeps an observation posture, and names the next data confirmation needed.

## 13. De-duplication Rules

Caption and image overlap is controlled structurally rather than by brittle word matching. Allowed overlap is limited to product name, update time, Market Regime, Fiona's core conclusion, Watch Next, tags, and disclaimer. The caption must not list all four heat-map cards, all Key Markets values, every narrative, or complete What/Why/Watch triplets. Tests enforce the absence of score dumps, key-market dumps, and duplicated event watch clauses.

## 14. Language Style

Chinese is primary, with standard finance terms such as `Market Regime`, `Evidence`, `ETF`, `US10Y`, `DXY`, `RWA`, `BTC`, and `ETH` retained when clearer. Marketing exaggeration, self-congratulation, price certainty, and trading instructions are prohibited. Fiona's tone is warm, calm, professional, restrained, and honest about uncertainty.

## 15. Disclaimer

The fixed caption disclaimer is: `本内容仅供参考，不构成任何投资建议。` The image may retain a longer risk statement; the caption does not repeat it.

## 16. Test Coverage

The RC suite covers full, missing, long-text, Risk On, Risk Off, Transition, Unknown, Limited Evidence, and no-high-confidence-narrative scenarios. It also checks length, complete-sentence compression, structure integrity, Fiona's View presence, Watch Next limits, hashtag limits and alias deduplication, data/image deduplication, absent fabricated numbers, prohibited language, and the disclaimer. Existing delivery tests continue to cover text, shadow, image, fallback, renderer, scheduler, and the other four briefs.

## 17. Release Criteria

Caption V1 can proceed to Image Mode review only when all tests pass, eight RC samples are accepted by Product, Shadow remains healthy, no real image send occurs during review, and no scheduler, ledger, renderer layout, Telegram transport, Railway variable, or non-Market-News brief behavior changes.
