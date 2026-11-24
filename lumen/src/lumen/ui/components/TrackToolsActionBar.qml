import QtQuick

// Thanh ngang |N  Xoá  Huỷ| hiện bên phải thùng rác khi đang chọn bài để xoá.
// Tách khỏi TrackTools chỉ vì lý do độ dài file; nó không có trạng thái riêng,
// chỉ nhận số bài đã chọn rồi bắn hai tín hiệu ra.
Rectangle {
    id: root

    property int count: 0

    signal deleteClicked()
    signal cancelClicked()

    readonly property int colorMs: 120
    readonly property int buttonPadding: Theme.spacingMd
    readonly property real disabledOpacity: 0.4

    implicitWidth: row.implicitWidth + Theme.spacingSm * 2
    width: implicitWidth
    radius: Theme.radiusSm
    // Đủ đục để đọc được khi nằm cạnh danh sách bài hát; nền mờ 0.08 chìm hẳn.
    color: Theme.alpha(Theme.surfaceVariant, 0.96)
    border.width: 1
    border.color: Theme.alpha(Theme.outline, 0.5)

    Row {
        id: row

        anchors.centerIn: parent
        spacing: Theme.spacingSm

        // Chỉ con số, không kèm chữ — chủ dự án yêu cầu dạng |N  Xoá  Huỷ|.
        Text {
            anchors.verticalCenter: parent.verticalCenter
            leftPadding: Theme.spacingXs
            text: String(root.count)
            color: Theme.onSurfaceVariant
            font.pixelSize: Theme.fontSizeMd
            font.family: Theme.fontFamily
        }

        Rectangle {
            id: deleteButton

            anchors.verticalCenter: parent.verticalCenter
            width: deleteLabel.implicitWidth + root.buttonPadding * 2
            height: deleteLabel.implicitHeight + Theme.spacingXs * 2
            radius: Theme.radiusSm
            opacity: root.count > 0 ? 1 : root.disabledOpacity
            color: Theme.alpha(Theme.error, deleteArea.containsMouse ? 0.28 : 0.16)

            Behavior on color {
                ColorAnimation { duration: root.colorMs; easing.type: Easing.OutCubic }
            }
            Behavior on opacity {
                NumberAnimation { duration: root.colorMs; easing.type: Easing.OutCubic }
            }

            Text {
                id: deleteLabel

                anchors.centerIn: parent
                text: "Xoá"
                color: Theme.error
                font.pixelSize: Theme.fontSizeSm
                font.family: Theme.fontFamily
            }

            MouseArea {
                id: deleteArea

                anchors.fill: parent
                enabled: root.count > 0
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: root.deleteClicked()
            }
        }

        Rectangle {
            anchors.verticalCenter: parent.verticalCenter
            width: cancelLabel.implicitWidth + root.buttonPadding * 2
            height: cancelLabel.implicitHeight + Theme.spacingXs * 2
            radius: Theme.radiusSm
            color: cancelArea.containsMouse ? Theme.alpha(Theme.onSurface, 0.10) : "transparent"
            border.width: 1
            border.color: Theme.alpha(Theme.outline, 0.4)

            Behavior on color {
                ColorAnimation { duration: root.colorMs; easing.type: Easing.OutCubic }
            }

            Text {
                id: cancelLabel

                anchors.centerIn: parent
                text: "Huỷ"
                color: Theme.onSurfaceVariant
                font.pixelSize: Theme.fontSizeSm
                font.family: Theme.fontFamily
            }

            MouseArea {
                id: cancelArea

                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: root.cancelClicked()
            }
        }
    }
}
