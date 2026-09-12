#!/bin/bash
# No system dependencies: coros.py is stdlib-only. Prompts for COROS
# credentials, stores them in ~/.config/omarchy-coros/credentials (0600),
# and tests the login before finishing.
#
# Ownership rule (konnectarchy pattern): every file this script writes
# carries a marker, and `setup.sh uninstall` only removes marked files it
# owns. Shared things are left alone and listed.
set -euo pipefail

PLUGIN_ID="io.github.astorrer.omarchy-coros"
LINK_DIR="$HOME/.config/omarchy/plugins"
CONF_DIR="$HOME/.config/omarchy-coros"
CREDS="$CONF_DIR/credentials"
CREDS_MARK="# Written by omarchy-coros setup.sh"

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
  if [[ -d $HOME/.cache/omarchy-coros ]]; then
    rm -rf "$HOME/.cache/omarchy-coros"
    echo "Removed ~/.cache/omarchy-coros"
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
echo "COROS login (stored in $CREDS, mode 0600 — never in git)."
if [[ -f $CREDS ]]; then
  file_email=$(grep "^COROS_EMAIL=" "$CREDS" | cut -d= -f2- || true)
  file_password=$(grep "^COROS_PASSWORD=" "$CREDS" | cut -d= -f2- || true)
  file_region=$(grep "^COROS_REGION=" "$CREDS" | cut -d= -f2- || true)
fi
if [[ -t 0 ]]; then
  echo "Leave blank to keep an existing value."
  read -r -p "COROS email [${COROS_EMAIL:-${file_email:-}}]: " email
  email=${email:-${COROS_EMAIL:-${file_email:-}}}
  read -r -s -p "COROS password: " password
  echo
  read -r -p "Region (eu/us) [${COROS_REGION:-${file_region:-eu}}]: " region
  region=${region:-${COROS_REGION:-${file_region:-eu}}}
  password=${password:-${COROS_PASSWORD:-${file_password:-}}}
else
  echo "Non-interactive: taking credentials from the environment or file."
  email=${COROS_EMAIL:-${file_email:-}}
  password=${COROS_PASSWORD:-${file_password:-}}
  region=${COROS_REGION:-${file_region:-eu}}
fi
region=$(echo "$region" | tr "[:upper:]" "[:lower:]")
if [[ $region != eu && $region != us ]]; then
  echo "Region must be eu or us." >&2
  exit 1
fi
if [[ -z $email || -z $password ]]; then
  echo "Email and password are required (prompt or COROS_EMAIL/COROS_PASSWORD)." >&2
  exit 1
fi

mkdir -p "$CONF_DIR"
umask 077
{
  echo "$CREDS_MARK"
  printf "COROS_EMAIL=%s\nCOROS_PASSWORD=%s\nCOROS_REGION=%s\n" "$email" "$password" "$region"
} > "$CREDS"
chmod 600 "$CREDS"
echo "Wrote $CREDS"

if [[ ${OMARCHY_COROS_SETUP_SKIP_LOGIN_TEST:-} == 1 ]]; then
  echo "Skipped login test (OMARCHY_COROS_SETUP_SKIP_LOGIN_TEST=1)."
  exit 0
fi
echo
echo "Testing login (single attempt — failures here never trigger polling)..."
export COROS_EMAIL="$email" COROS_PASSWORD="$password" COROS_REGION="$region"
out=$(python3 "$ROOT/coros.py" snapshot --region "$region")
echo "$out" | python3 -c "import json,sys; d=json.load(sys.stdin); print('error:', d.get('error')); print({k: d.get(k) for k in ('hrv','hrvBaseline','rhr','load','sleepH','activity')})"
if echo "$out" | python3 -c "import json,sys; sys.exit(0 if json.load(sys.stdin).get('error') is None else 1)"; then
  echo
  echo "Login works. Add the COROS widget to the bar."
else
  echo
  echo "Login failed — check the email/password, or try the other region." >&2
  exit 1
fi
