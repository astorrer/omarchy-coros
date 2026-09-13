import QtQuick
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui
import "Model.js" as Model

// COROS recovery metrics for the Omarchy bar. Service.qml owns the
// `coros.py snapshot` poll so it keeps running while the popup is closed.
BarWidget {
  id: root
  moduleName: "io.github.astorrer.omarchy-coros"

  Service {
    id: coros
    settings: root.settings
    bar: root.bar
    moduleName: root.moduleName
  }

  readonly property string barMetric: coros.barMetric
  readonly property string barText: {
    if (barMetric === "icon") return ""
    var compact = Model.formatBar(coros.snapshot, barMetric)
    return compact !== "" ? compact : "COROS"
  }
  readonly property string tooltipText: Model.formatTooltip(coros.snapshot)

  visible: Model.authError(coros.snapshot) || !coros.hideWhenNoData || !Model.isEmpty(coros.snapshot)

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
    if ("client" in target) target.client = coros
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

  IpcHandler {
    target: "io.github.astorrer.omarchy-coros"

    function refresh(): void { coros.refresh() }
    function open(): void { root.open() }
    function close(): void { root.close() }
    function show(): void { root.open() }
    function hide(): void { root.close() }
    function toggle(): void { root.togglePanel() }
    function settings(): void {
      root.open()
      if (panelLoader.item && panelLoader.item.openSettings) panelLoader.item.openSettings()
    }
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
    dimmed: Model.authError(coros.snapshot)
    tooltipText: root.tooltipText
    onPressed: function(buttonCode) {
      if (buttonCode === Qt.RightButton) coros.refresh()
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
    dimmed: Model.authError(coros.snapshot)
    iconComponent: Component {
      CorosIcon {
        anchors.fill: parent
        color: iconBtn.foreground
        dimmed: Model.authError(coros.snapshot)
      }
    }
    onPressed: function(buttonCode) {
      if (buttonCode === Qt.RightButton) coros.refresh()
      else root.togglePanel()
    }
  }
}
