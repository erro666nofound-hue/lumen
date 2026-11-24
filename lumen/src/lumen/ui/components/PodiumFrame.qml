import QtQuick
import QtQuick.Shapes

import "MedalColors.js" as MedalColors

// Khung bao quanh cả mục "Most Recommend".
//
// Ý đồ: viền KHÔNG phải một màu trang trí tuỳ tiện — nó chuyển bạc → vàng →
// đồng đúng theo vị trí ba hạng đứng bên dưới. Nhìn viền là đọc được bố cục.
//
// Vòng gradient làm bằng MỘT ShapePath chứa hai hình chữ nhật lồng nhau với
// `OddEvenFill`: hình trong "khoét" hình ngoài thành cái vòng, và vòng đó tô
// được bằng gradient. Viền của Rectangle hay `strokeColor` của ShapePath đều
// chỉ nhận MỘT màu, nên không làm được chuyện này.
Item {
    id: root

    property string label: ""
    property color labelBackground: Theme.surface

    readonly property int thickness: 2
    readonly property int radius: Theme.radiusLg + 6
    readonly property int cornerLength: 22
    readonly property int shimmerMs: 3200

    Shape {
        id: ring

        anchors.fill: parent
        preferredRendererType: Shape.CurveRenderer

        ShapePath {
            fillRule: ShapePath.OddEvenFill
            strokeWidth: -1
            fillGradient: LinearGradient {
                x1: 0; y1: 0
                x2: root.width; y2: 0
                GradientStop { position: 0.0; color: MedalColors.stopsFor("silver")[1] }
                GradientStop { position: 0.5; color: MedalColors.stopsFor("gold")[0] }
                GradientStop { position: 1.0; color: MedalColors.stopsFor("bronze")[1] }
            }

            PathRectangle {
                x: 0; y: 0
                width: root.width
                height: root.height
                radius: root.radius
            }

            PathRectangle {
                x: root.thickness; y: root.thickness
                width: Math.max(1, root.width - root.thickness * 2)
                height: Math.max(1, root.height - root.thickness * 2)
                radius: Math.max(0, root.radius - root.thickness)
            }
        }
    }

    // Vệt sáng chạy vòng quanh viền, chậm. Cùng lối với RunningBorder: nét đứt
    // trên chính đường viền, `phase` tách khỏi hình học để không bị chốt sai
    // lúc ô còn rộng 0.
    property real phase: 0

    Shape {
        anchors.fill: parent
        preferredRendererType: Shape.CurveRenderer
        opacity: 0.75

        ShapePath {
            id: shimmerPath

            strokeWidth: root.thickness
            strokeColor: Qt.rgba(1, 1, 1, 0.9)
            fillColor: "transparent"
            capStyle: ShapePath.RoundCap
            strokeStyle: ShapePath.DashLine
            // Một vạch sáng ngắn, quãng trống rất dài -> đúng một vệt chạy.
            dashPattern: [root.dashLen / root.thickness, root.gapLen / root.thickness]
            dashOffset: root.phase * (root.dashLen + root.gapLen) / root.thickness

            PathRectangle {
                x: root.thickness / 2; y: root.thickness / 2
                width: Math.max(1, root.width - root.thickness)
                height: Math.max(1, root.height - root.thickness)
                radius: root.radius
            }
        }
    }

    readonly property real perimeter: Math.max(
        1, 2 * (root.width + root.height) - 8 * root.radius + 2 * Math.PI * root.radius)
    readonly property real dashLen: root.perimeter * 0.12
    readonly property real gapLen: root.perimeter - root.dashLen

    NumberAnimation {
        target: root
        property: "phase"
        running: true
        from: 0
        to: 1
        duration: root.shimmerMs
        loops: Animation.Infinite
    }

    // Ngoặc góc: bốn nét ngắn dày hơn viền, mỗi góc lấy màu của hạng gần nó.
    component Corner: Item {
        required property int cornerX
        required property int cornerY
        required property color tone

        width: root.cornerLength
        height: root.cornerLength
        x: cornerX === 0 ? -1 : root.width - width + 1
        y: cornerY === 0 ? -1 : root.height - height + 1

        Rectangle {
            width: parent.width; height: root.thickness + 1
            radius: height / 2
            color: parent.tone
            y: parent.cornerY === 0 ? 0 : parent.height - height
        }

        Rectangle {
            width: root.thickness + 1; height: parent.height
            radius: width / 2
            color: parent.tone
            x: parent.cornerX === 0 ? 0 : parent.width - width
        }
    }

    Corner { cornerX: 0; cornerY: 0; tone: MedalColors.stopsFor("silver")[0] }
    Corner { cornerX: 1; cornerY: 0; tone: MedalColors.stopsFor("bronze")[0] }
    Corner { cornerX: 0; cornerY: 1; tone: MedalColors.stopsFor("silver")[1] }
    Corner { cornerX: 1; cornerY: 1; tone: MedalColors.stopsFor("bronze")[1] }

    // Nhãn ngồi ĐÈ lên cạnh trên, cắt đứt đường viền — kiểu bảng tên gắn trên
    // khung, thay vì một dòng chữ trôi nổi phía trên.
    Rectangle {
        visible: root.label !== ""
        anchors.left: parent.left
        anchors.leftMargin: root.radius + Theme.spacingMd
        anchors.verticalCenter: parent.top
        width: labelText.implicitWidth + Theme.spacingMd * 2
        height: labelText.implicitHeight + Theme.spacingXs
        color: root.labelBackground

        Text {
            id: labelText

            anchors.centerIn: parent
            text: root.label
            color: Theme.onSurfaceVariant
            font.pixelSize: Theme.fontSizeSm
            font.family: Theme.fontFamily
            font.letterSpacing: 1.2
        }
    }
}
