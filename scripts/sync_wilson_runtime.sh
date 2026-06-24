#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="/Users/mac/Desktop/机器人工具/intelligen agent_lancelot/financial daily"
RUNTIME_DIR="${WILSON_RUNTIME_DIR:-$HOME/WilsonMarketNewsRuntime}"

mkdir -p "$RUNTIME_DIR"
rsync -a --delete "$PROJECT_DIR/app" "$RUNTIME_DIR/"
rsync -a "$PROJECT_DIR/config" "$RUNTIME_DIR/"
mkdir -p "$RUNTIME_DIR/scripts"
install -m 755 "$PROJECT_DIR/scripts/run_wilson_once.sh" "$RUNTIME_DIR/scripts/run_wilson_once.sh"
install -m 755 "$PROJECT_DIR/scripts/run_fiona_once.sh" "$RUNTIME_DIR/scripts/run_fiona_once.sh"
mkdir -p "$RUNTIME_DIR/reports/wilson"
mkdir -p "$RUNTIME_DIR/reports/fiona"

echo "Synced Wilson runtime to $RUNTIME_DIR"
