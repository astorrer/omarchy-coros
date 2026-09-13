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

Then run setup from the plugin folder (python check + optional dev symlink).
Sign in from the COROS panel on the bar — email, password, and region.
Credentials land in `~/.config/omarchy-coros/credentials` (mode 0600, never
in git, never in widget settings, never on argv). The password is stored
there so the 24h token refresh can log in again; it is hashed (MD5) for
the login call. The access token is cached separately
(`~/.cache/omarchy-coros/token.json`, mode 0600, 24h TTL).

```sh
~/.config/omarchy/plugins/io.github.astorrer.omarchy-coros/setup.sh
```

`COROS_EMAIL` / `COROS_PASSWORD` env vars still work as an override for
tests. If logins fail on both regions, polls back off for an hour and the
panel asks you to sign in again.

## Use

- The bar shows one compact metric (`HRV 24`); hover for the rest. Open the
  panel for Training Hub recovery: HRV vs baseline and band, resting HR,
  daily / 7-day / 28-day load, load ratio, weekly target, acute vs chronic,
  impact balance, fatigue, and last activity. Overnight and load sit
  three-across; HRV, load ratio, and the weekly target use a range. Accent
  means in-range / recovered; urgent means below-band HRV or overreaching
  load.
- The panel header shows whether you are signed in and which region (US/EU).
  Region is chosen on the sign-in form, not in a second settings row.
- Missing data shows as blank, never as an error — the helper exits zero and
  reports nulls when COROS has nothing (e.g. a rest day with no HRV sample).
- The **gear** opens settings: which metric groups to show, what the bar
  displays (COROS mark, HRV, RHR, load, or fatigue), poll interval,
  hide-when-empty, and change account. Settings are saved into the widget's
  config, so they survive restarts.

## Settings

Open from the gear in the panel, or Omarchy Settings → Bar → COROS:

| Key                 | Type    | Default | Meaning                                 |
|---------------------|---------|---------|-----------------------------------------|
| `refreshIntervalMin`| integer | 30      | Snapshot poll interval (15 min–24 h)    |
| `region`            | string  | `"eu"`  | COROS region, `eu` or `us`              |
| `hideWhenNoData`    | boolean | false   | Remove the widget from the bar when empty |
| `showRecovery`      | boolean | true    | Panel: HRV, RHR, balance, fatigue         |
| `showLoad`          | boolean | true    | Panel: daily and rolling training load    |
| `showActivity`      | boolean | true    | Panel: last workout                       |
| `barMetric`         | string  | `"hrv"` | Bar: `icon`, `hrv`, `rhr`, `load`, `fatigue` |

## How it works

`coros.py` (stdlib only) logs into the unofficial Training Hub REST API
(`teameuapi` for `eu`, `teamapi` for `us`), caches the auth token in
`~/.cache/omarchy-coros/token.json` (mode 0600, 24h TTL), and prints one JSON
snapshot object on stdout. The widget polls `coros.py snapshot` every
`refreshIntervalMin`. The password lives in the credentials file (0600);
the token cache is separate.

## Remove

```sh
omarchy plugin remove io.github.astorrer.omarchy-coros
```

To drop the token cache this plugin wrote:

```sh
~/.config/omarchy/plugins/io.github.astorrer.omarchy-coros/setup.sh uninstall
```

## Troubleshooting

- **Widget empty / sign-in failed** — open the panel and sign in. Pick **us**
  if your account lives on the America Training Hub (`t.coros.com`), **eu**
  for Europe (`t.eu.coros.com`). A wrong region is retried once automatically,
  and a successful login follows COROS's `regionId` onto the right host.
  Wrong credentials back off for an hour. This is email/password against the
  Training Hub API — not WAF, and not 2FA. Settings → Change account to switch
  users.
- **Logged out of the phone app** — not expected from v1: the Training Hub web
  login does not touch the mobile session. (Only the mobile sleep API, not
  used here, forces the phone app out.)
- **Stale data** — delete `~/.cache/omarchy-coros/token.json` to force a fresh
  login on the next poll.
- **HRV / resting HR blank after sign-in** — Training Hub often leaves *today*
  empty until overnight HRV is processed. The widget walks the last week and
  shows the newest day that has recovery metrics. Right-click the bar widget
  to refresh.
- **Sleep missing even though the COROS app has it** — expected. Training Hub
  `dayDetail` does not include sleep duration or stages (`tib` is training
  impact balance, not time in bed). Sleep lives on the mobile API, which
  logs you out of the phone app, so this plugin does not call it.

## Development

```sh
ruff check .
./tests/run
```

`./tests/run` lints, validates `manifest.json` (shape plus settings-schema
keys), runs the Python unit tests (mocked HTTP, no network), `omarchy plugin
validate`, and `qmllint`. `coros.py` lives on `feat/api-client`, the QML/JS
on `feat/ui` — see `PLAN.md` for file ownership.
