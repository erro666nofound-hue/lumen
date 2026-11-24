import QtQuick
import QtQuick.Shapes

// Vòng quay báo "đang chờ". Một cung tròn thật, vẽ bằng QtQuick.Shapes.
//
// Trước đây chỗ này xoay ký tự "◐": nét chữ dày mỏng không đều, tâm xoay lệch
// theo font, và mỗi font vẽ một kiểu. Cung tròn thì luôn ra đúng một hình.
//
// Sweep cũng thở vào–ra chứ không chỉ quay đều: vòng quay tốc độ đều nhìn như
// đứng yên khi phải chờ vài giây (nghe thử mất ~1,5s).
Item {
    id: root

    property bool running: false
    property color color: Theme.primary
    property real thickness: 2.5

    readonly property int spinMs: 900
    readonly property int breatheMs: 1100
    readonly property real minSweep: 40
    readonly property real maxSweep: 290

    visible: root.running
    implicitWidth: 18
    implicitHeight: 18

    Shape {
        id: shape

        anchors.fill: parent
        preferredRendererType: Shape.CurveRenderer
        // Quay cả hình thay vì đổi startAngle: rẻ hơn, và không phải vẽ lại
        // đường đi mỗi khung hình.
        rotation: 0

        ShapePath {
            strokeWidth: root.thickness
            strokeColor: root.color
            fillColor: "transparent"
            capStyle: ShapePath.RoundCap

            PathAngleArc {
                id: arc

                centerX: root.width / 2
                centerY: root.height / 2
                radiusX: Math.max(1, (Math.min(root.width, root.height) - root.thickness) / 2)
                radiusY: arc.radiusX
                startAngle: -90
                sweepAngle: root.minSweep
            }
        }
    }

    NumberAnimation {
        target: shape
        property: "rotation"
        running: root.running
        from: 0
        to: 360
        duration: root.spinMs
        loops: Animation.Infinite
    }

    SequentialAnimation {
        running: root.running
        loops: Animation.Infinite

        NumberAnimation {
            target: arc; property: "sweepAngle"
            to: root.maxSweep; duration: root.breatheMs; easing.type: Easing.InOutCubic
        }
        NumberAnimation {
            target: arc; property: "sweepAngle"
            to: root.minSweep; duration: root.breatheMs; easing.type: Easing.InOutCubic
        }
    }
}
