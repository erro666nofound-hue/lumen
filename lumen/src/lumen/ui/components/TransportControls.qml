import QtQuick

// Cụm điều khiển phát ở giữa PlayerBar: lùi / play-play / tới.
Row {
    id: root

    property bool playing: false
    // Tên `interactive`, KHÔNG phải `enabled`: `enabled` là thuộc tính sẵn có
    // của Item, khai trùng tên là đè lên nó — Qt cảnh báo, và ai đó đặt
    // `enabled: false` ở cha rồi tưởng con tắt theo sẽ im lặng không có tác dụng.
    property bool interactive: true

    signal playPauseRequested()
    signal nextRequested()
    signal previousRequested()

    // Chỉ có ý nghĩa nội bộ: kích thước riêng của cụm điều khiển này.
    readonly property int transportButtonSize: 28
    readonly property int mainButtonSize: 40

    spacing: Theme.spacingMd

    IconButton {
        width: root.transportButtonSize
        height: root.transportButtonSize
        anchors.verticalCenter: parent.verticalCenter
        glyph: "skip_previous"
        onClicked: {
            if (!root.interactive) return
            root.previousRequested()
        }
    }

    Rectangle {
        id: mainButton

        width: root.mainButtonSize
        height: root.mainButtonSize
        radius: width / 2
        anchors.verticalCenter: parent.verticalCenter
        color: mainButtonArea.containsMouse
            ? Theme.alpha(Theme.primary, 0.85)
            : Theme.primary

        Behavior on color {
            ColorAnimation { duration: 120; easing.type: Easing.OutCubic }
        }

        Text {
            anchors.centerIn: parent
            // Trạng thái quan trọng nhất của cả PlayerBar: người dùng phải
            // thấy ngay app đang phát hay đang tạm dừng.
            text: root.playing ? "pause" : "play_arrow"
            color: Theme.onPrimary
            font.pixelSize: Math.max(Theme.iconSize - 2, Math.round((Theme.fontSizeLg) * 1.4))
            font.family: Theme.iconFont
            font.variableAxes: ({ "FILL": 1 })
            // Font biến thiên + distance field vẽ vỡ nét icon trên cửa sổ thật (CB-058).
            renderType: Text.NativeRendering
        }

        MouseArea {
            id: mainButtonArea

            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: {
                if (!root.interactive) return
                root.playPauseRequested()
            }
        }
    }

    IconButton {
        width: root.transportButtonSize
        height: root.transportButtonSize
        anchors.verticalCenter: parent.verticalCenter
        glyph: "skip_next"
        onClicked: {
            if (!root.interactive) return
            root.nextRequested()
        }
    }
}
