# Changelog

## Unreleased

- Trim marketplace publishing instructions from the README.

## 0.1.0 - 2026-09-12

- Initial scaffold: `manifest.json`, `setup.sh`, `tests/run`, CI, docs.
  `coros.py` (feat/api-client) and the QML UI (feat/ui) to follow.
- Fix panel sign-in hanging: close stdin after sending the login JSON so
  `coros.py login` is not left waiting for EOF.
- Follow COROS `regionId` from the login response so US Training Hub
  accounts are queried on `teamapi` even when the form defaulted to EU.
- Show the latest day that actually has HRV/RHR instead of today's still-empty
  row (overnight metrics often land a day late) or the oldest row in the list.
- Compact the bar to a single metric (HRV, else RHR, else load) using a
  text slot instead of stuffing a sentence into a 21px icon slot.
- Rebuild the panel: signed-in status, padded login fields, US/EU only on
  the sign-in form, and a two-column metric grid that elides instead of
  overlapping.
- Poll interval is in minutes (default 30, range 15 min–24 h, step 15).
  + is slower, − is faster. Overnight HRV does not justify a tighter loop.
- Snapshot and panel use Training Hub `dayDetail` fields: HRV band, test RHR,
  7/28-day load, load ratio, weekly target, acute/chronic, impact balance,
  and fatigue. Sleep duration is omitted (`tib` is not time in bed).
- Settings toggles for overnight / load / activity groups, and a bar display
  picker (COROS mark, HRV, RHR, load, or fatigue). The mark is the official
  COROS SVG, filled with the bar foreground.
- Size the bar's open-panel underline a bit longer than the default dash
  and keep it centered under the COROS mark. Text mode uses the caption
  width.
- Scroll the settings view so controls stay inside the panel. Settings
  uses one header (Settings / Back), groups Bar then Panel then Account,
  and puts the bar display, hide-when-empty, and refresh interval first.
  The card grows with the form (capped a little above the usual popup
  height) so the whole page fits without scrolling on a normal bar.
  Back and Refresh in the header are buttons, not ghost labels.
- Pair each recovery number with a Nerd Font glyph and a range or state
  meter so HRV, load, and fatigue sit against a band instead of a JSON
  dump. Overnight and load sit three-across (panel matches weather's
  width); ratio and weekly target keep the full width. Accent marks
  in-range / recovered, urgent marks below-band HRV or overreaching load.
  The hero is the COROS mark and name with rotating status snippets
  (Dropbox-style), then overnight / load contents. HRV sits in Overnight
  with its band, not in the title.
- Last-activity icon follows the workout name: bike, run, walk, hike,
  swim, surf, yoga, ski, snowboard, lift, soccer, basketball; anything
  else falls back to run. Trail Run stays a run.
- Metrics animate with the theme: the resting-HR glyph double-thumps, the
  fatigue dots breathe (faster when strained), and range fills/thumbs ease
  like the battery bar. Colors stay on accent / urgent / foreground.
  Long last-activity names marquee instead of eliding.
- Quality pass (wave 1): malformed Training Hub bodies are `network`, not
  an hour of auth cooldown. HTTPS redirects stay on teamapi/teameuapi.
  Credentials are documented as plaintext 0600 (needed for token refresh),
  written only after a good login, and ignored if world-readable. The
  token cache is an atomic replace. The panel uses Omarchy's single
  cursor (refresh/settings/settings form); login fields block the key
  catcher so typing works. Network failures show in the tooltip and
  status instead of "waiting on metrics".
- Poll/login live in `Service.qml` (bar keeps polling while the popup is
  closed). Settings has Sign out; `coros.py logout` deletes credentials,
  token cache, and cooldown. Uninstall honors XDG config/cache dirs.
- Hardening (security review analog): credentials are written through the
  same `O_NOFOLLOW` + fsync + atomic-replace path as the token cache, so a
  planted symlink at the predictable path cannot redirect the plaintext
  password, and `setup.sh` refuses a symlinked credentials file.
  `coros.py login` reads stdin under a 64 KiB budget (bounded first line,
  bounded fallback), the panel clamps email/password before the write, and
  a hung login is SIGKILLed after 60 s like the snapshot poll. Cooldown
  marker writes are no-follow and a symlinked cooldown is never honored.
- Agent instruction/dev files (`AGENTS.md`, `PLAN.md`, `opencode.json`,
  `.opencode/`) are untracked and gitignored so they never ship in the
  installed plugin tree.
- Coverage: `coros.py` (100% lines/branches) and `Model.js` (99.98% bytes)
  are unit-tested to 98%+ with a `tests/coverage` harness and a CI coverage
  gate. The QML layer's decision logic (region normalization, refresh-interval
  math, login-payload clamping) moved into `Model.js` so it is testable
  headlessly; `setup.sh` behavior is covered at the subprocess level.
