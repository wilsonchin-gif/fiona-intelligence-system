# Fiona V2 Release Blocker Fix

Status: Completed locally; awaiting Wilson review
Date: 2026-07-27
Scope: Phase 2C release blockers only

## 1. Problem

The Phase 2C release audit identified two blockers:

1. `app/fiona_market_news_image.py` contained a macOS-only
   `/usr/bin/sips` SVG-to-PNG command.
2. `requirements.txt` stated that Runtime did not import Pillow, while the
   Phase 2C integration imported Pillow-backed modules during process startup.

These conditions weakened Railway Linux portability and made the documented
dependency behavior inaccurate.

## 2. Root Cause

The original Phase 2A prototype rendered SVG and converted it through a local
macOS command. Phase 2B later introduced the production Pillow renderer, but
the prototype converter remained as the default path in the shared image
module.

The Phase 2C delivery coordinator also imported Pillow and the card renderer at
module import time. Because Fiona Runtime imports the coordinator, all brief
types inherited the Pillow startup dependency even when
`FIONA_MARKET_NEWS_MODE=text`.

## 3. Fix

- The default `render_market_news_png` path now delegates to the existing
  Python Pillow renderer.
- The macOS subprocess converter was removed from the active Phase 2C image
  module.
- An explicitly injected converter remains available only as a test/prototype
  compatibility seam; no operating-system command is supplied by Fiona.
- Pillow image decoding, card rendering, and image assessments now load only
  when shadow/image processing is entered.
- `text` mode returns through the existing text sender before any image model,
  Pillow renderer, or image validation is invoked.
- Font files continue to resolve through `pathlib` from the repository root.
- `requirements.txt` now documents the real Pillow dependency and lazy-loading
  behavior.

## 4. Files Changed

Production and dependency files:

- `app/fiona_market_news_image.py`
- `app/fiona_market_news_delivery.py`
- `app/fiona_card_renderer.py`
- `requirements.txt`

Tests:

- `tests/test_fiona_market_news_image.py`
- `tests/test_fiona_card_renderer.py`
- `tests/test_fiona_production_pipeline.py`

Release documentation:

- `docs/releases/FIONA_V2_RELEASE_MANIFEST.md`
- `docs/releases/FIONA_V2_RELEASE_BLOCKER_FIX.md`

## 5. Compatibility Result

- Railway/Linux image path: compatible with Python and Pillow.
- Fixed fonts: repository-relative; no Mac system font dependency.
- Active Phase 2C path: no `sips`, ImageMagick CLI, or system image command.
- Active Phase 2C path: no `/Users/mac` absolute path.
- `text` mode: imports and runs its delivery path without Pillow.
- `shadow` and `image` modes: use the Pillow renderer.
- Scheduler, Ledger, Arbitration, Telegram delivery semantics, and the other
  four Brief types were not changed.

Repository-wide search still finds:

- a separate legacy `app/wilson.py` image exporter that is not called by the
  Fiona Railway scheduler path;
- historical audit and prototype documents that describe the former macOS
  implementation;
- unrelated legacy desktop export paths.

They were intentionally not changed because this phase is limited to the
Phase 2C release blockers.

## 6. Test Result

- Default local Python without Pillow:
  `python3 -m app.fiona_runtime --help` passed, confirming Runtime import.
- Targeted image, delivery, renderer, and production-pipeline tests:
  53 passed.
- Python compile check:
  passed.
- Full unit test suite:
  164 passed.
- Real Telegram sends:
  none.
- Commit:
  none.
- Push:
  none.
- Deploy:
  none.
