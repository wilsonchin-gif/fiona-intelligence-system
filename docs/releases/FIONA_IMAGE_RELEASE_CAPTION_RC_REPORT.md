# Fiona Image Release Caption RC Report

- Version: Fiona V2 Phase 2C Caption RC
- Status: Awaiting Product Review
- Owner: Fiona Intelligence Platform
- Updated: 2026-08-03

## Current Caption Problems

The previous caption compressed the full product into a generic four-hour summary. It repeated heat-map content, gave Fiona's View too little visual and semantic priority, omitted update time, Market Regime, Evidence, Watch Next, and the disclaimer, and could truncate text mechanically. It also provided no explicit uncertainty treatment for incomplete evidence.

## Optimization

- Reframed the caption as a conclusion layer while the image remains the evidence layer.
- Added UTC+8 timestamp, deterministic Market Regime, and deterministic Evidence.
- Limited What Changed to one or two event-plus-importance lines.
- Promoted Fiona's View to the central section with complete-sentence semantic compression.
- Added no more than three concrete Watch Next variables.
- Limited hashtags to eight and removed synonymous aliases.
- Added explicit Unknown, Limited Evidence, and no-high-confidence-narrative handling.
- Added a fixed one-line disclaimer and prohibited price-prediction, trading, and marketing language.

## Before / After

Before: market-state recap, one key-change title, short Fiona view, and tags. The reader still needed the image to understand confidence and what to monitor.

After: the first screen exposes Market Regime and Evidence, then one or two material changes, Fiona's decision layer, and three verifiable confirmation points. Detailed scores and prices stay in the card.

The complete eight-scenario comparison is generated locally at `reports/prototypes/fiona_market_news_caption_rc/caption_comparison.md` and remains excluded from Git.

## Test Result

- Caption RC tests: 12 passed
- Full unit test suite: 176 passed
- Compile check: passed for `app/` and `scripts/`
- No real Telegram message was sent

## Remaining Risks

- Caption judgment quality remains bounded by the quality and alignment of the existing ViewModel fields.
- Structural deduplication prevents data dumps but does not compute semantic similarity against every rendered sentence.
- The composer reuses card intelligence rules through a lazy import; a future shared intelligence module would reduce this coupling without changing behavior.
- Image Mode still requires explicit Product approval and a controlled Railway variable change after review.

## Image Mode Recommendation

Recommendation: **Conditional Go**. Caption RC is technically ready for Product review, but production must remain in `shadow` until Wilson accepts the eight samples and production observability confirms no regression. After approval, switch only `FIONA_MARKET_NEWS_MODE=image`, retain existing text fallback, and monitor the first scheduled Market News occurrence before broader acceptance.
