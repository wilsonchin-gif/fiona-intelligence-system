# Fiona Intelligence System V1.0 - Phase 2

Phase 2 adds narrative judgment and memory. It is still independent from the live Telegram scheduler.

## Modules

- `app/fiona_narrative.py`
  - Builds narrative records from normalized Fiona events.
  - Detects known narratives and creates custom narrative buckets when needed.
  - Scores frequency, source diversity, cross-market reach, momentum, funds confirmation, persistence, and intelligence value.
  - Classifies narratives as Current, Emerging, Watchlist, Fading, or False.
  - Produces Daily and Weekly narrative text blocks.

- `app/fiona_memory.py`
  - Separates Event Memory, Narrative Memory, and Decision Memory.
  - Stores what the market is currently talking about, not just what happened.
  - Can persist memory to JSON for later runtime integration.

- `app/fiona_types.py`
  - Adds `NarrativeStatus`.
  - Adds `NarrativeRecord`.

## Narrative Rules

- `Current Narrative`
  - Narrative score 80+ and still active.

- `Emerging Narrative`
  - Narrative score 60-79 and still active.

- `Watchlist Narrative`
  - Narrative score 40-59.

- `Fading Narrative`
  - Low score, or no fresh signal for more than two days.

- `False Narrative`
  - High attention but weak funds confirmation.
  - Short-lived hype with poor persistence.
  - Repeated mentions with low intelligence value.

## Current Runtime Status

Phase 2 is intentionally not wired into the live scheduled Telegram task yet.

The existing scheduled task remains active and currently sends text-only summaries:

```text
WILSON_SEND=1
WILSON_SEND_IMAGES=0
```

## Tests

```bash
python3 -m unittest discover -s tests -p 'test*.py'
```
