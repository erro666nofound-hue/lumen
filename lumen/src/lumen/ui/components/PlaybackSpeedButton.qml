import QtQuick
import QtQuick.Controls as QQC

// Pill hiện tốc độ phát hiện tại ("1x", "1.25x", ...) — bấm vào mở bảng có
// thanh kéo 0x-3x cộng 4 nút cài sẵn. Cùng phong cách pill tự co giãn theo chữ
// như SortChip.qml, nhưng không có mũi tên lên/xuống.
//
// Bảng dùng QtQuick.Controls.Popup — xem lý do đã kiểm chứng bằng probe
// PySide6 thật trong VolumeButton.qml (Main.qml dùng Window trần vẫn chạy
// Popup tốt, tự có Overlay ẩn). Component không tự gọi Player, chỉ bắn
// speedRequested ra ngoài.
// QtQuick.Controls PHẢI import có tên miền (as QQC). Qt 6.11 có sẵn một kiểu
// tên SearchField, và import module THẮNG component cùng thư mục — nên
// "import QtQuick.Controls" trần sẽ âm thầm thay SearchField của dự án bằng
// của Qt, làm mọi signal handler của ta biến mất. qmllint KHÔNG bắt được lỗi
// này; chỉ nạp QML thật mới lộ ra.
Item {
    id: root

    property real speed: 1.0
    // Tên `interactive`, KHÔNG phải `enabled`: `enabled` là thuộc tính sẵn có
    // của Item, khai trùng tên là đè lên nó — Qt cảnh báo, và ai đó đặt
    // `enabled: false` ở cha rồi tưởng con tắt theo sẽ im lặng không có tác dụng.
    property bool interactive: true
    // Giao diện ra ngoài, đồng bộ hai chiều với Popup qua gán tay trong
    // onOpenedChanged — KHÔNG bind "open: panel.opened" (xem VolumeButton.qml
    // để biết vì sao gán mệnh lệnh sẽ phá binding).
    property bool open: false

    readonly property int fadeInMs: 160
    readonly property int fadeOutMs: 120

    signal speedRequested(real rate)

    // Bốn tốc độ cài sẵn, đúng thứ tự hiển thị trong bảng.
    readonly property var presets: [0.75, 1.0, 1.25, 2.0]
    // Chỉ có ý nghĩa nội bộ: kích thước/đệm riêng của pill và bảng kéo.
    readonly property int verticalPadding: Theme.spacingXs
    readonly property int panelWidth: 208
    readonly property int panelPadding: Theme.spacingMd
    readonly property int presetSpacing: Theme.spacingXs
    // Sai số so sánh dấu phẩy động khi tìm nút cài sẵn khớp tốc độ hiện tại.
    readonly property real presetEpsilon: 0.001

    // "1.00x" -> "1x", "1.25x" giữ nguyên -- bỏ số 0 thừa nhưng không bỏ số có nghĩa.
    function formatSpeed(v) {
        let s = v.toFixed(2).replace(/0+$/, "").replace(/\.$/, "")
        return s + "x"
    }

    implicitWidth: pillText.implicitWidth + Theme.spacingMd * 2
    implicitHeight: pillText.implicitHeight + root.verticalPadding * 2

    Rectangle {
        id: pill

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
            text: root.formatSpeed(root.speed)
            color: root.open
                ? Theme.primary
                : (mouseArea.containsMouse ? Theme.onSurface : Theme.onSurfaceVariant)
            font.pixelSize: Theme.fontSizeMd
            font.family: Theme.fontFamily

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

    // Bảng chọn tốc độ — nổi phía trên pill, canh theo mép phải để không tràn
    // ra ngoài cửa sổ (nút này nằm gần rìa phải PlayerBar).
    QQC.Popup {
        id: panel

        parent: root
        x: root.width - width
        y: -height - Theme.spacingSm
        width: root.panelWidth
        height: panelColumn.implicitHeight + root.panelPadding * 2
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

        Column {
            id: panelColumn

            anchors.left: parent.left
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            anchors.leftMargin: root.panelPadding
            anchors.rightMargin: root.panelPadding
            spacing: Theme.spacingSm

            RangeSlider {
                width: panelColumn.width
                minValue: 0
                maxValue: 3
                stepSize: 0.05
                value: root.speed
                interactive: root.interactive
                onValueRequested: (v) => root.speedRequested(v)
            }

            Row {
                width: panelColumn.width
                spacing: root.presetSpacing

                Repeater {
                    model: root.presets

                    Rectangle {
                        id: presetPill

                        width: (panelColumn.width - root.presetSpacing * (root.presets.length - 1)) / root.presets.length
                        height: presetLabel.implicitHeight + Theme.spacingXs * 2
                        radius: Theme.radiusSm
                        color: Math.abs(root.speed - modelData) < root.presetEpsilon
                            ? Theme.alpha(Theme.primary, 0.18)
                            : Theme.alpha(Theme.onSurface, 0.06)

                        Behavior on color {
                            ColorAnimation { duration: 140; easing.type: Easing.OutCubic }
                        }

                        Text {
                            id: presetLabel

                            anchors.centerIn: parent
                            text: root.formatSpeed(modelData)
                            color: Math.abs(root.speed - modelData) < root.presetEpsilon
                                ? Theme.primary
                                : Theme.onSurfaceVariant
                            font.pixelSize: Theme.fontSizeSm
                            font.family: Theme.fontFamily
                        }

                        MouseArea {
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.speedRequested(modelData)
                        }
                    }
                }
            }
        }
    }
}
