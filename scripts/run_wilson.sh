#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="/Users/mac/Desktop/intelligen agent_lancelot/financial daily"
cd "$PROJECT_DIR"

if [[ -f ".env.wilson" ]]; then
  set -a
  source ".env.wilson"
  set +a
fi

GLOBAL_ARGS=(--timezone "${WILSON_TIMEZONE:-Asia/Manila}")
if [[ "${WILSON_SEND:-0}" == "1" ]]; then
  GLOBAL_ARGS+=(--send)
fi

python3 -m app.wilson "${GLOBAL_ARGS[@]}" watch --interval-minutes "${WILSON_INTERVAL_MINUTES:-240}"
