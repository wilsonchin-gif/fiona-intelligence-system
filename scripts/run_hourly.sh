#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="/Users/mac/Desktop/intelligen agent_lancelot/financial daily"
cd "$PROJECT_DIR"

python3 -m app.main watch --interval-minutes 240
