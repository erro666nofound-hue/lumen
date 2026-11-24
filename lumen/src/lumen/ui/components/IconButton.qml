import QtQuick

Rectangle {
    id: root

    width: 28
    height: 28
    radius: Theme.radiusSm
    color: mouseArea.containsMouse ? Theme.alpha(Theme.onSurface, 0.10) : "transparent"

    property string glyph: ""
    property color hoverColor: Theme.onSurface

    signal clicked()

    Text {
        anchors.centerIn: parent
        text: root.glyph
        color: mouseArea.containsMouse ? root.hoverColor : Theme.onSurfaceVariant
        font.pixelSize: Math.max(Theme.iconSize - 2, Math.round((Theme.fontSizeMd) * 1.4))
        font.family: Theme.iconFont
        font.variableAxes: ({ "FILL": 1 })
        // Font biến thiên + distance field vẽ vỡ nét icon trên cửa sổ thật (CB-058).
        renderType: Text.NativeRendering

        Behavior on color {
            ColorAnimation { duration: 120; easing.type: Easing.OutCubic }
        }
    }

    Behavior on color {
        ColorAnimation { duration: 120; easing.type: Easing.OutCubic }
    }

    MouseArea {
        id: mouseArea

        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: root.clicked()
    }
}
