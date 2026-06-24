#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${FIONA_PROJECT_DIR:-$(cd "$SCRIPT_DIR/.." && pwd)}"
cd "$PROJECT_DIR"

ENV_FILE="$PROJECT_DIR/config/fiona.env"
if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

TIMEZONE="${FIONA_TIMEZONE:-Asia/Manila}"
BRIEF="${FIONA_BRIEF:-auto}"
OUTPUT="${FIONA_OUTPUT_DIR:-$HOME/WilsonMarketNewsRuntime/FionaReports}"

if [[ "${FIONA_SEND:-0}" == "1" ]]; then
  exec python3 -m app.fiona_runtime --timezone "$TIMEZONE" --output "$OUTPUT" --brief "$BRIEF" --send run-once
fi

exec python3 -m app.fiona_runtime --timezone "$TIMEZONE" --output "$OUTPUT" --brief "$BRIEF" run-once
