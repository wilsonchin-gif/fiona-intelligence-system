# Fiona V2 Limited Release Manifest

Status: Release preparation audit
Release gate: Phase 2C blockers resolved; awaiting controlled commit review
Prepared: 2026-07-27

## 1. Release Objective

Introduce the Fiona Market News limited image-delivery pipeline behind
`FIONA_MARKET_NEWS_MODE`, while preserving the current text delivery as the
default behavior.

The release is limited to Fiona Market News. It does not change Scheduler,
Ledger, Arbitration, Morning, Evening, Daily, Weekly, or Alert behavior.

## 2. Included Features

- Railway-compatible Pillow renderer for a fixed 1080 x 1350 PNG.
- Bundled Noto Sans SC fonts for deterministic Chinese rendering.
- Market Regime, Evidence Level, Fiona's View, Heat Map, What Changed,
  Key Markets, Narrative, Watch Next, Historical Context, Tags, and Disclaimer.
- Delivery modes:
  - `text`: existing Market News text delivery.
  - `shadow`: existing text delivery plus local render and validation.
  - `image`: one PNG document with caption and classified fallback behavior.
- Dedicated Telegram `sendDocument` path with caption normalization.
- PNG dimension, format, size, temporary-file cleanup, and delivery-state
  validation.
- Offline dry-run coverage for full, missing-data, and long-text scenarios.

## 3. Changed Production Files

- `app/fiona_runtime.py`
- `app/telegram_service.py`
- `app/fiona_card_renderer.py`
- `app/fiona_market_news_delivery.py`
- `app/fiona_market_news_image.py`
- `requirements.txt`
- `config/fiona.env.example`
- `README.md`
- `assets/fonts/NotoSansSC-Regular.otf`
- `assets/fonts/NotoSansSC-Bold.otf`
- `assets/fonts/OFL-NotoSansSC.txt`
- `assets/fonts/README.md`

Compatibility result:

- The Phase 2C image path uses Pillow only and contains no macOS image command.
- Pillow is loaded on demand by shadow/image rendering and validation.
- Runtime and `text` mode import successfully without Pillow.
- Fixed fonts resolve from repository-relative `pathlib` paths.

## 4. Added Tests

- `tests/test_fiona_card_renderer.py`
- `tests/test_fiona_market_news_delivery.py`
- `tests/test_fiona_market_news_image.py`
- `tests/test_fiona_production_pipeline.py`
- `tests/test_telegram_service.py`

Release QA support:

- `scripts/dry_run_fiona_market_news_phase2c.py`
- `scripts/generate_fiona_market_news_prototypes.py`

The prototype fixture script is imported by the delivery tests and dry-run
script. It is not a production runtime entry point.

## 5. Added Documentation

- `docs/v2/FIONA_VISUAL_SYSTEM_V1.md`
- `docs/v2/FIONA_MARKET_NEWS_CARD_SPEC_V1.md`
- `docs/v2/FIONA_MARKET_NEWS_IMAGE_INTELLIGENCE.md`
- `docs/v2/FIONA_PHASE_2B_RENDERER_REPORT.md`
- `docs/v2/FIONA_PHASE_2B5_PRODUCT_REFINEMENT.md`
- `docs/v2/FIONA_PHASE_2C_LIMITED_RELEASE.md`
- `docs/releases/FIONA_V2_RELEASE_MANIFEST.md`

## 6. Excluded Files

Generated and local-only:

- `reports/`
- `tmp/`
- `__pycache__/`
- `*.png`
- dry-run output files
- prototype output files

Prototype-only generators:

- `scripts/generate_fiona_market_news_v2.py`
- `scripts/generate_fiona_market_news_v25.py`

Temporary or superseded reports:

- `docs/audits/FIONA_PRODUCTION_PIPELINE_AUDIT.md`
- `docs/v2/FIONA_PHASE_2A_PROTOTYPE_REPORT.md`

Unrelated workspace documentation:

- `docs/PRODUCT_STATUS.md`
- `docs/RELEASE_HISTORY.md`
- `docs/ROADMAP.md`
- `docs/SYSTEM_ARCHITECTURE.md`
- `docs/VERSION_MATRIX.md`
- `docs/decision/`
- `docs/release/`
- `docs/fiona_project_memo.docx`

## 7. Rollback Method

1. Keep `FIONA_MARKET_NEWS_MODE=text` for the first deployment.
2. If shadow validation fails, return the variable to `text`; Telegram remains
   on the existing text path.
3. If image delivery fails after cutover, return the variable to `text` before
   any code rollback.
4. If the deployed code itself is unhealthy, redeploy the previous known-good
   Railway revision.
5. No database migration, persistent data migration, Scheduler migration, or
   Telegram Bot configuration rollback is required.

The controlled release commit still requires explicit Wilson approval. No
commit, push, or deployment is part of this manifest update.
