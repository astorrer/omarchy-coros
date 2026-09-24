import QtQuick
import Quickshell
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

  readonly property int refreshIntervalMin: Model.refreshIntervalMinutes(setting("refreshIntervalMin", ""), setting("refreshIntervalSec", ""))
  readonly property string region: Model.validRegion(setting("region", "eu"))
  readonly property bool hideWhenNoData: setting("hideWhenNoData", false) === true
  readonly property bool showRecovery: setting("showRecovery", true) !== false
  readonly property bool showLoad: setting("showLoad", true) !== false
  readonly property bool showActivity: setting("showActivity", true) !== false
  readonly property bool showToday: setting("showToday", true) !== false
  readonly property string barMetric: Model.validBarMetric(setting("barMetric", "hrv"))
  readonly property string helperPath: decodeURIComponent(Qt.resolvedUrl("coros.py").toString().replace(/^file:\/\//, ""))
  readonly property var helperEnv: Model.helperEnvironment(
    Quickshell.env("HOME"),
    Quickshell.env("XDG_CACHE_HOME"),
    Quickshell.env("XDG_CONFIG_HOME"))

  function setting(name, fallback) {
    return Model.settingValue(root.settings, name, fallback)
  }

  function snapshotArgs() {
    return Model.snapshotArgs(root.helperPath, root.region)
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
    loginBusy = true
    notify("Signing in…")
    loginProcess.payload = Model.loginPayload(email, password, region)
    loginProcess.stdinEnabled = true
    loginProcess.running = false
    loginProcess.running = true
    writeSetting("region", Model.validRegion(region))
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
    id: loginTimeout
    interval: 60000
    repeat: false
    onTriggered: {
      if (loginProcess.running) {
        loginProcess.signal(9)
        loginProcess.running = false
      }
      root.loginBusy = false
      root.notify("Sign-in timed out")
    }
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
    clearEnvironment: true
    environment: root.helperEnv
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
    command: [Model.HELPER_INTERPRETER, root.helperPath, "login"]
    clearEnvironment: true
    environment: root.helperEnv
    stdout: StdioCollector {
      id: loginStdout
      waitForEnd: true
    }
    onStarted: {
      write(payload)
      payload = ""
      // Close the write channel so coros.py login sees EOF (stdin.read / readline).
      stdinEnabled = false
      loginTimeout.start()
    }
    onExited: {
      loginTimeout.stop()
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
    command: [Model.HELPER_INTERPRETER, root.helperPath, "logout"]
    clearEnvironment: true
    environment: root.helperEnv
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
