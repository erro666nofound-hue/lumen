import QtQuick
import QtQuick.Effects

// Một bài trong "Nhạc của tôi": ảnh bên trái, tên bên phải.
//
// Cố ý NẰM NGANG và bằng khoảng nửa RecommendCard: mục này là cuốn sổ liệt kê
// mọi bài từng tải nên thường rất dài, thẻ dọc cỡ thẻ đề xuất sẽ đẩy trang dài
// gấp mấy lần mà chẳng cho thêm thông tin gì.
//
// Ảnh là URL https lấy theo video id (xem HistoryBridge), KHÔNG phải file trên
// máy: sổ còn kể cả những bài người dùng đã xoá, mà bài đã xoá thì không còn
// bìa nào trên đĩa nữa.
Rectangle {
    id: root

    property string title: ""
    property string artist: ""
    property string thumbnail: ""
    // Bài vẫn còn trên máy hay đã xoá — chỉ là một chấm nhỏ, không đổi bố cục.
    property bool stillOwned: false
    property bool selected: false

    signal clicked()

    readonly property int pad: Theme.spacingXs
    readonly property int thumbWidth: 76
    readonly property int hoverMs: 140

    height: root.thumbWidth * 9 / 16 + root.pad * 2
    radius: Theme.radiusMd
    color: root.selected
        ? Theme.alpha(Theme.primary, 0.18)
        : Theme.alpha(Theme.onSurface, hover.hovered ? 0.08 : 0.04)
    border.width: 1
    border.color: root.selected ? Theme.primary : Theme.alpha(Theme.outline, 0.18)

    Behavior on color {
        ColorAnimation { duration: root.hoverMs; easing.type: Easing.OutCubic }
    }

    Behavior on border.color {
        ColorAnimation { duration: root.hoverMs; easing.type: Easing.OutCubic }
    }

    HoverHandler { id: hover }

    Item {
        id: thumbBox

        anchors.left: parent.left
        anchors.leftMargin: root.pad
        anchors.verticalCenter: parent.verticalCenter
        width: root.thumbWidth
        height: width * 9 / 16

        // frame/mask cùng cấp cha trực tiếp — maskSource xuyên nhiều cấp cha
        // không đáng tin cậy (xem chú thích thực nghiệm ở TrackCard.qml).
        Item {
            id: thumbFrame

            anchors.fill: parent
            layer.enabled: true
            layer.effect: MultiEffect {
                maskEnabled: true
                maskSource: thumbMask
                autoPaddingEnabled: false
            }

            // Vẽ trước Image: chưa tải xong/không có ảnh thì Image trong suốt
            // để lộ đúng ô này, không cần theo dõi status.
            Rectangle {
                anchors.fill: parent
                color: Theme.alpha(Theme.primary, 0.14)

                Text {
                    anchors.centerIn: parent
                    text: "music_note"
                    color: Theme.primary
                    font.pixelSize: Math.max(Theme.iconSize - 2, Math.round((Theme.fontSizeMd) * 1.4))
                    font.family: Theme.iconFont
                    font.variableAxes: ({ "FILL": 1 })
                    // Font biến thiên + distance field vẽ vỡ nét icon trên cửa sổ thật (CB-058).
                    renderType: Text.NativeRendering
                }
            }

            Image {
                anchors.fill: parent
                visible: root.thumbnail !== ""
                source: root.thumbnail
                fillMode: Image.PreserveAspectCrop
                asynchronous: true
                clip: true
            }
        }

        Rectangle {
            id: thumbMask

            anchors.fill: parent
            radius: Theme.radiusSm
            visible: false
            layer.enabled: true
        }
    }

    Column {
        anchors.left: thumbBox.right
        anchors.leftMargin: Theme.spacingSm
        anchors.right: dot.left
        anchors.rightMargin: Theme.spacingXs
        anchors.verticalCenter: parent.verticalCenter
        spacing: 1

        Text {
            width: parent.width
            text: root.title !== "" ? root.title : "(không rõ tên)"
            color: Theme.onSurface
            font.pixelSize: Theme.fontSizeSm
            font.family: Theme.fontFamily
            elide: Text.ElideRight
            maximumLineCount: 2
            wrapMode: Text.WordWrap
        }

        Text {
            width: parent.width
            visible: root.artist !== ""
            text: root.artist
            color: Theme.onSurfaceVariant
            font.pixelSize: Theme.fontSizeSm
            font.family: Theme.fontFamily
            elide: Text.ElideRight
        }
    }

    // Còn trên máy hay đã xoá.
    Rectangle {
        id: dot

        anchors.right: parent.right
        anchors.rightMargin: root.pad + 2
        anchors.verticalCenter: parent.verticalCenter
        width: 6
        height: 6
        radius: 3
        color: root.stillOwned ? Theme.primary : Theme.alpha(Theme.onSurface, 0.25)
    }

    MouseArea {
        anchors.fill: parent
        cursorShape: Qt.PointingHandCursor
        onClicked: root.clicked()
    }
}
