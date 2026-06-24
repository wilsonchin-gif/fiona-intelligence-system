# Fiona Intelligence System V1.0 - Phase 3

Phase 3 adds scheduled brief generation. It is still independent from the live Telegram scheduler.

## Module

- `app/fiona_briefing.py`
  - Defines Fiona brief types and schedule contracts.
  - Builds Fiona Morning, Evening, Market News, Daily, and Weekly text.
  - Uses Fiona events, narrative records, and optional market snapshots.
  - Keeps Morning and Evening concise, within 300 Chinese characters for the brief body.
  - Preserves the user perspective layer:
    - what happened
    - why it matters
    - who is affected
    - what to watch next

## Schedule Contract

- Fiona Morning: 07:30
- Fiona Evening: 20:30
- Fiona Market News: 00:00
- Fiona Daily: 22:30
- Fiona Weekly: Sunday 21:00

## Current Runtime Status

Phase 3 is intentionally not wired into the live scheduled Telegram task yet.

The existing scheduled task remains active and currently sends text-only Wilson summaries:

```text
WILSON_SEND=1
WILSON_SEND_IMAGES=0
```

## Tests

```bash
python3 -m unittest discover -s tests -p 'test*.py'
```
