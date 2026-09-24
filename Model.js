.pragma library

var PLUGIN_VERSION = "0.2.0"
var PROJECT_URL = "https://github.com/astorrer/omarchy-coros"
var REFRESH_MIN_MINUTES = 15
var REFRESH_MAX_MINUTES = 1440
var REFRESH_DEFAULT_MINUTES = 30
var REFRESH_STEP_MINUTES = 15

function parseJson(raw) {
  try {
    var parsed = JSON.parse(String(raw || "").trim())
    return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : null
  } catch (e) {
    return null
  }
}

function parseError(value) {
  if (typeof value !== "string") return null
  var s = value.trim()
  if (s === "auth" || s === "network") return s
  return s === "" ? null : "network"
}

function num(value) {
  if (value === null || value === undefined || value === "") return null
  var n = Number(value)
  return isFinite(n) ? n : null
}

function str(value) {
  if (value === null || value === undefined) return null
  var s = String(value).trim()
  return s !== "" ? s : null
}

// coros.py snapshot prints exactly one JSON object; missing data is null.
function parseSnapshot(raw) {
  var parsed = parseJson(raw)
  if (!parsed) return null
  return {
    hrv: num(parsed.hrv),
    hrvBaseline: num(parsed.hrvBaseline),
    hrvBandLow: num(parsed.hrvBandLow),
    hrvBandHigh: num(parsed.hrvBandHigh),
    rhr: num(parsed.rhr),
    testRhr: num(parsed.testRhr),
    load: num(parsed.load),
    load7d: num(parsed.load7d),
    load28d: num(parsed.load28d),
    loadRatio: num(parsed.loadRatio),
    loadState: num(parsed.loadState),
    loadWeek: num(parsed.loadWeek),
    loadWeekMin: num(parsed.loadWeekMin),
    loadWeekMax: num(parsed.loadWeekMax),
    ati: num(parsed.ati),
    cti: num(parsed.cti),
    balance: num(parsed.balance),
    fatigue: num(parsed.fatigue),
    fatigueState: num(parsed.fatigueState),
    readiness: num(parsed.readiness),
    recoveryHours: num(parsed.recoveryHours),
    race5k: num(parsed.race5k),
    race10k: num(parsed.race10k),
    raceHalf: num(parsed.raceHalf),
    raceMarathon: num(parsed.raceMarathon),
    plan: str(parsed.plan),
    planKm: num(parsed.planKm),
    planMin: num(parsed.planMin),
    activity: str(parsed.activity),
    activityDay: str(parsed.activityDay),
    day: str(parsed.day),
    error: parseError(parsed.error)
  }
}

function formatDay(value) {
  var raw = String(value || "").replace(/-/g, "")
  if (raw.length !== 8) return ""
  var months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
  var month = parseInt(raw.slice(4, 6), 10)
  var day = parseInt(raw.slice(6, 8), 10)
  if (month < 1 || month > 12 || day < 1 || day > 31) return ""
  return months[month - 1] + " " + day
}

function hrvDelta(hrv, baseline) {
  var h = num(hrv)
  var b = num(baseline)
  if (h === null || b === null) return null
  return h - b
}

function authError(snapshot) {
  return !!(snapshot && typeof snapshot === "object" && snapshot.error === "auth")
}

function networkError(snapshot) {
  return !!(snapshot && typeof snapshot === "object" && snapshot.error === "network")
}

function signedIn(snapshot) {
  return !!(snapshot && typeof snapshot === "object" && !authError(snapshot) && !networkError(snapshot))
}

function isEmpty(snapshot) {
  if (networkError(snapshot)) return false
  if (!snapshot || typeof snapshot !== "object") return true
  return num(snapshot.hrv) === null
    && num(snapshot.hrvBaseline) === null
    && num(snapshot.rhr) === null
    && num(snapshot.load) === null
    && num(snapshot.load7d) === null
    && num(snapshot.fatigue) === null
    && num(snapshot.readiness) === null
    && num(snapshot.raceMarathon) === null
    && str(snapshot.plan) === null
    && str(snapshot.activity) === null
}

