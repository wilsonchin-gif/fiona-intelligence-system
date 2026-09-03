# Fiona iOS Visual QA

- Version: V3.1-alpha.1
- Status: Production and real-device acceptance PASS
- Updated: 2026-09-03

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

## Real-Device Acceptance

Wilson completed real iPhone Telegram acceptance on 2026-09-03 after production
activation of `photo + en-US`.

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

Gate 1 real-device acceptance is complete. Future presentation-layer changes
must repeat real-device QA; this result is not a blanket approval for later
layouts or delivery modes.
