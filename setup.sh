#!/bin/bash
# No system dependencies: coros.py is stdlib-only. `setup.sh uninstall` only
# removes what this plugin wrote (the dev symlink and the token cache); it
# never touches credentials (those live only in COROS_EMAIL / COROS_PASSWORD,
# never on disk).
set -euo pipefail

PLUGIN_ID="io.github.astorrer.omarchy-coros"
LINK_DIR="$HOME/.config/omarchy/plugins"

uninstall() {
  if [[ -L $LINK_DIR/$PLUGIN_ID ]]; then
    rm "$LINK_DIR/$PLUGIN_ID"
    echo "Removed dev symlink $LINK_DIR/$PLUGIN_ID"
  else
    echo "No dev symlink found."
  fi
  if [[ -d $HOME/.cache/omarchy-coros ]]; then
    rm -rf "$HOME/.cache/omarchy-coros"
    echo "Removed ~/.cache/omarchy-coros"
  else
    echo "No omarchy-coros cache found."
  fi
  echo
  echo "Left in place (yours to decide):"
  echo "  - COROS_EMAIL / COROS_PASSWORD env vars"
}

if [[ ${1:-} == uninstall ]]; then
  uninstall
  exit 0
fi

echo "Checking python3 (stdlib only, no packages needed)..."
command -v python3 >/dev/null || { echo "python3 not found" >&2; exit 1; }
python3 --version

echo
echo "Linking dev install (konnectarchy pattern: the plugins dir holds a"
echo "symlink to this repo, so the bar runs your checkout live)..."
mkdir -p "$LINK_DIR"
ROOT=$(cd "$(dirname "$0")" && pwd)
if [[ -L $LINK_DIR/$PLUGIN_ID ]]; then
  if [[ $(readlink "$LINK_DIR/$PLUGIN_ID") == "$ROOT" ]]; then
    echo "Dev symlink already correct."
  else
    echo "Dev symlink points elsewhere: $(readlink "$LINK_DIR/$PLUGIN_ID")" >&2
    exit 1
  fi
else
  ln -s "$ROOT" "$LINK_DIR/$PLUGIN_ID"
  echo "Linked $LINK_DIR/$PLUGIN_ID -> $ROOT"
fi

echo
echo "Omarchy-coros is ready. Export COROS_EMAIL and COROS_PASSWORD where the"
echo "bar process can see them, then add the widget: region defaults to eu,"
echo "switch to us in the widget settings if your COROS account lives there."
