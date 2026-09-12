.pragma library

var PLUGIN_VERSION = "0.1.0"
var PROJECT_URL = "https://github.com/astorrer/omarchy-coros"

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
    rhr: num(parsed.rhr),
    load: num(parsed.load),
    sleepH: num(parsed.sleepH),
    activity: str(parsed.activity)
  }
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
    && num(snapshot.sleepH) === null
    && str(snapshot.activity) === null
}

function authError(snapshot) {
  return !!(snapshot && typeof snapshot === "object" && snapshot.error === "auth")
}

function formatDelta(d) {
  if (d === null || d === undefined || !isFinite(Number(d))) return ""
  var r = Math.round(Number(d))
  return "(" + (r > 0 ? "+" + r : String(r)) + ")"
}

// Bar line, e.g. "HRV 42 (-3) | RHR 48 | Load 85". Null segments are skipped,
// errors never surface here — worst case is "".
function formatSnapshot(snapshot) {
  try {
    if (!snapshot || typeof snapshot !== "object") return ""
    var parts = []
    var hrv = num(snapshot.hrv)
    if (hrv !== null) {
      var text = "HRV " + hrv
      var delta = formatDelta(hrvDelta(hrv, snapshot.hrvBaseline))
      if (delta !== "") text += " " + delta
      parts.push(text)
    }
    var rhr = num(snapshot.rhr)
    if (rhr !== null) parts.push("RHR " + rhr)
    var load = num(snapshot.load)
    if (load !== null) parts.push("Load " + load)
    return parts.join(" | ")
  } catch (e) {
    return ""
  }
}