// Nerd Font glyphs (Material Design). The number is not the point of
// reference — the icon, the band, and the state dots are.
var ICON = {
  hrv: "󰻹",
  rhr: "󰋑",
  test: "󰋕",
  balance: "󰗑",
  load: "󰄨",
  ratio: "󰊚",
  week: "󰄪",
  acute: "󰄪",
  activity: "󰜎",
  bike: "󰂣",
  swim: "󰘆",
  walk: "󰖃",
  hike: "󰵿",
  yoga: "󱅻",
  ski: "󱌄",
  snowboard: "󱌇",
  lift: "󱅝",
  surf: "󱝆",
  soccer: "󰒸",
  basket: "󰠆",
  batteryFull: "󰁹",
  battery80: "󰂂",
  battery50: "󰁿",
  battery20: "󰁼",
  batteryEmpty: "󰂃"
}

function loadStateLabel(state) {
  var labels = { 1: "Recovering", 2: "Productive", 3: "Maintaining", 4: "Overreaching", 5: "Excessive" }
  return labels[Number(state)] || ""
}

function fatigueStateLabel(state) {
  var labels = { 1: "Fresh", 2: "Recovered", 3: "Balanced", 4: "Tired", 5: "Fatigued" }
  return labels[Number(state)] || ""
}

function fatigueIcon(state) {
  var icons = { 1: ICON.batteryFull, 2: ICON.battery80, 3: ICON.battery50, 4: ICON.battery20, 5: ICON.batteryEmpty }
  return icons[Number(state)] || ICON.battery50
}

function activityIcon(name) {
  var s = String(name || "").toLowerCase()
  if (/snowboard/.test(s)) return ICON.snowboard
  if (/ski|snowshoe/.test(s)) return ICON.ski
  if (/yoga|pilates|stretch/.test(s)) return ICON.yoga
  if (/strength|weight|gym|lift|cross.?train/.test(s)) return ICON.lift
  if (/surf|kite.?surf/.test(s)) return ICON.surf
  if (/swim|pool|aqua/.test(s)) return ICON.swim
  if (/run|jog|treadmill/.test(s)) return ICON.activity
  if (/hike|backpack/.test(s)) return ICON.hike
  if (/walk/.test(s)) return ICON.walk
  if (/basket/.test(s)) return ICON.basket
  if (/soccer|football/.test(s)) return ICON.soccer
  if (/e-?mountain|e-?bike|gravel|cycl|bike|ride/.test(s)) return ICON.bike
  return ICON.activity
}

function withState(value, label) {
  if (value === null || value === undefined || value === "") return ""
  return label ? String(value) + " · " + label : String(value)
}

function formatRace(seconds) {
  var n = num(seconds)
  if (n === null || n <= 0) return ""
  n = Math.round(n)
  var h = Math.floor(n / 3600)
  var m = Math.floor((n % 3600) / 60)
  var s = n % 60
  var mm = (m < 10 ? "0" : "") + m
  var ss = (s < 10 ? "0" : "") + s
  return h > 0 ? h + ":" + mm + ":" + ss : m + ":" + ss
}

var RACE_ORDER = [
  { key: "race5k", label: "5K", short: "5K" },
  { key: "race10k", label: "10K", short: "10K" },
  { key: "raceHalf", label: "Half", short: "HM" },
  { key: "raceMarathon", label: "Marathon", short: "M" }
]

function bestRace(snapshot) {
  for (var i = RACE_ORDER.length - 1; i >= 0; i--) {
    var secs = num(snapshot ? snapshot[RACE_ORDER[i].key] : null)
    if (secs !== null && secs > 0) return { spec: RACE_ORDER[i], seconds: secs }
  }
  return null
}

function formatRaceShort(seconds) {
  var n = num(seconds)
  if (n === null || n <= 0) return ""
  n = Math.round(n)
  var h = Math.floor(n / 3600)
  var m = Math.floor((n % 3600) / 60)
  return h > 0 ? h + ":" + (m < 10 ? "0" : "") + m : m + ":" + (n % 60 < 10 ? "0" : "") + (n % 60)
}

function readinessTone(pct) {
  var n = num(pct)
  if (n === null) return "neutral"
  if (n >= 75) return "good"
  if (n <= 40) return "bad"
  return "neutral"
}

function readinessStep(pct) {
  var n = num(pct)
  return n === null ? 0 : Math.max(1, Math.min(5, Math.ceil(n / 20)))
}

