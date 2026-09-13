.pragma library

var PLUGIN_VERSION = "0.1.0"
var PROJECT_URL = "https://github.com/astorrer/omarchy-coros"
var REFRESH_MIN_MINUTES = 15
var REFRESH_MAX_MINUTES = 1440
var REFRESH_DEFAULT_MINUTES = 30
var REFRESH_STEP_MINUTES = 15

function parseJson(raw) {
  try {
    var parsed = JSON.parse(String(raw || "").trim())
    return parsed && typeof parsed === "object" ? parsed : null
  } catch (e) {
    return null
  }
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
    activity: str(parsed.activity),
    activityDay: str(parsed.activityDay),
    day: str(parsed.day),
    error: str(parsed.error)
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

function isEmpty(snapshot) {
  if (!snapshot || typeof snapshot !== "object") return true
  return num(snapshot.hrv) === null
    && num(snapshot.hrvBaseline) === null
    && num(snapshot.rhr) === null
    && num(snapshot.load) === null
    && num(snapshot.load7d) === null
    && num(snapshot.fatigue) === null
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
  return HERO_PHRASES[heroMood(snapshot)] || []
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
  var empty = { recovery: [], load: [], bars: [], activity: [] }
  if (!signedIn(snapshot)) return empty
  var recoveryOn = !groups || groups.recovery !== false
  var loadOn = !groups || groups.load !== false
  var activityOn = !groups || groups.activity !== false
  var out = { recovery: [], load: [], bars: [], activity: [] }
  function add(list, spec) {
    var row = metricRow(spec)
    if (row) list.push(row)
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
  return g.recovery.concat(g.load, g.bars, g.activity)
}

function validBarMetric(value) {
  var v = String(value === undefined || value === null ? "" : value).trim().toLowerCase()
  if (v === "icon" || v === "hrv" || v === "rhr" || v === "load" || v === "fatigue") return v
  return "hrv"
}

function formatBar(snapshot, metric) {
  try {
    if (!signedIn(snapshot)) return ""
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
    }
    return formatSnapshot(snapshot)
  } catch (e) {
    return ""
  }
}

function authError(snapshot) {
  return !!(snapshot && typeof snapshot === "object" && snapshot.error === "auth")
}

function signedIn(snapshot) {
  return !!(snapshot && typeof snapshot === "object" && !authError(snapshot))
}

function formatDelta(d) {
  if (d === null || d === undefined || !isFinite(Number(d))) return ""
  var r = Math.round(Number(d))
  return r > 0 ? "+" + r : String(r)
}

function regionLabel(region) {
  return String(region || "").trim().toLowerCase() === "us" ? "US" : "EU"
}

function clampRefreshMinutes(value) {
  var n = Number(value)
  if (!isFinite(n)) n = REFRESH_DEFAULT_MINUTES
  n = Math.round(n / REFRESH_STEP_MINUTES) * REFRESH_STEP_MINUTES
  if (n < REFRESH_MIN_MINUTES) return REFRESH_MIN_MINUTES
  if (n > REFRESH_MAX_MINUTES) return REFRESH_MAX_MINUTES
  return n
}

function formatRefreshLabel(minutes) {
  var n = clampRefreshMinutes(minutes)
  if (n >= 60 && n % 60 === 0) return "Refresh every " + (n / 60) + " h"
  return "Refresh every " + n + " min"
}

// Compact bar label. One metric so it fits a laptop bar; details live in
// the panel and tooltip. Prefer HRV, then RHR, then load.
function formatSnapshot(snapshot) {
  try {
    if (!signedIn(snapshot)) return ""
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
