import QtQuick

import "RatingLevels.js" as Levels

// Thanh kéo mức độ yêu thích: chặn → bình thường → yêu thích → rất yêu thích.
//
// Bốn nút rời chiếm cả một hàng ngang và không nói được rằng bốn mức này nằm
// trên MỘT thang. Thanh kéo nói ngay: kéo sang phải là thích hơn.
//
// Tên bốn nấc nằm NGAY DƯỚI vạch của nó, không dồn vào một chữ ở đầu thanh —
// nhìn là biết kéo tới đâu thì được gì, khỏi phải kéo thử.
//
// Khi đang kéo, núm bám sát con trỏ chứ không nhảy từng nấc; thả tay mới nam
// châm về nấc gần nhất.
Item {
    id: root

    // -1 chặn · 0 bình thường · 1 yêu thích · 2 rất yêu thích
    property int rating: 0
    property bool rated: false

    signal ratingPicked(int value)
    signal ratingCleared()

    readonly property int trackHeight: 4
    readonly property int knobSize: 16
    readonly property int tickHeight: 8
    readonly property int moveMs: 200
    readonly property real dimLabel: 0.55

    readonly property int lastIndex: Levels.STEPS.length - 1
    readonly property real span: Math.max(1, width - root.knobSize)

    // Đang kéo thì đi theo tay, buông ra thì đi theo điểm đã chọn.
    property bool dragging: false
    property real dragRatio: 0

    readonly property real ratio: root.dragging
        ? root.dragRatio
        : Levels.indexOf(root.rating) / root.lastIndex
    // Nấc mà cú kéo hiện tại sẽ rơi vào — dùng cho cả nhãn lẫn màu.
    readonly property int liveIndex: Math.round(root.ratio * root.lastIndex)
    readonly property color tone: Theme[Levels.TONE_KEYS[root.liveIndex]]

    implicitHeight: root.knobSize + Theme.spacingXs + labels.height
        + (guess.visible ? guess.implicitHeight + Theme.spacingXs : 0)

    function ratioAt(mouseX) {
        return Math.max(0, Math.min(1, (mouseX - root.knobSize / 2) / root.span))
    }

    function tickX(index) {
        return root.knobSize / 2 + index * root.span / root.lastIndex
    }

    // Bấm/thả ở nấc đang chọn = bỏ đánh giá, trả về cho Lumen tự đoán.
    function commit(index) {
        const picked = Levels.STEPS[index]
        if (root.rated && picked === root.rating)
            root.ratingCleared()
        else
            root.ratingPicked(picked)
    }

    Rectangle {
        id: track

        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.topMargin: root.knobSize / 2 - height / 2
        height: root.trackHeight
        radius: height / 2
        color: Theme.alpha(Theme.onSurface, 0.14)

        Rectangle {
            anchors.left: parent.left
            anchors.top: parent.top
            anchors.bottom: parent.bottom
            width: knob.x + knob.width / 2
            radius: height / 2
            color: Theme.alpha(root.tone, root.rated || root.dragging ? 0.85 : 0.4)

            Behavior on color {
                ColorAnimation { duration: root.moveMs; easing.type: Easing.OutCubic }
            }
        }

        Repeater {
            model: Levels.STEPS.length

            Rectangle {
                required property int index

                x: root.tickX(index) - width / 2
                anchors.verticalCenter: parent.verticalCenter
                width: 2
                height: root.tickHeight
                radius: 1
                color: index <= root.liveIndex
                    ? Theme.alpha(root.tone, 0.55)
                    : Theme.alpha(Theme.onSurface, 0.22)
            }
        }
    }

    Rectangle {
        id: knob

        x: root.ratio * root.span
        y: 0
        width: root.knobSize
        height: root.knobSize
        radius: width / 2
        color: root.rated || root.dragging ? root.tone : Theme.surfaceVariant
        border.width: 2
        border.color: root.tone
        scale: root.dragging ? 1.15 : 1

        // Trong lúc kéo thì KHÔNG nội suy: núm phải dính tay, thêm hoạt ảnh vào
        // là thành lệt bệt chạy sau con trỏ.
        //
        // OutCubic chứ KHÔNG OutBack: OutBack vọt quá đích rồi lùi lại, nên mỗi
        // lần nhả tay núm lại ngoáy một cái.
        Behavior on x {
            enabled: !root.dragging
            NumberAnimation { duration: root.moveMs; easing.type: Easing.OutCubic }
        }

        Behavior on color {
            ColorAnimation { duration: root.moveMs; easing.type: Easing.OutCubic }
        }

        Behavior on border.color {
            ColorAnimation { duration: root.moveMs; easing.type: Easing.OutCubic }
        }

        Behavior on scale {
            NumberAnimation { duration: 120; easing.type: Easing.OutCubic }
        }
    }

    // Tên từng nấc, canh vào vạch của nó rồi kẹp trong bề ngang — nhãn đầu và
    // nhãn cuối nếu canh giữa đúng vạch sẽ thò ra ngoài mép.
    Item {
        id: labels

        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.topMargin: root.knobSize + Theme.spacingXs
        height: Theme.fontSizeSm + Theme.spacingXs

        Repeater {
            model: Levels.STEPS.length

            Text {
                id: stepLabel

                required property int index

                x: Math.max(0, Math.min(root.width - width,
                                        root.tickX(index) - width / 2))
                text: Levels.LABELS[index]
                color: index === root.liveIndex ? root.tone : Theme.onSurfaceVariant
                opacity: index === root.liveIndex ? 1 : root.dimLabel
                font.pixelSize: Theme.fontSizeSm
                font.family: Theme.fontFamily

                Behavior on color {
                    ColorAnimation { duration: root.moveMs; easing.type: Easing.OutCubic }
                }

                MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.commit(stepLabel.index)
                }
            }
        }
    }

    Text {
        id: guess

        anchors.left: parent.left
        anchors.top: labels.bottom
        anchors.topMargin: Theme.spacingXs
        visible: !root.rated && !root.dragging
        text: "Lumen tự đoán — kéo thanh để tự đặt"
        color: Theme.onSurfaceVariant
        opacity: root.dimLabel
        font.pixelSize: Theme.fontSizeSm
        font.family: Theme.fontFamily
    }

    MouseArea {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        height: root.knobSize
        cursorShape: Qt.PointingHandCursor

        onPressed: (mouse) => {
            root.dragRatio = root.ratioAt(mouse.x)
            root.dragging = true
        }
        onPositionChanged: (mouse) => {
            if (pressed)
                root.dragRatio = root.ratioAt(mouse.x)
        }
        // Đặt mức TRƯỚC rồi mới hạ cờ kéo. Làm ngược lại thì trong khoảnh khắc
        // giữa hai lệnh, `ratio` rơi về mức CŨ — núm chạy ngược về chỗ cũ rồi
        // mới bắn sang chỗ mới.
        onReleased: (mouse) => {
            root.commit(Math.round(root.ratioAt(mouse.x) * root.lastIndex))
            root.dragging = false
        }
        onCanceled: root.dragging = false
    }
}
