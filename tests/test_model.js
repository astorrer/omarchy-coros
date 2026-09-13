const fs = require("fs")
const path = require("path")

const source = fs
  .readFileSync(path.join(__dirname, "..", "Model.js"), "utf8")
  .replace(/\.pragma library\s*/, "")

const Model = new Function(
  source +
    "; return { parseSnapshot, hrvDelta, isEmpty, authError, signedIn, formatDelta, regionLabel, formatDay, loadStateLabel, fatigueStateLabel, metricRows, validBarMetric, formatBar, clampRefreshMinutes, formatRefreshLabel, formatSnapshot, formatTooltip, PLUGIN_VERSION, REFRESH_MIN_MINUTES, REFRESH_MAX_MINUTES, REFRESH_DEFAULT_MINUTES, REFRESH_STEP_MINUTES }"
)()

let failures = 0
function check(actual, expected, message) {
  const ok = JSON.stringify(actual) === JSON.stringify(expected)
  if (!ok) {
    failures += 1
    console.error(`FAIL ${message}: got ${JSON.stringify(actual)}, want ${JSON.stringify(expected)}`)
  }
}

const snap = {
  hrv: 24,
  hrvBaseline: 26,
  hrvBandLow: 22,
  hrvBandHigh: 30,
  rhr: 61,
  testRhr: 64,
  load: 0,
  load7d: 24,
  load28d: 238,
  loadRatio: 0.16,
  loadState: 1,
  loadWeek: 18,
  loadWeekMin: 210,
  loadWeekMax: 315,
  ati: 5,
  cti: 30,
  balance: 25,
  fatigue: -25,
  fatigueState: 1,
  activity: "Eagle Mountain E-Mountain Bike",
  activityDay: "2026-09-07",
  day: "2026-09-10",
  error: null
}

check(/^\d+\.\d+\.\d+$/.test(Model.PLUGIN_VERSION), true, "PLUGIN_VERSION is semver")
check(Model.signedIn(snap), true, "signedIn ok")
check(Model.signedIn({ error: "auth" }), false, "signedIn auth error")
check(Model.authError({ error: "auth" }), true, "authError")
check(Model.REFRESH_MIN_MINUTES, 15, "refresh min")
check(Model.REFRESH_MAX_MINUTES, 1440, "refresh max")
check(Model.REFRESH_DEFAULT_MINUTES, 30, "refresh default")
check(Model.REFRESH_STEP_MINUTES, 15, "refresh step")
check(Model.clampRefreshMinutes(1), 15, "clamp floors to 15")
check(Model.clampRefreshMinutes(2000), 1440, "clamp caps at 24h")
check(Model.clampRefreshMinutes(37), 30, "clamp snaps to step")
check(Model.formatRefreshLabel(30), "Refresh every 30 min", "label minutes")
check(Model.formatRefreshLabel(1440), "Refresh every 24 h", "label hours")
check(Model.regionLabel("us"), "US", "regionLabel us")
check(Model.regionLabel("eu"), "EU", "regionLabel eu")
check(Model.formatDelta(-2), "-2", "formatDelta negative")
check(Model.formatDelta(3.2), "+3", "formatDelta positive")
check(Model.loadStateLabel(1), "Recovering", "loadState recovering")
check(Model.fatigueStateLabel(1), "Fresh", "fatigueState fresh")
check(Model.formatSnapshot(snap), "HRV 24", "bar is compact HRV")
check(Model.formatSnapshot({ error: "auth" }), "", "bar empty on auth error")
check(Model.formatSnapshot({ hrv: null, rhr: 61, load: 0, error: null }), "RHR 61", "bar falls back to RHR")
check(Model.formatDay("2026-09-10"), "Sep 10", "formatDay iso")
check(Model.formatDay(20260907), "Sep 7", "formatDay yyyymmdd")
check(
  Model.formatTooltip(snap),
  "COROS — Sep 10 · HRV 24 (-2) · RHR 61 · Load 0 · 7d 24 · Fresh · Eagle Mountain E-Mountain Bike (Sep 7)",
  "tooltip lists details"
)
check(Model.formatTooltip({ error: "auth" }), "COROS — sign in from the panel", "tooltip auth")
check(Model.isEmpty({ hrv: null, hrvBaseline: null, rhr: null, load: null, activity: null, error: null }), true, "isEmpty")
check(Model.isEmpty(snap), false, "isEmpty with data")

const rows = Model.metricRows(snap)
check(rows[0], { label: "Resting HR", value: "61" }, "row rhr")
check(rows[1], { label: "Test RHR", value: "64" }, "row test rhr")
check(rows[2], { label: "Impact balance", value: "25" }, "row balance")
check(rows[3], { label: "Fatigue", value: "-25 · Fresh" }, "row fatigue")
check(rows[4], { label: "Daily load", value: "0" }, "row daily load zero")
check(rows[7], { label: "Load ratio", value: "0.16 · Recovering" }, "row load ratio")
check(rows[8], { label: "This week", value: "18 · rec 210–315" }, "row week")
check(Model.validBarMetric("ICON"), "icon", "validBarMetric icon")
check(Model.validBarMetric("nope"), "hrv", "validBarMetric fallback")
check(Model.formatBar(snap, "icon"), "", "formatBar icon is empty")
check(Model.formatBar(snap, "rhr"), "RHR 61", "formatBar rhr")
check(Model.formatBar(snap, "fatigue"), "Fresh", "formatBar fatigue")
check(Model.metricRows(snap, { recovery: false, load: false, activity: true }).length, 1, "rows activity only")
check(Model.metricRows(snap, { recovery: true, load: false, activity: false })[0].label, "Resting HR", "rows recovery only")

const parsed = Model.parseSnapshot(JSON.stringify(snap))
check(parsed.hrv, 24, "parseSnapshot hrv")
check(parsed.balance, 25, "parseSnapshot balance")
check(parsed.activity, "Eagle Mountain E-Mountain Bike", "parseSnapshot activity")

if (failures > 0) {
  console.error(`${failures} model checks failed`)
  process.exit(1)
}
console.log("model ok")
