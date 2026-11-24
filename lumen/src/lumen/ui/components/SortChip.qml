import QtQuick

// Pill nhỏ để chọn tiêu chí sắp xếp thư viện — thay cho hàng tiêu đề cột
// đã bỏ khi thư viện chuyển sang lưới thẻ.
Rectangle {
    id: root

    property string label: ""
    property bool active: false
    property bool descending: false

    signal clicked()

    // Chỉ có ý nghĩa nội bộ: khoảng đệm ngang/dọc trong pill và khoảng cách tới mũi tên.
    readonly property int horizontalPadding: 14
    readonly property int chipHeight: 32
    readonly property int arrowSpacing: Theme.spacingXs

    implicitWidth: row.implicitWidth + root.horizontalPadding * 2
    implicitHeight: root.chipHeight
    // Design R-1: chip đang chọn tô đặc màu nhấn, chip khác chỉ viền mảnh.
    radius: height / 2
    color: root.active ? Theme.primary : "transparent"
    border.width: root.active ? 0 : 1
    border.color: Theme.alpha(Theme.onSurface, 0.12)
    Behavior on color {
        ColorAnimation { duration: 140; easing.type: Easing.OutCubic }
    }

    MouseArea {
        id: mouseArea

        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: root.clicked()
    }

    Row {
        id: row

        anchors.centerIn: parent
        spacing: root.arrowSpacing

        Text {
            anchors.verticalCenter: parent.verticalCenter
            text: root.label
            color: root.active ? Theme.onPrimary : (mouseArea.containsMouse ? Theme.onSurface : Theme.onSurfaceVariant)
            font.pixelSize: Theme.fontSizeSm + 1
            font.weight: root.active ? Font.DemiBold : Font.Normal
            font.family: Theme.fontFamily

            Behavior on color {
                ColorAnimation { duration: 140; easing.type: Easing.OutCubic }
            }
        }

        Text {
            visible: root.active
            anchors.verticalCenter: parent.verticalCenter
            text: root.descending ? "arrow_downward" : "arrow_upward"
            color: Theme.onPrimary
            font.pixelSize: Theme.fontSizeMd
            font.family: Theme.iconFont
            renderType: Text.NativeRendering
        }
    }
}
