import QtQuick

// Màn hình trống: thư viện chưa có bài nào, tìm kiếm không ra kết quả, v.v.
Item {
    id: root

    property string glyph: ""
    property string title: ""
    property string subtitle: ""

    // Chỉ có ý nghĩa nội bộ: cỡ chữ glyph lớn và bề ngang tối đa của khối chữ.
    readonly property int glyphSize: 48
    readonly property int maxTextWidth: 320

    Column {
        anchors.centerIn: parent
        spacing: Theme.spacingMd
        width: root.maxTextWidth

        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: root.glyph
            color: Theme.alpha(Theme.onSurface, 0.25)
            font.pixelSize: Math.max(Theme.iconSize - 2, Math.round((root.glyphSize) * 1.4))
            font.family: Theme.iconFont
            font.variableAxes: ({ "FILL": 1 })
            // Font biến thiên + distance field vẽ vỡ nét icon trên cửa sổ thật (CB-058).
            renderType: Text.NativeRendering
        }

        Text {
            width: parent.width
            horizontalAlignment: Text.AlignHCenter
            text: root.title
            color: Theme.onSurface
            font.pixelSize: Theme.fontSizeLg
            font.family: Theme.fontFamily
            wrapMode: Text.WordWrap
        }

        Text {
            width: parent.width
            horizontalAlignment: Text.AlignHCenter
            text: root.subtitle
            color: Theme.onSurfaceVariant
            font.pixelSize: Theme.fontSizeMd
            font.family: Theme.fontFamily
            wrapMode: Text.WordWrap
        }
    }
}
