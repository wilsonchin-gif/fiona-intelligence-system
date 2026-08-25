# Fiona iOS Visual QA

- Version: V3.1-alpha.1
- Status: Automated and desktop review complete; real-device review pending
- Updated: 2026-08-25

## Test Artifacts

Generated locally under `reports/prototypes/fiona_v3_1_gate1/` and excluded from
Git:

- `market_news_gate1_full_1440x1800.png`
- `market_news_gate1_missing_1440x1800.png`
- `market_news_gate1_stress_1440x1800.png`
- matching V3.0 1080 x 1350 comparison cards
- 390 x 488 scaled preview simulations for Full, Missing, and Stress

Production rendering remains native 1440 x 1800. The 390 x 488 artifacts are QA
simulations only and are never sent to Telegram.

## Automated Checks

| Check | Result |
|---|---|
| Native size and 4:5 ratio | PASS |
| Direct render; resize interception | PASS |
| RGB PNG decode | PASS |
| File size below 1.5 MB | PASS |
| Outer safe margin >= 72 px | PASS |
| Top/bottom safe area >= 48 px | PASS |
| Minimum token text >= 17 px | PASS |
| Full/Missing/Stress render | PASS |
| V3.1 PNG bytes | 264,753 / 260,912 / 241,607 |
| Caption characters | 389 / 387 / 353 |
| Fixed typography under stress | PASS |
| CJK leakage in English card/caption | PASS |
| Telegram calls during QA | 0 |
| Ledger mutations during QA | 0 |

## Product Review

### Three-second read

Market Regime and Fiona's View remain above supporting evidence. The judgment
hero is still the visual center and is not placed at a crop-sensitive edge.

### Ten-second read

The primary driver, next confirmation, evidence level, and material changes can
be scanned without reading dense market values.

### Thirty-second read

Heat Map, Key Markets, Narrative Context, Watch Next, and Historical Context
complete the intelligence chain while preserving the V3 information density.

### Missing and stress behavior

Missing data uses explicit English states and does not invent zeroes. Long text
is semantically clipped; type does not shrink and component regions remain
fixed.

## Remaining Device Gate

No real iPhone Telegram client was used in this implementation run. Before
activating `photo + en-US`, an isolated Telegram validation chat must confirm:

- Telegram server processing does not produce unacceptable softness;
- iPhone feed preview preserves judgment readability and safe edges;
- opened-image zoom is crisp;
- caption truncation and line breaks are acceptable;
- one actual message ID is returned and no duplicate fallback is produced.

The Gate 1 verdict is therefore `PASS WITH CONDITIONS`, not an unconditional
real-device acceptance.
