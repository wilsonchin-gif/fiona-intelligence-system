#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="/Users/mac/Desktop/intelligen agent_lancelot/financial daily"
PYTHON="/Users/mac/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3"

cd "$PROJECT_DIR"
"$PYTHON" -m app.desktop_export
"$PYTHON" -m app.readable_preview
