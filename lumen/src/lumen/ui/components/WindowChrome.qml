import QtQuick
import QtQuick.Window

// Thanh đầu cửa sổ: chỉ là nhãn hiệu + nút đóng.
// KHÔNG kéo được, KHÔNG double-click phóng to, KHÔNG nút thu nhỏ.
// Mọi thao tác cửa sổ thuộc về Hyprland (SUPER + kéo, phím tắt đóng...).
// Nút thu nhỏ bị bỏ có chủ đích: trên WM tiling không có taskbar để gọi cửa sổ trở lại.
Item {
    id: root

    signal closeClicked()

    readonly property int brandDotSize: 8

    // R-1: logo Lumen nay nằm ở đầu thanh bên, như design — ẩn bản ở đây cho khỏi lặp.
    Row {
        id: brand
        visible: false

        anchors.left: parent.left
        anchors.leftMargin: Theme.spacingLg
        anchors.verticalCenter: parent.verticalCenter
        spacing: Theme.spacingSm

        Rectangle {
            width: root.brandDotSize
            height: root.brandDotSize
            radius: root.brandDotSize / 2
            color: Theme.primary
            anchors.verticalCenter: parent.verticalCenter
        }

        Text {
            text: "Lumen"
            color: Theme.onSurface
            font.pixelSize: Theme.fontSizeMd
            font.family: Theme.fontFamily
            font.weight: Font.DemiBold
            anchors.verticalCenter: parent.verticalCenter
        }
    }

    IconButton {
        anchors.right: parent.right
        anchors.rightMargin: Theme.spacingSm
        anchors.verticalCenter: parent.verticalCenter

        glyph: "close"
        hoverColor: Theme.error
        onClicked: {
            root.closeClicked()
            Window.window.close()
        }
    }
}
