import QtQuick

// Hộp cảnh báo xác nhận xoá nhiều bài khỏi track -- liệt kê rõ tên từng bài
// đã chọn để người dùng biết chính xác cái gì sắp mất trước khi bấm Xoá (yêu
// cầu chủ dự án). Chỉ gỡ khỏi track, KHÔNG đụng thư viện/file trên đĩa -- dòng
// phụ bên dưới nói rõ điều đó để người dùng không sợ mất file.
//
// visible gắn qua "opacity > ngưỡng" ở root (không chỉ ở lớp phủ) để khi
// đóng, MouseArea nuốt chuột cũng biến mất theo -- nếu không, lưới phía dưới
// sẽ bị khoá chuột dù hộp trông như đã đóng.
Item {
    id: root

    property bool open: false
    property var titles: []

    signal confirmed()
    signal cancelled()

    // Chỉ có ý nghĩa nội bộ.
    readonly property int cardMaxWidth: 420
    readonly property int maxListHeight: 200
    readonly property int buttonHeight: 44
    readonly property int fadeInMs: 160
    readonly property int fadeOutMs: 120

    // opacity/scale thay cho bật/tắt "visible" trần -- trước đây hộp cụp một
    // cái vì không có animation nào cả. Cùng cặp thời lượng/easing 160ms
    // OutCubic (vào) / 120ms InCubic (ra) mà VolumeButton.qml dùng cho Popup
    // của nó, và TrackDeleteConfirm.qml (hộp xoá cả track) dùng lại y hệt --
    // để mọi hộp nổi trong app chuyển động giống nhau.
    opacity: root.open ? 1 : 0
    visible: root.opacity > 0.01

    Behavior on opacity {
        NumberAnimation {
            duration: root.open ? root.fadeInMs : root.fadeOutMs
            easing.type: root.open ? Easing.OutCubic : Easing.InCubic
        }
    }

    // Chỉ tối đi RẤT nhẹ. Phần "tách nền" giờ do lớp MỜ của TrackView đảm nhận
    // (xem property blurStrength ở đó) — để nguyên 0.5 như trước thì nền đen kịt
    // và không còn nhìn ra đang mờ hay đang tắt đèn.
    Rectangle {
        anchors.fill: parent
        color: Theme.alpha(Theme.shadow, 0.18)
    }

    MouseArea {
        // Nuốt hết chuột, không cho lọt xuống lưới phía dưới.
        anchors.fill: parent
    }

    Rectangle {
        id: card

        anchors.centerIn: parent
        width: Math.min(root.cardMaxWidth, root.width - Theme.spacingXl * 2)
        height: body.height + Theme.spacingLg * 2
        radius: Theme.radiusLg
        color: Theme.alpha(Theme.surfaceVariant, 0.96)
        border.width: 1
        border.color: Theme.alpha(Theme.outline, 0.5)
        scale: root.open ? 1 : 0.92

        Behavior on scale {
            NumberAnimation {
                duration: root.open ? root.fadeInMs : root.fadeOutMs
                easing.type: root.open ? Easing.OutCubic : Easing.InCubic
            }
        }

        Column {
            id: body

            anchors.top: parent.top
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.margins: Theme.spacingLg
            spacing: Theme.spacingMd

            Text {
                width: parent.width
                text: "Xoá " + root.titles.length + " bài khỏi track?"
                color: Theme.onSurface
                font.pixelSize: Theme.fontSizeLg
                font.family: Theme.fontFamily
                wrapMode: Text.WordWrap
            }

            Text {
                width: parent.width
                text: "File mp3 của các bài này sẽ bị xoá khỏi máy. Không thể hoàn tác."
                color: Theme.onSurfaceVariant
                font.pixelSize: Theme.fontSizeSm
                font.family: Theme.fontFamily
                wrapMode: Text.WordWrap
            }

            Item {
                width: parent.width
                height: Math.min(root.maxListHeight, listView.contentHeight)
                clip: true

                ListView {
                    id: listView

                    anchors.fill: parent
                    clip: true
                    model: root.titles
                    spacing: Theme.spacingXs

                    delegate: Text {
                        width: listView.width
                        text: modelData
                        color: Theme.onSurfaceVariant
                        font.pixelSize: Theme.fontSizeSm
                        font.family: Theme.fontFamily
                        elide: Text.ElideRight
                    }
                }
            }

            Row {
                width: parent.width
                spacing: Theme.spacingSm

                Rectangle {
                    width: (parent.width - parent.spacing) / 2
                    height: root.buttonHeight
                    radius: Theme.radiusSm
                    color: cancelArea.containsMouse ? Theme.alpha(Theme.onSurface, 0.10) : "transparent"
                    border.width: 1
                    border.color: Theme.alpha(Theme.outline, 0.4)

                    Text {
                        anchors.centerIn: parent
                        text: "Chọn lại"
                        color: Theme.onSurfaceVariant
                        font.pixelSize: Theme.fontSizeSm
                        font.family: Theme.fontFamily
                    }

                    MouseArea {
                        id: cancelArea

                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.cancelled()
                    }
                }

                Rectangle {
                    width: (parent.width - parent.spacing) / 2
                    height: root.buttonHeight
                    radius: Theme.radiusSm
                    color: Theme.alpha(Theme.error, deleteArea.containsMouse ? 0.28 : 0.16)

                    Behavior on color {
                        ColorAnimation { duration: 120; easing.type: Easing.OutCubic }
                    }

                    Text {
                        anchors.centerIn: parent
                        text: "Xoá"
                        color: Theme.error
                        font.pixelSize: Theme.fontSizeSm
                        font.family: Theme.fontFamily
                    }

                    MouseArea {
                        id: deleteArea

                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.confirmed()
                    }
                }
            }
        }
    }
}
