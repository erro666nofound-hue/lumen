import QtQuick

import "MedalColors.js" as MedalColors

// Bệ đứng dưới một thẻ bục: khối kim loại có số hạng khắc chìm.
//
// Đây là thứ lấp "lãnh địa" của mỗi hạng. Trước đó ba thẻ dính vào nhau ở giữa
// còn hai bên trống trơn; giờ mỗi hạng có một khoảng riêng, và trong khoảng đó
// có một vật thật chứ không phải chỗ trống.
//
// Chiều cao bệ theo thứ hạng — đó cũng là thứ nhấc thẻ lên những độ cao khác
// nhau, nên chân và đỉnh ba thẻ tự so le mà không cần con số bù riêng.
Item {
    id: root

    property string medal: ""
    property int rank: 0
    property real intensity: 1.0

    // Gán vào property KIỂU color để ép chuỗi "#rrggbb" thành màu thật —
    // MedalColors trả về chuỗi, mà `.r/.g/.b` trên chuỗi là undefined và
    // Qt.rgba(undefined,...) cho ra ĐEN. Bệ đầu tiên đen sì vì đúng lỗi này.
    readonly property color toneLight: MedalColors.stopsFor(root.medal)[0]
    readonly property color toneMid: MedalColors.stopsFor(root.medal)[1]
    readonly property color toneDark: MedalColors.stopsFor(root.medal)[2]
    readonly property int appearMs: 320
    // Mặt trên dày bấy nhiêu, và hai cạnh vát vào bấy nhiêu.
    readonly property int faceHeight: 7
    readonly property int bevel: 6

    opacity: 0
    Component.onCompleted: root.opacity = 1

    Behavior on opacity {
        NumberAnimation { duration: root.appearMs; easing.type: Easing.OutCubic }
    }

    // Quầng sáng mềm hắt lên từ mặt bệ — nối bệ với thẻ đứng trên nó, để hai
    // thứ trông như một khối chứ không phải hai vật rời rạc.
    Rectangle {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: topFace.top
        width: parent.width * 0.9
        height: 26
        gradient: Gradient {
            orientation: Gradient.Vertical
            GradientStop { position: 0.0; color: "transparent" }
            GradientStop {
                position: 1.0
                color: Qt.rgba(root.toneLight.r, root.toneLight.g, root.toneLight.b,
                               0.22 * root.intensity)
            }
        }
    }

    // MẶT TRÊN của bệ: một dải sáng hơn, thụt vào hai bên. Đây là thứ biến hai
    // hình chữ nhật thành một KHỐI có bề dày — thiếu nó thì bệ chỉ là miếng ván
    // mỏng dán dưới chân thẻ.
    Rectangle {
        id: topFace

        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: block.top
        width: parent.width - root.bevel * 2
        height: root.faceHeight
        topLeftRadius: Theme.radiusSm
        topRightRadius: Theme.radiusSm
        gradient: Gradient {
            orientation: Gradient.Vertical
            GradientStop { position: 0.0; color: Qt.lighter(root.toneLight, 1.06) }
            GradientStop { position: 1.0; color: root.toneMid }
        }
    }

    Rectangle {
        id: block

        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        height: parent.height - root.faceHeight
        // Chỉ bo hai góc trên: bệ mọc lên từ nền, đáy phải phẳng.
        topLeftRadius: Theme.radiusMd
        topRightRadius: Theme.radiusMd
        gradient: Gradient {
            orientation: Gradient.Vertical
            GradientStop { position: 0.0; color: root.toneMid }
            GradientStop { position: 0.55; color: Qt.darker(root.toneMid, 1.35) }
            GradientStop { position: 1.0; color: root.toneDark }
        }

        // Hai vệt tối dọc ở mép: cạnh khối bắt ít sáng hơn mặt chính diện.
        Rectangle {
            anchors.left: parent.left
            anchors.top: parent.top
            anchors.bottom: parent.bottom
            width: root.bevel
            color: Qt.rgba(0, 0, 0, 0.22)
        }

        Rectangle {
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.bottom: parent.bottom
            width: root.bevel
            color: Qt.rgba(0, 0, 0, 0.22)
        }

        // KHÔNG khắc số hạng ở đây: huy hiệu trên thẻ đã nói thứ hạng, và thẻ
        // đứng ngay giữa bệ nên số sẽ bị che gần hết.
    }
}
