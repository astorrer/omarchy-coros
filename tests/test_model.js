const fs = require("fs")
const path = require("path")

const source = fs
  .readFileSync(path.join(__dirname, "..", "Model.js"), "utf8")
  .replace(/\.pragma library\s*/, "")

const Model = new Function(
  source +
    "; return { parseSnapshot, hrvDelta, isEmpty, authError, networkError, signedIn, formatDelta, regionLabel, validRegion, formatDay, loadStateLabel, fatigueStateLabel, metricRows, metricGroups, validBarMetric, formatBar, clampRefreshMinutes, refreshIntervalMinutes, formatRefreshLabel, formatSnapshot, formatTooltip, settingValue, loginPayload, snapshotArgs, PLUGIN_VERSION, REFRESH_MIN_MINUTES, REFRESH_MAX_MINUTES, REFRESH_DEFAULT_MINUTES, REFRESH_STEP_MINUTES, HELPER_INTERPRETER, HELPER_SYSTEM_PATH, helperEnvironment, ICON, activityIcon, fatigueIcon, hrvRange, formatTick, hrvTone, fatigueTone, loadTone, weekTone, heroMood, heroPhrases, formatRace, formatRaceShort, bestRace, RACE_ORDER, readinessTone, readinessStep, readinessIcon, recoveryEtaText }"
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
check(Model.signedIn({ error: "network" }), false, "signedIn network error")
check(Model.authError({ error: "auth" }), true, "authError")
check(Model.authError({ error: "network" }), false, "authError not network")
check(Model.networkError({ error: "network" }), true, "networkError")
check(Model.networkError({ error: "auth" }), false, "networkError not auth")
check(Model.networkError(null), false, "networkError null")
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
check(Model.validRegion("eu"), "eu", "validRegion eu")
check(Model.validRegion("us"), "us", "validRegion us")
check(Model.validRegion("US"), "us", "validRegion upcase")
check(Model.validRegion(" eu "), "eu", "validRegion trims")
check(Model.validRegion(""), "eu", "validRegion empty")
check(Model.validRegion(undefined), "eu", "validRegion undefined")
check(Model.validRegion(null), "eu", "validRegion null")
check(Model.validRegion("asia"), "eu", "validRegion garbage")
check(Model.refreshIntervalMinutes("30", ""), 30, "refresh from min string")
check(Model.refreshIntervalMinutes("37", ""), 30, "refresh min snapped to step")
check(Model.refreshIntervalMinutes("abc", "3600"), 60, "refresh falls back to sec")
check(Model.refreshIntervalMinutes("", "45"), 15, "refresh sec rounds up to a minute")
check(Model.refreshIntervalMinutes("", ""), 30, "refresh sec absent defaults")
check(Model.refreshIntervalMinutes("abc", "def"), 30, "refresh both invalid defaults")
check(Model.refreshIntervalMinutes("-5", ""), 15, "refresh negative clamps")
check(Model.refreshIntervalMinutes("0", ""), 15, "refresh zero clamps")
check(Model.refreshIntervalMinutes("", "0"), 30, "refresh sec zero defaults")
check(Model.formatDelta(-2), "-2", "formatDelta negative")
check(Model.formatDelta(3.2), "+3", "formatDelta positive")
check(Model.loadStateLabel(1), "Recovering", "loadState recovering")
check(Model.fatigueStateLabel(1), "Fresh", "fatigueState fresh")
check(Model.formatSnapshot(snap), "HRV 24", "bar is compact HRV")
check(Model.formatSnapshot({ error: "auth" }), "", "bar empty on auth error")
check(Model.formatSnapshot({ error: "network", hrv: 24 }), "", "bar empty on network error")
check(Model.formatSnapshot({ hrv: null, rhr: 61, load: 0, error: null }), "RHR 61", "bar falls back to RHR")
check(Model.formatDay("2026-09-10"), "Sep 10", "formatDay iso")
check(Model.formatDay(20260907), "Sep 7", "formatDay yyyymmdd")
check(
  Model.formatTooltip(snap),
  "COROS — Sep 10 · HRV 24 (-2) · RHR 61 · Load 0 · 7d 24 · Fresh · Eagle Mountain E-Mountain Bike (Sep 7)",
  "tooltip lists details"
)
check(Model.formatTooltip({ error: "auth" }), "COROS — sign in from the panel", "tooltip auth")
check(Model.formatTooltip({ error: "network" }), "COROS — can't reach Training Hub", "tooltip network")
check(Model.formatTooltip({ error: "network", hrv: 24 }), "COROS — can't reach Training Hub", "tooltip network ignores metrics")
check(Model.isEmpty({ hrv: null, hrvBaseline: null, rhr: null, load: null, activity: null, error: null }), true, "isEmpty")
check(Model.isEmpty(snap), false, "isEmpty with data")
check(Model.isEmpty({ error: "network" }), false, "isEmpty network is not hideable")
check(Model.isEmpty({ hrv: null, hrvBaseline: null, rhr: null, load: null, load7d: null, fatigue: null, activity: null, error: "network" }), false, "isEmpty network with null metrics")

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
check(rows[3].label, "Daily", "row daily load")
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
check(Model.heroMood({ error: "network" }), "idle", "network is idle")
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
check(Model.formatBar({ error: "network", hrv: 24 }, "hrv"), "", "formatBar empty on network")
check(Model.metricRows(snap, { recovery: false, load: false, activity: true }).length, 1, "rows activity only")
check(Model.metricRows(snap, { recovery: true, load: false, activity: false })[0].label, "Resting HR", "rows recovery only")

const parsed = Model.parseSnapshot(JSON.stringify(snap))
check(parsed.hrv, 24, "parseSnapshot hrv")
check(parsed.balance, 25, "parseSnapshot balance")
check(parsed.activity, "Eagle Mountain E-Mountain Bike", "parseSnapshot activity")
check(parsed.error, null, "parseSnapshot null error")
check(Model.parseSnapshot("{"), null, "parseSnapshot invalid json")
check(Model.parseSnapshot("[]"), null, "parseSnapshot array")
check(Model.parseSnapshot("null"), null, "parseSnapshot null")
check(Model.parseSnapshot('{"error":"network"}').error, "network", "parseSnapshot network error")
check(Model.parseSnapshot('{"error":"auth"}').error, "auth", "parseSnapshot auth error")
check(Model.parseSnapshot('{"error":"timeout"}').error, "network", "parseSnapshot unknown string error")
check(Model.parseSnapshot('{"error":1}').error, null, "parseSnapshot non-string error")
check(Model.parseSnapshot('{"error":null}').error, null, "parseSnapshot json null error")
check(Model.parseSnapshot('{"hrv":24,"error":"network"}').hrv, 24, "parseSnapshot keeps metrics with network")

check(Model.settingValue({}, "region", "eu"), "eu", "settingValue missing uses fallback")
check(Model.settingValue({ region: "us" }, "region", "eu"), "us", "settingValue present wins")
check(Model.settingValue({ region: null }, "region", "eu"), "eu", "settingValue null uses fallback")
check(Model.settingValue({ region: undefined }, "region", "eu"), "eu", "settingValue undefined uses fallback")
check(Model.settingValue({ hideWhenNoData: false }, "hideWhenNoData", true), false, "settingValue keeps falsy")
check(Model.settingValue(null, "region", "eu"), "eu", "settingValue no settings uses fallback")

const longEmail = "a".repeat(300)
const longPass = "p".repeat(2000)
const emailClamped = Model.loginPayload(longEmail, "pass", "eu")
check(JSON.parse(emailClamped).email.length, 254, "loginPayload clamps email to 254 chars")
check(JSON.parse(emailClamped).email, "a".repeat(254), "loginPayload email exact clamp")
check(JSON.parse(Model.loginPayload("a@b.c", longPass, "eu")).password.length, 1024, "loginPayload clamps password to 1024 chars")
check(JSON.parse(Model.loginPayload("a@b.c", "p", "US")).region, "us", "loginPayload normalizes region")
check(Model.loginPayload("a@b.c", "p", "US"), '{"email":"a@b.c","password":"p","region":"us"}\n', "loginPayload exact json with newline")
check(Model.loginPayload(undefined, undefined, ""), '{"email":"","password":"","region":"eu"}\n', "loginPayload empty creds")
check(Model.loginPayload("a@b.c", "p", "eu"), '{"email":"a@b.c","password":"p","region":"eu"}\n', "loginPayload eu region")
check(Model.snapshotArgs("/opt/omarchy/coros.py", "eu"), [Model.HELPER_INTERPRETER, "/opt/omarchy/coros.py", "snapshot", "--region", "eu"], "snapshotArgs")
check(Model.snapshotArgs("coros.py", "us"), [Model.HELPER_INTERPRETER, "coros.py", "snapshot", "--region", "us"], "snapshotArgs us region")
check(Model.HELPER_INTERPRETER, "/usr/bin/python3", "helper interpreter is fixed path")
check(Model.HELPER_SYSTEM_PATH, "/usr/local/bin:/usr/bin", "helper PATH is fixed")
check(Model.helperEnvironment("/h", "/c", "/cfg"), { PATH: Model.HELPER_SYSTEM_PATH, HOME: "/h", XDG_CACHE_HOME: "/c", XDG_CONFIG_HOME: "/cfg" }, "helperEnvironment passes XDG bases")
check(Model.helperEnvironment("/h", null, ""), { PATH: Model.HELPER_SYSTEM_PATH, HOME: "/h" }, "helperEnvironment omits empty XDG")

check(Model.parseSnapshot(""), null, "parseSnapshot empty raw")
check(Model.parseSnapshot('{"error":""}').error, null, "parseSnapshot blank error is null")
check(Model.parseSnapshot('{"hrv":"abc"}').hrv, null, "num non-numeric is null")
check(Model.parseSnapshot('{"activity":"  "}').activity, null, "str whitespace is null")
check(Model.formatDay(""), "", "formatDay empty is blank")
check(Model.formatDay("2026-13-01"), "", "formatDay invalid month blank")
check(Model.hrvDelta(null, 26), null, "hrvDelta null hrv")
check(Model.hrvDelta(24, null), null, "hrvDelta null baseline")
check(Model.isEmpty(null), true, "isEmpty null snapshot")
check(Model.isEmpty(42), true, "isEmpty non-object snapshot")
check(Model.loadStateLabel(null), "", "loadStateLabel unknown is empty")
check(Model.fatigueStateLabel(null), "", "fatigueStateLabel unknown is empty")
check(Model.fatigueIcon(99), Model.ICON.battery50, "fatigueIcon unknown falls back")
check(Model.activityIcon(null), Model.ICON.activity, "activityIcon empty falls back")
check(Model.activityIcon("Paddle Boarding"), Model.ICON.activity, "activityIcon unknown falls back")
check(Model.formatTick(null), "", "formatTick null is blank")
check(Model.hrvRange(null), null, "hrvRange null snapshot")
check(Model.hrvRange({ hrv: 24 }), null, "hrvRange missing bands")
check(Model.hrvTone(null), "neutral", "hrvTone missing range is neutral")
check(Model.fatigueTone(null), "neutral", "fatigueTone empty is neutral")
check(Model.fatigueTone(3), "neutral", "fatigueTone mid is neutral")
check(Model.loadTone(5), "bad", "loadTone overreach is bad")
check(Model.loadTone(3), "good", "loadTone maintaining is good")
check(Model.weekTone(null, 210, 315), "neutral", "weekTone null pos is neutral")
check(Model.weekTone(250, 210, 315), "good", "weekTone in range is good")
check(Model.heroPhrases({ error: "auth" }), [], "heroPhrases idle is empty")
check(Model.validBarMetric(undefined), "hrv", "validBarMetric undefined falls back")
check(Model.validBarMetric(null), "hrv", "validBarMetric null falls back")
check(Model.formatDelta(null), "", "formatDelta null is blank")
check(Model.formatDelta(undefined), "", "formatDelta undefined is blank")
check(Model.regionLabel(null), "EU", "regionLabel empty is EU")
check(Model.clampRefreshMinutes("abc"), 30, "clamp non-number defaults")
check(Model.refreshIntervalMinutes("", "20"), 15, "refresh sec sub-minute floors to 15")
check(Model.formatSnapshot({ hrv: null, rhr: null, load: 0, error: null }), "Load 0", "formatSnapshot load")
check(Model.formatSnapshot({ hrv: null, rhr: null, load: null, error: null }), "", "formatSnapshot no data")
check(Model.formatBar(snap, "hrv"), "HRV 24", "formatBar hrv")
check(Model.formatBar(snap, "load"), "Load 0", "formatBar load")
check(Model.formatBar({ hrv: null, rhr: 61, load: 0, error: null }, "hrv"), "RHR 61", "formatBar falls through to snapshot")
check(Model.formatBar({ hrv: null, rhr: null, load: null, fatigueState: null, fatigue: 25, error: null }, "fatigue"), "25", "formatBar fatigue numeric fallback")
check(Model.formatBar({ hrv: 24, error: null }, "nope"), "HRV 24", "formatBar unknown metric normalizes")
check(Model.formatBar({ hrv: Symbol("x") }, "hrv"), "", "formatBar protects against throw")
check(Model.formatSnapshot({ hrv: Symbol("x") }), "", "formatSnapshot protects against throw")
check(Model.formatTooltip(null), "COROS", "tooltip null snapshot")
check(Model.formatTooltip({ day: null, hrv: null, rhr: null, load: null, load7d: null, fatigueState: null, activity: null, error: null }), "COROS", "tooltip no data")
check(Model.formatTooltip({ activity: "Morning Run", error: null, hrv: null, rhr: null, load: null, load7d: null, fatigueState: null, day: null }), "COROS — Morning Run", "tooltip activity without day")
check(Model.formatTooltip({ hrv: Symbol("x") }), "COROS", "tooltip protects against throw")

check(Model.metricGroups(null), { recovery: [], load: [], bars: [], activity: [], today: [], predict: [] }, "metricGroups unsigned is empty")
check(Model.metricGroups({ error: "auth" }), { recovery: [], load: [], bars: [], activity: [], today: [], predict: [] }, "metricGroups auth is empty")
let noRatio = {
  error: null, hrvBandLow: null, hrvBandHigh: null, hrv: null, hrvBaseline: null, testRhr: null,
  rhr: 61, balance: 0, fatigue: 25, fatigueState: null, load: 3, load7d: 24, load28d: 238,
  loadRatio: null, loadState: null, loadWeek: null, ati: null, cti: null, activity: null, activityDay: null, day: null
}
let gNoRatio = Model.metricGroups(noRatio)
check(gNoRatio.recovery.length, 3, "groups recovery rows with empty fatigue label")
check(gNoRatio.recovery[1].value, "25", "groups fatigue falls back to numeric")
check(gNoRatio.load.length, 2, "groups ratio-null drops ratio row")
check(gNoRatio.bars.length, 0, "groups ratio-null no bars")
let mutedRatio = {
  error: null, rhr: null, fatigueState: null, fatigue: null, balance: null, load: 3,
  load7d: null, load28d: null, loadRatio: 0.5, loadState: null, loadWeek: null, ati: null,
  cti: null, activity: null, activityDay: null, day: null
}
let gMuted = Model.metricGroups(mutedRatio)
check(gMuted.load.length, 1, "groups ratio-null load only today")
check(gMuted.bars.length, 1, "groups ratio row with no label")
check(gMuted.bars[0].value, "0.50", "groups ratio value without label")
let only7 = {
  error: null, rhr: null, fatigueState: null, fatigue: null, balance: null, load: 3,
  load7d: 24, load28d: null, loadRatio: 0.8, loadState: 1, loadWeek: null, loadWeekMin: null,
  loadWeekMax: null, ati: null, cti: null, activity: null, activityDay: null, day: null
}
let gOnly7 = Model.metricGroups(only7)
check(gOnly7.load[1].id, "load7d", "groups 7-day only row")
let only28 = {
  error: null, rhr: null, fatigueState: null, fatigue: null, balance: null, load: 3,
  load7d: null, load28d: 238, loadRatio: 0.8, loadState: 1, loadWeek: null, loadWeekMin: null,
  loadWeekMax: null, ati: null, cti: null, activity: null, activityDay: null, day: null
}
let gOnly28 = Model.metricGroups(only28)
check(gOnly28.load[1].id, "load28d", "groups 28-day only row")
let noDay = {
  error: null, rhr: null, fatigueState: 1, fatigue: null, balance: null, load: null,
  load7d: null, load28d: null, loadRatio: null, loadState: null, loadWeek: null, ati: null,
  cti: null, activity: "Morning Run", activityDay: undefined, day: null
}
let gNoDay = Model.metricGroups(noDay)
check(gNoDay.activity.length, 1, "groups activity row without day")
check(gNoDay.activity[0].label, "Last activity", "groups activity without day")

const todaySnap = {
  hrv: 24, hrvBaseline: 26, hrvBandLow: 22, hrvBandHigh: 30, rhr: 61, testRhr: 64,
  load: 40, load7d: 24, load28d: 238, loadRatio: 0.8, loadState: 2, loadWeek: 18,
  loadWeekMin: 210, loadWeekMax: 315, ati: 5, cti: 30, balance: 25, fatigue: -25, fatigueState: 1,
  readiness: 82, recoveryHours: 6.5, race5k: 1172, race10k: 2458, raceHalf: 5464, raceMarathon: 12084,
  plan: "Tempo Run", planKm: 8, planMin: 46,
  activity: "Run 10k", activityDay: "2026-09-07", day: "2026-09-10", error: null
}

check(Model.formatRace(1172), "19:32", "formatRace minutes")
check(Model.formatRace(2458), "40:58", "formatRace just under an hour")
check(Model.formatRace(5464), "1:31:04", "formatRace over an hour")
check(Model.formatRace(12084), "3:21:24", "formatRace marathon")
check(Model.formatRace(null), "", "formatRace null")
check(Model.formatRace(0), "", "formatRace zero")
check(Model.formatRace(-5), "", "formatRace negative")
check(Model.formatRaceShort(1172), "19:32", "formatRaceShort minutes")
check(Model.formatRaceShort(2458), "40:58", "formatRaceShort seconds kept")
check(Model.formatRaceShort(5464), "1:31", "formatRaceShort hour minutes")
check(Model.formatRaceShort(12084), "3:21", "formatRaceShort marathon")
check(Model.formatRaceShort(null), "", "formatRaceShort null")
check(Model.bestRace(todaySnap).spec.short, "M", "bestRace prefers the marathon")
check(Model.bestRace({ race5k: 1172, error: null }).spec.short, "5K", "bestRace falls back to 5K")
check(Model.bestRace({ raceHalf: 5464, error: null }).spec.short, "HM", "bestRace half")
check(Model.bestRace({ error: null }), null, "bestRace none")
check(Model.bestRace(null), null, "bestRace null snapshot")
check(Model.readinessTone(82), "good", "readinessTone good")
check(Model.readinessTone(75), "good", "readinessTone good edge")
check(Model.readinessTone(40), "bad", "readinessTone bad edge")
check(Model.readinessTone(41), "neutral", "readinessTone neutral")
check(Model.readinessTone(null), "neutral", "readinessTone null")
check(Model.readinessStep(82), 5, "readinessStep full")
check(Model.readinessStep(1), 1, "readinessStep floor is one dot")
check(Model.readinessStep(0), 1, "readinessStep zero still one dot")
check(Model.readinessStep(100), 5, "readinessStep caps at five")
check(Model.readinessStep(null), 0, "readinessStep null is zero")
check(Model.readinessIcon(82), Model.ICON.batteryFull, "readinessIcon full")
check(Model.readinessIcon(79), Model.ICON.battery80, "readinessIcon eighty")
check(Model.readinessIcon(60), Model.ICON.battery80, "readinessIcon eighty edge")
check(Model.readinessIcon(59), Model.ICON.battery50, "readinessIcon fifty")
check(Model.readinessIcon(40), Model.ICON.battery50, "readinessIcon fifty edge")
check(Model.readinessIcon(20), Model.ICON.battery20, "readinessIcon twenty")
check(Model.readinessIcon(19), Model.ICON.batteryEmpty, "readinessIcon empty")
check(Model.readinessIcon(null), Model.ICON.battery50, "readinessIcon null")
check(Model.recoveryEtaText(null), "", "recoveryEta null")
check(Model.recoveryEtaText(0), "Fully recovered", "recoveryEta zero is done")
check(Model.recoveryEtaText(-1), "Fully recovered", "recoveryEta negative is done")
check(Model.recoveryEtaText(0.5), "Full in 30 min", "recoveryEta sub-hour minutes")
check(Model.recoveryEtaText(0.01), "Full in 1 min", "recoveryEta tiny is one minute")
check(Model.recoveryEtaText(1), "Full in 1 h", "recoveryEta whole hour")
check(Model.recoveryEtaText(6.5), "Full in 6½ h", "recoveryEta half")
check(Model.recoveryEtaText(6.25), "Full in 6¼ h", "recoveryEta quarter")
check(Model.recoveryEtaText(6.75), "Full in 6¾ h", "recoveryEta three quarters")
check(Model.recoveryEtaText(6.9), "Full in 7 h", "recoveryEta rounds up")
check(Model.recoveryEtaText(2), "Full in 2 h", "recoveryEta two hours")

let gToday = Model.metricGroups(todaySnap)
check(gToday.today.length, 2, "today tiles plan and readiness")
check(gToday.today[0].id, "plan", "today plan id")
check(gToday.today[0].label, "Today's plan", "today plan label")
check(gToday.today[0].value, "Tempo Run · 8 km · 46 min", "today plan value")
check(gToday.today[0].icon, Model.ICON.activity, "today plan icon from name")
check(gToday.today[1].id, "readiness", "today readiness id")
check(gToday.today[1].value, "82%", "today readiness value")
check(gToday.today[1].hint, "Full in 6½ h", "today readiness hint is the eta")
check(gToday.today[1].step, 5, "today readiness step")
check(gToday.today[1].tone, "good", "today readiness tone")
check(gToday.today[1].lo, 0, "today readiness range lo")
check(gToday.today[1].hi, 100, "today readiness range hi")
check(gToday.today[1].pos, 82, "today readiness pos")
check(gToday.predict.length, 4, "predict tiles")
check(gToday.predict[0].label, "5K", "predict 5k label")
check(gToday.predict[0].value, "19:32", "predict 5k value")
check(gToday.predict[1].value, "40:58", "predict 10k value")
check(gToday.predict[2].value, "1:31:04", "predict half value")
check(gToday.predict[3].label, "Marathon", "predict marathon label")
check(gToday.predict[3].value, "3:21:24", "predict marathon value")
check(gToday.predict[3].icon, Model.ICON.activity, "predict uses the run glyph")
let gMutedToday = Model.metricGroups(todaySnap, { today: false })
check(gMutedToday.today.length, 0, "today group mutes")
check(gMutedToday.predict.length, 4, "predict stays on")
let gBarePlan = Model.metricGroups({ plan: "Easy Jog", error: null })
check(gBarePlan.today.length, 1, "plan without extras still shows")
check(gBarePlan.today[0].value, "Easy Jog", "plan value bare")
let gNoHours = Model.metricGroups({ readiness: 55, error: null })
check(gNoHours.today[0].hint, "", "readiness without hours has no hint")
let gPartialRaces = Model.metricGroups({ race10k: 2458, raceMarathon: 12084, error: null })
check(gPartialRaces.predict.length, 2, "predict only known races")
check(gPartialRaces.predict[1].id, "raceMarathon", "predict keeps race order")

let todayRows = Model.metricRows(todaySnap)
check(todayRows.length, 15, "rows include today and predict")
check(todayRows[0].id, "plan", "rows plan first")
check(todayRows[1].id, "readiness", "rows readiness second")
check(todayRows[2].label, "Resting HR", "rows recovery follows")
check(todayRows[10].id, "race5k", "rows predict after bars")
check(todayRows[14].id, "activity", "rows activity last")
check(Model.metricRows(todaySnap, { today: false }).length, 13, "rows honor today gate")

check(Model.validBarMetric("readiness"), "readiness", "validBarMetric readiness")
check(Model.validBarMetric("RACE"), "race", "validBarMetric race")
check(Model.formatBar(todaySnap, "readiness"), "Ready 82%", "formatBar readiness")
check(Model.formatBar(todaySnap, "race"), "M 3:21", "formatBar race marathon")
check(Model.formatBar({ race5k: 1172, error: null }, "race"), "5K 19:32", "formatBar race 5k fallback")
check(Model.formatBar({ raceHalf: 5464, error: null }, "race"), "HM 1:31", "formatBar race half")
check(Model.formatBar({ hrv: 24, error: null }, "race"), "HRV 24", "formatBar race falls through when empty")
check(Model.formatBar({ hrv: 24, error: null }, "readiness"), "HRV 24", "formatBar readiness falls through")

const parsedToday = Model.parseSnapshot(
  JSON.stringify({ readiness: 82, recoveryHours: 6.5, race5k: 1172, race10k: 2458, raceHalf: 5464, raceMarathon: 12084, plan: "Tempo Run", planKm: 8, planMin: 46, error: null })
)
check(parsedToday.readiness, 82, "parseSnapshot readiness")
check(parsedToday.recoveryHours, 6.5, "parseSnapshot recoveryHours")
check(parsedToday.race5k, 1172, "parseSnapshot race5k")
check(parsedToday.raceMarathon, 12084, "parseSnapshot raceMarathon")
check(parsedToday.plan, "Tempo Run", "parseSnapshot plan")
check(parsedToday.planKm, 8, "parseSnapshot planKm")
check(parsedToday.planMin, 46, "parseSnapshot planMin")
check(Model.parseSnapshot('{"plan":"  "}').plan, null, "parseSnapshot blank plan is null")
check(Model.parseSnapshot('{"plan":42}').plan, "42", "parseSnapshot stringifies plan")
check(Model.parseSnapshot('{"planKm":"8"}').planKm, 8, "parseSnapshot numeric string planKm")
check(Model.parseSnapshot('{"readiness":null,"plan":null,"raceMarathon":null}').readiness, null, "parseSnapshot null readiness")

check(Model.isEmpty({ hrv: null, hrvBaseline: null, rhr: null, load: null, load7d: null, fatigue: null, readiness: 82, raceMarathon: null, plan: null, activity: null, error: null }), false, "isEmpty readiness is data")
check(Model.isEmpty({ hrv: null, hrvBaseline: null, rhr: null, load: null, load7d: null, fatigue: null, readiness: null, raceMarathon: 12084, plan: null, activity: null, error: null }), false, "isEmpty race is data")
check(Model.isEmpty({ hrv: null, hrvBaseline: null, rhr: null, load: null, load7d: null, fatigue: null, readiness: null, raceMarathon: null, plan: "Tempo Run", activity: null, error: null }), false, "isEmpty plan is data")
check(Model.isEmpty({ hrv: null, hrvBaseline: null, rhr: null, load: null, load7d: null, fatigue: null, readiness: null, raceMarathon: null, plan: null, activity: null, error: null }), true, "isEmpty all null stays empty")

check(Model.heroPhrases(todaySnap).indexOf("Readiness 82%") >= 0, true, "hero readiness phrase")
check(Model.heroPhrases(todaySnap).indexOf("Today · Tempo Run 8 km") >= 0, true, "hero plan phrase")
check(Model.heroPhrases({ error: "auth" }), [], "heroPhrases idle stays empty")
check(Model.heroPhrases({ hrv: null, error: null }).length, 0, "heroPhrases empty snapshot no extras")

check(
  Model.formatTooltip(todaySnap),
  "COROS — Sep 10 · HRV 24 (-2) · RHR 61 · Load 40 · 7d 24 · Ready 82% · Full in 6½ h · Today Tempo Run 8 km · Fresh · Run 10k (Sep 7)",
  "tooltip includes readiness and plan"
)
check(
  Model.formatTooltip({ readiness: 82, recoveryHours: 0, error: null, day: null, hrv: null, rhr: null, load: null, load7d: null, fatigueState: null, activity: null }),
  "COROS — Ready 82% · Fully recovered",
  "tooltip readiness without eta tail"
)
check(Model.RACE_ORDER.length, 4, "race order covers the four distances")

if (failures > 0) {
  console.error(`${failures} model checks failed`)
  process.exit(1)
}
console.log("model ok")
