import QtQuick

// Nút glyph bật/tắt (lặp, trộn bài, ...). Trước đây shuffle/repeat chỉ đổi
// MÀU CHỮ khi bật — quá tinh tế, người dùng thật sự không nhận ra chúng là nút
// bấm. Giờ có thêm nền mờ (pill) khi bật/hover, giống affordance của IconButton
// nhưng còn giữ được trạng thái "đang bật" sau khi rời chuột ra.
//
// Mở rộng cho nút lặp (3 trạng thái off/all/one, không còn là bool đơn giản):
//  - activeBgAlpha cho phép nơi dùng tô đậm nền khác nhau giữa hai trạng thái
//    "bật" khác nhau (all vs one) mà không cần thêm khái niệm mới trong component.
//  - label khác rỗng thì mỗi lần bấm hiện một bong bóng chữ nổi lên trên nút rồi
//    tự mờ dần — xác nhận trực quan "bạn vừa đổi sang trạng thái nào", vì glyph
//    và badge nhỏ không đủ rõ để phân biệt all/one khi liếc nhanh.
Item {
    id: root

    property string glyph: ""
    property bool active: false
    // Chữ nhỏ ở góc, ví dụ "1" cho lặp-một-bài. Rỗng thì ẩn.
    property string badge: ""
    // Độ đậm nền pill khi active — nơi dùng tự chọn để phân biệt các trạng thái
    // "bật" khác nhau (ví dụ lặp danh sách vs lặp một bài).
    property real activeBgAlpha: 0.16
    // Chữ hiện trong bong bóng thoáng qua mỗi lần bấm. Rỗng thì không có bong bóng.
    property string label: ""

    signal clicked()

    readonly property int badgeFontSize: 8
    // Kích thước/thời lượng riêng của bong bóng nhãn — không dùng chung Theme vì
    // đây là hoạt ảnh xác nhận thoáng qua, không phải ngôn ngữ thiết kế chung.
    readonly property int labelBubbleMargin: Theme.spacingSm
    readonly property int labelFadeInMs: 120
    readonly property int labelHoldMs: 1000
    readonly property int labelFadeOutMs: 300

    Rectangle {
        anchors.fill: parent
        radius: Theme.radiusSm
        color: root.active
            ? Theme.alpha(Theme.primary, root.activeBgAlpha)
            : (mouseArea.containsMouse ? Theme.alpha(Theme.onSurface, 0.10) : "transparent")

        Behavior on color {
            ColorAnimation { duration: 120; easing.type: Easing.OutCubic }
        }
    }

    Text {
        anchors.centerIn: parent
        text: root.glyph
        color: root.active
            ? Theme.primary
            : (mouseArea.containsMouse ? Theme.onSurface : Theme.onSurfaceVariant)
        font.pixelSize: Math.max(Theme.iconSize - 2, Math.round((Theme.fontSizeMd) * 1.4))
        font.family: Theme.iconFont
        font.variableAxes: ({ "FILL": 1 })
        // Font biến thiên + distance field vẽ vỡ nét icon trên cửa sổ thật (CB-058).
        renderType: Text.NativeRendering

        Behavior on color {
            ColorAnimation { duration: 120; easing.type: Easing.OutCubic }
        }
    }

    Text {
        visible: root.badge !== ""
        anchors.top: parent.top
        anchors.right: parent.right
        text: root.badge
        color: Theme.primary
        font.pixelSize: root.badgeFontSize
        font.family: Theme.fontFamily
    }

    // Bong bóng xác nhận nổi lên trên nút mỗi lần bấm, tự mờ dần. z cao để
    // không bị các Item anh em khác trong hàng (rightCluster) che mất.
    Rectangle {
        id: labelBubble

        visible: root.label !== ""
        opacity: 0
        z: 10
        anchors.bottom: parent.top
        anchors.bottomMargin: root.labelBubbleMargin
        anchors.horizontalCenter: parent.horizontalCenter
        implicitWidth: labelText.implicitWidth + Theme.spacingSm * 2
        implicitHeight: labelText.implicitHeight + Theme.spacingXs * 2
        radius: Theme.radiusSm
        color: Theme.alpha(Theme.surfaceVariant, 0.95)

        Text {
            id: labelText

            anchors.centerIn: parent
            text: root.label
            color: Theme.onSurface
            font.pixelSize: Theme.fontSizeSm
            font.family: Theme.fontFamily
        }

        SequentialAnimation {
            id: labelAnimation

            NumberAnimation {
                target: labelBubble
                property: "opacity"
                to: 1
                duration: root.labelFadeInMs
                easing.type: Easing.OutCubic
            }
            PauseAnimation { duration: root.labelHoldMs }
            NumberAnimation {
                target: labelBubble
                property: "opacity"
                to: 0
                duration: root.labelFadeOutMs
                easing.type: Easing.InCubic
            }
        }
    }

    MouseArea {
        id: mouseArea

        anchors.fill: parent
        enabled: root.enabled
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: {
            if (root.label !== "") labelAnimation.restart()
            root.clicked()
        }
    }
}
