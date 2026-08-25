# Fiona American English Output Standard

- Version: V3.1-alpha.1
- Status: Market News implemented; remaining products pending
- Updated: 2026-08-25

## Purpose

Define a deterministic American-English user layer without discarding original
source language or letting a model independently rewrite financial facts.

## Locale Contract

`FIONA_OUTPUT_LOCALE=zh-CN|en-US`

- Default and invalid fallback: `zh-CN`.
- Parsing: trim whitespace, case-insensitive.
- Internal timestamps remain ISO-8601.
- Market News display timestamp: `AUG 25 · 20:00 UTC+8`.

## Language Flow

```text
Original title/text/source metadata
  -> normalized Fiona event
  -> conservative intelligence projection
  -> centralized en-US string resources
  -> deterministic CJK leakage validation
```

Original title, text/snippet, source language, source URL, and source name stay
in provenance when current upstream structures provide them. Primary user
output is English. Gate 1 does not add an external translation API.

## Fiona Voice

- Calm, precise, professional, restrained, and analytical.
- Describe evidence, uncertainty, transmission, and confirmation variables.
- Do not predict price, recommend trades, manufacture urgency, or overstate
  incomplete evidence.
- Prefer natural American financial editorial language over literal translation.

## Canonical Terms

| Concept | Fiona term |
|---|---|
| Fiona judgment | `Fiona's View` / `Today's Judgment` |
| Market condition | `Market Regime` |
| Research support | `Evidence` |
| Material update | `What Changed` |
| Next observable variables | `Watch Next` |
| Prior-cycle reference | `Historical Context` |
| No meaningful update | `No material change.` |
| Missing evidence | `Data coverage limited` / `Data unavailable` |
| Disclaimer | `For informational purposes only. Not investment advice.` |

## Caption Standard

The native-photo caption contains:

1. `Fiona Global Intelligence`
2. concise UTC+8 timestamp
3. one market-state line
4. one Fiona judgment line
5. optional Watch Next line
6. up to four safe hashtags
7. minimal disclaimer

Target length is 180-450 visible characters. It must not repeat the full card,
contain report-style sections, broken markup, CJK text, or unapproved `4H`
language while the legacy cadence remains active.

## Leakage Rule

The primary Market News artifact rejects unexpected ideographs, Japanese
kana, CJK punctuation, and full-width forms in `en-US` mode. Source provenance
is not part of the primary artifact and can preserve original-language text.
Entity-name exceptions require an explicit product-approved allowlist; Gate 1
uses no automatic allowlist.

## Model Language Control

Current Gate 1 Market News projection is deterministic and does not call an LLM,
so no prompt change is applicable. Any future model-generated surface must
explicitly request American English, preserve facts separately, and pass the
same post-generation leakage boundary. A model may not independently determine
source verification or silently alter financial facts.

## Current Coverage

Implemented for Market News card, native caption, text fallback, missing-data
copy, timestamp, judgment, and disclaimer. Morning, Evening, Daily, Weekly, and
Alert remain Chinese-capable legacy products and require a controlled future
migration. V3.1-alpha.1 therefore does not claim `en-US` everywhere.
