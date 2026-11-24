import QtQuick

// Nút phát tròn cho một bài chưa tải về: mặc định / đang nghe thử / đang bóc
// luồng. Dùng ở thẻ đề xuất và ở bảng chi tiết "Nhạc của tôi".
//
// Nền ĐẶC màu chủ đạo chứ không phải bóng mờ + viền: nó nằm đè lên ảnh thu nhỏ
// mà ảnh thì sáng tối đủ kiểu, nút mờ chìm nghỉm trên ảnh sáng.
Rectangle {
    id: root

    property bool active: false
    property bool loading: false
    property bool large: false
    // Nơi dùng tự quyết khi nào nút hiện (thẻ chỉ hiện lúc rê chuột).
    property bool shown: true

    signal clicked()

    readonly property int hoverMs: 140

    width: root.large ? 44 : 34
    height: width
    radius: width / 2
    color: root.loading
        ? Theme.alpha(Theme.shadow, 0.66)
        : (hover.hovered ? Theme.primary : Theme.alpha(Theme.primary, 0.88))
    opacity: (root.shown || root.active || root.loading) ? 1 : 0
    // Phình nhẹ khi rê thẳng vào nút, để biết con trỏ đang ở đâu.
    scale: hover.hovered ? 1.1 : 1

    Behavior on opacity {
        NumberAnimation { duration: root.hoverMs; easing.type: Easing.OutCubic }
    }

    Behavior on color {
        ColorAnimation { duration: root.hoverMs; easing.type: Easing.OutCubic }
    }

    Behavior on scale {
        NumberAnimation { duration: root.hoverMs; easing.type: Easing.OutBack }
    }

    // Quầng tối mềm quanh nút, tách nó khỏi ảnh phía sau.
    Rectangle {
        anchors.centerIn: parent
        width: parent.width + 8
        height: width
        radius: width / 2
        z: -1
        color: Theme.alpha(Theme.shadow, 0.35)
        opacity: root.loading ? 0 : 1
    }

    HoverHandler { id: hover }

    Text {
        anchors.centerIn: parent
        // Lệch phải một chút: tam giác ▶ có trọng tâm hình học nằm lệch trái
        // so với ô chữ, canh giữa máy móc thì nhìn lệch.
        anchors.horizontalCenterOffset: root.active ? 0 : 1
        visible: !root.loading
        text: root.active ? "pause" : "play_arrow"
        color: Theme.onPrimary
        font.pixelSize: Math.max(Theme.iconSize - 2, Math.round((root.large ? Theme.fontSizeLg : Theme.fontSizeMd) * 1.4))
        font.family: Theme.iconFont
        font.variableAxes: ({ "FILL": 1 })
        // Font biến thiên + distance field vẽ vỡ nét icon trên cửa sổ thật (CB-058).
        renderType: Text.NativeRendering
    }

    Spinner {
        anchors.centerIn: parent
        width: parent.width * 0.62
        height: width
        thickness: root.large ? 3 : 2.5
        running: root.loading
        color: Theme.onSurface
    }

    MouseArea {
        anchors.fill: parent
        enabled: !root.loading
        cursorShape: Qt.PointingHandCursor
        onClicked: root.clicked()
    }
}
