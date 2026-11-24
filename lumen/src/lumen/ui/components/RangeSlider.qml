import QtQuick

// Thanh kéo giá trị thật trong [minValue, maxValue] — tổng quát hoá từ
// VolumeControl.qml cũ (âm lượng chỉ là trường hợp minValue=0, maxValue=1).
// Giờ dùng chung cho âm lượng (VolumeButton) và tốc độ phát (PlaybackSpeedButton).
//
// Cùng cấu trúc với SeekBar.qml — dùng lại nguyên hai điểm thiết kế quan trọng
// ở đó, đừng "dọn dẹp" mất:
//  1. Vùng bắt chuột (hitHeight) CAO HƠN HẲN thanh nhìn thấy. Thanh chỉ dày 4px;
//     nếu vùng nhận chuột cũng 4px thì người dùng gần như không bấm trúng.
//  2. Khi đang kéo, thanh bám theo con trỏ NGAY (displayRatio), không đợi tầng
//     phát xác nhận giá trị mới. Đợi round-trip thì cảm giác kéo bị trễ và giật.
// Đây từng là một bug thật khi PlayerBar tự chế lại logic này
// bằng một MouseArea đơn giản không có vùng bắt chuột mở rộng.
Item {
    id: root

    property real value: 0          // giá trị THẬT trong [minValue, maxValue], không phải tỉ lệ 0..1
    property real minValue: 0
    property real maxValue: 1
    property real stepSize: 0       // 0 = liên tục (không làm tròn); >0 = kéo xong làm tròn theo bước này
    // Tên `interactive`, KHÔNG phải `enabled`: `enabled` là thuộc tính sẵn có
    // của Item, khai trùng tên là đè lên nó — Qt cảnh báo, và ai đó đặt
    // `enabled: false` ở cha rồi tưởng con tắt theo sẽ im lặng không có tác dụng.
    property bool interactive: true

    signal valueRequested(real value)   // giá trị THẬT đã áp dụng minValue/maxValue/stepSize

    // Chiều cao vùng nhận chuột — lớn hơn thanh để bấm/kéo thoải mái.
    readonly property int hitHeight: 20
    readonly property int knobSize: 10

    readonly property bool active: root.interactive && (hoverHandler.hovered || root._dragging)

    readonly property real ratio: root.maxValue > root.minValue
        ? Math.min(1, Math.max(0, (root.value - root.minValue) / (root.maxValue - root.minValue)))
        : 0
    // Tỉ lệ đang vẽ: lúc kéo thì bám con trỏ, lúc thường thì bám dữ liệu thật.
    readonly property real displayRatio: root._dragging ? root._dragRatio : root.ratio

    property bool _dragging: false
    property real _dragRatio: 0

    implicitHeight: root.hitHeight

    function _ratioForX(x) {
        if (track.width <= 0) return 0
        return Math.min(1, Math.max(0, x / track.width))
    }

    function _valueForRatio(ratio) {
        let raw = root.minValue + ratio * (root.maxValue - root.minValue)
        if (root.stepSize > 0) {
            raw = Math.round(raw / root.stepSize) * root.stepSize
            raw = Math.round(raw * 100) / 100   // chống sai số dấu phẩy động, ví dụ 1.2000000000002
        }
        return Math.min(root.maxValue, Math.max(root.minValue, raw))
    }

    function _setFromX(x) {
        root._dragRatio = root._ratioForX(x - track.x)
        root.valueRequested(root._valueForRatio(root._dragRatio))
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
            color: Theme.onSurfaceVariant

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
        color: Theme.onSurfaceVariant
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
            root._setFromX(mouse.x)
        }
        onPositionChanged: (mouse) => {
            if (root._dragging) root._setFromX(mouse.x)
        }
        onReleased: (mouse) => {
            root._setFromX(mouse.x)
            root._dragging = false
        }
        onCanceled: root._dragging = false
    }
}
