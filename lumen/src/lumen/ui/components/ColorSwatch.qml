import QtQuick

// Một ô màu trong bảng chọn. Bấm là cả app đổi màu theo.
Rectangle {
    id: root

    property string label: ""
    property color tone: "transparent"
    property bool active: false

    signal picked()

    readonly property int swatchSize: 44
    readonly property int checkSize: 18

    width: root.swatchSize
    height: root.swatchSize
    radius: Theme.radiusMd
    color: root.tone
    border.width: root.active ? 2 : 1
    border.color: root.active
        ? Theme.onSurface
        : Theme.alpha(Theme.onSurface, hover.hovered ? 0.45 : 0.18)
    scale: hover.hovered && !root.active ? 1.06 : 1

    Behavior on scale {
        NumberAnimation { duration: 120; easing.type: Easing.OutCubic }
    }

    Behavior on border.color {
        ColorAnimation { duration: 120; easing.type: Easing.OutCubic }
    }

    HoverHandler { id: hover }

    // Dấu tick lấy màu tương phản với chính ô đó, không lấy theo theme: ô càng
    // sáng thì tick càng phải tối, và ngược lại.
    Text {
        anchors.centerIn: parent
        visible: root.active
        text: "check"
        color: root.tone.hslLightness > 0.5 ? "#141018" : "#ffffff"
        font.pixelSize: Math.max(Theme.iconSize - 2, Math.round((root.checkSize) * 1.4))
        font.family: Theme.iconFont
        font.variableAxes: ({ "FILL": 1 })
        // Font biến thiên + distance field vẽ vỡ nét icon trên cửa sổ thật (CB-058).
        renderType: Text.NativeRendering
    }

    MouseArea {
        anchors.fill: parent
        cursorShape: Qt.PointingHandCursor
        onClicked: root.picked()
    }
}
