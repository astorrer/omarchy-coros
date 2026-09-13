#!/bin/bash
# No system dependencies: coros.py is stdlib-only. Checks python3 and
# optionally writes a dev symlink. Sign-in lives in the panel, not here.
# If COROS_EMAIL / COROS_PASSWORD are already in the environment, they are
# stored in ~/.config/omarchy-coros/credentials (0600) for headless installs.
#
# Ownership rule (konnectarchy pattern): every file this script writes
# carries a marker, and `setup.sh uninstall` only removes marked files it
# owns. Shared things are left alone and listed.
set -euo pipefail

PLUGIN_ID="io.github.astorrer.omarchy-coros"
CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"
CACHE_HOME="${XDG_CACHE_HOME:-$HOME/.cache}"
LINK_DIR="$HOME/.config/omarchy/plugins"
CONF_DIR="$CONFIG_HOME/omarchy-coros"
CACHE_DIR="$CACHE_HOME/omarchy-coros"
CREDS="$CONF_DIR/credentials"
CREDS_MARK="# Written by omarchy-coros"

owned_symlink() {
  [[ -L $LINK_DIR/$PLUGIN_ID ]] && [[ $(readlink "$LINK_DIR/$PLUGIN_ID") == "$ROOT" ]]
}

owned_creds() {
  [[ -f $CREDS ]] && grep -q "^$CREDS_MARK$" "$CREDS"
}

uninstall() {
  if owned_symlink; then
    rm "$LINK_DIR/$PLUGIN_ID"
    echo "Removed dev symlink $LINK_DIR/$PLUGIN_ID"
  else
    echo "No omarchy-coros dev symlink found (foreign links left alone)."
  fi
  if [[ -d $CACHE_DIR ]]; then
    rm -rf "$CACHE_DIR"
    echo "Removed $CACHE_DIR"
  else
    echo "No omarchy-coros cache found."
  fi
  if owned_creds; then
    rm "$CREDS"
    echo "Removed $CREDS"
  else
    echo "No omarchy-coros credentials file found."
  fi
  echo
  echo "Left in place (shared, or yours to decide):"
  echo "  - COROS_EMAIL / COROS_PASSWORD env vars, if you set any"
  echo
  echo "Remove the plugin with:"
  echo "  omarchy plugin remove $PLUGIN_ID"
}

if [[ ${1:-} == uninstall ]]; then
  ROOT=$(cd "$(dirname "$0")" && pwd)
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
if owned_symlink; then
  echo "Dev symlink already correct."
elif [[ -L $LINK_DIR/$PLUGIN_ID ]]; then
  echo "Dev symlink points elsewhere: $(readlink "$LINK_DIR/$PLUGIN_ID")" >&2
  exit 1
else
  ln -s "$ROOT" "$LINK_DIR/$PLUGIN_ID"
  echo "Linked $LINK_DIR/$PLUGIN_ID -> $ROOT"
fi

echo
echo "Sign in from the COROS panel on the bar — email and password never"
echo "go through this script. Optional: COROS_EMAIL / COROS_PASSWORD in the"
echo "environment still work for tests and headless installs."

if [[ -n ${COROS_EMAIL:-} && -n ${COROS_PASSWORD:-} ]]; then
  region=$(echo "${COROS_REGION:-eu}" | tr "[:upper:]" "[:lower:]")
  if [[ $region != eu && $region != us ]]; then
    echo "Region must be eu or us." >&2
    exit 1
  fi
  mkdir -p "$CONF_DIR"
  chmod 700 "$CONF_DIR"
  if [[ -L $CREDS ]]; then
    echo "Refusing to write $CREDS: it is a symlink (not moving creds through it)." >&2
    exit 1
  fi
  umask 077
  tmp="$CREDS.tmp"
  {
    echo "$CREDS_MARK"
    printf "COROS_EMAIL=%s\nCOROS_PASSWORD=%s\nCOROS_REGION=%s\n" "$COROS_EMAIL" "$COROS_PASSWORD" "$region"
  } > "$tmp"
  chmod 600 "$tmp"
  mv -f "$tmp" "$CREDS"
  echo "Wrote $CREDS from the environment."
  if [[ ${OMARCHY_COROS_SETUP_SKIP_LOGIN_TEST:-} == 1 ]]; then
    echo "Skipped login test (OMARCHY_COROS_SETUP_SKIP_LOGIN_TEST=1)."
    exit 0
  fi
  echo
  echo "Testing login..."
  export COROS_REGION="$region"
  out=$(python3 "$ROOT/coros.py" snapshot --region "$region")
  echo "$out" | python3 -c "import json,sys; d=json.load(sys.stdin); print('error:', d.get('error')); print({k: d.get(k) for k in ('hrv','hrvBaseline','rhr','load','sleepH','activity')})"
  if echo "$out" | python3 -c "import json,sys; sys.exit(0 if json.load(sys.stdin).get('error') is None else 1)"; then
    echo
    echo "Login works."
  else
    echo
    echo "Login failed — check COROS_EMAIL / COROS_PASSWORD, or try the other region." >&2
    exit 1
  fi
fi

echo
echo "Omarchy-coros is ready. Add the widget, then sign in from the panel."
