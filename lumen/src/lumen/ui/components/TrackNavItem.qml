import QtQuick
import QtQuick.Controls as QQC

// Một hàng track ở thanh bên: glyph + tên (elide khi dài) + số bài + nút
// phát/tạm dừng cả track + nút xoá track. File RIÊNG với NavItem.qml có chủ
// đích -- NavItem còn phục vụ "Thư viện" và "Tạo track", nhét thêm hai nút
// chỉ track mới cần vào đó sẽ làm hai chỗ dùng kia rối theo.
//
// IconButton và TrashGlyph dùng thẳng không cần import gì thêm -- cùng thư
// mục ui/components/ nên Qt tự nạp (import trần theo tên miền chỉ là bẫy với
// KIỂU MODULE như QtQuick.Controls, không phải với component cùng thư mục).
Item {
    id: root

    height: Theme.navItemHeight

    property string label: ""
    // Tối đa bốn đường dẫn ảnh bìa, cho ô bìa ghép (R-1).
    property var covers: []
    readonly property int coverSize: 28
    property int count: -1
    // Track này đang mở trên màn hình (không nhất thiết đang phát).
    property bool active: false
    // Track này đang thật sự phát (scope của Player trỏ vào nó VÀ đang chạy).
    property bool playing: false

    // Có bài đang tải vào track này -> viền chạy hai vạch.
    property bool downloading: false
    // Dải icon: giấu tên, số bài và hai nút; tên hiện khi rê chuột.
    property bool compact: false

    signal clicked()
    signal playToggled()
    signal deleteRequested()
    signal menuRequested(real sceneX, real sceneY)

    // Nền "đang chọn" do ô sáng TRƯỢT của thanh bên vẽ (Sidebar.qml), không vẽ ở đây.
    readonly property color _activeBg: "transparent"
    readonly property color _hoverBg: Theme.alpha(Theme.onSurface, 0.06)
    // Đang phát cũng tô sáng chữ như đang mở -- người dùng cần biết track nào
    // đang kêu nhạc dù đang đứng ở một track khác hoặc ở Thư viện.
    readonly property color _textColor: (root.active || root.playing) ? Theme.primary : Theme.onSurfaceVariant

    // Chỉ có ý nghĩa nội bộ: kích thước/khoảng cách hai nút tròn bên phải.
    readonly property int buttonSize: 26
    readonly property int buttonGap: Theme.spacingXs
    readonly property int trashGlyphWidth: 11
    readonly property int trashGlyphHeight: 14

    Rectangle {
        id: background

        anchors.fill: parent
        radius: Theme.radiusMd
        color: root.active
            ? root._activeBg
            : (rowHover.hovered ? root._hoverBg : "transparent")

        Behavior on color {
            ColorAnimation { duration: 140; easing.type: Easing.OutCubic }
        }
    }

    // HoverHandler thay vì MouseArea.containsMouse: nó vẫn báo hovered=true
    // cho cả hàng dù chuột đang nằm đúng trên hai nút con phía dưới (chúng có
    // MouseArea riêng, z cao hơn, "nuốt" sự kiện chuột nhưng KHÔNG chặn
    // HoverHandler của cha thấy con trỏ) -- nếu dùng containsMouse của một
    // MouseArea phủ cả hàng thì nền sẽ tắt sáng đúng lúc rê vào nút, giật mắt.
    // Cùng kỹ thuật TrackSongRow.qml đang dùng cho hàng có ô tick con.
    HoverHandler {
        id: rowHover
        cursorShape: Qt.PointingHandCursor
    }

    MouseArea {
        // Chỉ bắt cú bấm lên cả hàng, không tự theo dõi hover (đã có
        // rowHover ở trên lo phần đó). Khai báo TRƯỚC hai nút bên dưới và
        // hai nút đó tự đặt z cao hơn -- bấm đúng lên nút không lọt xuống
        // đây thành root.clicked().
        anchors.fill: parent
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        onClicked: (mouse) => {
            if (mouse.button === Qt.RightButton) {
                const at = root.mapToItem(null, mouse.x, mouse.y)
                root.menuRequested(at.x, at.y)
            } else {
                root.clicked()
            }
        }
    }

    // Ảnh bìa ghép nhỏ của track (design R-1) thay cho nốt nhạc.
    Mosaic {
        id: glyphText

        anchors.left: root.compact ? undefined : parent.left
        anchors.leftMargin: Theme.spacingSm
        anchors.horizontalCenter: root.compact ? parent.horizontalCenter : undefined
        anchors.verticalCenter: parent.verticalCenter
        width: root.coverSize
        height: root.coverSize
        radius: Theme.radiusSm
        covers: root.covers
    }

    Text {
        id: labelText

        visible: !root.compact
        anchors.left: glyphText.right
        anchors.leftMargin: Theme.spacingSm
        anchors.right: countText.left
        anchors.rightMargin: Theme.spacingSm
        anchors.verticalCenter: parent.verticalCenter
        text: root.label
        color: root._textColor
        font.pixelSize: Theme.fontSizeMd
        font.family: Theme.fontFamily
        elide: Text.ElideRight

        Behavior on color {
            ColorAnimation { duration: 140; easing.type: Easing.OutCubic }
        }
    }

    Text {
        id: countText

        // Design R-1: lúc yên chỉ có số bài (hoặc sóng nhạc nhỏ khi đang phát);
        // hai nút phát/xoá chỉ hiện khi rê chuột vào.
        visible: root.count >= 0 && !root.compact && !(root.playing && !rowHover.hovered)
        anchors.right: rowHover.hovered ? playButton.left : parent.right
        anchors.rightMargin: Theme.spacingMd
        anchors.verticalCenter: parent.verticalCenter
        text: root.count
        color: Theme.onSurfaceVariant
        font.pixelSize: Theme.fontSizeSm
        font.family: Theme.fontFamily
    }

    IconButton {
        id: playButton

        // Dải icon rộng 56px không đủ chỗ cho tên + hai nút. Ẩn nút đi; muốn
        // phát hay xoá thì mở track ra, hoặc nới cửa sổ rộng lại.
        visible: !root.compact && rowHover.hovered
        // z cao hơn MouseArea toàn hàng phía trên -- xem chú thích ở đó.
        z: 1
        anchors.right: deleteButton.left
        anchors.rightMargin: root.buttonGap
        anchors.verticalCenter: parent.verticalCenter
        width: root.buttonSize
        height: root.buttonSize
        glyph: root.playing ? "pause" : "play_arrow"
        hoverColor: Theme.primary

        onClicked: root.playToggled()
    }

    EqualizerBars {
        visible: root.playing && !rowHover.hovered && !root.compact
        anchors.right: parent.right
        anchors.rightMargin: Theme.spacingMd
        anchors.verticalCenter: parent.verticalCenter
        playing: root.playing
        barCount: 3
        barWidth: 3
        gap: 2
        height: 14
    }

    Rectangle {
        id: deleteButton

        visible: !root.compact && rowHover.hovered
        // z cao hơn MouseArea toàn hàng phía trên -- xem chú thích ở đó.
        z: 1
        anchors.right: parent.right
        anchors.rightMargin: Theme.spacingSm
        anchors.verticalCenter: parent.verticalCenter
        width: root.buttonSize
        height: root.buttonSize
        radius: Theme.radiusSm
        color: deleteArea.containsMouse ? Theme.alpha(Theme.error, 0.14) : "transparent"

        Behavior on color {
            ColorAnimation { duration: 120; easing.type: Easing.OutCubic }
        }

        TrashGlyph {
            anchors.centerIn: parent
            width: root.trashGlyphWidth
            height: root.trashGlyphHeight
            color: deleteArea.containsMouse ? Theme.error : Theme.onSurfaceVariant

            Behavior on color {
                ColorAnimation { duration: 120; easing.type: Easing.OutCubic }
            }
        }

        MouseArea {
            id: deleteArea

            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: root.deleteRequested()
        }
    }

    RunningBorder {
        anchors.fill: parent
        running: root.downloading
        radius: Theme.radiusMd
        color: Theme.primary
    }

    QQC.ToolTip {
        visible: root.compact && rowHover.hovered
        text: root.label + (root.count >= 0 ? "  ·  " + root.count + " bài" : "")
        delay: 300
    }
}
