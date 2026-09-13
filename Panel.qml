pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell
import qs.Commons
import qs.Ui
import "Model.js" as Model

Panel {
  id: root
  moduleName: "io.github.astorrer.omarchy-coros"
  manageIpc: false

  property var anchorItem: null
  property var hostWidget: null
  property string view: "main"
  property string loginReturn: "main"
  property string draftEmail: ""
  property string draftPassword: ""
  property string draftRegion: "eu"

  readonly property var client: hostWidget
  readonly property var snapshot: client ? client.snapshot : null
  readonly property bool showLogin: view === "login" || (view === "main" && Model.authError(snapshot))
  readonly property string regionText: Model.regionLabel(client ? client.region : "eu")

  readonly property string statusText: {
    if (!client) return ""
    if (client.actionStatus !== "") return client.actionStatus
    if (client.loginBusy) return "Signing in…"
    if (!snapshot) return "Checking COROS…"
    if (Model.authError(snapshot)) return "Sign in required"
    if (Model.isEmpty(snapshot)) return "Signed in · " + regionText + " · waiting on metrics"
    return "Signed in · " + regionText
  }

  readonly property string hrvValue: metricText(snapshot ? snapshot.hrv : null)
  readonly property string hrvMeta: {
    var parts = []
    var day = snapshot ? Model.formatDay(snapshot.day) : ""
    if (day !== "") parts.push(day)
    parts.push("Overnight HRV")
    if (snapshot && snapshot.hrvBaseline !== null && snapshot.hrvBaseline !== undefined)
      parts.push("baseline " + snapshot.hrvBaseline)
    var delta = snapshot ? Model.hrvDelta(snapshot.hrv, snapshot.hrvBaseline) : null
    var formatted = Model.formatDelta(delta)
    if (formatted !== "") parts.push(formatted)
    if (snapshot && snapshot.hrvBandLow !== null && snapshot.hrvBandLow !== undefined
        && snapshot.hrvBandHigh !== null && snapshot.hrvBandHigh !== undefined)
      parts.push(snapshot.hrvBandLow + "–" + snapshot.hrvBandHigh)
    return parts.join(" · ")
  }

  function metricText(value) {
    if (value === null || value === undefined) return "—"
    var s = String(value).trim()
    return s !== "" ? s : "—"
  }

  function open() {
    root.controller.show()
  }

  function close() {
    root.controller.hide()
  }

  function goBack() {
    if (root.view === "login") {
      root.view = root.loginReturn
      return
    }
    if (root.view === "settings") {
      root.view = "main"
      return
    }
    root.close()
  }

  function openSettings() {
    root.view = "settings"
    if (panelFlick) panelFlick.contentY = 0
  }

  function openLogin() {
    root.loginReturn = root.view === "settings" ? "settings" : "main"
    draftRegion = client && client.region === "us" ? "us" : "eu"
    draftPassword = ""
    root.view = "login"
  }

  function submitLogin() {
    if (!client || client.loginBusy) return
    client.saveLogin(draftEmail, draftPassword, draftRegion)
    draftPassword = ""
    root.view = "main"
  }

  function openProject() {
    Qt.openUrlExternally(Model.PROJECT_URL)
  }

  function switchPanel(direction) {
    if (root.bar && typeof root.bar.switchPanelFrom === "function")
      return root.bar.switchPanelFrom(root.hostWidget || root, direction)
    return false
  }

  function bumpRefresh(delta) {
    if (!client) return
    client.writeSetting(
      "refreshIntervalMin",
      Model.clampRefreshMinutes(client.refreshIntervalMin + delta * Model.REFRESH_STEP_MINUTES)
    )
  }

  component MetricCell: Column {
    id: cell
    property string label: ""
    property string value: "—"
    spacing: Style.space(2)

    Text {
      width: parent.width
      text: cell.label
      color: root.barForeground
      opacity: 0.45
      font.family: root.bar ? root.bar.fontFamily : Style.font.family
      font.pixelSize: Style.font.caption
    }

    Text {
      width: parent.width
      text: cell.value
      color: root.barForeground
      font.family: root.bar ? root.bar.fontFamily : Style.font.family
      font.pixelSize: Style.font.body
      elide: Text.ElideRight
      wrapMode: Text.NoWrap
      textFormat: Text.PlainText
    }
  }

  KeyboardPanel {
    id: panel
    anchorItem: root.anchorItem
    owner: root.hostWidget || root
    bar: root.bar
    open: root.opened
    focusTarget: keyCatcher
    contentWidth: panel.fittedContentWidth(Style.space(340))
    contentHeight: panel.fittedContentHeight(content.implicitHeight, Style.space(620))

    PanelKeyCatcher {
      id: keyCatcher
      anchors.fill: parent
      onCloseRequested: root.goBack()
      onTabRequested: function(direction) {
        root.switchPanel(direction)
      }

      Flickable {
        id: panelFlick
        anchors.fill: parent
        contentWidth: width
        contentHeight: content.implicitHeight
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        flickableDirection: Flickable.VerticalFlick
        interactive: contentHeight > height
        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

        Column {
          id: content
          width: panelFlick.width
          spacing: Style.space(12)

        RowLayout {
          width: parent.width
          spacing: Style.space(8)

          Text {
            text: root.view === "settings" ? "Settings" : "COROS"
            color: root.barForeground
            font.family: root.bar ? root.bar.fontFamily : Style.font.family
            font.pixelSize: Style.font.subtitle
            font.bold: true
            elide: Text.ElideRight
            Layout.fillWidth: true
          }

          Button {
            visible: root.view === "main" && !root.showLogin
            text: "Refresh"
            foreground: root.barForeground
            Layout.alignment: Qt.AlignRight | Qt.AlignVCenter
            onClicked: {
              if (root.client) root.client.refresh()
            }
          }

          Button {
            visible: root.view === "settings"
            text: "Back"
            foreground: root.barForeground
            bordered: true
            Layout.alignment: Qt.AlignRight | Qt.AlignVCenter
            onClicked: root.goBack()
          }
        }

        Text {
          width: parent.width
          visible: root.statusText !== "" && root.view !== "settings"
          text: root.statusText
          color: Model.authError(root.snapshot) && !(root.client && root.client.actionStatus) ? Color.urgent : root.barForeground
          opacity: Model.authError(root.snapshot) && !(root.client && root.client.actionStatus) ? 1.0 : 0.55
          font.family: root.bar ? root.bar.fontFamily : Style.font.family
          font.pixelSize: Style.font.body
          wrapMode: Text.WordWrap
        }

        Column {
          visible: root.showLogin
          width: parent.width
          spacing: Style.space(10)

          TextField {
            id: emailField
            width: parent.width
            placeholderText: "Email"
            text: root.draftEmail
            foreground: root.barForeground
            onTextChanged: root.draftEmail = text
            Keys.onReturnPressed: passwordField.forceActiveFocus()
          }

          TextField {
            id: passwordField
            width: parent.width
            placeholderText: "Password"
            password: true
            text: root.draftPassword
            foreground: root.barForeground
            onTextChanged: root.draftPassword = text
            onAccepted: root.submitLogin()
          }

          Text {
            width: parent.width
            text: "Region"
            color: root.barForeground
            opacity: 0.45
            font.family: root.bar ? root.bar.fontFamily : Style.font.family
            font.pixelSize: Style.font.caption
          }

          ButtonGroup {
            width: parent.width
            options: [
              { value: "us", label: "US" },
              { value: "eu", label: "EU" }
            ]
            value: root.draftRegion
            foreground: root.barForeground
            fontFamily: root.bar ? root.bar.fontFamily : Style.font.family
            focusable: false
            onChanged: function(value) { root.draftRegion = value }
          }

          Text {
            width: parent.width
            text: root.draftRegion === "us"
              ? "America Training Hub (t.coros.com)"
              : "Europe Training Hub (t.eu.coros.com)"
            color: root.barForeground
            opacity: 0.35
            font.family: root.bar ? root.bar.fontFamily : Style.font.family
            font.pixelSize: Style.font.caption
            wrapMode: Text.WordWrap
          }

          Button {
            width: parent.width
            text: root.client && root.client.loginBusy ? "Signing in…" : "Sign in"
            foreground: root.barForeground
            enabled: !(root.client && root.client.loginBusy)
            onClicked: root.submitLogin()
          }
        }

        Column {
          visible: root.view === "main" && !root.showLogin
          width: parent.width
          spacing: Style.space(12)

          Column {
            width: parent.width
            spacing: Style.space(2)

            Text {
              width: parent.width
              visible: !root.client || root.client.showRecovery
              text: root.hrvValue
              color: root.barForeground
              font.family: root.bar ? root.bar.fontFamily : Style.font.family
              font.pixelSize: Style.font.title
              font.bold: true
              elide: Text.ElideRight
            }

            Text {
              width: parent.width
              visible: !root.client || root.client.showRecovery
              text: root.hrvMeta
              color: root.barForeground
              opacity: 0.55
              font.family: root.bar ? root.bar.fontFamily : Style.font.family
              font.pixelSize: Style.font.caption
              wrapMode: Text.WordWrap
            }
          }

          Flickable {
            width: parent.width
            height: Math.min(metricsCol.implicitHeight, Style.space(320))
            contentHeight: metricsCol.implicitHeight
            clip: true
            boundsBehavior: Flickable.StopAtBounds

            Column {
              id: metricsCol
              width: parent.width
              spacing: Style.space(10)

              Repeater {
                model: Model.metricRows(root.snapshot, {
                  recovery: !root.client || root.client.showRecovery,
                  load: !root.client || root.client.showLoad,
                  activity: !root.client || root.client.showActivity
                })

                MetricCell {
                  required property var modelData
                  width: metricsCol.width
                  label: modelData.label
                  value: modelData.value
                }
              }
            }
          }

          PanelSeparator {
            width: parent.width
          }

          RowLayout {
            width: parent.width
            spacing: Style.space(10)

            Text {
              text: "COROS " + Model.PLUGIN_VERSION
              color: root.barForeground
              opacity: 0.45
              font.family: root.bar ? root.bar.fontFamily : Style.font.family
              font.pixelSize: Style.font.caption
              elide: Text.ElideRight
              Layout.fillWidth: true
              Layout.alignment: Qt.AlignVCenter
              MouseArea {
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: root.openProject()
              }
            }

            PanelActionButton {
              iconText: "󰒓"
              tooltipText: "Settings"
              foreground: root.barForeground
              Layout.alignment: Qt.AlignVCenter
              onClicked: root.openSettings()
            }
          }
        }

        Column {
          visible: root.view === "settings"
          width: parent.width
          spacing: Style.space(8)

          PanelSectionHeader {
            width: parent.width
            text: "BAR"
            foreground: root.barForeground
            fontFamily: root.bar ? root.bar.fontFamily : Style.font.family
          }

          ButtonGroup {
            width: parent.width
            options: [
              { value: "icon", label: "Icon" },
              { value: "hrv", label: "HRV" },
              { value: "rhr", label: "RHR" },
              { value: "load", label: "Load" },
              { value: "fatigue", label: "Fatigue" }
            ]
            value: root.client ? root.client.barMetric : "hrv"
            foreground: root.barForeground
            fontFamily: root.bar ? root.bar.fontFamily : Style.font.family
            focusable: false
            onChanged: function(value) {
              if (root.client) root.client.writeSetting("barMetric", value)
            }
          }

          Toggle {
            width: parent.width
            label: "Hide when no data"
            description: "Leave the bar until metrics arrive."
            checked: root.client ? root.client.hideWhenNoData : false
            foreground: root.barForeground
            fontFamily: root.bar ? root.bar.fontFamily : Style.font.family
            titleSize: Style.font.body
            onClicked: {
              if (root.client) {
                root.client.writeSetting("hideWhenNoData", !root.client.hideWhenNoData)
              }
            }
          }

          RowLayout {
            width: parent.width
            spacing: Style.space(8)

            Text {
              text: Model.formatRefreshLabel(root.client ? root.client.refreshIntervalMin : Model.REFRESH_DEFAULT_MINUTES)
              color: root.barForeground
              font.family: root.bar ? root.bar.fontFamily : Style.font.family
              font.pixelSize: Style.font.body
              Layout.fillWidth: true
              elide: Text.ElideRight
            }

            PanelActionButton {
              iconText: "−"
              tooltipText: "Faster"
              foreground: root.barForeground
              onClicked: root.bumpRefresh(-1)
            }

            PanelActionButton {
              iconText: "+"
              tooltipText: "Slower"
              foreground: root.barForeground
              onClicked: root.bumpRefresh(1)
            }
          }

          PanelSectionHeader {
            width: parent.width
            text: "PANEL"
            foreground: root.barForeground
            fontFamily: root.bar ? root.bar.fontFamily : Style.font.family
          }

          Toggle {
            width: parent.width
            label: "Overnight"
            description: "HRV, RHR, balance, and fatigue."
            checked: root.client ? root.client.showRecovery : true
            foreground: root.barForeground
            fontFamily: root.bar ? root.bar.fontFamily : Style.font.family
            titleSize: Style.font.body
            onClicked: {
              if (root.client) root.client.writeSetting("showRecovery", !root.client.showRecovery)
            }
          }

          Toggle {
            width: parent.width
            label: "Training load"
            description: "Daily, rolling, and weekly load."
            checked: root.client ? root.client.showLoad : true
            foreground: root.barForeground
            fontFamily: root.bar ? root.bar.fontFamily : Style.font.family
            titleSize: Style.font.body
            onClicked: {
              if (root.client) root.client.writeSetting("showLoad", !root.client.showLoad)
            }
          }

          Toggle {
            width: parent.width
            label: "Last activity"
            description: "Most recent Training Hub workout."
            checked: root.client ? root.client.showActivity : true
            foreground: root.barForeground
            fontFamily: root.bar ? root.bar.fontFamily : Style.font.family
            titleSize: Style.font.body
            onClicked: {
              if (root.client) root.client.writeSetting("showActivity", !root.client.showActivity)
            }
          }

          PanelSectionHeader {
            width: parent.width
            text: "ACCOUNT"
            foreground: root.barForeground
            fontFamily: root.bar ? root.bar.fontFamily : Style.font.family
          }

          Text {
            width: parent.width
            text: "Signed in · " + root.regionText
            color: root.barForeground
            opacity: 0.55
            font.family: root.bar ? root.bar.fontFamily : Style.font.family
            font.pixelSize: Style.font.body
            wrapMode: Text.WordWrap
          }

          Button {
            width: parent.width
            text: "Change account"
            foreground: root.barForeground
            bordered: true
            onClicked: root.openLogin()
          }
        }
      }
    }
    }
  }
}
