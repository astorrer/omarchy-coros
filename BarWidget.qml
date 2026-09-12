import QtQuick
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui
import "Model.js" as Model

// COROS recovery metrics for the Omarchy bar. A one-shot
// `coros.py snapshot --region <region>` poll owns the data: it prints exactly
// one JSON object on stdout, missing metrics are null, never an error exit
// for display. The bar shows a one-line summary and never shows errors.
BarWidget {
  id: root
  moduleName: "io.github.astorrer.omarchy-coros"

  property var snapshot: null
  property string actionStatus: ""
  property string _pollRegion: ""

  readonly property int refreshIntervalSec: intSetting("refreshIntervalSec", 30, 5, 120)
  readonly property string region: validRegion(setting("region", "eu"))
  readonly property bool hideWhenNoData: setting("hideWhenNoData", false) === true
  readonly property string helperPath: decodeURIComponent(Qt.resolvedUrl("coros.py").toString().replace(/^file:\/\//, ""))

  readonly property string barText: Model.formatSnapshot(snapshot)
  readonly property string tooltipText: barText !== ""
    ? "COROS — " + barText
    : (Model.authError(snapshot) ? "COROS — sign in from the panel" : "COROS")

  property bool loginBusy: false

  visible: Model.authError(snapshot) || !hideWhenNoData || !Model.isEmpty(snapshot)

  function intSetting(name, fallback, min, max) {
    var n = parseInt(String(setting(name, fallback)), 10)
    if (!isFinite(n)) n = fallback
    return Math.min(max, Math.max(min, n))
  }

  function validRegion(value) {
    var r = String(value === undefined || value === null ? "" : value).trim().toLowerCase()
    return r === "us" ? "us" : "eu"
  }

  function snapshotArgs() {
    return ["python3", helperPath, "snapshot", "--region", region]
  }

  function poll() {
    snapshotProcess.exec(root.snapshotArgs())
  }

  function refresh() {
    root.poll()
    notify("Refreshing…")
  }

  function applySnapshotLine(raw) {
    var line = String(raw || "").trim()
    if (line === "") return
    var parsed = Model.parseSnapshot(line)
    if (parsed) snapshot = parsed
  }

  function saveLogin(email, password, region) {
    var r = validRegion(region)
    loginBusy = true
    notify("Signing in…")
    loginProcess.payload = JSON.stringify({ email: email, password: password, region: r })
    loginProcess.running = false
    loginProcess.running = true
    writeSetting("region", r)
  }

  function writeSetting(key, value) {
    var entry = { id: moduleName }
    for (var k in root.settings) if (k !== "id") entry[k] = root.settings[k]
    entry[key] = value
    root.settings = entry
    if (root.bar && root.bar.shell && typeof root.bar.shell.updateEntryInline === "function")
      root.bar.shell.updateEntryInline(moduleName, entry)
  }

  function notify(text) {
    actionStatus = String(text || "")
    actionStatusTimer.restart()
  }

  // ---- Panel lifecycle shape contract for shell.summon/hide/toggle routing.
  readonly property bool opened: panelLoader.item ? panelLoader.item.opened === true : false
  readonly property bool popoutSwitchClosing: panelLoader.item
    ? panelLoader.item.popoutSwitchClosing === true
    : false

  function open() {
    if (panelLoader.item) panelLoader.item.open()
  }

  function close() {
    if (panelLoader.item) panelLoader.item.close()
  }

  function toggle() {
    if (panelLoader.item) panelLoader.item.toggle()
  }

  function togglePanel() {
    if (panelLoader.item) panelLoader.item.toggle()
  }

  function closeForPopoutSwitch() {
    if (panelLoader.item) panelLoader.item.closeForPopoutSwitch()
  }

  function injectPanel() {
    var target = panelLoader.item
    if (!target) return
    if ("bar" in target) target.bar = root.bar
    if ("hostWidget" in target) target.hostWidget = root
    if ("anchorItem" in target) target.anchorItem = button
  }

  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  onBarChanged: injectPanel()

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
    interval: root.refreshIntervalSec * 1000
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

  Process {
    id: snapshotProcess
    running: false
    command: root.snapshotArgs()
    stdout: SplitParser {
      onRead: root.applySnapshotLine(read)
    }
  }

  Process {
    id: loginProcess
    running: false
    stdinEnabled: true
    property string payload: ""
    command: ["python3", root.helperPath, "login"]
    stdout: SplitParser {
      onRead: root.applySnapshotLine(read)
    }
    onStarted: {
      write(payload)
      payload = ""
    }
    onExited: {
      root.loginBusy = false
      if (Model.authError(root.snapshot)) root.notify("Sign-in failed")
      else root.notify("Signed in")
    }
  }

  IpcHandler {
    target: "io.github.astorrer.omarchy-coros"

    function refresh(): void { root.refresh() }
    function open(): void { root.open() }
    function close(): void { root.close() }
    function show(): void { root.open() }
    function hide(): void { root.close() }
    function toggle(): void { root.togglePanel() }
  }

  Loader {
    id: panelLoader
    active: true
    source: Qt.resolvedUrl("Panel.qml")
    visible: false
    onLoaded: {
      root.injectPanel()
      Qt.callLater(root.injectPanel)
    }
  }

  BarIconButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: root.barText !== "" ? root.barText : "COROS"
    slotSize: Style.bar.statusSlot
    tooltipText: root.tooltipText

    onPressed: function(buttonCode) {
      if (buttonCode === Qt.RightButton) root.refresh()
      else root.togglePanel()
    }
  }
}