function readinessIcon(pct) {
  var n = num(pct)
  if (n === null) return ICON.battery50
  if (n >= 80) return ICON.batteryFull
  if (n >= 60) return ICON.battery80
  if (n >= 40) return ICON.battery50
  if (n >= 20) return ICON.battery20
  return ICON.batteryEmpty
}

function recoveryEtaText(hours) {
  var n = num(hours)
  if (n === null) return ""
  if (n <= 0) return "Fully recovered"
  if (n < 1) return "Full in " + Math.max(1, Math.round(n * 60)) + " min"
  var whole = Math.floor(n)
  var frac = n - whole
  var tail = ""
  if (frac >= 0.125 && frac < 0.375) tail = "¼"
  else if (frac >= 0.375 && frac < 0.625) tail = "½"
  else if (frac >= 0.625 && frac < 0.875) tail = "¾"
  else if (frac >= 0.875) whole += 1
  return "Full in " + whole + tail + " h"
}

function formatTick(value) {
  var n = num(value)
  if (n === null) return ""
  if (Math.abs(n - Math.round(n)) < 0.005) return String(Math.round(n))
  return n.toFixed(2).replace(/0+$/, "").replace(/\.$/, "")
}

function hrvRange(snapshot) {
  if (!snapshot) return null
  var lo = num(snapshot.hrvBandLow)
  var hi = num(snapshot.hrvBandHigh)
  var pos = num(snapshot.hrv)
  if (lo === null || hi === null || pos === null) return null
  return { lo: lo, hi: hi, pos: pos, mark: num(snapshot.hrvBaseline) }
}

function hrvTone(snapshot) {
  var r = hrvRange(snapshot)
  if (!r) return "neutral"
  if (r.pos < r.lo) return "bad"
  return "good"
}

function fatigueTone(state) {
  var s = Number(state)
  if (!isFinite(s) || s <= 0) return "neutral"
  if (s <= 2) return "good"
  if (s >= 4) return "bad"
  return "neutral"
}

function loadTone(state) {
  var s = Number(state)
  if (s >= 4) return "bad"
  if (s === 2 || s === 3) return "good"
  return "neutral"
}

function weekTone(pos, lo, hi) {
  var p = num(pos), a = num(lo), b = num(hi)
  if (p === null || a === null || b === null) return "neutral"
  if (p > Math.max(a, b)) return "bad"
  if (p < Math.min(a, b)) return "neutral"
  return "good"
}

var HERO_PHRASES = {
  rest: [
    "Banking recovery",
    "Sleeping it off",
    "Resting easy",
    "Storing spark",
    "Hoarding heartbeats",
    "Coiling the spring"
  ],
  work: [
    "Putting in work",
    "Stacking strain",
    "Building the base",
    "Earning the miles",
    "Laying down load"
  ],
  strained: [
    "Digging deep",
    "Burning the match",
    "Running on fumes",
    "In the red",
    "Paying it back"
  ],
  low: [
    "Chasing the band",
    "Heart running quiet",
    "Need a night",
    "Pulse under par"
  ]
}

function heroMood(snapshot) {
  if (!signedIn(snapshot) || isEmpty(snapshot)) return "idle"
  var fat = num(snapshot.fatigueState)
  var load = num(snapshot.loadState)
  if (fat >= 4 || load >= 4) return "strained"
  if (hrvTone(snapshot) === "bad") return "low"
  if (load === 2 || load === 3) return "work"
  return "rest"
}

function heroPhrases(snapshot) {
  var phrases = (HERO_PHRASES[heroMood(snapshot)] || []).slice()
  if (!signedIn(snapshot) || isEmpty(snapshot)) return phrases
  var readiness = num(snapshot.readiness)
  if (readiness !== null) phrases.push("Readiness " + Math.round(readiness) + "%")
  var plan = str(snapshot.plan)
  if (plan) {
    var km = num(snapshot.planKm)
    phrases.push("Today · " + plan + (km !== null ? " " + km + " km" : ""))
  }
  return phrases
}

