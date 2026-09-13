import QtQuick
import Quickshell.Io
import "Model.js" as Model

Item {
  id: root

  property var settings: ({})
  property var bar: null
  property string moduleName: ""

  property var snapshot: null
  property bool loginBusy: false
  property string actionStatus: ""
  property string _pollRegion: ""
  property bool _signingOut: false

  readonly property int refreshIntervalMin: {
    var n = parseInt(String(setting("refreshIntervalMin", "")), 10)
    if (isFinite(n)) return Model.clampRefreshMinutes(n)
    var sec = parseInt(String(setting("refreshIntervalSec", "")), 10)
    if (isFinite(sec) && sec > 0) return Model.clampRefreshMinutes(Math.round(sec / 60) || Model.REFRESH_MIN_MINUTES)
    return Model.REFRESH_DEFAULT_MINUTES
  }
  readonly property string region: validRegion(setting("region", "eu"))
  readonly property bool hideWhenNoData: setting("hideWhenNoData", false) === true
  readonly property bool showRecovery: setting("showRecovery", true) !== false
  readonly property bool showLoad: setting("showLoad", true) !== false
  readonly property bool showActivity: setting("showActivity", true) !== false
  readonly property string barMetric: Model.validBarMetric(setting("barMetric", "hrv"))
  readonly property string helperPath: decodeURIComponent(Qt.resolvedUrl("coros.py").toString().replace(/^file:\/\//, ""))

  function setting(name, fallback) {
    var value = settings ? settings[name] : undefined
    return value === undefined || value === null ? fallback : value
  }

  function validRegion(value) {
    var r = String(value === undefined || value === null ? "" : value).trim().toLowerCase()
    return r === "us" ? "us" : "eu"
  }

  function snapshotArgs() {
    return ["python3", helperPath, "snapshot", "--region", region]
  }

  function poll() {
    if (snapshotProcess.running || root._signingOut) return
    snapshotTimeout.restart()
    snapshotProcess.exec(root.snapshotArgs())
  }

  function refresh() {
    root.poll()
    notify("Refreshing…")
  }

  function applySnapshotLine(raw) {
    var parsed = Model.parseSnapshot(String(raw || "").trim())
    snapshot = parsed ? parsed : { error: "network" }
    return parsed
  }

  function saveLogin(email, password, region) {
    var r = validRegion(region)
    loginBusy = true
    notify("Signing in…")
    loginProcess.payload = JSON.stringify({ email: email, password: password, region: r }) + "\n"
    loginProcess.stdinEnabled = true
    loginProcess.running = false
    loginProcess.running = true
    writeSetting("region", r)
  }

  function logout() {
    if (root._signingOut || loginProcess.running) return
    root._signingOut = true
    snapshotTimeout.stop()
    if (snapshotProcess.running) {
      snapshotProcess.signal(9)
      snapshotProcess.running = false
    }
    snapshot = { error: "auth" }
    notify("Signing out…")
    logoutProcess.running = true
  }

  function writeSetting(key, value) {
    var entry = { id: moduleName }
    for (var k in root.settings) if (k !== "id") entry[k] = root.settings[k]
    entry[key] = value
    if (parent && "settings" in parent)
      parent.settings = entry
    else
      root.settings = entry
    if (root.bar && root.bar.shell && typeof root.bar.shell.updateEntryInline === "function")
      root.bar.shell.updateEntryInline(moduleName, entry)
  }

  function notify(text) {
    actionStatus = String(text || "")
    actionStatusTimer.restart()
  }

  onSettingsChanged: {
    if (region !== _pollRegion) {
      _pollRegion = region
      poll()
    }
  }

  Component.onCompleted: {
    _pollRegion = region
    poll()
  }

  Timer {
    id: pollTimer
    interval: root.refreshIntervalMin * 60 * 1000
    repeat: true
    running: true
    onTriggered: root.poll()
  }

  Timer {
    id: actionStatusTimer
    interval: 2200
    repeat: false
    onTriggered: root.actionStatus = ""
  }

  Timer {
    id: snapshotTimeout
    interval: 60000
    repeat: false
    onTriggered: {
      if (root._signingOut) return
      if (snapshotProcess.running) {
        snapshotProcess.signal(9)
        snapshotProcess.running = false
      }
      root.applySnapshotLine("")
    }
  }

  Process {
    id: snapshotProcess
    running: false
    command: root.snapshotArgs()
    stdout: StdioCollector {
      id: snapshotStdout
      waitForEnd: true
    }
    onExited: {
      snapshotTimeout.stop()
      if (root._signingOut) return
      root.applySnapshotLine(snapshotStdout.text)
    }
  }

  Process {
    id: loginProcess
    running: false
    stdinEnabled: true
    property string payload: ""
    command: ["python3", root.helperPath, "login"]
    stdout: StdioCollector {
      id: loginStdout
      waitForEnd: true
    }
    onStarted: {
      write(payload)
      payload = ""
      // Close the write channel so coros.py login sees EOF (stdin.read / readline).
      stdinEnabled = false
    }
    onExited: {
      root.loginBusy = false
      var parsed = Model.parseSnapshot(loginStdout.text)
      if (parsed) root.snapshot = parsed
      if (!parsed || Model.authError(parsed)) root.notify("Sign-in failed")
      else root.notify("Signed in")
    }
  }

  Process {
    id: logoutProcess
    running: false
    command: ["python3", root.helperPath, "logout"]
    stdout: StdioCollector {
      waitForEnd: true
    }
    onExited: {
      root.snapshot = { error: "auth" }
      root._signingOut = false
      root.notify("Signed out")
    }
  }
}
