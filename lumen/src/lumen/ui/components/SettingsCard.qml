import QtQuick

// Một nhóm Cài đặt theo design R-1: tên nhóm viết hoa nhỏ phía trên, rồi một
// thẻ kính thứ hai (chỗ đọc chữ, QĐ-037) chứa các SettingsRow liền nhau.
Column {
    id: root

    property string title: ""
    default property alias content: body.data

    spacing: Theme.spacingMd

    Text {
        text: root.title
        color: Theme.onSurfaceVariant
        font.pixelSize: Theme.fontSizeSm
        font.weight: Font.DemiBold
        font.family: Theme.fontFamily
        font.letterSpacing: 1.2
    }

    Rectangle {
        width: root.width
        height: body.implicitHeight + Theme.spacingXs * 2
        radius: Theme.radiusLg
        color: Theme.alpha(Theme.onSurface, 0.045)
        border.width: 1
        border.color: Theme.alpha(Theme.onSurface, 0.075)

        Column {
            id: body

            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.leftMargin: Theme.spacingLg
            anchors.rightMargin: Theme.spacingLg
            anchors.topMargin: Theme.spacingXs
            spacing: 0

        }
    }
}
