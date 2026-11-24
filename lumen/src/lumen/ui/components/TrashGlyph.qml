import QtQuick

// Icon thùng rác vẽ thuần bằng Rectangle — không ký tự BMP nào ra hình thùng
// rác, mà ký tự ngoài BMP thì đã hỏng một lần trên máy này (xem CLAUDE.md).
//
// Mọi kích thước tính theo TỈ LỆ của khung, không phải số pixel cứng: bản đầu
// dùng 2px/3px cố định, đặt vào khung 13px thì nắp chiếm gần hết và icon nhìn
// ra cái nồi. Đặt khung CAO hơn RỘNG (ví dụ 15x18) thì mới ra dáng thùng rác.
Item {
    id: root

    property color color: Theme.onSurfaceVariant

    // Tỉ lệ các phần so với khung — đổi ở đây là đổi dáng, không cần sửa chỗ dùng.
    readonly property real handleWidthFactor: 0.42
    readonly property real bodyWidthFactor: 0.78
    readonly property int hairline: Math.max(1, Math.round(height * 0.07))
    readonly property int gap: Math.max(1, Math.round(height * 0.06))

    // Quai — thanh ngắn trên cùng.
    Rectangle {
        id: handle

        anchors.top: parent.top
        anchors.horizontalCenter: parent.horizontalCenter
        width: Math.round(parent.width * root.handleWidthFactor)
        height: root.hairline
        radius: height / 2
        color: root.color
    }

    // Nắp — thanh ngang rộng hết khung.
    Rectangle {
        id: lid

        anchors.top: handle.bottom
        anchors.topMargin: root.gap
        anchors.horizontalCenter: parent.horizontalCenter
        width: parent.width
        height: root.hairline
        radius: height / 2
        color: root.color
    }

    // Thân — viền rỗng, bo nhẹ hai góc dưới.
    Rectangle {
        id: body

        anchors.top: lid.bottom
        anchors.topMargin: root.gap
        anchors.bottom: parent.bottom
        anchors.horizontalCenter: parent.horizontalCenter
        width: Math.round(parent.width * root.bodyWidthFactor)
        radius: Math.max(1, Math.round(root.height * 0.08))
        color: "transparent"
        border.width: root.hairline
        border.color: root.color

        // Hai vạch dọc bên trong.
        Row {
            anchors.centerIn: parent
            spacing: Math.max(2, Math.round(body.width * 0.22))

            Repeater {
                model: 2

                Rectangle {
                    width: root.hairline
                    height: Math.round(body.height * 0.46)
                    radius: width / 2
                    color: root.color
                }
            }
        }
    }
}
