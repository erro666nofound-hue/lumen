import QtQuick
import QtQuick.Shapes

// Hai vạch sáng chạy vòng quanh viền — dấu hiệu "đang tải" cho một track ở
// thanh bên và cho một bài chưa tải xong trong danh sách.
//
// Dùng nét ĐỨT trên đúng đường viền rồi cho `dashOffset` chạy: hai vạch thật,
// bám sát bo góc, không phải hai chấm bay lòng vòng bên trên. Rẻ hơn hạt
// particle nhiều — thứ này có thể hiện cùng lúc trên nhiều hàng.
Item {
    id: root

    property bool running: false
    property color color: Theme.primary
    property real radius: Theme.radiusMd
    property real thickness: 2

    // Pha 0..1 của vòng chạy. Tách khỏi hình học có chủ ý — xem khối animation.
    property real phase: 0

    // Chu vi xấp xỉ, để độ dài vạch luôn bằng một phần cố định của viền dù ô
    // to hay nhỏ — đặt cứng độ dài thì ô hẹp trông như viền liền.
    readonly property real perimeter: Math.max(
        1, 2 * (root.width + root.height) - 8 * root.radius + 2 * Math.PI * root.radius)
    // ĐÚNG HAI vạch: mẫu nét là [vạch, trống] nên nó lặp lại sau mỗi
    // 2 × dashLength. Muốn lặp đúng hai lần quanh viền thì dashLength phải là
    // MỘT PHẦN TƯ chu vi (đặt 1/8 ra bốn vạch — đã chụp ảnh thấy).
    readonly property real dashLength: root.perimeter / 4
    readonly property int cycleMs: 1600

    visible: root.running
    // Không nhận chuột: đây chỉ là lớp trang trí nằm đè lên nội dung.
    enabled: false

    Shape {
        id: shape

        anchors.fill: parent
        preferredRendererType: Shape.CurveRenderer

        ShapePath {
            id: path

            strokeWidth: root.thickness
            strokeColor: root.color
            fillColor: "transparent"
            capStyle: ShapePath.RoundCap
            strokeStyle: ShapePath.DashLine
            // Đơn vị dashPattern là BỘI của strokeWidth, không phải pixel.
            dashPattern: [root.dashLength / root.thickness, root.dashLength / root.thickness]
            // Vị trí vạch suy TỪ pha, không phải do animation đặt thẳng. Xem
            // chú thích ở khối animation bên dưới về lý do.
            dashOffset: root.phase * 2 * root.dashLength / root.thickness

            PathRectangle {
                x: root.thickness / 2
                y: root.thickness / 2
                width: Math.max(1, root.width - root.thickness)
                height: Math.max(1, root.height - root.thickness)
                radius: root.radius
            }
        }
    }

    // Animation chỉ chạy một con số 0..1 KHÔNG phụ thuộc hình học; quãng chạy
    // thật suy ra từ pha đó qua binding ở trên.
    //
    // Trước đây animation đặt thẳng `dashOffset` với `to:` tính từ chu vi. Qt
    // chốt giá trị `to` NGAY LÚC animation bắt đầu — mà lúc đó ô còn rộng 0 nên
    // quãng chạy ≈ 0: hai vạch đứng im, tới tận vòng lặp sau (1,6s) mới nhúc
    // nhích. Đúng triệu chứng "hiện ra rồi một lúc mới chạy".
    //
    // Chạy hết một chu kỳ vạch+trống thì hình lặp lại y hệt, nên vòng lặp liền
    // mạch, không giật khi quay về đầu.
    NumberAnimation {
        target: root
        property: "phase"
        running: root.running
        from: 0
        to: 1
        duration: root.cycleMs
        loops: Animation.Infinite
    }
}
