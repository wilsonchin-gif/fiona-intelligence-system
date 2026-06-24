#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${WILSON_PROJECT_DIR:-$(cd "$SCRIPT_DIR/.." && pwd)}"
cd "$PROJECT_DIR"

ENV_FILE="$PROJECT_DIR/config/wilson.env"
if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

TIMEZONE="${WILSON_TIMEZONE:-Asia/Manila}"
if [[ "${WILSON_SEND:-0}" == "1" ]]; then
  exec python3 -m app.wilson --timezone "$TIMEZONE" --send run-once
fi

exec python3 -m app.wilson --timezone "$TIMEZONE" run-once
