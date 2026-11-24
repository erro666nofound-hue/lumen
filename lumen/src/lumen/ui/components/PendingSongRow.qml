import QtQuick
import QtQuick.Effects

// Một bài ĐANG TẢI, nằm cuối danh sách của track và trông ĐÚNG NHƯ một bài đã
// tải xong (ảnh bìa, tên, thời lượng, tác giả, cùng bề rộng cột) — chỉ tối đi,
// có hai vạch chạy quanh viền và phần trăm.
//
// Cùng bố cục với TrackSongRow.qml có chủ ý: bài chuyển từ "đang tải" sang
// "đã có" mà không nhảy chỗ hay đổi hình dạng.
//
// Ảnh và tên lấy từ nơi gọi (thẻ vừa bấm đã biết sẵn), không chờ downloader dò
// xong — xem `hint_*` trong bridge/download_bridge.py.
Item {
    id: root

    property string title: ""
    property string artist: ""
    property string durationText: ""
    property string thumbnail: ""
    property real progress: 0
    property string detail: ""

    // Giống hệt TrackSongRow để các cột thẳng hàng nhau.
    readonly property int coverSize: 32
    readonly property int durationWidth: 56
    readonly property int artistWidth: 160
    // Chỗ trống đúng bằng cột ngày thêm của TrackSongRow. Bài đang tải CHƯA có
    // ngày thêm (nó chưa vào thư viện), nhưng cột vẫn phải chừa: thiếu chỗ này
    // là lúc tải xong hàng nhảy ngang một đoạn vì các cột lệch nhau.
    readonly property int addedWidth: 84
    readonly property real dimOpacity: 0.55
    readonly property int animMs: 200

    opacity: 0
    Component.onCompleted: root.opacity = 1

    Behavior on opacity {
        NumberAnimation { duration: root.animMs; easing.type: Easing.OutCubic }
    }

    Rectangle {
        anchors.fill: parent
        radius: Theme.radiusMd
        color: Theme.alpha(Theme.primary, 0.06)
    }

    // Cả phần nội dung mờ đi, KHÔNG mờ viền chạy và phần trăm: hai thứ đó phải
    // nổi lên thì mới nói được là "đang tải".
    Item {
        id: content

        anchors.fill: parent
        opacity: root.dimOpacity

        Text {
            id: artistLabel

            anchors.right: parent.right
            anchors.rightMargin: Theme.spacingMd
            anchors.verticalCenter: parent.verticalCenter
            width: root.artistWidth
            text: root.artist
            color: Theme.onSurfaceVariant
            font.pixelSize: Theme.fontSizeSm
            font.family: Theme.fontFamily
            elide: Text.ElideRight
        }

        Text {
            id: durationLabel

            anchors.right: artistLabel.left
            anchors.rightMargin: Theme.spacingMd + root.addedWidth + Theme.spacingMd
            anchors.verticalCenter: parent.verticalCenter
            width: root.durationWidth
            horizontalAlignment: Text.AlignRight
            text: root.durationText
            color: Theme.onSurfaceVariant
            font.pixelSize: Theme.fontSizeSm
            font.family: Theme.fontFamily
        }

        Item {
            id: coverContainer

            anchors.left: parent.left
            anchors.leftMargin: Theme.spacingSm
            anchors.verticalCenter: parent.verticalCenter
            width: root.coverSize
            height: root.coverSize

            // coverFrame và coverMask PHẢI cùng cấp bên trong coverContainer —
            // lệch ra ngoài là layer render rỗng trắng, không cảnh báo gì.
            Item {
                id: coverFrame

                anchors.fill: parent
                layer.enabled: true
                layer.effect: MultiEffect {
                    maskEnabled: true
                    maskSource: coverMask
                    autoPaddingEnabled: false
                }

                Rectangle {
                    anchors.fill: parent
                    color: Theme.alpha(Theme.primary, 0.18)

                    Text {
                        anchors.centerIn: parent
                        text: "music_note"
                        color: Theme.primary
                        font.pixelSize: Math.max(Theme.iconSize - 2, Math.round((Theme.fontSizeSm) * 1.4))
                        font.family: Theme.iconFont
                        font.variableAxes: ({ "FILL": 1 })
                        // Font biến thiên + distance field vẽ vỡ nét icon trên cửa sổ thật (CB-058).
                        renderType: Text.NativeRendering
                    }
                }

                Image {
                    anchors.fill: parent
                    visible: root.thumbnail !== ""
                    source: root.thumbnail
                    fillMode: Image.PreserveAspectCrop
                    asynchronous: true
                }
            }

            Rectangle {
                id: coverMask

                anchors.fill: parent
                radius: Theme.radiusSm
                visible: false
                layer.enabled: true
            }
        }

        Text {
            anchors.left: coverContainer.right
            anchors.leftMargin: Theme.spacingSm
            anchors.right: durationLabel.left
            anchors.rightMargin: Theme.spacingMd
            anchors.verticalCenter: parent.verticalCenter
            text: root.title !== "" ? root.title : "Đang lấy thông tin bài hát..."
            color: Theme.onSurface
            font.pixelSize: Theme.fontSizeMd
            font.family: Theme.fontFamily
            elide: Text.ElideRight
        }
    }

    // Phần trăm, đè lên ảnh bìa: chỗ duy nhất luôn trống và luôn nhìn thấy.
    Rectangle {
        anchors.left: parent.left
        anchors.leftMargin: Theme.spacingSm
        anchors.verticalCenter: parent.verticalCenter
        width: root.coverSize
        height: root.coverSize
        radius: Theme.radiusSm
        color: Theme.alpha(Theme.shadow, 0.62)

        Text {
            anchors.centerIn: parent
            text: root.progress > 0 ? Math.round(root.progress * 100) + "%" : "..."
            color: Theme.onSurface
            font.pixelSize: Theme.fontSizeSm
            font.family: Theme.fontFamily
        }
    }

    RunningBorder {
        anchors.fill: parent
        running: true
        radius: Theme.radiusMd
        color: Theme.primary
    }
}
