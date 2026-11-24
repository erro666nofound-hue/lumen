import QtQuick
import QtQuick.Effects

// Ảnh đại diện kênh, cắt tròn. Chưa tải được thì hiện chữ cái đầu của tên.
//
// frame và mask PHẢI cùng một cấp cha trực tiếp — xem TrackCard.qml.
Item {
    id: root

    property string avatar: ""
    property string name: ""
    property int letterSize: Theme.fontSizeMd

    Item {
        anchors.fill: parent
        layer.enabled: true
        layer.effect: MultiEffect {
            maskEnabled: true
            maskSource: mask
            autoPaddingEnabled: false
        }

        Rectangle {
            anchors.fill: parent
            color: Theme.alpha(Theme.primary, 0.16)

            Text {
                anchors.centerIn: parent
                text: root.name.length > 0 ? root.name.charAt(0).toUpperCase() : "♪"
                color: Theme.primary
                font.pixelSize: root.letterSize
                font.family: Theme.fontFamily
            }
        }

        Image {
            anchors.fill: parent
            visible: root.avatar !== ""
            source: root.avatar
            fillMode: Image.PreserveAspectCrop
            asynchronous: true
        }
    }

    Rectangle {
        id: mask

        anchors.fill: parent
        radius: width / 2
        visible: false
        layer.enabled: true
    }
}
