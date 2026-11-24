import QtQuick

// Nhãn nhóm nhỏ trong thanh bên (vd. "PLAYLIST", "THƯ VIỆN").
Item {
    id: root

    property string text: ""

    implicitWidth: label.implicitWidth
    implicitHeight: label.implicitHeight
    anchors.topMargin: Theme.spacingLg

    Text {
        id: label

        text: root.text.toUpperCase()
        color: Theme.onSurfaceVariant
        font.pixelSize: Theme.fontSizeSm
        font.family: Theme.fontFamily
        font.letterSpacing: 0.6
    }
}
