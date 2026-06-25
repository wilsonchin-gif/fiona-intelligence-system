# Fiona Intelligence System

Fiona is a market intelligence assistant for GitHub + Railway + Telegram production deployment.

Fiona focuses on:

- fewer pushes
- higher signal
- market context
- narrative tracking
- risk observation

Fiona does not provide investment advice, price targets, or trading instructions.

## Production Runtime

Railway starts Fiona with:

```bash
python3 -m app.fiona_runtime --send run-scheduler
```

The runtime continuously checks whether a scheduled brief is due and writes runtime output under `reports/fiona/`.

Scheduler polling interval priority:

1. `WILSON_INTERVAL_MINUTES`
2. `FIONA_RUNTIME_INTERVAL_MINUTES`
3. runtime default

## Scheduled Briefs

Current production tasks:

- `00:00` Fiona Market News
- `07:30` Fiona Morning
- `20:30` Fiona Evening
- `22:30` Fiona Daily
- Sunday `21:00` Fiona Weekly

Timezone is controlled by `WILSON_TIMEZONE`.

## Telegram

Telegram delivery uses `app/telegram_service.py`.

Production sending path:

```text
Fiona Runtime -> telegram_service -> Telegram Bot API
```

Target priority:

1. `TELEGRAM_GROUP_ID`
2. `TELEGRAM_CHAT_ID`
3. `TELEGRAM_CHANNEL_ID`

Production recommendation: configure only `TELEGRAM_GROUP_ID` as the default Telegram target.

`TELEGRAM_CHANNEL_ID` is kept only for backward compatibility and is not recommended as the default production target.

Not recommended for production defaults:

- `FIONA_SEND`
- `FIONA_SEND_TELEGRAM`
- `TELEGRAM_CHANNEL_ID`

## Recommended Railway Variables

```env
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_GROUP_ID=your_group_id
WILSON_SEND=1
WILSON_TIMEZONE=Asia/Manila
WILSON_INTERVAL_MINUTES=240
FIONA_ALERT_ENABLED=0
FIONA_ALERT_DRY_RUN=1
```

Send switch priority:

1. `WILSON_SEND`
2. `FIONA_SEND`
3. `FIONA_SEND_TELEGRAM`

If `WILSON_SEND` exists, it is the production source of truth.

## Alert Engine

Fiona Alert Engine code exists in the project, but production real-time alerts are disabled by default.

Use:

```env
FIONA_ALERT_ENABLED=0
FIONA_ALERT_DRY_RUN=1
```

Only enable real-time alerts after production validation:

```env
FIONA_ALERT_ENABLED=1
FIONA_ALERT_DRY_RUN=0
```

## Local Dry Run

Generate a brief without sending Telegram:

```bash
WILSON_SEND=0 python3 -m app.fiona_runtime --brief daily --send run-once
```

Generate a specific brief:

```bash
WILSON_SEND=0 python3 -m app.fiona_runtime --brief morning --send run-once
WILSON_SEND=0 python3 -m app.fiona_runtime --brief evening --send run-once
WILSON_SEND=0 python3 -m app.fiona_runtime --brief market-news --send run-once
WILSON_SEND=0 python3 -m app.fiona_runtime --brief weekly --send run-once
```

## Tests

Run all unit tests:

```bash
python3 -m unittest discover -s tests
```

## Documentation System

Fiona follows:

```text
Code First, Documentation Always.
```

Every development cycle must run Documentation Sync before commit:

- update `docs/changelog/CHANGELOG.md`
- update `docs/roadmap/roadmap.md`
- update related PRD files under `docs/prd/`
- update architecture / deployment / decision log when relevant
- update UI docs and screenshots when Telegram or image layout changes
- generate release notes under `docs/releases/`
- export `.docx` files to `docs/export/` when document tooling is available

Documentation entry:

```text
docs/README.md
```

## Files

- `app/`: Fiona runtime, content engine, scoring, memory, Telegram service, and current snapshot builder.
- `config/`: source configuration and environment examples.
- `docs/`: phase notes and design documents.
- `scripts/`: local helper scripts.
- `tests/`: unit tests.
- `railway.toml`: Railway production start command.
- `requirements.txt`: Python dependency marker for Railway.
- `runtime.txt`: Python runtime version.

## Security

Never commit secrets.

Ignored runtime and secret files include:

- `.env`
- `config/*.env`
- `reports/`
- `tmp/`
- `node_modules/`
- `*.log`

Disclaimer: 本内容仅供参考，不构成任何投资建议。投资有风险，入市需谨慎。
