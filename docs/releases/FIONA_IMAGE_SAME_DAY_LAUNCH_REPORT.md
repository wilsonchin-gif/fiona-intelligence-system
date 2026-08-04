# Fiona Image Same-Day Launch Report

版本：V2 Phase 2
状态：Dedicated validator remediation ready; container validation pending
负责人：Wilson / Codex
日期：2026-08-04 UTC+8

## Release Objective

Remove the stale Daily catch-up blocker, validate Caption RC and the 1080x1350
Pillow renderer in the Railway production image, then activate one-document
Market News delivery only if every safety gate passes.

## Included Changes

- freshness-aware collision arbitration
- previous-day Daily expiry protection
- pre-arbitration expiry filtering
- terminal collision suppression to prevent delayed duplicate pushes
- production-safe Market News image validation command
- regression and seven-day simulation tests
- arbitration and launch documentation

## Production Behavior Boundaries

- five fixed schedule times: unchanged
- Morning/Evening/Daily/Weekly content: unchanged
- Telegram sender and unknown-delivery protection: unchanged
- renderer layout and Caption RC: unchanged
- Alert Engine: unchanged and not activated
- Railway variables: unchanged until final image gate

## Gate Record

| Gate | Status | Evidence |
|---|---|---|
| Root cause | PASS | Deterministic stale Daily priority bias reproduced. |
| Arbitration | PASS locally | Midnight and Monday collision tests. |
| Duplicate prevention | PASS locally | Collision losers terminally suppressed. |
| Compile | PASS locally | `python3 -m compileall app scripts`. |
| Full tests | PASS locally | 193 tests passed. |
| Railway deploy | PASS | Formal deployment `eb899126-818f-48b4-b452-d940885c5ed4`, source `4b15bb6807a295c32f42a22b6b3480fadaba612b`. |
| Production validation | PENDING RETRY | The first attempt loaded `railway.toml`; dedicated `/railway.validator.toml` remediation is ready. |
| Caption RC | PENDING CONTAINER VALIDATION | Local RC passed; Railway-container metrics are still required. |
| Image activation | NOT STARTED | Production remains `FIONA_MARKET_NEWS_MODE=shadow`. |
| First live image | Pending | Expected next 00:00 UTC+8 occurrence. |

Dedicated remediation is now prepared in `/railway.validator.toml`. The next
temporary validator must explicitly set Custom Config File Path to that file
before its source deployment is accepted. The formal service remains bound to
the default `/railway.toml`.

## Railway Validator Attempt

- temporary service: `fiona-image-validator`
- source commit: `4b15bb6807a295c32f42a22b6b3480fadaba612b`
- requested command: `python3 -m app.fiona_runtime validate-market-news-image`
- effective command after build: `python3 -m app.fiona_runtime --send run-scheduler`
- root cause: code-based `/railway.toml` took precedence over the temporary
  service start-command setting
- safety controls: no Telegram credentials; `WILSON_SEND=0`; restart policy
  `NEVER`; no cron, domain, or volume
- observed runtime: one scheduler cycle, `send=false`, no due occurrences, no
  occurrence results, and no errors
- cleanup: temporary service and deployment removed; no temporary Railway
  resource remains

## Production Validation Metrics

Not produced because the validation command did not execute. Required values
remain:

```text
view_model_success=true
caption_success=true
render_success=true
image_validation=true
png_width=1080
png_height=1350
png_size_bytes<1500000
cleanup_state=success
telegram_api_calls=0
scheduler_ledger_mutations=0
errors=[]
```

Local real-data validation (not the Railway gate) passed with:

```text
caption_length=517
market_regime=Risk On
evidence_level=Moderate
png_width=1080
png_height=1350
png_size_bytes=306068
cleanup_state=success
telegram_api_calls=0
scheduler_ledger_mutations=0
```

## Commit / Push / Deploy

- baseline commit: `4b15bb6807a295c32f42a22b6b3480fadaba612b`
- validator config commit: pending
- push: pending validator config commit
- Railway deployment: formal baseline service healthy

## Image Activation

- previous mode: `shadow`
- target mode: `image`
- activation: blocked by failed container validation gate
- other variable changes: prohibited

## First Live Delivery

Pending. Acceptance requires one Telegram document with caption and hashtags,
no additional text message, no duplicate, successful cleanup, and a successful
occurrence ledger status.

## Rollback

Primary rollback is `image -> shadow`. Secondary rollback is `shadow -> text`.
No manual resend should occur before ledger inspection.

## Unfinished Items

- deploy a temporary service with Custom Config File Path set to
  `/railway.validator.toml`
- Railway production-image validation
- image-mode activation
- first live 00:00 occurrence verification
