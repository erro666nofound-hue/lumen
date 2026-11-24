import QtQuick
import QtQuick.Controls as QQC

// Bảng tự chọn màu: ba thanh — sắc, độ đậm, độ sáng — và một ô xem trước.
//
// Ba thanh thay vì một bánh xe màu: kéo từng thanh thì biết mình đang đổi cái
// gì, còn bánh xe thì đổi hai thứ cùng lúc và rất khó chỉnh lại cho đúng.
//
// QtQuick.Controls PHẢI import có tên miền (as QQC) — xem CLAUDE.md mục 5.
QQC.Popup {
    id: root

    property real hue: 0.72
    property real saturation: 0.62
    property real lightness: 0.68

    signal accepted(string color)

    readonly property int panelWidth: 300
    readonly property int stripHeight: 22
    readonly property int previewSize: 40
    readonly property int openMs: 160

    readonly property color current: Qt.hsla(root.hue, root.saturation, root.lightness, 1)

    width: root.panelWidth
    height: column.implicitHeight + padding * 2
    padding: Theme.spacingLg
    modal: true
    dim: false
    closePolicy: QQC.Popup.CloseOnPressOutside | QQC.Popup.CloseOnEscape

    background: Rectangle {
        radius: Theme.radiusLg
        // ĐÚNG công thức kính của cửa sổ (QĐ-037), không phải một tấm riêng.
        // 0.97 là con số của luật CŨ: kính cửa sổ 0.45 rồi hộp này 0.97 nữa chỉ
        // còn ~1.6% ảnh nền, trong khi cả app để lọt 55% — một mảng đen giữa
        // một app trong suốt, đúng bệnh của bảng đồng bộ cũ.
        color: Theme.alpha(Theme.surface,
                           Theme.wallpaper !== "" ? Theme.wallpaperSurfaceAlpha
                                                  : Theme.surfaceAlpha)
        border.width: 1
        // Kính mỏng đi thì cái viền là thứ DUY NHẤT còn nói "hộp hết ở đây".
        border.color: Theme.alpha(Theme.outline, 0.60)
    }

    enter: Transition {
        NumberAnimation { property: "opacity"; from: 0; to: 1
                          duration: root.openMs; easing.type: Easing.OutCubic }
    }
    exit: Transition {
        NumberAnimation { property: "opacity"; from: 1; to: 0
                          duration: root.openMs; easing.type: Easing.InCubic }
    }

    // Lớp kính THỨ HAI, đúng chỗ đọc chữ — QĐ-037. Khung hộp để sáng cho hợp
    // với cả app; khối chữ thì cần một lớp nữa, không thì trang phía sau (đã
    // mờ nhưng vẫn còn lốm đốm màu) hiện lên ngay dưới hàng chữ.
    Rectangle {
        anchors.fill: column
        anchors.margins: -Theme.spacingSm
        radius: Theme.radiusMd
        color: Theme.alpha(Theme.surface, 0.45)
    }

    Column {
        id: column

        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        spacing: Theme.spacingMd

        Row {
            spacing: Theme.spacingMd

            Rectangle {
                width: root.previewSize
                height: root.previewSize
                radius: Theme.radiusMd
                color: root.current
                border.width: 1
                border.color: Theme.alpha(Theme.onSurface, 0.25)
            }

            Column {
                anchors.verticalCenter: parent.verticalCenter
                spacing: 2

                Text {
                    text: "Màu của bạn"
                    color: Theme.onSurface
                    font.pixelSize: Theme.fontSizeMd
                    font.family: Theme.fontFamily
                }

                Text {
                    text: root.current.toString()
                    color: Theme.onSurfaceVariant
                    font.pixelSize: Theme.fontSizeSm
                    font.family: Theme.fontFamily
                }
            }
        }

        // Mỗi thanh vẽ sẵn dải màu MÀ NÓ điều khiển, nên nhìn là biết kéo sang
        // trái/phải thì màu đi về đâu.
        ColorStrip {
            width: parent.width
            height: root.stripHeight
            label: "Sắc"
            ratio: root.hue
            gradientStops: [
                Qt.hsla(0, root.saturation, root.lightness, 1),
                Qt.hsla(0.17, root.saturation, root.lightness, 1),
                Qt.hsla(0.33, root.saturation, root.lightness, 1),
                Qt.hsla(0.5, root.saturation, root.lightness, 1),
                Qt.hsla(0.67, root.saturation, root.lightness, 1),
                Qt.hsla(0.83, root.saturation, root.lightness, 1),
                Qt.hsla(1, root.saturation, root.lightness, 1)
            ]
            onPicked: (value) => root.hue = value
        }

        ColorStrip {
            width: parent.width
            height: root.stripHeight
            label: "Độ đậm"
            ratio: root.saturation
            gradientStops: [
                Qt.hsla(root.hue, 0, root.lightness, 1),
                Qt.hsla(root.hue, 1, root.lightness, 1)
            ]
            onPicked: (value) => root.saturation = value
        }

        ColorStrip {
            width: parent.width
            height: root.stripHeight
            label: "Độ sáng"
            ratio: root.lightness
            gradientStops: [
                Qt.hsla(root.hue, root.saturation, 0.15, 1),
                Qt.hsla(root.hue, root.saturation, 0.5, 1),
                Qt.hsla(root.hue, root.saturation, 0.9, 1)
            ]
            onPicked: (value) => root.lightness = value
        }

        Row {
            anchors.right: parent.right
            spacing: Theme.spacingSm

            TextButton {
                label: "Huỷ"
                onClicked: root.close()
            }

            TextButton {
                label: "Dùng màu này"
                onClicked: {
                    root.accepted(root.current.toString())
                    root.close()
                }
            }
        }
    }
}
