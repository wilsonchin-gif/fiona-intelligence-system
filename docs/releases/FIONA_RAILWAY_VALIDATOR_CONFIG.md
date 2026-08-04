# Fiona Railway Validator Config

Version: V2 Phase 2
Status: Ready for controlled container validation
Owner: Wilson / Codex
Updated: 2026-08-04 UTC+8

## Previous Failure

The first temporary `fiona-image-validator` service requested the command:

```text
python3 -m app.fiona_runtime validate-market-news-image
```

During the Railway build, the repository root `/railway.toml` was discovered.
Its production scheduler command replaced the temporary service command. The
safety controls prevented Telegram delivery, and the temporary service was
deleted without changing the formal service.

## Config As Code Precedence

Railway combines service settings with repository Config as Code. Values from
the repository configuration take precedence for that deployment. A Dashboard
start-command override therefore cannot safely turn the production
`/railway.toml` into a one-shot validator.

## Dedicated Validator Design

The repository now contains two explicit configurations:

- `/railway.toml`: formal production scheduler, `ON_FAILURE`
- `/railway.validator.toml`: one-shot image validation, `NEVER`

The validator uses the same `NIXPACKS` builder as production while replacing
only the deploy command and restart policy. It has no cron, healthcheck,
Telegram secret, or local filesystem path.

## Production Isolation

The formal Railway service continues to use the default `/railway.toml` and:

```text
python3 -m app.fiona_runtime --send run-scheduler
```

The temporary validator must explicitly set its Custom Config File Path to:

```text
/railway.validator.toml
```

The validator must never use the default config path.

## Validation Procedure

1. Create `fiona-image-validator` in the existing Railway project.
2. Set Custom Config File Path to `/railway.validator.toml` before deployment.
3. Connect `wilsonchin-gif/fiona-intelligence-system`, branch `main`.
4. Set only `WILSON_TIMEZONE=Asia/Hong_Kong`,
   `FIONA_MARKET_NEWS_MODE=shadow`, and `WILSON_SEND=0`.
5. Do not add Telegram credentials, cron, domain, or volume.
6. Verify deployment details show the dedicated config path and validation
   command.
7. Require exit code 0 and the complete non-sensitive validation JSON.

## Cleanup Procedure

After preserving non-sensitive validation metrics, delete the validator
service. Confirm that no deployment, replica, domain, volume, cron, variable,
or continuing cost resource remains.

## Rollback

The validator is isolated and can be deleted without changing production. If
image mode is later enabled and runtime errors appear, change `image` back to
`shadow`; use `text` only if the entire image path must be disabled.

## Known Risks

- An incorrect or missing Custom Config File Path can load `/railway.toml` and
  start the scheduler.
- Config source and effective start command must be checked in deployment
  metadata before accepting validator output.
- Container validation does not replace acceptance of the first real Market
  News document delivery.
