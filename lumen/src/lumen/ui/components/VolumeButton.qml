import QtQuick
import QtQuick.Controls as QQC

// Pill âm lượng thu gọn — thay cho thanh kéo 56px luôn luôn hiện trước đây.
// Bấm vào mở bảng chứa RangeSlider thật. Component không tự gọi Player, chỉ
// bắn valueRequested ra ngoài (PlayerBar nối vào Player.setVolume).
//
// Chữ "Vol" thay vì glyph loa 🔊: đã tự kiểm chứng trên desktop thật — glyph đó
// nằm ngoài Basic Multilingual Plane (cần surrogate pair) và cần font màu emoji
// riêng để vẽ đúng, ra tofu trên máy này dù font đã cài. Mọi glyph khác đang
// dùng trong app (♪ ⏮⏭▶⏸⋯) đều nằm trong BMP nên luôn có phông dự phòng vẽ được
// — chữ thường thì chắc chắn vẽ được, giống cách PlaybackSpeedButton đã làm.
//
// Bảng kéo dùng QtQuick.Controls.Popup: đã kiểm chứng bằng probe PySide6 thật
// (không phải đoán) rằng Popup chạy tốt dưới Window trần (Main.qml không dùng
// ApplicationWindow) — Qt tự tạo Overlay ẩn cho QQuickWindow khi cần. Popup
// cho cả đóng bằng Esc lẫn đóng khi bấm ra ngoài miễn phí qua closePolicy.
// QtQuick.Controls PHẢI import có tên miền (as QQC). Qt 6.11 có sẵn một kiểu
// tên SearchField, và import module THẮNG component cùng thư mục — nên
// "import QtQuick.Controls" trần sẽ âm thầm thay SearchField của dự án bằng
// của Qt, làm mọi signal handler của ta biến mất. qmllint KHÔNG bắt được lỗi
// này; chỉ nạp QML thật mới lộ ra.
Item {
    id: root

    property real value: 0
    // Tên `interactive`, KHÔNG phải `enabled`: `enabled` là thuộc tính sẵn có
    // của Item, khai trùng tên là đè lên nó — Qt cảnh báo, và ai đó đặt
    // `enabled: false` ở cha rồi tưởng con tắt theo sẽ im lặng không có tác dụng.
    property bool interactive: true
    // Giao diện ra ngoài, đồng bộ HAI CHIỀU với Popup bằng gán tay trong
    // onOpenedChanged bên dưới — KHÔNG bind "open: pop.opened". Gán mệnh lệnh
    // vào một property đang có binding sẽ phá binding đó vĩnh viễn (bug thật
    // đã xảy ra trong dự án này, xem PlayerBar.qml). "open" ở đây luôn là
    // property thường, không ai bind vào nó.
    property bool open: false

    readonly property int fadeInMs: 160
    readonly property int fadeOutMs: 120

    signal valueRequested(real value)

    // Chỉ có ý nghĩa nội bộ: kích thước pill/bảng kéo hiện ra khi bấm.
    readonly property int verticalPadding: Theme.spacingXs
    readonly property int panelWidth: 172
    readonly property int panelPadding: Theme.spacingMd

    implicitWidth: pillText.implicitWidth + Theme.spacingMd * 2
    implicitHeight: pillText.implicitHeight + root.verticalPadding * 2

    Rectangle {
        id: iconButton

        anchors.fill: parent
        radius: Theme.radiusSm
        color: root.open
            ? Theme.alpha(Theme.primary, 0.16)
            : (mouseArea.containsMouse ? Theme.alpha(Theme.onSurface, 0.10) : "transparent")

        Behavior on color {
            ColorAnimation { duration: 120; easing.type: Easing.OutCubic }
        }

        Text {
            id: pillText

            anchors.centerIn: parent
            text: "volume_up"
            color: root.open
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

        MouseArea {
            id: mouseArea

            anchors.fill: parent
            enabled: root.interactive
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: panel.opened ? panel.close() : panel.open()
        }
    }

    // Bảng kéo âm lượng — nổi phía trên icon, canh theo mép phải để không tràn
    // ra ngoài cửa sổ (icon này nằm gần rìa phải PlayerBar).
    QQC.Popup {
        id: panel

        parent: root
        x: root.width - width
        y: -height - Theme.spacingSm
        width: root.panelWidth
        height: slider.implicitHeight + root.panelPadding * 2
        // OutsideParent chứ không phải OutsidePress — đã ĐO cả hai bằng probe thật:
        // với CloseOnPressOutside thì bấm lại chính nút này không đóng được bảng
        // (overlay đóng trước, rồi MouseArea thấy nó đã đóng nên mở lại ngay).
        // OutsideParent coi cú bấm lên nút là "trong phạm vi cha" nên bảng không
        // tự đóng, để MouseArea toggle đúng. Bấm sang nút khác vẫn đóng bảng này
        // VÀ mở bảng kia trong cùng một cú bấm.
        closePolicy: QQC.Popup.CloseOnPressOutsideParent | QQC.Popup.CloseOnEscape
        padding: 0
        background: Rectangle {
            color: Theme.alpha(Theme.surfaceVariant, 0.96)
            border.width: 1
            border.color: Theme.alpha(Theme.outline, 0.5)
            radius: Theme.radiusMd
        }

        // Chiều ngược lại: Popup tự đóng (Esc, bấm ra ngoài) -> root.open theo
        // dõi bằng gán tay, không phải binding. Xem chú thích tại "property
        // bool open" phía trên vì sao.

        // Popup style Basic KHÔNG có transition mặc định (đã kiểm chứng trong
        // /usr/lib/qt6/qml/QtQuick/Controls/Basic/Popup.qml) — thiếu hai khối
        // này thì bảng bật/tắt cụp một cái.
        enter: Transition {
            ParallelAnimation {
                NumberAnimation { property: "opacity"; from: 0; to: 1
                                  duration: root.fadeInMs; easing.type: Easing.OutCubic }
                NumberAnimation { property: "scale"; from: 0.92; to: 1
                                  duration: root.fadeInMs; easing.type: Easing.OutCubic }
            }
        }
        exit: Transition {
            NumberAnimation { property: "opacity"; from: 1; to: 0
                              duration: root.fadeOutMs; easing.type: Easing.InCubic }
        }

        onOpenedChanged: root.open = panel.opened

        RangeSlider {
            id: slider

            anchors.left: parent.left
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            anchors.leftMargin: root.panelPadding
            anchors.rightMargin: root.panelPadding
            minValue: 0
            maxValue: 1
            value: root.value
            interactive: root.interactive
            onValueRequested: (v) => root.valueRequested(v)
        }
    }
}
