# Fiona Intelligence System

Fiona is a market intelligence assistant for GitHub + Railway + Telegram production deployment.

Fiona focuses on:

- fewer pushes
- higher signal
- market context
- narrative tracking
- risk observation

Fiona does not provide investment advice, price targets, or trading instructions.

## Current Product Status

- Production: Fiona V3.0.0 Design System 1.0 (`a8678b0`)
- Railway delivery: Market News `image` mode
- Fiona V3.1 Global 4H Intelligence: Gate 0 closed on 2026-08-25
- V3.1-alpha.1 Gate 1: `CLOSED` and production validated
- Effective Telegram presentation: native `photo` + `en-US`
- Coverage and cadence remain `legacy`; 4H Delta remains `off`
- V3.1-alpha.2 Gate 2: Implemented / Shadow Candidate; global selection is not activated
- Gate 3 remains locked

## Production Runtime

Railway starts Fiona with:

```bash
python3 -m app.fiona_runtime --send run-scheduler
```

The runtime continuously checks whether a scheduled brief is due and writes runtime output under `reports/fiona/`.

## Local Workspace

Wilson AI Lab is the long-term workspace. The active Fiona repository currently
lives at:

```text
/Users/mac/Desktop/Wilson AI Lab/Fiona Intelligence Platform/03_Development/fiona-intelligence-system/
```

Local runtime data and historical reports live under:

```text
~/Documents/Wilson AI Lab/Fiona Intelligence Platform/04_Data/
```

Scheduler polling interval priority:

1. CLI `--interval-minutes`
2. `WILSON_INTERVAL_MINUTES`
3. `FIONA_RUNTIME_INTERVAL_MINUTES`
4. runtime default `5`

Production recommendation: keep `WILSON_INTERVAL_MINUTES=5`. Do not use `240` for the Railway scheduler because fixed-time briefs can be missed if the process starts outside the due window.

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
WILSON_TIMEZONE=Asia/Hong_Kong
WILSON_INTERVAL_MINUTES=5
FIONA_ALERT_ENABLED=0
FIONA_ALERT_DRY_RUN=1
FIONA_MARKET_NEWS_MODE=image
FIONA_TELEGRAM_MEDIA_MODE=photo
FIONA_OUTPUT_LOCALE=en-US
FIONA_COVERAGE_PROFILE=legacy
```

Send switch priority:

1. `WILSON_SEND`
2. `FIONA_SEND`
3. `FIONA_SEND_TELEGRAM`

If `WILSON_SEND` exists, it is the production source of truth.

## Market News Image Mode

Market News delivery is controlled by one feature flag. The code-safe default
remains `text`; the validated V3.0.0 Railway production setting is `image`:

```env
FIONA_MARKET_NEWS_MODE=image
```

- `text`: send the current text brief only. This remains the rollback setting and
  the code default when the variable is absent.
- `shadow`: send the current text brief, then generate and validate the PNG in
  the background without sending the image.
- `image`: send one PNG document with its Caption. A definite image-path failure
  falls back to the current text brief.

Invalid values are logged and safely treated as `text`. Future delivery changes
must still pass text/shadow validation before a controlled production cutover.

V3.1-alpha.1 uses two independent, reversible Market News flags:

```env
FIONA_TELEGRAM_MEDIA_MODE=photo
FIONA_OUTPUT_LOCALE=en-US
```

- `document` preserves the V3.0 1080 x 1350 `sendDocument` path.
- `photo` selects the native 1440 x 1800 `sendPhoto` path.
- `zh-CN` preserves the legacy Market News language.
- `en-US` selects the centralized American-English Market News output layer.

Production has validated `photo + en-US`; the code still retains legacy-safe
defaults when either flag is absent or invalid. A definite photo failure falls
back to text once; an ambiguous Telegram outcome does not trigger a retry or
fallback. Gate 1 is closed, while global coverage, global cadence, and 4H Delta
remain inactive.

Offline image delivery verification:

```bash
python3 scripts/dry_run_fiona_market_news_phase2c.py
```

The dry-run uses a fake Telegram transport and makes no network request.

## Global Coverage Shadow

Gate 2 adds a canonical source registry in `config/sources.json`, provenance,
deterministic event clustering, and dynamic 6:3:1 editorial ranking. The exact
seven legacy feeds remain authoritative for every user-visible brief.
Only Market News evaluates the expanded source set in an isolated Shadow
path. It adds no Telegram send, scheduled occurrence, or ledger write.

Keep `FIONA_COVERAGE_PROFILE=legacy`. Both legal values (`legacy`, `global_631`)
are parsed, but this alpha release never promotes Shadow selections into
production content. Invalid values warn and fall back to legacy. No additional
coverage flag is introduced. Cadence remains legacy and Delta remains off.

```bash
python3 -m app.fiona_runtime validate-source-registry
python3 -m app.fiona_runtime validate-global-coverage
```

These validators do not send Telegram or mutate scheduler state. The second
command reads public source endpoints. Runtime observations emit
`fionaGlobalCoverageShadow` with source health and 24h/7d metrics, without
article bodies or credentials. Observation JSON is ephemeral on Railway
without a Volume; Gate 2 does not create one. Activation needs reviewed
evidence covering 14 days and at least 100 distinct qualified event clusters.

See [Gate 2 implementation](docs/v3_1/gates/GATE_2_IMPLEMENTATION.md) and
[source inventory](docs/v3_1/FIONA_GLOBAL_SOURCE_REGISTRY.md).

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

V3.1 Gate 0 records:

- `docs/v3_1/FIONA_V3_1_PRODUCT_FREEZE.md`
- `docs/v3_1/FIONA_V3_1_IMPLEMENTATION_ROADMAP.md`
- `docs/v3_1/FIONA_V3_1_RELEASE_STRATEGY.md`
- `docs/v3_1/gates/GATE_0_CLOSEOUT.md`

V3.1 Gate 1 records:

- `docs/v3_1/gates/GATE_1_IMPLEMENTATION.md`
- `docs/v3_1/FIONA_NATIVE_PHOTO_SPEC.md`
- `docs/v3_1/FIONA_EN_US_OUTPUT_STANDARD.md`
- `docs/v3_1/FIONA_IOS_VISUAL_QA.md`
- `docs/releases/FIONA_V3_1_ALPHA_1_RELEASE_NOTES.md`

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
