#!/bin/bash
# No system dependencies: coros.py is stdlib-only. `setup.sh uninstall` only
# removes the token cache this plugin wrote; it never touches credentials
# (those live only in COROS_EMAIL / COROS_PASSWORD, never on disk).
set -euo pipefail

uninstall() {
  if [[ -d $HOME/.cache/omarchy-coros ]]; then
    rm -rf "$HOME/.cache/omarchy-coros"
    echo "Removed ~/.cache/omarchy-coros"
  else
    echo "No omarchy-coros cache found."
  fi
  echo
  echo "Left in place (yours to decide):"
  echo "  - COROS_EMAIL / COROS_PASSWORD env vars"
  echo
  echo "Remove the plugin with:"
  echo "  omarchy plugin remove io.github.astorrer.omarchy-coros"
}

if [[ ${1:-} == uninstall ]]; then
  uninstall
  exit 0
fi

echo "Checking python3 (stdlib only, no packages needed)..."
command -v python3 >/dev/null || { echo "python3 not found" >&2; exit 1; }
python3 --version

echo
echo "Omarchy-coros is ready. Export COROS_EMAIL and COROS_PASSWORD where the"
echo "bar process can see them, then add the widget: region defaults to eu,"
echo "switch to us in the widget settings if your COROS account lives there."
