import QtQuick
import QtQuick.Effects

// Vệt sáng quét chéo qua mặt thẻ huy chương khi rê chuột — cảm giác ánh sáng
// lướt trên kim loại. Chỉ chạy khi `running`, KHÔNG chạy liên tục: cả bục có
// ba thẻ, để chúng loé mãi thì trang nhấp nháy liên tục, rất khó chịu.
//
// Vệt phải bị cắt theo GÓC BO của thẻ, nếu không nó tràn ra bốn góc thành bốn
// mẩu sáng lởm chởm trên nền tối. Dùng đúng lối che của dự án: layer.effect
// MultiEffect + maskSource là anh em CÙNG CHA TRỰC TIẾP (xem chú thích trong
// RecommendCard.qml/TrackCard.qml: maskSource xuyên nhiều cấp cha không đáng
// tin cậy).
Item {
    id: root

    property bool running: false
    property real radius: 0

    // Bề rộng vệt theo bề ngang thẻ, để thẻ to thẻ nhỏ loé trông như nhau.
    readonly property real bandWidth: Math.max(40, root.width * 0.35)
    readonly property int sweepMs: 620
    readonly property real tilt: 18

    visible: root.running || sweep.running

    Item {
        id: frame

        anchors.fill: parent
        layer.enabled: true
        layer.effect: MultiEffect {
            maskEnabled: true
            maskSource: mask
            autoPaddingEnabled: false
        }

        Rectangle {
            id: band

            // Cao hơn thẻ và nghiêng đi, nên hai đầu vệt luôn nằm ngoài khung —
            // không bao giờ thấy điểm bắt đầu/kết thúc của dải gradient.
            y: -root.height * 0.5
            width: root.bandWidth
            height: root.height * 2
            rotation: root.tilt
            opacity: 0
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0.0; color: "transparent" }
                GradientStop { position: 0.5; color: Qt.rgba(1, 1, 1, 0.55) }
                GradientStop { position: 1.0; color: "transparent" }
            }
        }
    }

    Rectangle {
        id: mask

        anchors.fill: parent
        radius: root.radius
        visible: false
        layer.enabled: true
    }

    SequentialAnimation {
        id: sweep

        running: root.running
        // Rê chuột và giữ nguyên thì loé lại sau một nhịp nghỉ, chứ không quét
        // liên tục thành hiệu ứng chớp.
        loops: Animation.Infinite

        ParallelAnimation {
            NumberAnimation {
                target: band; property: "x"
                from: -root.bandWidth * 1.5; to: root.width + root.bandWidth * 0.5
                duration: root.sweepMs; easing.type: Easing.OutSine
            }
            SequentialAnimation {
                NumberAnimation { target: band; property: "opacity"; to: 1; duration: root.sweepMs * 0.25 }
                PauseAnimation { duration: root.sweepMs * 0.35 }
                NumberAnimation { target: band; property: "opacity"; to: 0; duration: root.sweepMs * 0.4 }
            }
        }
        PauseAnimation { duration: 900 }

        onRunningChanged: if (!sweep.running) band.opacity = 0
    }
}
