# omarchy-coros build plan

Omarchy bar-widget plugin that shows COROS recovery metrics (HRV, RHR,
sleep, training load) on the bar. Follows the omdeako pattern.

## Decisions (locked)

- Data source: unofficial Training Hub REST (`teameuapi` / `teamapi`), not MCP,
  not Partner API. Per-user self-login, nothing hosted.
- `coros.py`: stdlib only, no pip installs. One-shot commands print exactly one
  JSON object on stdout; `watch` streams NDJSON (omdeako contract).
- v1 metrics: whatever Training Hub `dayDetail` actually returns (HRV vs
  baseline and band, RHR / test RHR, daily and rolling load, load ratio,
  weekly target, acute/chronic, impact balance, fatigue) plus last activity.
  No mobile sleep API in v1 (AES login, 1h TTL, logs phone app out). `tib`
  is training impact balance, not time in bed.
- Auth: `POST /account/login {account, accountType:2, pwd: md5}`, token cached
  in `~/.cache/omarchy-coros/token.json` mode 0600, 24h TTL. Retry login on
  `1019`, try other region. Password never stored.

## Contract (branches must agree)

- `coros.py snapshot` prints:
  one JSON object from Training Hub `dayDetail` + last activity (see AGENTS.md
  for keys). Metrics null when missing. `error` is null, "auth" (polls back
  off 1h), or "network". Never an error exit for display.
- Settings keys (`manifest.json` schema): `refreshIntervalMin`, `region`
  (`eu`/`us`), `hideWhenNoData`. QML reads the same keys.
- Credentials: env `COROS_EMAIL`/`COROS_PASSWORD` wins;
  `~/.config/omarchy-coros/credentials` (0600, written by `coros.py login` from
  the panel, stdin JSON — never argv) is the fallback. Never in git, never
  echoed, never in widget settings.

## Branches (short-lived, merge to main)

- `feat/scaffold`: `manifest.json` (id `io.github.astorrer.omarchy-coros`),
  `AGENTS.md`, `README.md`, `LICENSE` (MIT), `.gitignore`, `setup.sh`
  (+ safe `uninstall`), `ruff.toml`, `tests/run`, `.github/workflows/test.yml`,
  `CHANGELOG.md`. No Python, no QML.
- `feat/api-client`: `coros.py` + `tests/test_coros.py` (mocked HTTP, no
  network). Owns only those two files.
- `feat/ui`: `BarWidget.qml`, `Panel.qml`, `Model.js` + QML/JS test hooks.
  Polls `coros.py snapshot`, honors `refreshIntervalMin`/`hideWhenNoData`.
  Owns only QML/JS files.

## Order

1. Land `feat/scaffold` first (contract files others import).
2. `feat/api-client` + `feat/ui` in parallel worktrees (file ownership above,
   no overlap).
3. `@security-review` (big-pickle, read-only) on the merged result before
   release. It does not take a branch.
4. Merge to `main`, bump `version` in `manifest.json`, update `CHANGELOG.md`.

## Verify per branch

```sh
ruff check .
./tests/run
```
