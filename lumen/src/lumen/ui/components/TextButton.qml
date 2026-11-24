import QtQuick

// Nút chữ có viền, dùng cho các việc phụ trong phần cài đặt.
Rectangle {
    id: root

    property string label: ""
    // Việc mang tính xoá bỏ thì tô theo màu cảnh báo.
    property bool danger: false

    signal clicked()

    readonly property int buttonHeight: 32

    width: text.implicitWidth + Theme.spacingLg
    height: root.buttonHeight
    radius: Theme.radiusSm
    color: hover.hovered
        ? Theme.alpha(root.danger ? Theme.error : Theme.primary, 0.16)
        : Theme.alpha(Theme.onSurface, 0.05)
    border.width: 1
    border.color: Theme.alpha(root.danger ? Theme.error : Theme.outline, 0.35)

    Behavior on color {
        ColorAnimation { duration: 120; easing.type: Easing.OutCubic }
    }

    HoverHandler { id: hover }

    Text {
        id: text

        anchors.centerIn: parent
        text: root.label
        color: hover.hovered
            ? (root.danger ? Theme.error : Theme.primary)
            : Theme.onSurface
        font.pixelSize: Theme.fontSizeMd
        font.family: Theme.fontFamily
    }

    MouseArea {
        anchors.fill: parent
        cursorShape: Qt.PointingHandCursor
        onClicked: root.clicked()
    }
}
