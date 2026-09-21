#!/usr/bin/env bash
# Build the extension into dist/HaiLPER-<version>.oxt
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
SRC="$ROOT/src"

VERSION="$(sed -n 's/.*<version value="\([^"]*\)".*/\1/p' "$SRC/description.xml" | head -1)"
VERSION="${VERSION:-0.0.0}"
OUT="$ROOT/dist/HaiLPER-$VERSION.oxt"

mkdir -p "$ROOT/dist"
rm -f "$ROOT/dist"/*.oxt

if ! command -v zip >/dev/null 2>&1; then
  echo "zip is required to build the .oxt" >&2
  exit 1
fi

(
  cd "$SRC"
  zip -r -X -q "$OUT" . \
    -x '.*' -x '__pycache__/*' -x '*/__pycache__/*' -x '*.pyc'
)

echo "Built $OUT"
