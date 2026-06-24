# Fiona Intelligence System V1.0 - Phase 1

Fiona is a Market Intelligence Officer, not a news bot.

Phase 1 implements the alert judgment foundation without changing the current scheduled Wilson text push.

## Modules

- `app/fiona_types.py`
  - Unified `FionaEvent` structure.
  - Scores, direction, alert level, lifecycle status, push decision.
  - Event memory record.

- `app/fiona_scoring.py`
  - `Intelligence Score` for 24h market importance.
  - `Conviction Score` for signal alignment.

- `app/fiona_classifier.py`
  - S/A/B alert classification.
  - Hard triggers for price, ETF, macro, regulation, institution, risk.
  - Alert template renderer.

- `app/fiona_lifecycle.py`
  - NEW / ONGOING / RESOLVED lifecycle.
  - Re-push allowed when intelligence score rises by 15+, level upgrades, or key evidence appears.
  - RESOLVED summaries can be pushed for previously S-level events.

- `app/fiona_engine.py`
  - Phase 1 pipeline:
    - score event
    - classify event
    - apply lifecycle

## Current Runtime Status

Phase 1 is intentionally not wired into the live scheduled Telegram task yet.

The existing scheduled task remains active and currently sends text-only summaries:

```text
WILSON_SEND=1
WILSON_SEND_IMAGES=0
```

## Tests

```bash
python3 -m unittest discover -s tests -p 'test*.py'
```

