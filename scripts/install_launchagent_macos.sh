#!/usr/bin/env bash
# Replaces PROJECT_ROOT in the plist with this repo’s path and installs the LaunchAgent.

set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLIST_SRC="$ROOT/scripts/com.serpprototype.serp-collect.plist"
DEST="$HOME/Library/LaunchAgents/com.serpprototype.serp-collect.plist"

sed "s|PROJECT_ROOT|$ROOT|g" "$PLIST_SRC" >"$DEST"
echo "Installed: $DEST"
echo "Loading agent..."
launchctl unload "$DEST" 2>/dev/null || true
launchctl load "$DEST"
echo "Done. Runs every 24h (86400s) and once now (RunAtLoad). Logs: $ROOT/out/logs/"
echo "Unload with: launchctl unload $DEST"
