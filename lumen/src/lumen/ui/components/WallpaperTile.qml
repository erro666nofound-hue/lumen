import QtQuick

// Một ô trong bảng chọn nền: ảnh thu nhỏ bo góc, tên nằm trong một hộp nhỏ.
//
// Bo góc bằng MẶT NẠ chứ không bằng `clip`: `clip: true` cắt theo hình chữ nhật
// bao ngoài, không theo góc bo — ảnh vẫn vuông chằn chặn ở bốn góc (bẫy đã ghi
// đã ghi lại, xem RoundedImage.qml).
Item {
    id: root

    property string label: ""
    property string source: ""
    property string glyph: ""
    property bool active: false
    property bool removable: false

    signal picked()
    signal removed()

    readonly property int removeSize: 20
    readonly property int cornerRadius: Theme.radiusMd

    RoundedImage {
        anchors.fill: parent
        radius: root.cornerRadius
        source: root.source
    }

    // Viền vẽ ĐÈ lên trên mặt nạ, cùng bán kính, nên không hở góc.
    Rectangle {
        anchors.fill: parent
        radius: root.cornerRadius
        color: "transparent"
        border.width: root.active ? 2 : 1
        border.color: root.active
            ? Theme.primary
            : Theme.alpha(Theme.onSurface, hover.hovered ? 0.35 : 0.15)

        Behavior on border.color {
            ColorAnimation { duration: 120; easing.type: Easing.OutCubic }
        }
    }

    Text {
        id: glyphText
        anchors.centerIn: parent
        anchors.verticalCenterOffset: root.label !== "" ? -Theme.spacingSm : 0
        visible: root.glyph !== ""
        text: root.glyph
        color: Theme.onSurfaceVariant
        font.pixelSize: Math.max(Theme.iconSize - 2, Math.round((Theme.fontSizeXl) * 1.4))
        font.family: Theme.iconFont
        font.variableAxes: ({ "FILL": 1 })
        // Font biến thiên + distance field vẽ vỡ nét icon trên cửa sổ thật (CB-058).
        renderType: Text.NativeRendering
    }

    // Ô không có ảnh (Từ máy…, Không nền): tên nằm ngay dưới icon.
    Text {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: glyphText.bottom
        visible: root.glyph !== "" && root.label !== ""
        text: root.label
        color: Theme.onSurfaceVariant
        font.pixelSize: Theme.fontSizeSm
        font.family: Theme.fontFamily
    }

    // Tên nằm trong hộp bo góc riêng, không phải một dải chữ trần trên ảnh.
    Rectangle {
        anchors.left: parent.left
        anchors.bottom: parent.bottom
        anchors.margins: Theme.spacingSm
        width: Math.min(nameLabel.implicitWidth + Theme.spacingMd, parent.width - Theme.spacingLg)
        height: nameLabel.implicitHeight + Theme.spacingXs * 2
        visible: root.glyph === "" && root.label !== ""
        radius: Theme.radiusSm
        color: Theme.alpha(Theme.shadow, 0.65)

        Text {
            id: nameLabel

            anchors.centerIn: parent
            width: parent.width - Theme.spacingSm
            text: root.label
            color: "#ffffff"
            font.pixelSize: Theme.fontSizeSm
            font.family: Theme.fontFamily
            elide: Text.ElideMiddle
        }
    }

    HoverHandler { id: hover }

    MouseArea {
        anchors.fill: parent
        cursorShape: Qt.PointingHandCursor
        onClicked: root.picked()
    }

    // Nút quên ảnh — chỉ bỏ khỏi danh sách nhớ, KHÔNG xoá file trên máy.
    Rectangle {
        anchors.top: parent.top
        anchors.right: parent.right
        anchors.margins: Theme.spacingXs
        width: root.removeSize
        height: root.removeSize
        radius: width / 2
        visible: root.removable && hover.hovered
        color: Theme.alpha(Theme.shadow, 0.75)

        Text {
            anchors.centerIn: parent
            text: "close"
            color: "#ffffff"
            font.pixelSize: Math.max(Theme.iconSize - 2, Math.round((Theme.fontSizeSm) * 1.4))
            font.family: Theme.iconFont
            font.variableAxes: ({ "FILL": 1 })
            // Font biến thiên + distance field vẽ vỡ nét icon trên cửa sổ thật (CB-058).
            renderType: Text.NativeRendering
        }

        MouseArea {
            anchors.fill: parent
            cursorShape: Qt.PointingHandCursor
            onClicked: root.removed()
        }
    }
}
