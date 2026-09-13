# Changelog

## 0.1.0 - Unreleased

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
