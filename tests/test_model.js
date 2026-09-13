const fs = require("fs")
const path = require("path")

const source = fs
  .readFileSync(path.join(__dirname, "..", "Model.js"), "utf8")
  .replace(/\.pragma library\s*/, "")

const Model = new Function(
  source +
    "; return { parseSnapshot, hrvDelta, isEmpty, authError, signedIn, formatDelta, regionLabel, formatDay, loadStateLabel, fatigueStateLabel, metricRows, metricGroups, validBarMetric, formatBar, clampRefreshMinutes, formatRefreshLabel, formatSnapshot, formatTooltip, PLUGIN_VERSION, REFRESH_MIN_MINUTES, REFRESH_MAX_MINUTES, REFRESH_DEFAULT_MINUTES, REFRESH_STEP_MINUTES, ICON, activityIcon, fatigueIcon, hrvRange, formatTick, hrvTone, fatigueTone, loadTone, weekTone, heroMood, heroPhrases }"
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
const grouped = Model.metricGroups(snap)
check(grouped.recovery.length, 3, "overnight tiles")
check(grouped.load.length, 3, "load tiles")
check(grouped.bars.length, 2, "load bars")
check(grouped.activity.length, 1, "activity row")
check(rows[0].label, "Resting HR", "row rhr label")
check(rows[0].value, "61", "row rhr value")
check(rows[0].icon, Model.ICON.rhr, "row rhr icon")
check(rows[0].hint, "test RHR 64", "test rhr folds into rhr")
check(rows[1].label, "Fatigue", "row fatigue")
check(rows[1].value, "Fresh", "row fatigue value is the state")
check(rows[1].icon, Model.ICON.batteryFull, "row fatigue icon full when fresh")
check(rows[1].tone, "good", "fresh is good")
check(rows[1].steps, 5, "row fatigue steps")
check(rows[1].step, 1, "row fatigue step")
check(rows[2].label, "Balance", "row balance")
check(rows[3].label, "Today", "row daily load")
check(rows[3].value, "0", "row daily load zero")
check(rows[4].label, "7 / 28 day", "rolling load combined")
check(rows[4].value, "24 · 238", "rolling load values")
check(rows[5].label, "Acute · chronic", "row acute")
check(rows[6].label, "Load ratio", "row load ratio")
check(rows[6].value, "0.16 · Recovering", "row load ratio value")
check(rows[6].lo, 0.8, "row load ratio lo")
check(rows[6].hi, 1.3, "row load ratio hi")
check(rows[6].tone, "neutral", "recovering is rest not alarm")
check(rows[7].label, "This week", "row week")
check(rows[7].value, "18", "row week value")
check(rows[7].lo, 210, "row week lo")
check(rows[7].tone, "neutral", "under weekly target is rest")
check(rows[8].icon, Model.ICON.bike, "activity icon from name")
check(rows[8].value, "Eagle Mountain E-Mountain Bike", "activity name as value")
check(rows[8].label, "Last activity · Sep 7", "activity day in label")
check(Model.hrvTone(snap), "good", "hrv in band is good")
check(Model.hrvTone({ hrv: 18, hrvBandLow: 22, hrvBandHigh: 30 }), "bad", "hrv below band is bad")
check(Model.hrvTone({ hrv: 33, hrvBandLow: 23, hrvBandHigh: 31, hrvBaseline: 27 }), "good", "hrv above band is good")
check(Model.weekTone(18, 210, 315), "neutral", "weekTone rest")
check(Model.weekTone(400, 210, 315), "bad", "weekTone over")
check(Model.fatigueTone(1), "good", "fatigueTone fresh")
check(Model.fatigueTone(5), "bad", "fatigueTone fatigued")
check(Model.heroMood(snap), "rest", "fresh recovering is rest")
check(Model.heroPhrases(snap).length > 0, true, "rest has snippets")
check(Model.heroMood({ error: "auth" }), "idle", "auth is idle")
check(
  Model.heroMood({ hrv: 18, hrvBandLow: 22, hrvBandHigh: 30, fatigueState: 1, loadState: 1, error: null }),
  "low",
  "below-band hrv is low"
)
check(
  Model.heroMood({ hrv: 24, hrvBandLow: 22, hrvBandHigh: 30, fatigueState: 1, loadState: 2, error: null }),
  "work",
  "productive load is work"
)
check(
  Model.heroMood({ hrv: 24, hrvBandLow: 22, hrvBandHigh: 30, fatigueState: 5, loadState: 1, error: null }),
  "strained",
  "fatigued is strained"
)
check(Model.activityIcon("Morning Run"), Model.ICON.activity, "run icon")
check(Model.activityIcon("Trail Run"), Model.ICON.activity, "trail run is run not hike")
check(Model.activityIcon("Pool Swim"), Model.ICON.swim, "swim icon")
check(Model.activityIcon("Open Water Swim"), Model.ICON.swim, "open water swim")
check(Model.activityIcon("Easy Walk"), Model.ICON.walk, "walk icon")
check(Model.activityIcon("Lunch Hike"), Model.ICON.hike, "hike icon")
check(Model.activityIcon("Yoga Flow"), Model.ICON.yoga, "yoga icon")
check(Model.activityIcon("Downhill Ski"), Model.ICON.ski, "ski icon")
check(Model.activityIcon("Resort Snowboard"), Model.ICON.snowboard, "snowboard before ski")
check(Model.activityIcon("Strength"), Model.ICON.lift, "lift icon")
check(Model.activityIcon("Indoor Cycling"), Model.ICON.bike, "cycling is bike")
check(Model.activityIcon("Basketball"), Model.ICON.basket, "basket icon")
check(Model.activityIcon("Pickup Soccer"), Model.ICON.soccer, "soccer icon")
check(Model.activityIcon("Morning Surf"), Model.ICON.surf, "surf icon")
check(Model.ICON.swim !== Model.ICON.activity, true, "swim is not the run fallback")
check(Model.ICON.walk !== Model.ICON.activity, true, "walk is not the run fallback")
check(Model.hrvRange(snap), { lo: 22, hi: 30, pos: 24, mark: 26 }, "hrvRange")
check(Model.formatTick(0.16), "0.16", "formatTick ratio")
check(Model.formatTick(18), "18", "formatTick int")
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
