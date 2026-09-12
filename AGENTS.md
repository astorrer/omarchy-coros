# AGENTS.md

Instructions for AI coding agents working in this repository.

## Project

Omarchy-coros is an Omarchy bar-widget plugin that shows COROS recovery
metrics (HRV, RHR, training load, last activity) on the bar. `BarWidget.qml`
is the manifest entry point; it hosts the panel (`Panel.qml`), the poll logic,
and the formatting helpers (`Model.js`). The Python CLI `coros.py` (stdlib
only) logs into the unofficial COROS Training Hub REST API (`teameuapi` /
`teamapi`), caches the auth token in `~/.cache/omarchy-coros/token.json`, and
prints recovery metrics as JSON.

## Commands

```sh
ruff check .   # lint (config in ruff.toml, narrow ruleset)
./tests/run    # run all unit tests (Python, plugin validate, qmllint)
```

CI (`.github/workflows/test.yml`) runs ruff and the tests on every push and
pull request. Run them before you finish; all must pass.

Python is 3.12, ruff is the only Python linter. `coros.py` and its tests use
mocked HTTP only — no network, ever.

## Conventions

- Short-lived feature branches (`feat/scaffold`, `feat/api-client`, `feat/ui`)
  merge to `main` with the file ownership in `PLAN.md` — no overlap.
- Keep `CHANGELOG.md` updated for user-facing changes.
- Release flow (konnectarchy pattern): bump `version` in `manifest.json` and
  `PLUGIN_VERSION` in `Model.js` together (tests enforce they match), update
  `CHANGELOG.md`, commit, then push an annotated tag `vX.Y.Z`.
- Match the existing style: concise code, no speculative abstractions, no
  comments unless they earn their place.
- Do not commit secrets (never `COROS_EMAIL` / `COROS_PASSWORD`, never the
  token cache), and do not touch `__pycache__/` or `.ruff_cache/`.
- One-shot `coros.py` commands print exactly one JSON object on stdout; the
  QML side parses that one line. `coros.py watch` is the exception: it streams
  NDJSON state lines on stdout. No pip installs, ever.

## Scope notes

- Sign-in lives in the panel, not `setup.sh`. `coros.py login` reads
  `{email,password,region}` JSON from stdin (password never on argv), writes
  `~/.config/omarchy-coros/credentials` (0600), and prints a snapshot.
  `setup.sh` is install plumbing (python check, optional symlink); it must
  never print a password. `uninstall` must only remove files this plugin
  wrote (dev symlink, credentials file, token cache).
- Settings keys in `manifest.json` `barWidget.schema` must stay in sync with
  the QML that reads them (`refreshIntervalSec`, `region`,
  `hideWhenNoData`).
- `coros.py snapshot` prints `{"hrv":42,"hrvBaseline":45,"rhr":48,"load":85,
  "sleepH":7.2,"activity":"Run 10k","error":null}`. Metrics are null when
  missing; `error` is null, "auth" (bad/missing login — widget shows the
  setup hint, polls back off for an hour), or "network". Never a non-zero
  exit for display. Credentials: env wins, credentials file is the fallback.
  QML polls `coros.py snapshot` and honors `refreshIntervalSec` /
  `hideWhenNoData`.
