# Fiona American English Output Standard

- Version: V3.1-alpha.1.1
- Status: All active Telegram presentation surfaces implemented; production observation pending
- Updated: 2026-09-02

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
output is English. Gate 1.1 does not add an external translation API.

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
| Morning context | `Overnight Market` / `Today's Watch` |
| Evening context | `Tonight's Focus` / `Night Risk Radar` |
| Event significance | `Why It Matters` |
| Alert impact | `Affected Assets` / `Fiona Assessment` |
| Confirmation variable | `Next Confirmation` |
| Severity S / A / B / C | `Critical` / `High` / `Moderate` / `Low` |

All active products consume this shared terminology through
`app/fiona_locale.py`. Individual brief builders may compose different
sentences, but they do not invent competing translations for shared concepts.

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

Every active Telegram text payload and the primary Market News artifact reject
unexpected ideographs, Japanese kana, CJK punctuation, and full-width forms in
`en-US` mode. Source provenance is not part of the primary artifact and can
preserve original-language text. Entity-name exceptions require an explicit
product-approved allowlist; Gate 1.1 uses no automatic allowlist.

Failure handling is bounded: known deterministic labels are repaired once,
then the existing category-aware English synthesis is used, then one safe
English fallback is allowed. If that fallback is unsafe, delivery fails. Fiona
does not silently send mixed-language content and does not enter an unbounded
regeneration loop.

## Model Language Control

Current Gate 1.1 presentation is deterministic and does not call an LLM, so no
prompt change is applicable. Any future model-generated surface must
explicitly request American English, preserve facts separately, and pass the
same post-generation leakage boundary. A model may not independently determine
source verification or silently alter financial facts.

## Current Coverage

Implemented for Market News card, native caption, Morning, Evening, Daily,
Weekly, Alert, text fallback, missing-data copy, timestamp, judgment,
confirmation language, and disclaimer. The default remains `zh-CN`; when
`FIONA_OUTPUT_LOCALE=en-US`, every active Telegram presentation surface uses
the same final language guard.

Historical documents, internal logs, source-provenance fields, and inactive
legacy report generators are outside the production user-surface contract and
may retain their original language.
