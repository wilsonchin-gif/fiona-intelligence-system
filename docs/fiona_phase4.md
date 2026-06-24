# Fiona Intelligence System V1.0 - Phase 4

Phase 4 adds the independent Fiona runtime. It is ready to run manually or be scheduled later, but it does not replace the active Wilson scheduler.

## New Runtime

- `app/fiona_runtime.py`
  - Builds a Fiona snapshot from the current Wilson market data collector.
  - Converts market snapshot data into normalized Fiona events.
  - Scores events with the Fiona Alert Engine.
  - Updates persistent Fiona Memory.
  - Generates selected Fiona briefs:
    - `alert`
    - `morning`
    - `evening`
    - `market-news`
    - `daily`
    - `weekly`
    - `auto`
  - Sends Telegram text only when `--send` or `FIONA_SEND=1` is enabled.
  - Uses Wilson text fallback if Fiona generation fails after a snapshot is available.

## New Script

- `scripts/run_fiona_once.sh`

Default behavior:

```bash
FIONA_SEND=0
FIONA_BRIEF=auto
```

Manual examples:

```bash
bash scripts/run_fiona_once.sh
python3 -m app.fiona_runtime --brief daily run-once
python3 -m app.fiona_runtime --brief alert --send run-once
```

## New Config Template

- `config/fiona.env.example`

```text
FIONA_TIMEZONE=Asia/Manila
FIONA_OUTPUT_DIR="$HOME/WilsonMarketNewsRuntime/FionaReports"
FIONA_BRIEF=auto
FIONA_SEND=0
```

## Push Rules

- Only `alert` can push Fiona Alert messages.
- Scheduled `auto` runs generate the due brief only, avoiding notification fatigue.
- Explicit scheduled briefs such as `daily` only push that brief.
- Telegram push failure is logged and does not stop the runtime.

## Current Production Status

The active launchd job is still Wilson:

```text
com.local.wilson-market-news
00:00 / 04:00 / 08:00 / 12:00 / 16:00 / 20:00
```

Current Wilson config remains:

```text
WILSON_SEND=1
WILSON_SEND_IMAGES=0
```

Fiona runtime is available but not activated as a replacement scheduler yet.
