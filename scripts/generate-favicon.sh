#!/usr/bin/env bash
# Regenerates site/favicon.png from the source icon, then rebuilds the site.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE_ICON="$REPO_ROOT/docs/img/pulse-code-icon.png"
FAVICON="$REPO_ROOT/site/favicon.png"

if command -v magick >/dev/null 2>&1; then
  MAGICK="magick"
elif command -v convert >/dev/null 2>&1; then
  MAGICK="convert"
else
  echo "error: imagemagick not found (need 'magick' or 'convert' on PATH)" >&2
  exit 1
fi

"$MAGICK" "$SOURCE_ICON" -resize 64x64 "$FAVICON"
echo "wrote $FAVICON"

python3 "$REPO_ROOT/site/generate.py"
