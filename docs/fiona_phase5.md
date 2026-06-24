# Fiona Intelligence System V1.0 - Phase 5

Phase 5 installs Fiona as an independent local launchd job for internal testing.

## Launchd Job

- Label: `com.local.fiona-intelligence`
- Plist: `scripts/launchd/com.local.fiona-intelligence.plist`
- Installed path: `~/Library/LaunchAgents/com.local.fiona-intelligence.plist`
- Runtime script: `/Users/mac/WilsonMarketNewsRuntime/scripts/run_fiona_once.sh`

## Internal Test Mode

Fiona is configured to generate reports only:

```text
FIONA_SEND=0
FIONA_BRIEF=auto
```

No Telegram message is sent by the launchd job until `FIONA_SEND=1` is explicitly enabled.

## Schedule

Times are local UTC+8.

- 00:00 Fiona Market News
- 07:30 Fiona Morning
- 20:30 Fiona Evening
- 22:30 Fiona Daily
- Sunday 21:00 Fiona Weekly

## Output

```text
/Users/mac/WilsonMarketNewsRuntime/FionaReports
```

Latest files:

- `latest/fiona_telegram.md`
- `latest/fiona_events.json`
- `latest/fiona_narratives.json`
- `latest/fiona_status.json`
- `fiona_memory.json`

Logs:

- `/Users/mac/WilsonMarketNewsRuntime/reports/fiona/fiona.out.log`
- `/Users/mac/WilsonMarketNewsRuntime/reports/fiona/fiona.err.log`
- `/Users/mac/WilsonMarketNewsRuntime/FionaReports/fiona_telegram_push.log`

## Current Production Status

Wilson remains the active Telegram production scheduler.

Fiona is installed as a parallel internal-test scheduler and does not push Telegram messages yet.
