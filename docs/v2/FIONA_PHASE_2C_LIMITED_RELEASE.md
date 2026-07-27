# Fiona Phase 2C Limited Production Release

- Version: V2 Phase 2C
- Status: Local implementation, pending Wilson review
- Owner: Fiona Product / Engineering
- Updated: 2026-07-27
- Default mode: `text`

## 1. Scope

Phase 2C connects the existing Market News ViewModel, Caption composer, Pillow
renderer, and Telegram `sendDocument` capability behind a production-safe
feature flag. It does not switch production to image mode.

## 2. Existing Production Pipeline

```text
Scheduler
  -> run_once
  -> build_payload
  -> build_market_news_brief
  -> push_text
  -> telegram_service.send_message
```

Scheduler occurrence generation, catch-up, arbitration, ledger, and duplicate
protection remain unchanged.

## 3. New Delivery Architecture

```text
Scheduler
  -> Runtime
  -> one market snapshot / event / narrative set
  -> MarketNewsDeliveryCoordinator
       -> text
       -> shadow
       -> image
  -> telegram_service
```

The coordinator owns mode behavior, ViewModel construction, Caption creation,
temporary files, PNG validation, `sendDocument`, fallback, and metrics.
Renderer code does not send Telegram messages.

Market News uses the isolated `send_document_with_caption` service method.
Existing `send_message`, `send_photo`, and legacy `send_document` behavior is
unchanged for other product paths.

## 4. Mode Definitions

### text

- Uses the existing `push_text` path.
- Does not build the image ViewModel.
- Does not render PNG.
- Does not call `sendDocument`.

### shadow

- Sends the existing text brief.
- Builds one ViewModel from the same runtime payload.
- Builds Caption and PNG.
- Validates PNG and records metrics.
- Never calls `sendDocument`.
- Render failure does not change successful text delivery.

### image

- Builds one ViewModel.
- Generates one Caption and one PNG.
- Validates the PNG.
- Calls Telegram `sendDocument` with Caption.
- Does not send text after confirmed document success.
- Uses legacy text only after a definite image-path failure.

## 5. Environment Variable

```env
FIONA_MARKET_NEWS_MODE=text
```

Legal values are `text`, `shadow`, and `image`. Parsing trims whitespace and is
case-insensitive. An invalid value emits a structured warning and becomes
`text`. The default is always `text`.

## 6. Image Mode Flow

```text
Build ViewModel once
  -> Compose safe plain-text Caption
  -> Create unique TemporaryDirectory
  -> Render 1080 x 1350 RGB PNG
  -> Validate format, dimensions, mode, and size
  -> sendDocument
  -> Confirm Telegram message_id
  -> Clean temporary directory
```

## 7. Shadow Mode Flow

```text
Send legacy text
  -> Build ViewModel once
  -> Compose Caption
  -> Render and validate PNG
  -> Record metrics
  -> Clean temporary directory
  -> Do not send image
```

The text result remains the scheduler-visible delivery result.

## 8. Fallback Flow

The image path falls back to legacy text once after:

- ViewModel, Caption, temporary file, renderer, font, or validation failure
- Telegram definite API rejection
- Definite HTTP failure
- Missing `message_id`

Fallback does not run after confirmed image success. A failed fallback remains
visible to the existing scheduler through `brief_push.delivery_status=failed`.

## 9. Unknown Delivery State Handling

A timeout, network disconnect, or unparseable Telegram response can occur after
Telegram may have accepted the document. The coordinator does not send fallback
text in this state.

Without changing Scheduler or Ledger, the result is mapped to the existing
terminal `partial_delivery` state with `unknown_delivery_state=true`. This
prevents automatic retry and possible duplicate delivery. The remaining
limitation is that the ledger label is `partial_delivery`, not a dedicated
document-unknown state.

## 10. Logging and Metrics

Structured Market News logs include:

- requested mode
- occurrence ID when available
- render and validation status
- render and send durations
- image dimensions and bytes
- Caption length
- data completeness
- Market Regime
- Evidence Level
- fallback and cleanup status
- final delivery channel
- sanitized error category

Logs exclude Bot Token, Telegram API URL, complete Caption, and raw market
responses.

