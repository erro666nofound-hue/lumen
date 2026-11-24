import QtQuick

// Hộp cảnh báo xác nhận xoá CẢ MỘT TRACK -- khác DeleteConfirmSheet.qml (chỉ
// gỡ vài bài đã chọn khỏi track, nhạc vẫn còn) và khác TrackToolsActionBar.qml
// (thanh ngang |N Xoá Huỷ| cạnh nút). Xoá track giờ xoá luôn nhạc + file mp3
// trên đĩa (Playlists.remove ở tầng Python), nên phải nói RÕ tên track và nói
// RÕ file sẽ mất, không dùng lại nguyên văn hai mẫu trên vì nội dung của
// chúng nói sai thứ sẽ xảy ra ở đây.
//
// Sống ở Main.qml (KHÔNG phải Sidebar.qml nữa) và phủ đúng vùng chrome+nội
// dung -- giống hệt cách DeleteConfirmSheet phủ TrackView -- vì thanh bên chỉ
// rộng Theme.sidebarWidth (208px), một thẻ co gọn trong đó bị bó hẹp ở góc
// trái thay vì nằm giữa màn hình. Nền phía sau được làm MỜ bởi lớp MultiEffect
// ở Main.qml (property contentBlurStrength, áp lên LibraryView/TrackView) --
// rectangle bên dưới ở component này chỉ tối rất nhẹ để không đè lên phần
// "tách nền" mà lớp mờ đã lo, y hệt DeleteConfirmSheet.qml.
//
// visible gắn qua "opacity > ngưỡng" ở root (không chỉ ở lớp phủ) để khi
// đóng, MouseArea nuốt chuột cũng biến mất theo -- nếu không, Thư viện/Track
// phía sau sẽ bị khoá chuột dù hộp trông như đã đóng. Animation vào/ra dùng
// Behavior (không phải Transition của QQC.Popup, vì đây là Item thường) --
// cùng cặp thời lượng/easing 160ms OutCubic (vào) và 120ms InCubic (ra) mà
// VolumeButton.qml dùng cho Popup của nó, để mọi hộp nổi trong app chuyển
// động giống nhau.
Item {
    id: root

    property bool open: false
    property string trackName: ""
    property int songCount: -1

    signal confirmed()
    signal cancelled()

    // Chỉ có ý nghĩa nội bộ.
    readonly property int cardMaxWidth: 420
    readonly property int buttonHeight: 44
    readonly property int fadeInMs: 160
    readonly property int fadeOutMs: 120

    opacity: root.open ? 1 : 0
    visible: root.opacity > 0.01

    Behavior on opacity {
        NumberAnimation {
            duration: root.open ? root.fadeInMs : root.fadeOutMs
            easing.type: root.open ? Easing.OutCubic : Easing.InCubic
        }
    }

    // Chỉ tối đi RẤT nhẹ -- phần "tách nền" chính là lớp MỜ do Main.qml đảm
    // nhận (contentBlurStrength), y hệt lý do đã ghi trong DeleteConfirmSheet.qml.
    Rectangle {
        anchors.fill: parent
        color: Theme.alpha(Theme.shadow, 0.18)
    }

    MouseArea {
        // Nuốt hết chuột, không cho lọt xuống Thư viện/Track phía sau.
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
                text: "Xoá track “" + root.trackName + "”?"
                color: Theme.onSurface
                font.pixelSize: Theme.fontSizeMd
                font.family: Theme.fontFamily
                wrapMode: Text.WordWrap
            }

            Text {
                width: parent.width
                text: (root.songCount >= 0 ? "Toàn bộ " + root.songCount + " bài" : "Toàn bộ bài")
                    + " bên trong sẽ bị xoá khỏi thư viện VÀ khỏi máy. Không thể hoàn tác."
                color: Theme.onSurfaceVariant
                font.pixelSize: Theme.fontSizeSm
                font.family: Theme.fontFamily
                wrapMode: Text.WordWrap
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

                    Behavior on color {
                        ColorAnimation { duration: 120; easing.type: Easing.OutCubic }
                    }

                    Text {
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
