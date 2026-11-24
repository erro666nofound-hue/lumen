import QtQuick

// Một dòng Cài đặt theo design R-1: chữ (đậm) + lời giải thích (mờ) bên trái,
// nút điều khiển bên phải; cửa sổ hẹp hoặc nút quá to thì nút xuống dưới chữ.
// Các dòng trong một thẻ cách nhau bằng một vạch mảnh.
Item {
    id: root

    property string label: ""
    property string hint: ""
    // Dãy nhiều ô (màu, ảnh nền) luôn nằm DƯỚI chữ, không chen sang phải.
    property bool stacked: false
    default property alias control: holder.data

    readonly property int padV: 14
    readonly property int gap: Theme.spacingLg
    readonly property int sideFrom: 520
    readonly property real controlWidth: holder.children.length > 0 ? holder.children[0].implicitWidth : 0
    readonly property bool side: !root.stacked && root.width >= root.sideFrom && root.controlWidth > 0
        && root.controlWidth <= root.width * 0.55

    width: parent ? parent.width : 0
    height: root.side
        ? Math.max(textColumn.implicitHeight, holder.childrenRect.height) + root.padV * 2
        : textColumn.implicitHeight + (root.controlWidth > 0 || holder.childrenRect.height > 0
                                       ? Theme.spacingSm + holder.childrenRect.height : 0) + root.padV * 2

    Rectangle {
        // Dòng đầu trong thẻ (y = 0) không cần vạch ngăn phía trên.
        visible: root.y > 0
        width: parent.width
        height: 1
        color: Theme.alpha(Theme.onSurface, 0.075)
    }

    Column {
        id: textColumn

        width: root.side ? root.width - root.controlWidth - root.gap : root.width
        y: root.side ? (root.height - implicitHeight) / 2 : root.padV
        spacing: 2

        Text {
            width: parent.width
            text: root.label
            color: Theme.onSurface
            font.pixelSize: Theme.fontSizeMd + 1
            font.weight: Font.Medium
            font.family: Theme.fontFamily
            wrapMode: Text.WordWrap
        }
        Text {
            width: parent.width
            visible: root.hint !== ""
            text: root.hint
            color: Theme.onSurfaceVariant
            font.pixelSize: Theme.fontSizeSm + 1
            font.family: Theme.fontFamily
            wrapMode: Text.WordWrap
        }
    }

    Item {
        id: holder

        x: root.side ? root.width - root.controlWidth : 0
        y: root.side ? (root.height - height) / 2 : textColumn.y + textColumn.implicitHeight + Theme.spacingSm
        width: root.side ? root.controlWidth : root.width
        height: childrenRect.height
    }
}
