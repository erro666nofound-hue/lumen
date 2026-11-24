import QtQuick

// Bài vừa chọn "bay" từ thẻ vào đúng hàng track ở thanh bên, rồi nảy một cái.
//
// Không có nó thì bấm tải xong chẳng thấy gì xảy ra ở đâu cả — người dùng phải
// tự đoán bài chui vào track nào. Đây là thứ nối liền chỗ BẤM với chỗ ĐẾN.
//
// Sống ở tầng cửa sổ (Main.qml) chứ không trong thẻ hay thanh bên: nó phải bay
// XUYÊN QUA cả hai, mà item bay bên trong một cây con sẽ bị cắt ở biên.
Item {
    id: root

    property string thumbnail: ""

    // Báo khi ảnh đã CHẠM nơi đến. Viền chạy của track chỉ được bật sau đó,
    // nếu không track sáng lên trước cả khi bài bay tới — nhìn ngược nhân quả.
    signal landed(int playlistId)

    property int targetPlaylistId: -1

    readonly property int size: 44
    readonly property int flightMs: 520
    readonly property int landMs: 180

    visible: false
    width: root.size
    height: root.size
    z: 200

    // Bay từ điểm này tới điểm kia, cả hai theo toạ độ cửa sổ.
    function launch(fromX, fromY, toX, toY, playlistId) {
        root.targetPlaylistId = playlistId
        flight.stop()
        root.x = fromX - root.size / 2
        root.y = fromY - root.size / 2
        flight.toX = toX - root.size / 2
        flight.toY = toY - root.size / 2
        root.visible = true
        root.opacity = 1
        root.scale = 1
        flight.start()
    }

    Rectangle {
        anchors.fill: parent
        radius: Theme.radiusMd
        color: Theme.alpha(Theme.primary, 0.9)
        // Viền sáng để bóc ảnh ra khỏi nền — bay qua trang đầy ảnh thu nhỏ mà
        // không có viền thì nhìn như một mảng ảnh vỡ ra chứ không như một vật.
        border.width: 2
        border.color: Theme.onSurface
        clip: true

        Image {
            anchors.fill: parent
            anchors.margins: 2
            visible: root.thumbnail !== ""
            source: root.thumbnail
            fillMode: Image.PreserveAspectCrop
            asynchronous: true
        }

        Text {
            anchors.centerIn: parent
            visible: root.thumbnail === ""
            text: "music_note"
            color: Theme.onPrimary
            font.pixelSize: Math.max(Theme.iconSize - 2, Math.round((Theme.fontSizeLg) * 1.4))
            font.family: Theme.iconFont
            font.variableAxes: ({ "FILL": 1 })
            // Font biến thiên + distance field vẽ vỡ nét icon trên cửa sổ thật (CB-058).
            renderType: Text.NativeRendering
        }
    }

    SequentialAnimation {
        id: flight

        property real toX: 0
        property real toY: 0

        ParallelAnimation {
            // OutCubic cho X, InCubic cho Y: đường bay hơi vòng cung xuống chứ
            // không thẳng đơ như kéo chuột.
            NumberAnimation {
                target: root; property: "x"; to: flight.toX
                duration: root.flightMs; easing.type: Easing.OutCubic
            }
            NumberAnimation {
                target: root; property: "y"; to: flight.toY
                duration: root.flightMs; easing.type: Easing.InCubic
            }
            NumberAnimation {
                target: root; property: "scale"; to: 0.45
                duration: root.flightMs; easing.type: Easing.InCubic
            }
        }
        // Nảy một cái khi chạm nơi đến, rồi tắt.
        ParallelAnimation {
            NumberAnimation {
                target: root; property: "scale"; to: 0.9
                duration: root.landMs; easing.type: Easing.OutBack
            }
            NumberAnimation {
                target: root; property: "opacity"; to: 0
                duration: root.landMs; easing.type: Easing.InCubic
            }
        }

        onFinished: {
            root.visible = false
            root.landed(root.targetPlaylistId)
        }
    }
}
