# Fiona V3.1-alpha.1 Release Notes

- Release: Native Telegram Photo + American English
- Status: Historical implementation record; production validated at Gate 1 closeout
- Date: 2026-08-25
- Closeout: 2026-09-03 (`docs/v3_1/gates/GATE_1_CLOSEOUT.md`)
- Production baseline: V3.0.0

## Highlights

- Production-grade native Telegram `sendPhoto` contract.
- Native iOS-first 1440 x 1800 Market News card.
- Centralized `en-US` Market News output boundary.
- Definite photo failure -> one text fallback.
- Unknown delivery -> no automatic retry or fallback.

## New Capabilities

- `FIONA_TELEGRAM_MEDIA_MODE=document|photo` with legacy default `document`.
- `FIONA_OUTPUT_LOCALE=zh-CN|en-US` with legacy default `zh-CN`.
- Locale resources, American-English timestamp and missing-data language, short
  native caption, and user-visible CJK guard.
- Source provenance sidecar for fields currently available on Fiona events.
- Photo/locale observability and a production-safe validator with no Telegram
  or scheduler-ledger side effects.

## Compatibility

The existing V3.0 document + Chinese path is the default. Scheduler, five brief
times, ledger, arbitration, source coverage, Alert behavior, Railway command,
and production variables are unchanged.

## Validation

- Full, Missing, and Stress 1440 x 1800 prototypes.
- Four media/locale combinations.
- Explicit/unknown Telegram failure matrix.
- Full unit suite and Python compile.
- No real Telegram test message.

## Known Limitations

- Real iOS Telegram-client review is still required.
- Morning, Evening, Daily, Weekly, and Alert are not migrated to `en-US`.
- Current upstream source provenance is incomplete.
- Global coverage, 6:3:1, six-slot cadence, Delta, and durable state are outside
  this release.

## Rollback

Keep or restore:

```env
FIONA_TELEGRAM_MEDIA_MODE=document
FIONA_OUTPUT_LOCALE=zh-CN
```

No data migration is involved.

## Gate Verdict at Implementation Time

`PASS WITH CONDITIONS`: deployable behind legacy defaults; activation requires
isolated Telegram/iOS review and explicit Product approval. Gate 2 is not
started.

Final production acceptance was completed on 2026-09-03. Gate 1 is now closed;
the authoritative final record is `docs/v3_1/gates/GATE_1_CLOSEOUT.md`.
