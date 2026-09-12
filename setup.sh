#!/bin/bash
# No system dependencies: coros.py is stdlib-only. Prompts for COROS
# credentials, stores them in ~/.config/omarchy-coros/credentials (0600),
# and tests the login before finishing. `setup.sh uninstall` only removes
# what this plugin wrote (the dev symlink, the credentials file, and the
# token cache).
set -euo pipefail

PLUGIN_ID="io.github.astorrer.omarchy-coros"
LINK_DIR="$HOME/.config/omarchy/plugins"
CONF_DIR="$HOME/.config/omarchy-coros"
CREDS="$CONF_DIR/credentials"

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
  if [[ -f $CREDS ]]; then
    rm "$CREDS"
    echo "Removed $CREDS"
  else
    echo "No credentials file found."
  fi
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
echo "COROS login (stored in $CREDS, mode 0600 — never in git)."
echo "Leave blank to keep an existing value."
if [[ -f $CREDS ]]; then
  COROS_EMAIL=$(grep "^COROS_EMAIL=" "$CREDS" | cut -d= -f2- || true)
  COROS_REGION=$(grep "^COROS_REGION=" "$CREDS" | cut -d= -f2- || true)
fi
read -r -p "COROS email [${COROS_EMAIL:-}]: " email
email=${email:-${COROS_EMAIL:-}}
read -r -s -p "COROS password: " password
echo
read -r -p "Region (eu/us) [${COROS_REGION:-eu}]: " region
region=$(echo "${region:-${COROS_REGION:-eu}}" | tr "[:upper:]" "[:lower:]")
if [[ $region != eu && $region != us ]]; then
  echo "Region must be eu or us." >&2
  exit 1
fi
if [[ -z $email ]]; then
  echo "Email is required." >&2
  exit 1
fi

mkdir -p "$CONF_DIR"
umask 077
if [[ -n $password ]]; then
  printf "COROS_EMAIL=%s\nCOROS_PASSWORD=%s\nCOROS_REGION=%s\n" "$email" "$password" "$region" > "$CREDS"
else
  printf "COROS_EMAIL=%s\nCOROS_REGION=%s\n" "$email" "$region" > "$CREDS"
  if ! grep -q "^COROS_PASSWORD=" "$CREDS"; then
    echo "No password on file and none entered." >&2
    exit 1
  fi
fi
chmod 600 "$CREDS"
echo "Wrote $CREDS"

echo
echo "Testing login (single attempt — failures here never trigger polling)..."
if [[ -z $password ]]; then
  password=$(grep "^COROS_PASSWORD=" "$CREDS" | cut -d= -f2- || true)
fi
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
