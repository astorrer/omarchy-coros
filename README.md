# Omarchy-coros

COROS recovery metrics on the Omarchy bar. The widget logs into your COROS
Training Hub account and shows HRV vs baseline, resting heart rate, training
load, and the last activity — per-user self-login, nothing hosted.

## Requirements

- A COROS account with data in the Training Hub.
- `python3` — already on every Omarchy install; the helper is stdlib-only.

## Install

```sh
omarchy plugin add https://github.com/astorrer/omarchy-coros.git --enable
```

Then run setup from the plugin folder. It symlinks the dev install, asks
for your COROS email/password/region, stores them in
`~/.config/omarchy-coros/credentials` (mode 0600, never in git), and tests
the login once before finishing:

```sh
~/.config/omarchy/plugins/io.github.astorrer.omarchy-coros/setup.sh
```

No environment variables needed: the helper reads the credentials file
itself, so the bar process needs no extra plumbing (`COROS_EMAIL` /
`COROS_PASSWORD` env vars still work as an override). The password is
hashed for the login call and never stored — only the access token is
cached (`~/.cache/omarchy-coros/token.json`, mode 0600, 24h TTL).

If logins fail on both regions, polls back off for an hour (instead of
hammering the API and risking a lockout) and the widget tells you to
re-run setup.

## Use

- The bar shows HRV, resting heart rate, training load, and the last activity.
- Missing data shows as blank, never as an error — the helper exits zero and
  reports nulls when COROS has nothing (e.g. a rest day with no HRV sample).
- The **gear** opens the settings view: poll interval, region, and
  hide-when-empty. Settings are saved into the widget's config, so they
  survive restarts.

## Settings

Open from the gear in the panel, or Omarchy Settings → Bar → COROS:

| Key                 | Type    | Default | Meaning                                 |
|---------------------|---------|---------|-----------------------------------------|
| `refreshIntervalSec`| integer | 30      | Snapshot poll interval (5–120)          |
| `region`            | string  | `"eu"`  | COROS region, `eu` or `us`              |
| `hideWhenNoData`    | boolean | false   | Remove the widget from the bar when empty |

## How it works

`coros.py` (stdlib only) logs into the unofficial Training Hub REST API
(`teameuapi` for `eu`, `teamapi` for `us`), caches the auth token in
`~/.cache/omarchy-coros/token.json` (mode 0600, 24h TTL), and prints one JSON
snapshot object on stdout. The widget polls `coros.py snapshot` every
`refreshIntervalSec`. The password is hashed for the login call and never
stored.

## Remove

```sh
omarchy plugin remove io.github.astorrer.omarchy-coros
```

To drop the token cache this plugin wrote:

```sh
~/.config/omarchy/plugins/io.github.astorrer.omarchy-coros/setup.sh uninstall
```

## Troubleshooting

- **Widget empty** — re-run `setup.sh`: it re-tests the login and tells you
  whether the email/password or the region (`eu` vs `us`) is wrong. A wrong
  region is retried once automatically; wrong credentials back off for an
  hour to avoid hammering the API.
- **Logged out of the phone app** — not expected from v1: the Training Hub web
  login does not touch the mobile session. (Only the mobile sleep API, not
  used here, forces the phone app out.)
- **Stale data** — delete `~/.cache/omarchy-coros/token.json` to force a fresh
  login on the next poll.

## Development

```sh
ruff check .
./tests/run
```

`./tests/run` lints, validates `manifest.json` (shape plus settings-schema
keys), runs the Python unit tests (mocked HTTP, no network), `omarchy plugin
validate`, and `qmllint`. `coros.py` lives on `feat/api-client`, the QML/JS
on `feat/ui` — see `PLAN.md` for file ownership.
