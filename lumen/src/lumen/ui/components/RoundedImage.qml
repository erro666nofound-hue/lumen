import QtQuick
import QtQuick.Effects

// Ảnh bo góc thật sự.
//
// `clip: true` trên một Rectangle bo góc KHÔNG cắt theo góc bo — nó cắt theo
// hình chữ nhật bao ngoài, nên ảnh vẫn vuông chằn chặn ở bốn góc. Muốn bo thì
// phải che bằng mask, y như CircleAvatar.
//
// frame và mask PHẢI cùng một cấp cha trực tiếp — xem TrackCard.qml.
Item {
    id: root

    property string source: ""
    property int radius: Theme.radiusSm

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
            color: Theme.alpha(Theme.onSurface, 0.08)
        }

        Image {
            anchors.fill: parent
            visible: root.source !== ""
            source: root.source
            fillMode: Image.PreserveAspectCrop
            asynchronous: true
        }
    }

    Rectangle {
        id: mask

        anchors.fill: parent
        radius: root.radius
        visible: false
        layer.enabled: true
    }
}