function metricRow(spec) {
  var value = spec.value
  if (value === null || value === undefined || value === "") return null
  return {
    id: spec.id || "",
    icon: spec.icon || "",
    label: spec.label,
    value: String(value),
    hint: spec.hint || "",
    lo: spec.lo !== undefined ? spec.lo : null,
    hi: spec.hi !== undefined ? spec.hi : null,
    pos: spec.pos !== undefined ? spec.pos : null,
    mark: spec.mark !== undefined ? spec.mark : null,
    steps: spec.steps || 0,
    step: spec.step || 0,
    tone: spec.tone || "neutral"
  }
}

function metricGroups(snapshot, groups) {
  var empty = { recovery: [], load: [], bars: [], activity: [], today: [], predict: [] }
  if (!signedIn(snapshot)) return empty
  var recoveryOn = !groups || groups.recovery !== false
  var loadOn = !groups || groups.load !== false
  var activityOn = !groups || groups.activity !== false
  var todayOn = !groups || groups.today !== false
  var out = { recovery: [], load: [], bars: [], activity: [], today: [], predict: [] }
  function add(list, spec) {
    var row = metricRow(spec)
    if (row) list.push(row)
  }
  if (todayOn) {
    var plan = str(snapshot.plan)
    if (plan) {
      var planValue = plan
      var planKm = num(snapshot.planKm)
      var planMin = num(snapshot.planMin)
      if (planKm !== null) planValue += " · " + planKm + " km"
      if (planMin !== null) planValue += " · " + planMin + " min"
      add(out.today, {
        id: "plan",
        icon: activityIcon(plan),
        label: "Today's plan",
        value: planValue
      })
    }
    var readiness = num(snapshot.readiness)
    if (readiness !== null) {
      add(out.today, {
        id: "readiness",
        icon: readinessIcon(readiness),
        label: "Readiness",
        value: Math.round(readiness) + "%",
        hint: recoveryEtaText(snapshot.recoveryHours),
        steps: 5,
        step: readinessStep(readiness),
        tone: readinessTone(readiness),
        lo: 0,
        hi: 100,
        pos: readiness
      })
    }
  }
  for (var r = 0; r < RACE_ORDER.length; r++) {
    var secs = num(snapshot[RACE_ORDER[r].key])
    if (secs !== null && secs > 0)
      add(out.predict, {
        id: RACE_ORDER[r].key,
        icon: ICON.activity,
        label: RACE_ORDER[r].label,
        value: formatRace(secs)
      })
  }
  if (recoveryOn) {
    var rhrHint = ""
    if (num(snapshot.testRhr) !== null && num(snapshot.testRhr) !== num(snapshot.rhr))
      rhrHint = "test RHR " + snapshot.testRhr
    add(out.recovery, {
      id: "rhr",
      icon: ICON.rhr,
      label: "Resting HR",
      value: snapshot.rhr,
      hint: rhrHint
    })
    var fatLabel = fatigueStateLabel(snapshot.fatigueState)
    add(out.recovery, {
      id: "fatigue",
      icon: fatigueIcon(snapshot.fatigueState),
      label: "Fatigue",
      value: fatLabel || snapshot.fatigue,
      steps: 5,
      step: num(snapshot.fatigueState) || 0,
      tone: fatigueTone(snapshot.fatigueState)
    })
    add(out.recovery, {
      id: "balance",
      icon: ICON.balance,
      label: "Balance",
      value: snapshot.balance
    })
  }
  if (loadOn) {
    add(out.load, {
      id: "load",
      icon: ICON.load,
      label: "Today",
      value: snapshot.load
    })
    var d7 = num(snapshot.load7d)
    var d28 = num(snapshot.load28d)
    if (d7 !== null && d28 !== null)
      add(out.load, {
        id: "rolling",
        icon: ICON.week,
        label: "7 / 28 day",
        value: d7 + " · " + d28
      })
    else if (d7 !== null)
      add(out.load, { id: "load7d", icon: ICON.week, label: "7-day", value: d7 })
    else if (d28 !== null)
      add(out.load, { id: "load28d", icon: ICON.week, label: "28-day", value: d28 })
    if (num(snapshot.ati) !== null && num(snapshot.cti) !== null)
      add(out.load, {
        id: "acute",
        icon: ICON.acute,
        label: "Acute · chronic",
        value: snapshot.ati + " / " + snapshot.cti
      })
    var ratio = num(snapshot.loadRatio)
    var ratioLabel = loadStateLabel(snapshot.loadState)
    add(out.bars, {
      id: "ratio",
      icon: ICON.ratio,
      label: "Load ratio",
      value: withState(ratio === null ? "" : ratio.toFixed(2), ratioLabel),
      lo: ratio === null ? null : 0.8,
      hi: ratio === null ? null : 1.3,
      pos: ratio,
      mark: ratio === null ? null : 1,
      tone: loadTone(snapshot.loadState)
    })
    var week = num(snapshot.loadWeek)
    if (week !== null) {
      add(out.bars, {
        id: "week",
        icon: ICON.week,
        label: "This week",
        value: week,
        lo: num(snapshot.loadWeekMin),
        hi: num(snapshot.loadWeekMax),
        pos: week,
        tone: weekTone(week, snapshot.loadWeekMin, snapshot.loadWeekMax)
      })
    }
  }
  if (activityOn) {
    var activity = str(snapshot.activity)
    if (activity) {
      var activityDay = formatDay(snapshot.activityDay)
      add(out.activity, {
        id: "activity",
        icon: activityIcon(activity),
        label: activityDay ? "Last activity · " + activityDay : "Last activity",
        value: activity
      })
    }
  }
  return out
}

