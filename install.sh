#!/usr/bin/env bash
# Build and (re)install the extension into the default LibreOffice user profile.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
IDENTIFIER="io.github.rokusaburo.hailper"

# Installing while LibreOffice is running makes unopkg leave extra unpacked
# copies behind, which LibreOffice then loads as duplicate sidebar panels.
if pgrep -x soffice.bin >/dev/null 2>&1 || pgrep -x soffice >/dev/null 2>&1; then
  echo "LibreOffice is running. Close it completely before installing." >&2
  exit 1
fi

"$ROOT/build.sh"

# unopkg refuses to add an already-installed version, so remove first.
unopkg remove "$IDENTIFIER" >/dev/null 2>&1 || true

# Purge any leftover unpacked copies from earlier installs.
CACHE="${HOME}/.config/libreoffice/4/user/uno_packages/cache/uno_packages"
rm -rf "$CACHE"/*/AICopilot.oxt "$CACHE"/*/AICopilot.oxtproperties 2>/dev/null || true
find "$CACHE" -mindepth 1 -maxdepth 1 -type d -empty -delete 2>/dev/null || true

OXT="$(ls -1 "$ROOT/dist"/HaiLPER-*.oxt 2>/dev/null | sort -V | tail -1)"
if [ -z "$OXT" ]; then
  echo "No built .oxt found in $ROOT/dist." >&2
  exit 1
fi

unopkg add "$OXT"

echo "Installed $OXT. Restart LibreOffice to load the updated extension."
