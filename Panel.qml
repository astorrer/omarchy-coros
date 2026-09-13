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
  property bool cursorActive: false
  property string focusSection: "refresh"
  property int regionIndex: 1
  property int metricIndex: 1
  property int intervalIndex: 0
  readonly property var loginRegions: ["us", "eu"]
  readonly property var barMetrics: ["icon", "hrv", "rhr", "load", "fatigue"]
  readonly property var settingsSections: ["back", "metric", "hide", "interval", "overnight", "load", "activity", "account", "signout"]

  property var client: null
  readonly property var snapshot: client ? client.snapshot : null
  readonly property bool showLogin: view === "login" || (view === "main" && Model.authError(snapshot))
  readonly property string regionText: Model.regionLabel(client ? client.region : "eu")

  readonly property string statusText: {
    if (!client) return ""
    if (client.actionStatus !== "") return client.actionStatus
    if (client.loginBusy) return "Signing in…"
    if (!snapshot) return "Checking COROS…"
    if (Model.authError(snapshot)) return "Sign in required"
    if (Model.networkError(snapshot)) return "Can't reach Training Hub"
    if (Model.isEmpty(snapshot)) return "Signed in · " + regionText + " · waiting on metrics"
    return "Signed in · " + regionText
  }

  readonly property string hrvValue: metricText(snapshot ? snapshot.hrv : null)
  readonly property string hrvDeltaText: snapshot ? Model.formatDelta(Model.hrvDelta(snapshot.hrv, snapshot.hrvBaseline)) : ""
  readonly property var hrvBand: snapshot ? Model.hrvRange(snapshot) : null
  readonly property string hrvMeta: {
    var parts = ["Overnight HRV"]
    var day = snapshot ? Model.formatDay(snapshot.day) : ""
    if (day !== "") parts.push(day)
    return parts.join(" · ")
  }
  readonly property color dim: Qt.darker(barForeground, 1.4)
  readonly property string fontFamily: bar ? bar.fontFamily : Style.font.family
  readonly property bool showRecovery: !client || client.showRecovery
  readonly property bool showLoad: !client || client.showLoad
  readonly property bool showActivity: !client || client.showActivity
  readonly property string hrvToneName: snapshot ? Model.hrvTone(snapshot) : "neutral"
  readonly property string heroMood: snapshot ? Model.heroMood(snapshot) : "idle"
  readonly property var heroPhraseList: snapshot ? Model.heroPhrases(snapshot) : []
  readonly property bool rotatingPhrases: opened && view === "main" && !showLogin && heroPhraseList.length > 1
  property int phraseIndex: 0
  readonly property string heroStatusText: {
    if (showLogin) return ""
    if (Model.networkError(snapshot)) return "Can't reach Training Hub"
    if (!snapshot || Model.isEmpty(snapshot)) return "Waiting on metrics"
    if (heroPhraseList.length === 0) return "Signed in · " + regionText
    return heroPhraseList[phraseIndex % heroPhraseList.length]
  }
  readonly property string hrvRowValue: {
    var v = hrvValue
    if (v === "—" || hrvDeltaText === "") return v
    return v + " · " + hrvDeltaText
  }
  readonly property var groups: Model.metricGroups(snapshot, {
    recovery: showRecovery,
    load: showLoad,
    activity: showActivity
  })

  function toneColor(tone) {
    if (tone === "good") return Color.accent
    if (tone === "bad") return Color.urgent
    return root.barForeground
  }

  readonly property int metricColumns: 3

  function metricTileWidth(flow) {
    if (!flow) return 1
    var gaps = flow.spacing * (root.metricColumns - 1)
    return Math.max(1, Math.floor((flow.width - gaps) / root.metricColumns))
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
      cursorActive = false
      focusSection = root.loginReturn === "settings" ? "back" : "refresh"
      return
    }
    if (root.view === "settings") {
      root.view = "main"
      cursorActive = false
      focusSection = "refresh"
      return
    }
    root.close()
  }

  function openSettings() {
    root.view = "settings"
    cursorActive = false
    focusSection = "back"
    if (panelFlick) panelFlick.contentY = 0
  }

  function openLogin() {
    root.loginReturn = root.view === "settings" ? "settings" : "main"
    draftRegion = client && client.region === "us" ? "us" : "eu"
    draftPassword = ""
    cursorActive = false
    focusSection = "region"
    regionIndex = draftRegion === "us" ? 0 : 1
    root.view = "login"
    if (keyCatcher) keyCatcher.forceActiveFocus()
  }

  function submitLogin() {
    if (!client || client.loginBusy) return
    client.saveLogin(draftEmail, draftPassword, draftRegion)
    draftPassword = ""
    cursorActive = false
    focusSection = "refresh"
    root.view = "main"
    if (keyCatcher) keyCatcher.forceActiveFocus()
  }

  function signOut() {
    if (!client) return
    client.logout()
    draftPassword = ""
    cursorActive = false
    focusSection = "refresh"
    root.view = "main"
    if (keyCatcher) keyCatcher.forceActiveFocus()
  }

  function setCursor(section, index) {
    cursorActive = true
    focusSection = section
    if (index === undefined || index < 0) return
    if (section === "region") regionIndex = index
    else if (section === "metric") metricIndex = index
    else if (section === "interval") intervalIndex = index
  }

  function armCursor() {
    cursorActive = true
    if (showLogin) {
      if (focusSection !== "region" && focusSection !== "signin") {
        focusSection = "region"
        regionIndex = draftRegion === "us" ? 0 : 1
      }
    } else if (view === "settings") {
      if (settingsSections.indexOf(focusSection) < 0) focusSection = "back"
    } else if (focusSection !== "refresh" && focusSection !== "settings") {
      focusSection = "refresh"
    }
  }

  function moveCursor(dx, dy) {
    if (showLogin) moveLoginCursor(dx, dy)
    else if (view === "settings") moveSettingsCursor(dx, dy)
    else moveMainCursor(dy)
  }

  function moveLoginCursor(dx, dy) {
    if (focusSection !== "region" && focusSection !== "signin") {
      focusSection = "region"
      regionIndex = draftRegion === "us" ? 0 : 1
    }
    if (dy < 0) focusSection = "region"
    else if (dy > 0) focusSection = "signin"
    if (dx !== 0 && focusSection === "region")
      regionIndex = Math.max(0, Math.min(loginRegions.length - 1, regionIndex + dx))
  }

  function moveMainCursor(dy) {
    if (dy === 0) return
    focusSection = dy > 0 ? "settings" : "refresh"
  }

  function moveSettingsCursor(dx, dy) {
    if (dy !== 0) {
      var i = settingsSections.indexOf(focusSection)
      if (i < 0) i = 0
      focusSection = settingsSections[Math.max(0, Math.min(settingsSections.length - 1, i + dy))]
      if (focusSection === "metric") {
        var m = barMetrics.indexOf(client ? client.barMetric : "hrv")
        metricIndex = m < 0 ? 1 : m
      }
    }
    if (dx !== 0) {
      if (focusSection === "metric")
        metricIndex = Math.max(0, Math.min(barMetrics.length - 1, metricIndex + dx))
      else if (focusSection === "interval")
        intervalIndex = Math.max(0, Math.min(1, intervalIndex + dx))
      else if (focusSection === "account" && dx > 0)
        focusSection = "signout"
      else if (focusSection === "signout" && dx < 0)
        focusSection = "account"
    }
  }

  function activateCursor() {
    if (!cursorActive) return
    if (showLogin) {
      if (focusSection === "signin") submitLogin()
      else if (focusSection === "region") draftRegion = loginRegions[regionIndex] || "eu"
      return
    }
    if (view === "settings") {
      if (focusSection === "back") goBack()
      else if (focusSection === "metric") {
        if (client && metricIndex >= 0 && metricIndex < barMetrics.length)
          client.writeSetting("barMetric", barMetrics[metricIndex])
      } else if (focusSection === "hide") {
        if (client) client.writeSetting("hideWhenNoData", !client.hideWhenNoData)
      } else if (focusSection === "interval") {
        bumpRefresh(intervalIndex === 0 ? -1 : 1)
      } else if (focusSection === "overnight") {
        if (client) client.writeSetting("showRecovery", !client.showRecovery)
      } else if (focusSection === "load") {
        if (client) client.writeSetting("showLoad", !client.showLoad)
      } else if (focusSection === "activity") {
        if (client) client.writeSetting("showActivity", !client.showActivity)
      } else if (focusSection === "account") {
        openLogin()
      } else if (focusSection === "signout") {
        signOut()
      }
      return
    }
    if (focusSection === "refresh") {
      if (client) client.refresh()
    } else if (focusSection === "settings") {
      openSettings()
    }
  }

  function openProject() {
    Qt.openUrlExternally(Model.PROJECT_URL)
  }

  function switchPanel(direction) {
    if (root.bar && typeof root.bar.switchPanelFrom === "function")
      return root.bar.switchPanelFrom(root.hostWidget || root, direction)
    return false
  }

  onHeroMoodChanged: phraseIndex = 0
  onOpenedChanged: if (opened) {
    cursorActive = false
    Qt.callLater(function() { if (keyCatcher) keyCatcher.forceActiveFocus() })
  }

  Timer {
    id: phraseTimer
    interval: 2800
    running: root.rotatingPhrases
    repeat: true
    onTriggered: phraseSwap.restart()
  }

  SequentialAnimation {
    id: phraseSwap
    PropertyAnimation {
      target: hero
      property: "metaOpacity"
      to: 0.0
      duration: 180
      easing.type: Easing.OutQuad
    }
    ScriptAction {
      script: {
        var n = root.heroPhraseList.length
        if (n > 0) root.phraseIndex = (root.phraseIndex + 1) % n
      }
    }
    PropertyAnimation {
      target: hero
      property: "metaOpacity"
      to: 1.0
      duration: 260
      easing.type: Easing.InQuad
    }
  }

  Connections {
    target: root
    function onRotatingPhrasesChanged() {
      if (!root.rotatingPhrases) {
        phraseSwap.stop()
        if (hero) hero.metaOpacity = 1.0
      }
    }
  }

  function bumpRefresh(delta) {
    if (!client) return
    client.writeSetting(
      "refreshIntervalMin",
      Model.clampRefreshMinutes(client.refreshIntervalMin + delta * Model.REFRESH_STEP_MINUTES)
    )
  }

  component RangeBar: Item {
    id: rangeBar
    property var lo: null
    property var hi: null
    property var pos: null
    property var mark: null
    property string tone: "neutral"
    readonly property color ink: root.toneColor(tone)
    readonly property bool ready: {
      if (lo === null || lo === undefined || hi === null || hi === undefined || pos === null || pos === undefined)
        return false
      var a = Number(lo), b = Number(hi), c = Number(pos)
      return isFinite(a) && isFinite(b) && isFinite(c)
    }
    visible: ready
    width: parent ? parent.width : 0
    implicitHeight: ready ? ink.height + Style.space(2) + captions.height : 0
    height: implicitHeight
    clip: true

    readonly property real dmin: {
      if (!ready) return 0
      var m = Math.min(Number(lo), Number(hi), Number(pos))
      var k = Number(mark)
      if (isFinite(k)) m = Math.min(m, k)
      return m
    }
    readonly property real dmax: {
      if (!ready) return 1
      var m = Math.max(Number(lo), Number(hi), Number(pos))
      var k = Number(mark)
      if (isFinite(k)) m = Math.max(m, k)
      return m === dmin ? dmin + 1 : m
    }

    readonly property bool bandIsWindow: {
      if (!ready) return false
      var span = dmax - dmin
      if (span <= 0) return false
      return Math.abs(Number(hi) - Number(lo)) / span < 0.95
    }

    function xAt(v) {
      var span = dmax - dmin
      if (span <= 0 || width <= 0) return 0
      var t = (Number(v) - dmin) / span
      if (t < 0) t = 0
      if (t > 1) t = 1
      return t * width
    }

    function clampLabelX(center, labelWidth) {
      var pos = center - labelWidth / 2
      if (pos < 0) return 0
      if (pos + labelWidth > width) return Math.max(0, width - labelWidth)
      return pos
    }

    Item {
      id: ink
      width: parent.width
      height: Style.space(8)

      Rectangle {
        id: track
        anchors.fill: parent
        radius: height / 2
        color: Qt.rgba(root.barForeground.r, root.barForeground.g, root.barForeground.b, 0.12)
      }

      Rectangle {
        visible: rangeBar.ready && rangeBar.bandIsWindow
        x: Math.min(rangeBar.xAt(rangeBar.lo), rangeBar.xAt(rangeBar.hi))
        width: Math.max(track.height, Math.abs(rangeBar.xAt(rangeBar.hi) - rangeBar.xAt(rangeBar.lo)))
        anchors.verticalCenter: track.verticalCenter
        height: track.height
        radius: height / 2
        color: Color.accent
        Behavior on x { NumberAnimation { duration: 320; easing.type: Easing.OutCubic } }
        Behavior on width { NumberAnimation { duration: 320; easing.type: Easing.OutCubic } }
        Behavior on color { ColorAnimation { duration: 220 } }
      }

      Rectangle {
        visible: rangeBar.ready && isFinite(Number(rangeBar.mark))
        x: rangeBar.xAt(rangeBar.mark) - 0.5
        width: 1
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        color: root.barForeground
        opacity: 0.45
      }

      Rectangle {
        id: thumb
        visible: rangeBar.ready
        width: Style.space(8)
        height: Style.space(8)
        radius: height / 2
        color: root.barForeground
        anchors.verticalCenter: track.verticalCenter
        x: Math.min(Math.max(0, rangeBar.xAt(rangeBar.pos) - width / 2), Math.max(0, parent.width - width))
        Behavior on x { NumberAnimation { duration: 320; easing.type: Easing.OutCubic } }
        SequentialAnimation on opacity {
          running: root.opened && root.view === "main" && rangeBar.tone === "bad"
          loops: Animation.Infinite
          alwaysRunToEnd: true
          NumberAnimation { from: 1.0; to: 0.35; duration: 480; easing.type: Easing.InOutSine }
          NumberAnimation { from: 0.35; to: 1.0; duration: 480; easing.type: Easing.InOutSine }
        }
      }
    }

    Item {
      id: captions
      y: ink.height + Style.space(2)
      width: parent.width
      height: Math.max(loLabel.implicitHeight, hiLabel.implicitHeight, combinedLabel.implicitHeight)

      readonly property real loX: rangeBar.clampLabelX(rangeBar.xAt(rangeBar.lo), loLabel.implicitWidth)
      readonly property real hiX: rangeBar.clampLabelX(rangeBar.xAt(rangeBar.hi), hiLabel.implicitWidth)
      readonly property bool overlap: loX + loLabel.implicitWidth + Style.space(6) > hiX

      Text {
        id: loLabel
        visible: !captions.overlap
        x: captions.loX
        text: Model.formatTick(rangeBar.lo)
        color: root.dim
        font.family: root.fontFamily
        font.pixelSize: Style.font.caption
      }

      Text {
        id: hiLabel
        visible: !captions.overlap
        x: captions.hiX
        text: Model.formatTick(rangeBar.hi)
        color: root.dim
        font.family: root.fontFamily
        font.pixelSize: Style.font.caption
      }

      Text {
        id: combinedLabel
        visible: captions.overlap
        x: rangeBar.clampLabelX(
          (rangeBar.xAt(rangeBar.lo) + rangeBar.xAt(rangeBar.hi)) / 2,
          implicitWidth
        )
        text: Model.formatTick(rangeBar.lo) + "–" + Model.formatTick(rangeBar.hi)
        color: root.dim
        font.family: root.fontFamily
        font.pixelSize: Style.font.caption
      }
    }
  }

  component StepMeter: Row {
    id: meter
    property int count: 5
    property int step: 0
    property string tone: "neutral"
    property bool live: false
    visible: count > 0 && step > 0
    spacing: Style.space(4)
    readonly property int pulseMs: tone === "bad" ? 420 : 900
    readonly property real pulseFloor: tone === "bad" ? 0.2 : 0.4

    Repeater {
      model: meter.count
      Rectangle {
        id: dot
        required property int index
        readonly property bool activeDot: (index + 1) === meter.step
        width: Style.space(7)
        height: Style.space(7)
        radius: width / 2
        color: activeDot ? root.toneColor(meter.tone) : root.barForeground
        opacity: activeDot ? 1.0 : 0.18
        Behavior on color { ColorAnimation { duration: 220 } }

        SequentialAnimation on opacity {
          running: meter.live && dot.activeDot
          loops: Animation.Infinite
          alwaysRunToEnd: true
          NumberAnimation { from: 1.0; to: meter.pulseFloor; duration: meter.pulseMs; easing.type: Easing.InOutSine }
          NumberAnimation { from: meter.pulseFloor; to: 1.0; duration: meter.pulseMs; easing.type: Easing.InOutSine }
          onRunningChanged: if (!running) dot.opacity = dot.activeDot ? 1.0 : 0.18
        }
      }
    }
  }

  component MetricTile: Item {
    id: tile
    property string icon: ""
    property string label: ""
    property string value: "—"
    property string hint: ""
    property int steps: 0
    property int step: 0
    property string tone: "neutral"
    property bool marquee: false
    property bool live: root.opened && root.view === "main" && !root.showLogin
    readonly property color ink: root.toneColor(tone)
    readonly property bool heartPulse: icon === Model.ICON.rhr
    implicitHeight: body.implicitHeight
    implicitWidth: body.implicitWidth

    Row {
      id: body
      width: parent.width
      spacing: Style.space(8)

      Text {
        id: iconGlyph
        width: Style.space(20)
        text: tile.icon
        color: tile.ink
        font.family: root.fontFamily
        font.pixelSize: Style.font.iconLarge
        horizontalAlignment: Text.AlignHCenter
        anchors.verticalCenter: parent.verticalCenter
        Behavior on color { ColorAnimation { duration: 220 } }
        transformOrigin: Item.Center
        SequentialAnimation on scale {
          running: tile.live && tile.heartPulse
          loops: Animation.Infinite
          alwaysRunToEnd: true
          NumberAnimation { to: 1.18; duration: 90; easing.type: Easing.OutQuad }
          NumberAnimation { to: 1.0; duration: 90; easing.type: Easing.InQuad }
          NumberAnimation { to: 1.12; duration: 80; easing.type: Easing.OutQuad }
          NumberAnimation { to: 1.0; duration: 120; easing.type: Easing.InQuad }
          PauseAnimation { duration: 720 }
          onRunningChanged: if (!running) iconGlyph.scale = 1
        }
      }

      Column {
        width: Math.max(0, body.width - Style.space(20) - body.spacing)
        spacing: Style.space(1)

        Item {
          id: valueClip
          width: parent.width
          height: valueText.implicitHeight
          clip: tile.marquee

          Text {
            id: valueText
            width: tile.marquee ? implicitWidth : valueClip.width
            textFormat: Text.PlainText
            text: tile.value
            color: tile.ink
            font.family: root.fontFamily
            font.pixelSize: Style.font.heading
            font.bold: true
            elide: tile.marquee ? Text.ElideNone : Text.ElideRight
            Behavior on color { ColorAnimation { duration: 220 } }
            readonly property bool needsScroll: tile.marquee && implicitWidth > valueClip.width + 1

            SequentialAnimation {
              running: valueText.needsScroll && tile.live
              loops: Animation.Infinite
              alwaysRunToEnd: true
              PauseAnimation { duration: 1800 }
              NumberAnimation {
                target: valueText
                property: "x"
                from: 0
                to: valueClip.width - valueText.implicitWidth
                duration: Math.max(4000, Math.round(valueText.implicitWidth * 22))
                easing.type: Easing.InOutQuad
              }
              PauseAnimation { duration: 1000 }
              NumberAnimation {
                target: valueText
                property: "x"
                to: 0
                duration: 500
                easing.type: Easing.InOutQuad
              }
              onRunningChanged: if (!running) valueText.x = 0
            }
          }
        }

        Text {
          width: parent.width
          textFormat: Text.PlainText
          text: tile.label.toUpperCase()
          color: root.dim
          font.family: root.fontFamily
          font.pixelSize: Style.font.caption
          font.bold: true
          font.letterSpacing: 1.2
          elide: Text.ElideRight
        }

        StepMeter {
          count: tile.steps
          step: tile.step
          tone: tile.tone
          live: tile.live
        }

        Text {
          width: parent.width
          visible: tile.hint !== ""
          textFormat: Text.PlainText
          text: tile.hint.toUpperCase()
          color: root.dim
          font.family: root.fontFamily
          font.pixelSize: Style.font.caption
          font.bold: true
          font.letterSpacing: 1.2
          elide: Text.ElideRight
        }
      }
    }
  }

  component RangeRow: Column {
    id: row
    property string label: ""
    property string value: ""
    property string tone: "neutral"
    property var lo: null
    property var hi: null
    property var pos: null
    property var mark: null
    spacing: Style.space(2)

    Row {
      width: parent.width
      spacing: Style.space(8)

      Text {
        width: Math.max(0, parent.width - valueLabel.implicitWidth - parent.spacing)
        textFormat: Text.PlainText
        text: row.label.toUpperCase()
        color: root.dim
        font.family: root.fontFamily
        font.pixelSize: Style.font.caption
        font.bold: true
        font.letterSpacing: 1.2
        elide: Text.ElideRight
        anchors.verticalCenter: parent.verticalCenter
      }

      Text {
        id: valueLabel
        textFormat: Text.PlainText
        text: row.value
        color: root.toneColor(row.tone)
        font.family: root.fontFamily
        font.pixelSize: Style.font.body
        font.bold: true
        elide: Text.ElideRight
      }
    }

    RangeBar {
      width: parent.width
      lo: row.lo
      hi: row.hi
      pos: row.pos
      mark: row.mark
      tone: row.tone
    }
  }

  KeyboardPanel {
    id: panel
    anchorItem: root.anchorItem
    owner: root.hostWidget || root
    bar: root.bar
    open: root.opened
    focusTarget: keyCatcher
    contentWidth: panel.fittedContentWidth(Style.space(480))
    contentHeight: panel.fittedContentHeight(content.implicitHeight, Style.space(620))

    PanelKeyCatcher {
      id: keyCatcher
      anchors.fill: parent
      blocked: emailField.activeFocus || passwordField.activeFocus
      onCloseRequested: root.goBack()
      onTabRequested: function(direction) {
        root.switchPanel(direction)
      }
      onMoveRequested: function(dx, dy) {
        if (root.showLogin && !root.cursorActive && dy > 0) {
          emailField.forceActiveFocus()
          return
        }
        if (!root.cursorActive) {
          root.armCursor()
          return
        }
        root.moveCursor(dx, dy)
      }
      onActivateRequested: root.activateCursor()
      onTextKey: function(t) {
        if ((t === "r" || t === "R") && root.client && !root.showLogin)
          root.client.refresh()
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
          spacing: Style.space(14)

        RowLayout {
          visible: root.view === "settings" || root.showLogin
          width: parent.width
          spacing: Style.space(8)

          Text {
            textFormat: Text.PlainText
            text: root.view === "settings" ? "Settings" : "COROS"
            color: root.barForeground
            font.family: root.fontFamily
            font.pixelSize: Style.font.subtitle
            font.bold: true
            elide: Text.ElideRight
            Layout.fillWidth: true
          }

          Button {
            visible: root.view === "settings"
            text: "Back"
            foreground: root.barForeground
            bordered: true
            Layout.alignment: Qt.AlignRight | Qt.AlignVCenter
            hasCursor: root.cursorActive && root.view === "settings" && root.focusSection === "back"
            onHovered: function(on) { if (on) root.setCursor("back") }
            onClicked: root.goBack()
          }
        }

        Text {
          width: parent.width
          visible: root.statusText !== "" && root.view !== "settings" && (root.showLogin || Model.isEmpty(root.snapshot) || Model.networkError(root.snapshot) || (root.client && root.client.actionStatus !== ""))
          textFormat: Text.PlainText
          text: root.statusText
          color: (Model.authError(root.snapshot) || Model.networkError(root.snapshot)) && !(root.client && root.client.actionStatus) ? Color.urgent : root.dim
          font.family: root.fontFamily
          font.pixelSize: Style.font.bodySmall
          wrapMode: Text.WordWrap
        }

        Column {
          visible: root.showLogin
          width: parent.width
          height: visible ? implicitHeight : 0
          spacing: Style.space(10)

          TextField {
            id: emailField
            width: parent.width
            placeholderText: "Email"
            text: root.draftEmail
            foreground: root.barForeground
            onTextChanged: root.draftEmail = text
            Keys.onReturnPressed: passwordField.forceActiveFocus()
            Keys.onEscapePressed: function(event) {
              root.goBack()
              keyCatcher.forceActiveFocus()
              event.accepted = true
            }
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
            Keys.onEscapePressed: function(event) {
              root.goBack()
              keyCatcher.forceActiveFocus()
              event.accepted = true
            }
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
            cursorIndex: root.cursorActive && root.showLogin && root.focusSection === "region" ? root.regionIndex : -1
            onChanged: function(value) { root.draftRegion = value }
            onHovered: function(index, isHovered) {
              if (isHovered) root.setCursor("region", index)
            }
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
            hasCursor: root.cursorActive && root.showLogin && root.focusSection === "signin"
            onHovered: function(on) { if (on) root.setCursor("signin") }
            onClicked: root.submitLogin()
          }
        }

        Column {
          visible: root.view === "main" && !root.showLogin
          width: parent.width
          height: visible ? implicitHeight : 0
          spacing: Style.space(14)

          Item {
            id: header
            width: parent.width
            implicitHeight: hero.implicitHeight
            readonly property bool refreshHasCursor: root.cursorActive && root.view === "main" && !root.showLogin && root.focusSection === "refresh"
            function refreshNow() {
              if (root.client) root.client.refresh()
            }
            function focusRefresh() { root.setCursor("refresh") }

            PanelHero {
              id: hero
              width: parent.width
              title: "COROS"
              meta: root.heroStatusText
              foreground: root.barForeground
              fontFamily: root.fontFamily
              iconComponent: Component {
                CorosIcon {
                  iconSize: Style.font.display
                  color: root.barForeground
                }
              }
              trailingControl: Component {
                PanelActionButton {
                  iconText: "󰑐"
                  tooltipText: "Refresh"
                  foreground: hero.foreground
                  fontFamily: hero.fontFamily
                  hasCursor: header.refreshHasCursor
                  onHovered: function(on) { if (on) header.focusRefresh() }
                  onClicked: header.refreshNow()
                }
              }
            }
          }

          Column {
            visible: root.showRecovery && (root.groups.recovery.length > 0 || root.hrvBand)
            width: parent.width
            spacing: Style.space(6)

            PanelSectionHeader {
              width: parent.width
              text: "OVERNIGHT"
              foreground: root.barForeground
              fontFamily: root.fontFamily
              font.letterSpacing: 1.2
            }

            RangeRow {
              visible: root.hrvBand !== null
              width: parent.width
              label: "HRV"
              value: root.hrvRowValue
              tone: root.hrvToneName
              lo: root.hrvBand ? root.hrvBand.lo : null
              hi: root.hrvBand ? root.hrvBand.hi : null
              pos: root.hrvBand ? root.hrvBand.pos : null
              mark: root.hrvBand ? root.hrvBand.mark : null
            }

            Flow {
              width: parent.width
              spacing: Style.space(12)

              Repeater {
                model: root.groups.recovery
                MetricTile {
                  required property var modelData
                  width: root.metricTileWidth(parent)
                  icon: modelData.icon
                  label: modelData.label
                  value: modelData.value
                  hint: modelData.hint
                  steps: modelData.steps
                  step: modelData.step
                  tone: modelData.tone
                }
              }
            }
          }

          Column {
            visible: root.showLoad && (root.groups.load.length > 0 || root.groups.bars.length > 0)
            width: parent.width
            spacing: Style.space(6)

            PanelSeparator {
              visible: root.showRecovery && root.groups.recovery.length > 0
              foreground: root.barForeground
            }

            PanelSectionHeader {
              width: parent.width
              text: "LOAD"
              foreground: root.barForeground
              fontFamily: root.fontFamily
              font.letterSpacing: 1.2
            }

            Flow {
              width: parent.width
              spacing: Style.space(12)

              Repeater {
                model: root.groups.load
                MetricTile {
                  required property var modelData
                  width: root.metricTileWidth(parent)
                  icon: modelData.icon
                  label: modelData.label
                  value: modelData.value
                  hint: modelData.hint
                  steps: modelData.steps
                  step: modelData.step
                  tone: modelData.tone
                }
              }
            }

            Item {
              visible: root.groups.bars.length > 0
              width: parent.width
              height: Style.space(8)
            }

            Repeater {
              model: root.groups.bars
              RangeRow {
                required property var modelData
                width: parent.width
                label: modelData.label
                value: modelData.value
                tone: modelData.tone
                lo: modelData.lo
                hi: modelData.hi
                pos: modelData.pos
                mark: modelData.mark
              }
            }
          }

          Repeater {
            model: root.groups.activity
            MetricTile {
              required property var modelData
              width: parent.width
              icon: modelData.icon
              label: modelData.label
              value: modelData.value
              hint: modelData.hint
              tone: modelData.tone
              marquee: true
            }
          }

          PanelSeparator {
            foreground: root.barForeground
          }

          RowLayout {
            width: parent.width
            spacing: Style.space(10)

            Text {
              textFormat: Text.PlainText
              text: "COROS " + Model.PLUGIN_VERSION
              color: root.dim
              font.family: root.fontFamily
              font.pixelSize: Style.font.caption
              font.letterSpacing: 1.2
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
              fontFamily: root.fontFamily
              Layout.alignment: Qt.AlignVCenter
              hasCursor: root.cursorActive && root.view === "main" && !root.showLogin && root.focusSection === "settings"
              onHovered: function(on) { if (on) root.setCursor("settings") }
              onClicked: root.openSettings()
            }
          }
        }

        Column {
          visible: root.view === "settings"
          width: parent.width
          height: visible ? implicitHeight : 0
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
            cursorIndex: root.cursorActive && root.view === "settings" && root.focusSection === "metric" ? root.metricIndex : -1
            onChanged: function(value) {
              if (root.client) root.client.writeSetting("barMetric", value)
            }
            onHovered: function(index, isHovered) {
              if (isHovered) root.setCursor("metric", index)
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
            hasCursor: root.cursorActive && root.view === "settings" && root.focusSection === "hide"
            onHovered: function(on) { if (on) root.setCursor("hide") }
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
              hasCursor: root.cursorActive && root.view === "settings" && root.focusSection === "interval" && root.intervalIndex === 0
              onHovered: function(on) { if (on) root.setCursor("interval", 0) }
              onClicked: root.bumpRefresh(-1)
            }

            PanelActionButton {
              iconText: "+"
              tooltipText: "Slower"
              foreground: root.barForeground
              hasCursor: root.cursorActive && root.view === "settings" && root.focusSection === "interval" && root.intervalIndex === 1
              onHovered: function(on) { if (on) root.setCursor("interval", 1) }
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
            hasCursor: root.cursorActive && root.view === "settings" && root.focusSection === "overnight"
            onHovered: function(on) { if (on) root.setCursor("overnight") }
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
            hasCursor: root.cursorActive && root.view === "settings" && root.focusSection === "load"
            onHovered: function(on) { if (on) root.setCursor("load") }
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
            hasCursor: root.cursorActive && root.view === "settings" && root.focusSection === "activity"
            onHovered: function(on) { if (on) root.setCursor("activity") }
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

          RowLayout {
            width: parent.width
            spacing: Style.space(8)

            Button {
              text: "Change account"
              foreground: root.barForeground
              bordered: true
              Layout.fillWidth: true
              hasCursor: root.cursorActive && root.view === "settings" && root.focusSection === "account"
              onHovered: function(on) { if (on) root.setCursor("account") }
              onClicked: root.openLogin()
            }

            Button {
              text: "Sign out"
              foreground: root.barForeground
              bordered: true
              Layout.fillWidth: true
              hasCursor: root.cursorActive && root.view === "settings" && root.focusSection === "signout"
              onHovered: function(on) { if (on) root.setCursor("signout") }
              onClicked: root.signOut()
            }
          }
        }
      }
    }
    }
  }
}