function metricRows(snapshot, groups) {
  var g = metricGroups(snapshot, groups)
  return g.today.concat(g.recovery, g.load, g.bars, g.predict, g.activity)
}

function validBarMetric(value) {
  var v = String(value === undefined || value === null ? "" : value).trim().toLowerCase()
  if (v === "icon" || v === "hrv" || v === "rhr" || v === "load" || v === "fatigue" || v === "readiness" || v === "race")
    return v
  return "hrv"
}

function formatBar(snapshot, metric) {
  try {
    if (networkError(snapshot) || !signedIn(snapshot)) return ""
    metric = validBarMetric(metric)
    if (metric === "icon") return ""
    if (metric === "hrv") {
      var hrv = num(snapshot.hrv)
      if (hrv !== null) return "HRV " + hrv
    } else if (metric === "rhr") {
      var rhr = num(snapshot.rhr)
      if (rhr !== null) return "RHR " + rhr
    } else if (metric === "load") {
      var load = num(snapshot.load)
      if (load !== null) return "Load " + load
    } else if (metric === "fatigue") {
      var fat = fatigueStateLabel(snapshot.fatigueState)
      if (fat) return fat
      if (num(snapshot.fatigue) !== null) return String(snapshot.fatigue)
    } else if (metric === "readiness") {
      var readiness = num(snapshot.readiness)
      if (readiness !== null) return "Ready " + Math.round(readiness) + "%"
    } else if (metric === "race") {
      var best = bestRace(snapshot)
      if (best) return best.spec.short + " " + formatRaceShort(best.seconds)
    }
    return formatSnapshot(snapshot)
  } catch (e) {
    return ""
  }
}

function formatDelta(d) {
  if (d === null || d === undefined || !isFinite(Number(d))) return ""
  var r = Math.round(Number(d))
  return r > 0 ? "+" + r : String(r)
}

function regionLabel(region) {
  return String(region || "").trim().toLowerCase() === "us" ? "US" : "EU"
}

function validRegion(value) {
  var r = String(value === undefined || value === null ? "" : value).trim().toLowerCase()
  return r === "us" ? "us" : "eu"
}

function clampRefreshMinutes(value) {
  var n = Number(value)
  if (!isFinite(n)) n = REFRESH_DEFAULT_MINUTES
  n = Math.round(n / REFRESH_STEP_MINUTES) * REFRESH_STEP_MINUTES
  if (n < REFRESH_MIN_MINUTES) return REFRESH_MIN_MINUTES
  if (n > REFRESH_MAX_MINUTES) return REFRESH_MAX_MINUTES
  return n
}

function refreshIntervalMinutes(minRaw, secRaw) {
  var n = parseInt(String(minRaw), 10)
  if (Number.isFinite(n)) return clampRefreshMinutes(n)
  var sec = parseInt(String(secRaw), 10)
  if (Number.isFinite(sec) && sec > 0) return clampRefreshMinutes(Math.round(sec / 60) || REFRESH_MIN_MINUTES)
  return REFRESH_DEFAULT_MINUTES
}

