import QtQuick

// Nút viên thuốc của design R-1: icon + chữ. `filled` = nền màu nhấn (nút
// chính như Phát), không thì chỉ viền mảnh. Bấm lún 0.86 như dynsle.
Item {
    id: root

    property string icon: ""
    property string label: ""
    property bool filled: false
    signal clicked()

    readonly property int pillHeight: 40
    readonly property int pressMs: 90

    // Nút chỉ có icon (⋯) thì tròn đều.
    implicitWidth: root.label === "" ? root.pillHeight : row.implicitWidth + Theme.spacingLg * 2
    implicitHeight: root.pillHeight
    width: implicitWidth
    height: root.pillHeight
    opacity: root.enabled ? 1 : 0.45
    scale: area.pressed ? 0.86 : 1
    Behavior on scale { NumberAnimation { duration: Math.max(1, (root.pressMs) * Theme.motionScale); easing.type: Easing.OutCubic } }

    Rectangle {
        anchors.fill: parent
        radius: height / 2
        color: root.filled ? Theme.primary
            : (area.containsMouse ? Theme.alpha(Theme.onSurface, 0.06) : "transparent")
        border.width: root.filled ? 0 : 1
        border.color: Theme.alpha(Theme.onSurface, 0.12)
    }
    Row {
        id: row
        anchors.centerIn: parent
        spacing: Theme.spacingSm

        MIcon {
            visible: root.icon !== ""
            name: root.icon
            size: Theme.iconSize
            color: root.filled ? Theme.onPrimary : Theme.onSurface
            anchors.verticalCenter: parent.verticalCenter
        }
        Text {
            visible: root.label !== ""
            text: root.label
            color: root.filled ? Theme.onPrimary : Theme.onSurface
            font.pixelSize: Theme.fontSizeMd
            font.weight: Font.DemiBold
            font.family: Theme.fontFamily
            anchors.verticalCenter: parent.verticalCenter
        }
    }
    MouseArea {
        id: area
        anchors.fill: parent
        hoverEnabled: true
        enabled: root.enabled
        cursorShape: Qt.PointingHandCursor
        onClicked: root.clicked()
    }
}
