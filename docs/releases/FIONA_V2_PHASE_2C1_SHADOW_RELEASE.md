# Fiona V2 Phase 2C.1 Shadow Release

Status: Local validation
Date: 2026-07-28
Production variable change: Pending

## Goal

Validate the Market News PNG pipeline with real production data while keeping
the existing Telegram text brief as the only user-visible output.

## Railway Variable

```env
FIONA_MARKET_NEWS_MODE=shadow
```

No Scheduler, task time, Ledger, Morning, Evening, Daily, Weekly, Alert, or
Telegram document-delivery setting changes are required.

## Shadow Behavior

1. Send the existing Market News text through the existing Telegram path.
2. Build the Market News ViewModel from the same production snapshot.
3. Render and validate a temporary 1080 x 1350 PNG with Pillow.
4. Record non-sensitive render and cleanup metrics.
5. Delete the temporary PNG.
6. Never call Telegram `sendDocument`.

A renderer or validation failure is recorded but does not change the successful
text delivery result.

## Observability Fields

- `delivery_mode`
- `render_success`
- `png_width`
- `png_height`
- `png_size_bytes`
- `caption_length`
- `fallback_state`
- `cleanup_state`

The log must not contain the Telegram token, full caption, legacy text payload,
chat ID, or user data.

## Release Checklist

- Railway deploy for commit `1ec151d` is healthy.
- Set `FIONA_MARKET_NEWS_MODE=shadow`.
- Confirm Telegram still receives exactly one Market News text brief.
- Confirm `delivery_mode=shadow`.
- Confirm `render_success=true`.
- Confirm PNG dimensions are 1080 x 1350.
- Confirm PNG size is greater than zero and below 1.5 MB.
- Confirm `fallback_state=not_applicable`.
- Confirm `cleanup_state=success`.
- Confirm `document_send_status=not_sent`.
- Observe multiple scheduled Market News cycles before considering image mode.

## Stop Conditions

Return the Railway variable to `text` if any of these persist:

- renderer or validation failures;
- missing font assets;
- PNG dimensions or size outside the product contract;
- cleanup failures;
- increased Scheduler cycle errors;
- duplicated or missing Telegram text briefs.

Image delivery remains disabled during Phase 2C.1.
