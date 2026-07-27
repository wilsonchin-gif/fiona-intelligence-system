# Fiona Phase 2B Renderer Report

Version: V2 Phase 2B

Status: Local prototype, pending Wilson review

Updated: 2026-07-24

## Scope

Phase 2B implements an isolated Market News card renderer. It does not connect
the renderer to the production runtime, scheduler, Telegram delivery, or Alert
Engine.

## Architecture

```text
MarketNewsViewModel
        |
        v
app.fiona_card_renderer
        |
        +-- Header
        +-- Fiona View
        +-- Heat Map
        +-- What Changed
        +-- Key Markets
        +-- Narrative
        +-- Tags
        +-- Footer
        |
        v
1080 x 1350 RGB PNG
```

## Rendering Contract

- Engine: Python Pillow
- Canvas: 1080 x 1350 pixels
- Format: optimized RGB PNG
- Fonts: bundled Noto Sans SC Regular and Bold
- Languages: Chinese, English, and numeric market data
- Layout: fixed component regions with pixel-aware wrapping
- Overflow policy: complete semantic units first; no partial ASCII market terms
- Confidence: High, Medium, or Low
- Data confidence: Verified, Partial, or Limited

## Production Isolation

The renderer is not imported by:

- `app/fiona_runtime.py`
- `app/fiona_scheduler.py`
- `app/telegram_service.py`

No Railway command, scheduler behavior, Telegram behavior, or production
Market News output is changed in this phase.

## Prototype Scenarios

- Full data
- Missing upstream data
- Long Chinese and mixed-language text

Output directory:

`reports/prototypes/fiona_market_news_v2/`

## Review Gate

Production integration remains blocked until the visual prototypes and test
results are approved by Wilson.
