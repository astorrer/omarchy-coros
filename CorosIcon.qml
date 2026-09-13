import QtQuick
import QtQuick.Shapes
import qs.Commons

// Official COROS mark from https://www.coros.com/public/images/COROS.svg
// filled with the bar foreground. Path is fitted to its ink bounds so the
// open hex sits in the optical canvas instead of the padded 1024 viewBox.
Item {
  id: root

  property real iconSize: Style.font.icon
  property color color: Color.foreground
  property bool dimmed: false

  width: iconSize
  height: iconSize
  implicitWidth: iconSize
  implicitHeight: iconSize
  opacity: dimmed ? 0.55 : 1.0

  readonly property real pathMinX: 120.10795918
  readonly property real pathMinY: 56.55789909
  readonly property real pathW: 804.96743424
  readonly property real pathH: 910.88420182
  readonly property real pad: 1.5
  readonly property real s: {
    var inner = Math.max(1, Math.min(width, height) - pad * 2)
    return Math.min(inner / pathW, inner / pathH)
  }

  // Position the viewBox so ink is centered. No layer: rasterizing a Shape
  // with a negative origin shifts the mark right of the slot underline.
  Shape {
    antialiasing: true
    preferredRendererType: Shape.CurveRenderer
    x: (root.width - root.pathW * root.s) / 2 - root.pathMinX * root.s
    y: (root.height - root.pathH * root.s) / 2 - root.pathMinY * root.s
    width: 1024 * root.s
    height: 1024 * root.s

    ShapePath {
      fillColor: root.color
      strokeWidth: 0
      scale: Qt.size(root.s, root.s)
      PathSvg {
        path: "M611.28637781 226.3848448l313.2594324 182.00737337L925.07539342 786.3244288 612.34554539 967.44210091l-52.8312832-28.51279417 245.1761334-182.36749028L804.22436181 437.85826304 562.20454798 254.81290525l49.08182983-28.42806045zM171.15984213 335.14018133l34.86779961 304.15059058 275.38359524 158.95988452 279.04831715-118.71151332v56.85612089l-313.7678336 181.11767325L120.10795918 728.9599067V366.78811193l51.03069867-31.62674745zM569.19505465 56.55789909l312.72984804 181.11767211 1.80058566 60.13954162-280.04393414-121.80428345-274.9175626 159.76485205-37.02850219 301.75687111-49.06064668-28.42806044 0.50840121-363.12504548L569.19505465 56.55789909z"
      }
    }
  }
}
