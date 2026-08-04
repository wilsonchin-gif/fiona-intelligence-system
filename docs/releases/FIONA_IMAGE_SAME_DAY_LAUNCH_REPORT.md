# Fiona Image Same-Day Launch Report

版本：V2 Phase 2
状态：Pre-production gates in progress
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
| Full tests | PASS locally | 189 tests passed. |
| Railway deploy | Pending | Source commit to be recorded. |
| Production validation | Pending | Must run inside deployed image. |
| Caption RC | Pending production validation | Hash/section metrics only. |
| Image activation | Pending | Only `FIONA_MARKET_NEWS_MODE` may change. |
| First live image | Pending | Expected next 00:00 UTC+8 occurrence. |

## Production Validation Metrics

Pending. Required values:

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

- commit: pending
- push: pending
- Railway deployment: pending
- source commit verification: pending

## Image Activation

- previous mode: `shadow`
- target mode: `image`
- activation: pending all gates
- other variable changes: prohibited

## First Live Delivery

Pending. Acceptance requires one Telegram document with caption and hashtags,
no additional text message, no duplicate, successful cleanup, and a successful
occurrence ledger status.

## Rollback

Primary rollback is `image -> shadow`. Secondary rollback is `shadow -> text`.
No manual resend should occur before ledger inspection.

## Unfinished Items

- Railway production-image validation
- image-mode activation
- first live 00:00 occurrence verification
