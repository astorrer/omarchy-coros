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

  readonly property string barText: {
    if (barMetric === "icon") return ""
    var compact = Model.formatBar(snapshot, barMetric)
    return compact !== "" ? compact : "COROS"
  }
  readonly property string tooltipText: Model.formatTooltip(snapshot)

  property bool loginBusy: false

  visible: Model.authError(snapshot) || !hideWhenNoData || !Model.isEmpty(snapshot)

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
    loginProcess.payload = JSON.stringify({ email: email, password: password, region: r }) + "\n"
    loginProcess.stdinEnabled = true
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
    if ("anchorItem" in target) target.anchorItem = root.barMetric === "icon" ? iconBtn : textBtn
  }

  implicitWidth: root.barMetric === "icon" ? iconBtn.implicitWidth : textBtn.implicitWidth
  implicitHeight: root.barMetric === "icon" ? iconBtn.implicitHeight : textBtn.implicitHeight

  // A bit longer than the default 55% dash, still centered on the mark
  // rather than spanning the whole slot (that overshoots left of the hex).
  readonly property real openPanelIndicatorWidth: root.barMetric === "icon"
    ? Style.bar.iconCanvas + Style.space(6)
    : (textBtn.labelWidth > 0 ? textBtn.labelWidth : 0)
  readonly property real openPanelIndicatorHeight: root.barMetric === "icon"
    ? Style.bar.iconSlot
    : 0

  onBarChanged: injectPanel()
  onBarMetricChanged: Qt.callLater(root.injectPanel)

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

  Process {
    id: snapshotProcess
    running: false
    command: root.snapshotArgs()
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: root.applySnapshotLine(text)
    }
  }

  Process {
    id: loginProcess
    running: false
    stdinEnabled: true
    property string payload: ""
    command: ["python3", root.helperPath, "login"]
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: root.applySnapshotLine(text)
    }
    onStarted: {
      write(payload)
      payload = ""
      // Close the write channel so coros.py login sees EOF (stdin.read / readline).
      stdinEnabled = false
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

  WidgetButton {
    id: textBtn
    visible: root.barMetric !== "icon"
    anchors.fill: parent
    bar: root.bar
    text: root.barText
    fontSize: Style.font.caption
    horizontalMargin: 8
    dimmed: Model.authError(root.snapshot)
    tooltipText: root.tooltipText
    onPressed: function(buttonCode) {
      if (buttonCode === Qt.RightButton) root.refresh()
      else root.togglePanel()
    }
  }

  BarIconButton {
    id: iconBtn
    visible: root.barMetric === "icon"
    anchors.fill: parent
    bar: root.bar
    slotSize: Style.bar.iconSlot
    tooltipText: root.tooltipText
    dimmed: Model.authError(root.snapshot)
    iconComponent: Component {
      CorosIcon {
        anchors.fill: parent
        color: iconBtn.foreground
        dimmed: Model.authError(root.snapshot)
      }
    }
    onPressed: function(buttonCode) {
      if (buttonCode === Qt.RightButton) root.refresh()
      else root.togglePanel()
    }
  }
}
