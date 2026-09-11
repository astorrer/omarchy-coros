# Omarchy-coros

COROS recovery metrics on the Omarchy bar. The widget logs into your COROS
Training Hub account and shows HRV vs baseline, resting heart rate, training
load, and the last activity — per-user self-login, nothing hosted.

## Requirements

- A COROS account with data in the Training Hub.
- `python3` — already on every Omarchy install; the helper is stdlib-only.
- Credentials in the environment (never in git, never echoed):
  - `COROS_EMAIL`
  - `COROS_PASSWORD`

## Install

```sh
omarchy plugin add https://github.com/astorrer/omarchy-coros.git --enable
```

Then run the one-time setup from the plugin folder (verifies `python3`, no
system packages needed):

```sh
~/.config/omarchy/plugins/io.github.astorrer.omarchy-coros/setup.sh
```

Export `COROS_EMAIL` and `COROS_PASSWORD` where the bar process can see them,
then add the widget to the bar.

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

- **Widget empty** — check `COROS_EMAIL` / `COROS_PASSWORD` are visible to the
  bar process, and that the region setting matches your account (`eu` vs `us`).
  A wrong region fails login; the widget retries the other region once.
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
