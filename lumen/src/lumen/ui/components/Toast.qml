import QtQuick

// Một thông báo nổi. Tự trượt lên và mờ dần khi xuất hiện, mờ đi khi biến mất.
Rectangle {
    id: root

    property string message: ""
    property string kind: "info"   // "info" | "error"

    signal dismissed()

    readonly property int horizontalPadding: 18
    readonly property int toastHeight: 40
    readonly property int glyphSpacing: Theme.spacingSm
    // Design R-1: rơi từ trên xuống, giãn ngang từ 0.6 rồi nảy (OutBack như dynsle).
    readonly property int enterDuration: 560
    readonly property int enterOffset: -70
    readonly property real enterSquash: 0.6
    // Độ nảy theo Cài đặt › Độ nảy (design R-1).
    readonly property real overshoot: Theme.overshoot

    readonly property bool isError: root.kind === "error"
    readonly property color accent: root.isError ? Theme.error : Theme.primary

    implicitWidth: row.implicitWidth + root.horizontalPadding * 2
    implicitHeight: root.toastHeight
    radius: height / 2
    // Chrome thoáng qua ⇒ ĐỤC (QĐ-040).
    color: Theme.surfaceVariant
    border.width: 1
    border.color: Theme.alpha(Theme.onSurface, 0.075)
    opacity: 0
    y: root.enterOffset
    transform: Scale {
        id: squash
        origin.x: root.width / 2
        xScale: root.enterSquash
        Behavior on xScale {
            NumberAnimation { duration: Math.max(1, (root.enterDuration) * Theme.motionScale); easing.type: Easing.OutBack; easing.overshoot: root.overshoot }
        }
    }

    Row {
        id: row

        anchors.centerIn: parent
        spacing: root.glyphSpacing

        Text {
            anchors.verticalCenter: parent.verticalCenter
            text: root.isError ? "error" : "check_circle"
            color: root.accent
            font.pixelSize: Math.max(Theme.iconSize - 2, Math.round((Theme.fontSizeMd) * 1.4))
            font.family: Theme.iconFont
            font.variableAxes: ({ "FILL": 1 })
            // Font biến thiên + distance field vẽ vỡ nét icon trên cửa sổ thật (CB-058).
            renderType: Text.NativeRendering
        }

        Text {
            anchors.verticalCenter: parent.verticalCenter
            text: root.message
            color: Theme.onSurface
            font.pixelSize: Theme.fontSizeMd
            font.family: Theme.fontFamily
        }
    }

    MouseArea {
        anchors.fill: parent
        cursorShape: Qt.PointingHandCursor
        onClicked: root.dismissed()
    }

    // Trượt lên + hiện dần ngay khi được tạo.
    Component.onCompleted: {
        root.opacity = 1
        root.y = 0
        squash.xScale = 1
    }

    Behavior on opacity {
        NumberAnimation { duration: Math.max(1, (root.enterDuration) * Theme.motionScale); easing.type: Easing.OutCubic }
    }

    Behavior on y {
        NumberAnimation { duration: Math.max(1, (root.enterDuration) * Theme.motionScale); easing.type: Easing.OutBack; easing.overshoot: root.overshoot }
    }
}
