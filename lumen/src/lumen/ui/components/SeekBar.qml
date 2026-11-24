import QtQuick

// Thanh tiến độ phát nhạc, kéo được để tua.
//
// Ba điểm thiết kế quan trọng, đừng "dọn dẹp" mất:
//  1. Vùng bắt chuột (hitHeight) CAO HƠN HẲN thanh nhìn thấy. Thanh chỉ dày 4px;
//     nếu vùng nhận chuột cũng 4px thì người dùng gần như không bấm trúng.
//  2. Khi đang kéo, thanh bám theo con trỏ NGAY (displayRatio), không đợi tầng phát
//     xác nhận vị trí mới. Đợi round-trip thì cảm giác kéo bị trễ và giật.
//  3. KHÔNG tua liên tục trong lúc kéo (đã từng làm vậy — nhạc cứ nhảy loạn suốt
//     lúc kéo, nghe rất khó chịu). Chỉ báo scrubStarted() một lần lúc bấm xuống và
//     scrubFinished(position) một lần lúc thả ra; ở giữa chỉ có displayRatio đổi
//     để mắt thấy đang kéo tới đâu, tai không nghe gì cho tới khi thả.
Item {
    id: root

    property real position: 0
    property real duration: 0
    property bool interactive: true

    // Bấm xuống -> âm thanh nên im lặng (nơi dùng tự lo việc tạm dừng).
    // Thả ra -> báo vị trí cuối cùng để nơi dùng tua thật rồi phát tiếp.
    signal scrubStarted()
    signal scrubFinished(real position)

    // Chiều cao vùng nhận chuột — lớn hơn thanh để bấm/kéo thoải mái.
    readonly property int hitHeight: 20
    readonly property int knobSize: 10

    readonly property bool active: root.interactive && (hoverHandler.hovered || root._dragging)

    // Tỉ lệ theo dữ liệu thật từ bên ngoài.
    readonly property real ratio: root.duration > 0
        ? Math.min(1, Math.max(0, root.position / root.duration))
        : 0
    // Tỉ lệ đang vẽ: lúc kéo thì bám con trỏ, lúc thường thì bám dữ liệu.
    readonly property real displayRatio: root._dragging ? root._dragRatio : root.ratio

    property bool _dragging: false
    property real _dragRatio: 0

    implicitHeight: root.hitHeight

    function _ratioForX(x) {
        if (track.width <= 0) return 0
        return Math.min(1, Math.max(0, x / track.width))
    }

    // Chỉ cập nhật hình vẽ tại chỗ — KHÔNG báo ra ngoài. Xem điểm 3 ở trên.
    function _updateDragRatio(x) {
        root._dragRatio = root._ratioForX(x - track.x)
    }

    function _finishDrag() {
        root._dragging = false
        root.scrubFinished(root.duration > 0 ? root._dragRatio * root.duration : 0)
    }

    Rectangle {
        id: track

        anchors.left: parent.left
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        height: root.active ? Theme.seekBarHeight * 2 : Theme.seekBarHeight
        radius: height / 2
        color: Theme.alpha(Theme.onSurface, 0.15)

        Behavior on height {
            NumberAnimation { duration: 120; easing.type: Easing.OutCubic }
        }

        Rectangle {
            id: filled

            anchors.left: parent.left
            anchors.top: parent.top
            anchors.bottom: parent.bottom
            width: track.width * root.displayRatio
            radius: height / 2
            color: Theme.primary

            // Tắt hẳn khi đang kéo, nếu không thanh sẽ đuổi theo tay một cách trễ nhịp.
            Behavior on width {
                enabled: !root._dragging
                NumberAnimation { duration: 120; easing.type: Easing.OutCubic }
            }
        }
    }

    Rectangle {
        id: knob

        visible: root.active
        width: root.knobSize
        height: root.knobSize
        radius: root.knobSize / 2
        color: Theme.primary
        anchors.verticalCenter: track.verticalCenter
        x: track.x + track.width * root.displayRatio - width / 2

        Behavior on x {
            enabled: !root._dragging
            NumberAnimation { duration: 120; easing.type: Easing.OutCubic }
        }
    }

    HoverHandler {
        id: hoverHandler

        enabled: root.interactive
        cursorShape: Qt.PointingHandCursor
    }

    MouseArea {
        id: mouseArea

        anchors.fill: parent
        enabled: root.interactive
        preventStealing: true

        onPressed: (mouse) => {
            root._dragging = true
            root._updateDragRatio(mouse.x)
            root.scrubStarted()
        }
        onPositionChanged: (mouse) => {
            if (root._dragging) root._updateDragRatio(mouse.x)
        }
        onReleased: (mouse) => {
            root._updateDragRatio(mouse.x)
            root._finishDrag()
        }
        // Ví dụ chuột bị hệ thống cướp giữa chừng (alt-tab...) — vẫn phải báo
        // scrubFinished, nếu không nơi dùng bị kẹt ở trạng thái tạm dừng mãi.
        onCanceled: root._finishDrag()
    }
}
