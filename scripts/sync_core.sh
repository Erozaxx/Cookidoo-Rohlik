#!/usr/bin/env bash
# Sync core library modules into the HA custom component (vendoring).
# Single source of truth: src/cookidoo_rohlik/. Run after any core change.
set -euo pipefail
cd "$(dirname "$0")/.."
SRC="src/cookidoo_rohlik"
DST="custom_components/cookidoo_rohlik/core"
MODULES=(models classify planner quantity rohlik_client matching orchestrator cookidoo_client render)
mkdir -p "$DST"
printf '"""Vendored core (auto-synced by scripts/sync_core.sh — do not edit here)."""\n' > "$DST/__init__.py"
for m in "${MODULES[@]}"; do
  cp "$SRC/$m.py" "$DST/$m.py"
  printf 'synced %s\n' "$m"
done
