#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/Users/mac/Library/Application Support/FinancialDaily"
PYTHON="/Users/mac/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3"

cd "$APP_DIR"
"$PYTHON" -m app.desktop_export
"$PYTHON" -m app.readable_preview
