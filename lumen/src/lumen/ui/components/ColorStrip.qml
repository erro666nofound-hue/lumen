import QtQuick

// Một thanh kéo có nhãn, tự vẽ dải màu mà nó điều khiển.
Item {
    id: root

    property string label: ""
    property real ratio: 0
    property var gradientStops: []

    signal picked(real ratio)

    readonly property int labelWidth: 64
    readonly property int knobWidth: 4

    // Lấy màu tại vị trí t (0..1) trên dải, nội suy giữa hai mốc gần nhất.
    //
    // `gradientStops` PHẢI chứa color thật (Qt.hsla(...)), không phải chuỗi:
    // chuỗi thì `.r` là undefined và Qt.rgba(undefined,...) ra màu đen — bẫy đã
    // đã ghi lại (xem MedalColors.js).
    function colorAt(t) {
        const stops = root.gradientStops
        if (stops.length === 0)
            return "transparent"
        if (stops.length === 1)
            return stops[0]
        const pos = Math.max(0, Math.min(1, t)) * (stops.length - 1)
        const index = Math.min(stops.length - 2, Math.floor(pos))
        const mix = pos - index
        const from = stops[index]
        const to = stops[index + 1]
        return Qt.rgba(from.r + (to.r - from.r) * mix,
                       from.g + (to.g - from.g) * mix,
                       from.b + (to.b - from.b) * mix, 1)
    }

    Text {
        id: caption

        anchors.left: parent.left
        anchors.verticalCenter: parent.verticalCenter
        width: root.labelWidth
        text: root.label
        color: Theme.onSurfaceVariant
        font.pixelSize: Theme.fontSizeSm
        font.family: Theme.fontFamily
    }

    Rectangle {
        id: strip

        anchors.left: caption.right
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        height: parent.height
        radius: height / 2
        border.width: 1
        border.color: Theme.alpha(Theme.outline, 0.3)

        // BẢY mốc màu cố định, màu của từng mốc tính bằng hàm.
        //
        // KHÔNG dùng Repeater ở đây: `Gradient.stops` chỉ nhận GradientStop, đưa
        // Repeater vào thì app không mở được — và qmllint không hề báo, chỉ nạp
        // QML thật mới lộ ra.
        gradient: Gradient {
            orientation: Gradient.Horizontal
            GradientStop { position: 0.0;    color: root.colorAt(0.0) }
            GradientStop { position: 0.1667; color: root.colorAt(0.1667) }
            GradientStop { position: 0.3333; color: root.colorAt(0.3333) }
            GradientStop { position: 0.5;    color: root.colorAt(0.5) }
            GradientStop { position: 0.6667; color: root.colorAt(0.6667) }
            GradientStop { position: 0.8333; color: root.colorAt(0.8333) }
            GradientStop { position: 1.0;    color: root.colorAt(1.0) }
        }

        // Con trỏ vị trí: viền trắng bên ngoài, lõi tối bên trong — nhìn rõ
        // trên mọi màu, kể cả trắng lẫn đen.
        Rectangle {
            x: root.ratio * (strip.width - width)
            width: root.knobWidth + 4
            height: strip.height + 4
            anchors.verticalCenter: parent.verticalCenter
            radius: width / 2
            color: "transparent"
            border.width: 2
            border.color: "#ffffff"

            Rectangle {
                anchors.fill: parent
                anchors.margins: 2
                radius: width / 2
                color: "transparent"
                border.width: 1
                border.color: "#00000080"
            }
        }

        MouseArea {
            anchors.fill: parent
            cursorShape: Qt.PointingHandCursor

            function pick(mouseX) {
                root.picked(Math.max(0, Math.min(1, mouseX / strip.width)))
            }

            onPressed: (mouse) => pick(mouse.x)
            onPositionChanged: (mouse) => {
                if (pressed)
                    pick(mouse.x)
            }
        }
    }
}
