import QtQuick

// URL của bài + nút chép. Bấm "Chép" đổi thành "Đã chép" một nhịp rồi trở lại,
// để người dùng biết cú bấm đã ăn (không có phản hồi thì không thể biết).
//
// QML KHÔNG có API clipboard. Mẹo "TextEdit ẩn + selectAll()/copy()" ĐÃ THỬ
// và ĐO trên máy này: clipboard giữ nguyên giá trị cũ, không ăn. Nên đi qua
// Clipboard (bridge/clipboard_bridge.py).
Item {
    id: root

    property string url: ""

    readonly property int rowHeight: 30
    readonly property int flashMs: 1200
    readonly property int hoverMs: 140

    implicitHeight: root.rowHeight

    Rectangle {
        anchors.fill: parent
        radius: Theme.radiusSm
        color: Theme.alpha(Theme.onSurface, 0.05)

        Text {
            id: urlText

            anchors.left: parent.left
            anchors.leftMargin: Theme.spacingSm
            anchors.right: copyButton.left
            anchors.rightMargin: Theme.spacingSm
            anchors.verticalCenter: parent.verticalCenter
            text: root.url
            color: Theme.onSurfaceVariant
            font.pixelSize: Theme.fontSizeSm
            font.family: Theme.fontFamily
            elide: Text.ElideMiddle
        }

        Rectangle {
            id: copyButton

            anchors.right: parent.right
            anchors.rightMargin: Theme.spacingXs
            anchors.verticalCenter: parent.verticalCenter
            width: copyLabel.implicitWidth + Theme.spacingMd
            height: parent.height - Theme.spacingXs * 2
            radius: Theme.radiusSm
            color: copied.running
                ? Theme.alpha(Theme.primary, 0.24)
                : (copyHover.hovered ? Theme.alpha(Theme.onSurface, 0.12) : "transparent")

            Behavior on color {
                ColorAnimation { duration: root.hoverMs; easing.type: Easing.OutCubic }
            }

            HoverHandler { id: copyHover }

            Text {
                id: copyLabel

                anchors.centerIn: parent
                text: copied.running ? "Đã chép" : "Chép"
                color: copied.running ? Theme.primary : Theme.onSurfaceVariant
                font.pixelSize: Theme.fontSizeSm
                font.family: Theme.fontFamily
            }

            MouseArea {
                anchors.fill: parent
                cursorShape: Qt.PointingHandCursor
                onClicked: {
                    Clipboard.setText(root.url)
                    copied.restart()
                }
            }

            Timer { id: copied; interval: root.flashMs }
        }
    }
}
