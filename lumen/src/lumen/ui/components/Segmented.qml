import QtQuick

// Thanh chọn một-trong-nhiều của design R-1: rãnh tối bo tròn, ô đang chọn tô
// màu nhấn. `options` = [[giá trị, nhãn], …].
Rectangle {
    id: root

    property var options: []
    property string current: ""
    signal picked(string value)

    readonly property int pad: 3
    readonly property int cellHeight: 32

    implicitWidth: row.implicitWidth + root.pad * 2
    implicitHeight: root.cellHeight + root.pad * 2
    width: implicitWidth
    height: implicitHeight
    radius: Theme.radiusMd
    color: Theme.alpha(Theme.shadow, 0.18)
    border.width: 1
    border.color: Theme.alpha(Theme.onSurface, 0.075)

    Row {
        id: row
        x: root.pad
        y: root.pad

        Repeater {
            model: root.options

            Rectangle {
                id: cell

                required property var modelData
                readonly property bool on: root.current === cell.modelData[0]

                width: label.implicitWidth + Theme.spacingLg * 2
                height: root.cellHeight
                radius: Theme.radiusSm + 1
                color: cell.on ? Theme.primary : "transparent"
                scale: area.pressed ? 0.92 : 1
                Behavior on scale { NumberAnimation { duration: Math.max(1, 90 * Theme.motionScale); easing.type: Easing.OutCubic } }
                Behavior on color { ColorAnimation { duration: Math.max(1, 160 * Theme.motionScale); easing.type: Easing.OutCubic } }

                Text {
                    id: label
                    anchors.centerIn: parent
                    text: cell.modelData[1]
                    color: cell.on ? Theme.onPrimary : (area.containsMouse ? Theme.onSurface : Theme.onSurfaceVariant)
                    font.pixelSize: Theme.fontSizeSm + 1
                    font.weight: cell.on ? Font.DemiBold : Font.Normal
                    font.family: Theme.fontFamily
                }
                MouseArea {
                    id: area
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.picked(cell.modelData[0])
                }
            }
        }
    }
}
