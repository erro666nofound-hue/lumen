import QtQuick

// Mấy vạch nhạc nhún nhảy, cho khoảng trống ở thanh bên đỡ trơ.
//
// Đang phát thì nhảy hẳn hoi; không phát thì thở nhẹ, chậm và thấp — im hẳn
// thì khoảng trống vẫn trơ như cũ, mà nhảy mãi thì lại nhức mắt.
//
// KHÔNG phải phổ âm thanh thật: mpv không đưa dữ liệu tần số ra, và đọc được
// thì cũng phải tính FFT mỗi khung hình cho một thứ trang trí. Đây là ngẫu
// nhiên có kiềm chế — nhìn thì không phân biệt được.
Item {
    id: root

    property bool playing: false
    property int barCount: 5
    property int barWidth: 4
    property int gap: 4
    property color barColor: Theme.primary

    readonly property int restHeight: 3
    readonly property int idleMs: 900
    readonly property int liveMs: 150

    implicitWidth: root.barCount * root.barWidth + (root.barCount - 1) * root.gap
    implicitHeight: 26

    // Gieo lại độ cao cho từng vạch. Mỗi vạch một con số riêng nên chúng lệch
    // pha nhau — cùng nhịp thì trông như cái lược, không ra nhạc.
    function _shuffle() {
        const low = root.playing ? 0.28 : 0.06
        const high = root.playing ? 1.0 : 0.22
        for (let i = 0; i < bars.count; i++) {
            const bar = bars.itemAt(i)
            if (bar)
                bar.level = low + Math.random() * (high - low)
        }
    }

    Timer {
        // Chỉ chạy khi mục này đang hiện: thanh bên hẹp lại là nó biến mất, và
        // lúc đó không việc gì phải đánh thức giao diện 7 lần mỗi giây.
        running: root.visible
        repeat: true
        interval: root.playing ? root.liveMs : root.idleMs
        triggeredOnStart: true
        onTriggered: root._shuffle()
    }

    Row {
        anchors.centerIn: parent
        spacing: root.gap

        Repeater {
            id: bars

            model: root.barCount

            Rectangle {
                id: bar

                required property int index
                property real level: 0.1

                width: root.barWidth
                height: Math.max(root.restHeight, root.implicitHeight * bar.level)
                radius: root.barWidth / 2
                anchors.verticalCenter: parent.verticalCenter
                color: root.barColor
                opacity: root.playing ? 0.85 : 0.35

                Behavior on height {
                    NumberAnimation {
                        duration: root.playing ? root.liveMs : root.idleMs
                        easing.type: Easing.OutCubic
                    }
                }

                Behavior on opacity {
                    NumberAnimation { duration: 320; easing.type: Easing.OutCubic }
                }
            }
        }
    }
}
