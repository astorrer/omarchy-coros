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

function loadStateLabel(state) {
  var labels = { 1: "Recovering", 2: "Productive", 3: "Maintaining", 4: "Overreaching", 5: "Excessive" }
  return labels[Number(state)] || ""
}

function fatigueStateLabel(state) {
  var labels = { 1: "Fresh", 2: "Recovered", 3: "Balanced", 4: "Tired", 5: "Fatigued" }
  return labels[Number(state)] || ""
}

function withState(value, label) {
  if (value === null || value === undefined || value === "") return ""
  return label ? String(value) + " · " + label : String(value)
}

function metricRows(snapshot, groups) {
  if (!signedIn(snapshot)) return []
  var recovery = !groups || groups.recovery !== false
  var load = !groups || groups.load !== false
  var activityOn = !groups || groups.activity !== false
  var rows = []
  function add(label, value) {
    if (value === null || value === undefined || value === "") return
    rows.push({ label: label, value: String(value) })
  }
  if (recovery) {
    add("Resting HR", snapshot.rhr)
    if (num(snapshot.testRhr) !== null && num(snapshot.testRhr) !== num(snapshot.rhr))
      add("Test RHR", snapshot.testRhr)
    add("Impact balance", snapshot.balance)
    add("Fatigue", withState(snapshot.fatigue, fatigueStateLabel(snapshot.fatigueState)))
  }
  if (load) {
    add("Daily load", snapshot.load)
    add("7-day load", snapshot.load7d)
    add("28-day load", snapshot.load28d)
    var ratio = num(snapshot.loadRatio)
    add("Load ratio", withState(ratio === null ? "" : ratio.toFixed(2), loadStateLabel(snapshot.loadState)))
    var week = num(snapshot.loadWeek)
    if (week !== null) {
      var rec = ""
      if (num(snapshot.loadWeekMin) !== null && num(snapshot.loadWeekMax) !== null)
        rec = " · rec " + snapshot.loadWeekMin + "–" + snapshot.loadWeekMax
      add("This week", week + rec)
    }
    if (num(snapshot.ati) !== null && num(snapshot.cti) !== null)
      add("Acute / chronic", snapshot.ati + " / " + snapshot.cti)
  }
  if (activityOn) {
    var activity = str(snapshot.activity)
    if (activity) {
      var activityDay = formatDay(snapshot.activityDay)
      add("Last activity", activityDay ? activity + " · " + activityDay : activity)
    }
  }
  return rows
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
