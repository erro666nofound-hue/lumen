import QtQuick

Rectangle {
    id: root

    color: Theme.alpha(Theme.onSurface, Theme.panelAlpha)
    radius: Theme.radiusLg
    border.width: 1
    border.color: Theme.alpha(Theme.outline, 0.35)

    property real padding: Theme.spacingLg

    default property alias content: inner.data

    Item {
        id: inner

        anchors.fill: parent
        anchors.margins: root.padding
    }
}
