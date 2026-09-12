import QtQuick
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

  readonly property var client: hostWidget
  readonly property var snapshot: client ? client.snapshot : null

  readonly property string statusText: {
    if (!client) return ""
    if (client.actionStatus !== "") return client.actionStatus
    if (Model.authError(snapshot)) return "COROS login failed — re-run setup.sh, then Refresh."
    if (Model.isEmpty(snapshot)) return "No COROS data yet — check login, then Refresh."
    return ""
  }

  readonly property string hrvText: {
    if (!snapshot || snapshot.hrv === null || snapshot.hrv === undefined) return "—"
    var text = String(snapshot.hrv)
    if (snapshot.hrvBaseline !== null && snapshot.hrvBaseline !== undefined) {
      var delta = Model.hrvDelta(snapshot.hrv, snapshot.hrvBaseline)
      text += "  (baseline " + snapshot.hrvBaseline
      if (delta !== null) {
        var r = Math.round(delta)
        text += ", " + (r > 0 ? "+" + r : String(r))
      }
      text += ")"
    }
    return text
  }

  readonly property string sleepText: {
    if (!snapshot || snapshot.sleepH === null || snapshot.sleepH === undefined) return "—"
    var n = Number(snapshot.sleepH)
    return isFinite(n) ? n.toFixed(1) + " h" : "—"
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
    if (root.view === "settings") {
      root.view = "main"
    } else {
      root.close()
    }
  }

  function openSettings() {
    root.view = "settings"
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
    var next = client.refreshIntervalSec + delta
    client.writeSetting("refreshIntervalSec", Math.min(120, Math.max(5, next)))
  }

  function setRegion(value) {
    if (!client) return
    client.writeSetting("region", value === "us" ? "us" : "eu")
  }

  KeyboardPanel {
    id: panel
    anchorItem: root.anchorItem
    owner: root.hostWidget || root
    bar: root.bar
    open: root.opened
    focusTarget: keyCatcher
    contentWidth: panel.fittedContentWidth(Style.space(340))
    contentHeight: panel.fittedContentHeight(content.implicitHeight, Style.space(560))

    PanelKeyCatcher {
      id: keyCatcher
      anchors.fill: parent
      onCloseRequested: root.goBack()
      onTabRequested: function(direction) {
        root.switchPanel(direction)
      }

      Column {
        id: content
        width: parent.width
        spacing: Style.space(10)

        // ---- Header: title, refresh. ----
        Item {
          width: parent.width
          height: Math.max(title.implicitHeight, refreshLabel.implicitHeight)

          Text {
            id: title
            anchors.left: parent.left
            anchors.verticalCenter: parent.verticalCenter
            text: "COROS"
            color: root.barForeground
            font.family: root.bar ? root.bar.fontFamily : Style.font.family
            font.pixelSize: Style.font.subtitle
            font.bold: true
          }

          Text {
            id: refreshLabel
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            text: "Refresh"
            color: root.barForeground
            opacity: 0.65
            font.family: root.bar ? root.bar.fontFamily : Style.font.family
            font.pixelSize: Style.font.body

            MouseArea {
              anchors.fill: parent
              anchors.margins: -Style.space(4)
              cursorShape: Qt.PointingHandCursor
              onClicked: {
                if (client) client.refresh()
              }
            }
          }
        }

        Text {
          width: parent.width
          visible: root.view === "main" && statusText !== ""
          text: statusText
          color: root.barForeground
          opacity: 0.55
          font.family: root.bar ? root.bar.fontFamily : Style.font.family
          font.pixelSize: Style.font.body
          elide: Text.ElideMiddle
        }

        // ---- Main view: recovery metrics, footer with the gear. ----
        Column {
          visible: root.view === "main"
          width: parent.width
          spacing: Style.space(10)

          Column {
            width: parent.width
            spacing: Style.space(8)

            RowLayout {
              width: parent.width
              spacing: Style.space(8)
              Text {
                text: "HRV"
                color: root.barForeground
                opacity: 0.55
                font.family: root.bar ? root.bar.fontFamily : Style.font.family
                font.pixelSize: Style.font.body
                Layout.fillWidth: true
              }
              Text {
                text: root.hrvText
                color: root.barForeground
                font.family: root.bar ? root.bar.fontFamily : Style.font.family
                font.pixelSize: Style.font.body
              }
            }

            RowLayout {
              width: parent.width
              spacing: Style.space(8)
              Text {
                text: "Resting HR"
                color: root.barForeground
                opacity: 0.55
                font.family: root.bar ? root.bar.fontFamily : Style.font.family
                font.pixelSize: Style.font.body
                Layout.fillWidth: true
              }
              Text {
                text: root.snapshot ? root.metricText(root.snapshot.rhr) : "—"
                color: root.barForeground
                font.family: root.bar ? root.bar.fontFamily : Style.font.family
                font.pixelSize: Style.font.body
              }
            }

            RowLayout {
              width: parent.width
              spacing: Style.space(8)
              Text {
                text: "Training load"
                color: root.barForeground
                opacity: 0.55
                font.family: root.bar ? root.bar.fontFamily : Style.font.family
                font.pixelSize: Style.font.body
                Layout.fillWidth: true
              }
              Text {
                text: root.snapshot ? root.metricText(root.snapshot.load) : "—"
                color: root.barForeground
                font.family: root.bar ? root.bar.fontFamily : Style.font.family
                font.pixelSize: Style.font.body
              }
            }

            RowLayout {
              width: parent.width
              spacing: Style.space(8)
              Text {
                text: "Sleep"
                color: root.barForeground
                opacity: 0.55
                font.family: root.bar ? root.bar.fontFamily : Style.font.family
                font.pixelSize: Style.font.body
                Layout.fillWidth: true
              }
              Text {
                text: root.sleepText
                color: root.barForeground
                font.family: root.bar ? root.bar.fontFamily : Style.font.family
                font.pixelSize: Style.font.body
              }
            }

            RowLayout {
              width: parent.width
              spacing: Style.space(8)
              Text {
                text: "Last activity"
                color: root.barForeground
                opacity: 0.55
                font.family: root.bar ? root.bar.fontFamily : Style.font.family
                font.pixelSize: Style.font.body
                Layout.fillWidth: true
              }
              Text {
                text: root.snapshot ? root.metricText(root.snapshot.activity) : "—"
                // User-authored activity names: never interpret markup.
                textFormat: Text.PlainText
                color: root.barForeground
                font.family: root.bar ? root.bar.fontFamily : Style.font.family
                font.pixelSize: Style.font.body
                elide: Text.ElideRight
                Layout.maximumWidth: parent.width * 0.6
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
              Layout.alignment: Qt.AlignVCenter
              MouseArea {
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: root.openProject()
              }
            }

            Item {
              Layout.fillWidth: true
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

        // ---- Settings view: toggles, interval stepper, region. ----
        Column {
          visible: root.view === "settings"
          width: parent.width
          spacing: Style.space(10)

          Item {
            width: parent.width
            height: Math.max(settingsHeader.implicitHeight, backLabel.implicitHeight)

            PanelSectionHeader {
              id: settingsHeader
              anchors.left: parent.left
              anchors.verticalCenter: parent.verticalCenter
              text: "SETTINGS"
              foreground: root.barForeground
              fontFamily: root.bar ? root.bar.fontFamily : Style.font.family
            }

            Text {
              id: backLabel
              anchors.right: parent.right
              anchors.verticalCenter: parent.verticalCenter
              text: "Back"
              color: root.barForeground
              opacity: 0.65
              font.family: root.bar ? root.bar.fontFamily : Style.font.family
              font.pixelSize: Style.font.body

              MouseArea {
                anchors.fill: parent
                anchors.margins: -Style.space(4)
                cursorShape: Qt.PointingHandCursor
                onClicked: root.goBack()
              }
            }
          }

          Toggle {
            width: parent.width
            label: "Hide when no data"
            description: "Remove COROS from the bar until metrics arrive."
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
              text: "Refresh every " + (root.client ? root.client.refreshIntervalSec : 30) + "s"
              color: root.barForeground
              font.family: root.bar ? root.bar.fontFamily : Style.font.family
              font.pixelSize: Style.font.body
              Layout.fillWidth: true
              elide: Text.ElideRight
            }

            PanelActionButton {
              iconText: "−"
              tooltipText: "Slower"
              foreground: root.barForeground
              onClicked: root.bumpRefresh(-1)
            }

            PanelActionButton {
              iconText: "+"
              tooltipText: "Faster"
              foreground: root.barForeground
              onClicked: root.bumpRefresh(1)
            }
          }

          PanelSeparator {
            width: parent.width
          }

          RowLayout {
            width: parent.width
            spacing: Style.space(8)

            Text {
              text: "Region"
              color: root.barForeground
              opacity: 0.55
              font.family: root.bar ? root.bar.fontFamily : Style.font.family
              font.pixelSize: Style.font.body
              Layout.fillWidth: true
            }

            Text {
              text: "eu"
              color: root.barForeground
              opacity: root.client && root.client.region === "eu" ? 1.0 : 0.45
              font.family: root.bar ? root.bar.fontFamily : Style.font.family
              font.pixelSize: Style.font.body
              font.bold: root.client && root.client.region === "eu"

              MouseArea {
                anchors.fill: parent
                anchors.margins: -Style.space(4)
                cursorShape: Qt.PointingHandCursor
                onClicked: root.setRegion("eu")
              }
            }

            Text {
              text: "us"
              color: root.barForeground
              opacity: root.client && root.client.region === "us" ? 1.0 : 0.45
              font.family: root.bar ? root.bar.fontFamily : Style.font.family
              font.pixelSize: Style.font.body
              font.bold: root.client && root.client.region === "us"

              MouseArea {
                anchors.fill: parent
                anchors.margins: -Style.space(4)
                cursorShape: Qt.PointingHandCursor
                onClicked: root.setRegion("us")
              }
            }
          }

          Text {
            width: parent.width
            text: "Training Hub region for coros.py snapshot."
            color: root.barForeground
            opacity: 0.35
            font.family: root.bar ? root.bar.fontFamily : Style.font.family
            font.pixelSize: Style.font.caption
            wrapMode: Text.WordWrap
          }
        }
      }
    }
  }
}