## 11. Temporary File Lifecycle

Production rendering uses a unique `TemporaryDirectory`. The PNG is cleaned in
`finally` after shadow validation, document success, definite failure, unknown
delivery state, or fallback. Production never writes cards into prototype or
dry-run folders.

## 12. Test Coverage

Tests cover:

- mode parsing and invalid fallback
- text, shadow, and image behavior
- shared ViewModel
- renderer and font failures
- invalid, empty, oversized, and wrong-dimension PNG
- definite and unknown Telegram failures
- no duplicate fallback
- temporary cleanup
- multipart Caption and document fields
- timeout, HTTP, API, and JSON response classification
- Market News Runtime routing
- full scheduler and brief regression suite

All Telegram calls in tests use mocks or fake transports.

## 13. Railway Compatibility

- Pillow has a Python-version-aware pin in `requirements.txt`.
- Noto Sans SC Regular and Bold are bundled under `assets/fonts/`.
- The OFL license is included.
- Font lookup is repository-relative through `pathlib`.
- Production renderer does not call `sips`.
- No `/Users/mac` path is embedded in runtime modules.
- PNG output is validated below 1.5 MB.

## 14. Deployment Prerequisites

- All tests and compile checks pass.
- Full, Missing, and Long dry-runs pass.
- Font files and license are included in the release scope.
- Railway first deploy explicitly keeps `FIONA_MARKET_NEWS_MODE=text`.
- Alert remains under its existing independent switch.

## 15. Rollback Procedure

Set:

```env
FIONA_MARKET_NEWS_MODE=text
```

Restart or redeploy the existing Railway service. No code rollback, scheduler
change, or Telegram configuration change is required.

## 16. Go-Live Checklist

### Repository

- Correct repository: Pass
- `main` matches `origin/main`: Pass
- No unexpected tracked diff: Pass

### Renderer

- Railway-compatible Pillow: Pass
- Fixed Noto Sans SC fonts and license: Pass
- Full / Missing / Long: Pass
- 1080 x 1350 and below 1.5 MB: Pass
- Visual overflow review: Pass

### Delivery

- text mode: Pass
- shadow mode: Pass
- image success: Pass with fake transport
- image fallback: Pass
- no duplicate fallback: Pass
- temporary cleanup: Pass

### Telegram

- `sendDocument` multipart mock: Pass
- Caption length safety: Pass
- network error classification: Pass
- Token-safe errors and logs: Pass
- real Telegram send: Not Executed

### Regression

- Scheduler unchanged: Pass
- Ledger unchanged: Pass
- Morning / Evening / Daily / Weekly unchanged: Pass
- Alert unchanged: Pass
- full tests: Pass, 161 tests
- compile check: Pass

### Release

- default mode is text: Pass
- Railway Variables unchanged: Pass
- commit: Not Executed
- push: Not Executed
- deploy: Not Executed

## 17. Known Risks

1. Telegram transport uncertainty is conservatively stored as the existing
   `partial_delivery` terminal state because this phase does not change Ledger.
2. Shadow validation is still required on Railway Linux before image cutover.
3. The current Caption is plain text. Future parse-mode support would require a
   separate escaping contract.

## 18. Explicit Non-Goals

Phase 2C does not modify:

- Scheduler timing, occurrence generation, catch-up, arbitration, or ledger
- Morning, Evening, Daily, Weekly, or Alert content
- data collectors or market judgment rules
- Railway command or production variables
- database, Knowledge Graph, or long-term image storage

## Manual Release Plan

### Stage 1: text

Deploy code while keeping `FIONA_MARKET_NEWS_MODE=text`. Confirm Railway
startup, Scheduler, Market News text, and all other briefs.

### Stage 2: shadow

Manually set `FIONA_MARKET_NEWS_MODE=shadow`. Observe several real Market News
occurrences. Verify successful 1080 x 1350 generation, font rendering, file
size, cleanup, and stable runtime behavior.

### Stage 3: image

Manually set `FIONA_MARKET_NEWS_MODE=image`. Verify the first document and
Caption, Chinese rendering, absence of duplicate text, and ledger result.

### Rollback

Set the mode back to `text` and restart the service.