function formatRefreshLabel(minutes) {
  var n = clampRefreshMinutes(minutes)
  if (n >= 60 && n % 60 === 0) return "Refresh every " + (n / 60) + " h"
  return "Refresh every " + n + " min"
}

function settingValue(settings, name, fallback) {
  var value = settings ? settings[name] : undefined
  return value === undefined || value === null ? fallback : value
}

// Producer-side caps: credentials are clamped before the payload reaches
// stdin, so coros.py login never buffers an oversized body.
function loginPayload(email, password, region) {
  var e = String(email || "").slice(0, 254)
  var p = String(password || "").slice(0, 1024)
  return JSON.stringify({ email: e, password: p, region: validRegion(region) }) + "\n"
}

// Panel-launched helpers require a fixed interpreter over a fixed system
// PATH and an explicit minimal environment: the login password travels on
// stdin, so neither the interpreter nor the helper's surroundings may be
// resolvable or inheritable from the ambient session (marketplace review).
var HELPER_INTERPRETER = "/usr/bin/python3"
var HELPER_SYSTEM_PATH = "/usr/local/bin:/usr/bin"

// Minimal environment for coros.py: a fixed PATH, HOME, and the XDG bases
// the helper actually reads. Ambient variables, including COROS_EMAIL /
// COROS_PASSWORD, do not cross this boundary; env credentials stay a
// deliberate terminal CLI behavior.
function helperEnvironment(home, cacheHome, configHome) {
  var env = { PATH: HELPER_SYSTEM_PATH, HOME: home }
  if (cacheHome) env.XDG_CACHE_HOME = cacheHome
  if (configHome) env.XDG_CONFIG_HOME = configHome
  return env
}

function snapshotArgs(helperPath, region) {
  return [HELPER_INTERPRETER, helperPath, "snapshot", "--region", region]
}

// Compact bar label. One metric so it fits a laptop bar; details live in
// the panel and tooltip. Prefer HRV, then RHR, then load.
function formatSnapshot(snapshot) {
  try {
    if (networkError(snapshot) || !signedIn(snapshot)) return ""
    var hrv = num(snapshot.hrv)
    if (hrv !== null) return "HRV " + hrv
    var rhr = num(snapshot.rhr)
    if (rhr !== null) return "RHR " + rhr
    var load = num(snapshot.load)
    if (load !== null) return "Load " + load
    return ""
  } catch (e) {
    return ""
  }
}

function formatTooltip(snapshot) {
  try {
    if (authError(snapshot)) return "COROS — sign in from the panel"
    if (networkError(snapshot)) return "COROS — can't reach Training Hub"
    if (!snapshot || typeof snapshot !== "object") return "COROS"
    var parts = []
    var day = formatDay(snapshot.day)
    if (day) parts.push(day)
    var hrv = num(snapshot.hrv)
    if (hrv !== null) {
      var text = "HRV " + hrv
      var delta = formatDelta(hrvDelta(hrv, snapshot.hrvBaseline))
      if (delta !== "") text += " (" + delta + ")"
      parts.push(text)
    }
    var rhr = num(snapshot.rhr)
    if (rhr !== null) parts.push("RHR " + rhr)
    var load = num(snapshot.load)
    if (load !== null) parts.push("Load " + load)
    var load7d = num(snapshot.load7d)
    if (load7d !== null) parts.push("7d " + load7d)
    var readiness = num(snapshot.readiness)
    if (readiness !== null) {
      var eta = recoveryEtaText(snapshot.recoveryHours)
      parts.push("Ready " + Math.round(readiness) + "%" + (eta ? " · " + eta : ""))
    }
    var plan = str(snapshot.plan)
    if (plan) {
      var planKm = num(snapshot.planKm)
      parts.push("Today " + plan + (planKm !== null ? " " + planKm + " km" : ""))
    }
    var fatigue = fatigueStateLabel(snapshot.fatigueState)
    if (fatigue) parts.push(fatigue)
    var activity = str(snapshot.activity)
    if (activity) {
      var activityDay = formatDay(snapshot.activityDay)
      parts.push(activityDay ? activity + " (" + activityDay + ")" : activity)
    }
    return parts.length ? "COROS — " + parts.join(" · ") : "COROS"
  } catch (e) {
    return "COROS"
  }
}
