#!/usr/bin/env bash
# Render a self-contained HTML dossier to a landscape PDF, fully headless.
# No browser window pops up. Chrome leaves background updater processes that
# can keep the command "running" past the render, so we bound it and reap them.
#
# Usage: render_pdf.sh <input.html> <output.pdf>
set -euo pipefail
SRC="${1:?usage: render_pdf.sh <input.html> <output.pdf>}"
OUT="${2:?usage: render_pdf.sh <input.html> <output.pdf>}"

CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
[ -x "$CHROME" ] || CHROME="/Applications/Google Chrome Canary.app/Contents/MacOS/Google Chrome Canary"
[ -x "$CHROME" ] || CHROME="/Applications/Chromium.app/Contents/MacOS/Chromium"
[ -x "$CHROME" ] || { echo "No Chrome/Chromium found in /Applications" >&2; exit 1; }

# absolute file:// URL
case "$SRC" in /*) ABS="$SRC";; *) ABS="$(pwd)/$SRC";; esac

TMP="$(mktemp -d)"
"$CHROME" --headless=new --disable-gpu --no-pdf-header-footer \
  --user-data-dir="$TMP" \
  --print-to-pdf="$OUT" --print-to-pdf-no-header \
  --virtual-time-budget=6000 \
  "file://$ABS" >/dev/null 2>&1 &
CPID=$!
# give the render up to ~10s, then reap Chrome + its updater children
sleep 10
kill "$CPID" 2>/dev/null || true
pkill -f "print-to-pdf=$OUT" 2>/dev/null || true
sleep 1
rm -rf "$TMP"

if [ -f "$OUT" ]; then
  echo "OK: $OUT ($(wc -c <"$OUT") bytes)"
else
  echo "FAILED to produce $OUT" >&2
  exit 1
fi
