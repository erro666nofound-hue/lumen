import QtQuick

import "RatingLevels.js" as Levels

// Một thẻ nhạc sĩ theo design R-1: thẻ NGANG — ảnh tròn bên trái, tên và
// "N bài · mức yêu thích" bên phải, nổi nhẹ lên khi rê chuột (nảy như dynsle).
//
// Mức mà Lumen tự đoán thì vẽ nhạt hơn mức người dùng tự đặt — nhìn là biết
// cái nào là ý mình, cái nào là app suy ra.
Rectangle {
    id: root

    property string name: ""
    property int songCount: 0
    property int rating: 0
    property bool rated: false
    property string avatar: ""
    property bool selected: false

    signal clicked()

    readonly property int avatarSize: 48
    readonly property int dotSize: 6
    readonly property real guessOpacity: 0.6
    readonly property int levelIndex: Levels.indexOf(root.rating)
    readonly property color tone: Theme[Levels.TONE_KEYS[root.levelIndex]]
    readonly property int liftPx: 2
    readonly property int liftMs: 380

    radius: Theme.radiusLg
    color: root.selected
        ? Theme.alpha(Theme.primary, 0.16)
        : Theme.alpha(Theme.onSurface, hover.hovered ? 0.07 : 0.045)
    border.width: 1
    border.color: root.selected ? Theme.alpha(Theme.primary, 0.5) : Theme.alpha(Theme.onSurface, 0.075)
    transform: Translate {
        y: hover.hovered ? -root.liftPx : 0
        Behavior on y { NumberAnimation { duration: Math.max(1, (root.liftMs) * Theme.motionScale); easing.type: Easing.OutBack; easing.overshoot: Theme.overshoot } }
    }

    Behavior on color {
        ColorAnimation { duration: Math.max(1, (120) * Theme.motionScale); easing.type: Easing.OutCubic }
    }

    HoverHandler { id: hover }

    CircleAvatar {
        id: avatarBox

        anchors.left: parent.left
        anchors.leftMargin: Theme.spacingMd
        anchors.verticalCenter: parent.verticalCenter
        width: root.avatarSize
        height: root.avatarSize
        avatar: root.avatar
        name: root.name
        letterSize: Theme.fontSizeLg
    }

    Column {
        anchors.left: avatarBox.right
        anchors.leftMargin: Theme.spacingMd
        anchors.right: parent.right
        anchors.rightMargin: Theme.spacingMd
        anchors.verticalCenter: parent.verticalCenter
        spacing: 2

        Text {
            width: parent.width
            text: root.name
            color: Theme.onSurface
            font.pixelSize: Theme.fontSizeMd + 0.5
            font.weight: Font.DemiBold
            font.family: Theme.fontFamily
            elide: Text.ElideRight
        }
        Row {
            spacing: Theme.spacingXs

            Text {
                anchors.verticalCenter: parent.verticalCenter
                text: (root.songCount > 0 ? root.songCount + " bài" : "—") + " ·"
                color: Theme.onSurfaceVariant
                font.pixelSize: Theme.fontSizeSm
                font.family: Theme.fontFamily
            }
            Rectangle {
                anchors.verticalCenter: parent.verticalCenter
                width: root.dotSize
                height: root.dotSize
                radius: width / 2
                color: root.tone
                opacity: root.rated ? 1 : root.guessOpacity
            }
            Text {
                anchors.verticalCenter: parent.verticalCenter
                text: Levels.LABELS[root.levelIndex]
                color: root.tone
                opacity: root.rated ? 1 : root.guessOpacity
                font.pixelSize: Theme.fontSizeSm
                font.family: Theme.fontFamily
            }
        }
    }

    MouseArea {
        anchors.fill: parent
        cursorShape: Qt.PointingHandCursor
        onClicked: root.clicked()
    }
}
