import QtQuick
import QtQuick.Controls as QQC
import QtQuick.Effects

// Bảng chi tiết một bài trong "Nhạc của tôi": ảnh, tên, nút nghe thử + tải vào
// track, rồi URL kèm nút chép.
//
// NỔI lên trên chứ không đẩy trang giãn ra: bảng chèn vào giữa lưới làm mọi thẻ
// bên dưới nhảy chỗ, và bài đang xem thì trôi khỏi tầm nhìn. QQC.Popup vẽ trong
// lớp phủ của cửa sổ nên nằm trên mọi thứ, và cho sẵn đóng-khi-bấm-ra-ngoài
// cùng đóng-bằng-Esc.
//
// Không tự gọi Player/Downloads — chỉ bắn signal ra ngoài, giống mọi thành
// phần khác của trang khám phá.
//
// QtQuick.Controls PHẢI import có tên miền (as QQC) — xem CLAUDE.md mục 5.
QQC.Popup {
    id: root

    property string title: ""
    property string artist: ""
    property string thumbnail: ""
    property string url: ""
    property string videoId: ""
    // Đang nghe thử đúng bài này / đang bóc luồng cho đúng bài này.
    property bool active: false
    property bool loading: false

    signal previewRequested()
    signal addRequested()

    readonly property int coverWidth: 240
    readonly property int panelWidth: 300
    readonly property int openMs: 200
    readonly property int closeMs: 140

    width: root.panelWidth
    height: column.implicitHeight + padding * 2
    padding: Theme.spacingLg
    // Xem chú thích cùng lý do trong TrackPicker.qml.
    modal: true
    dim: false
    closePolicy: QQC.Popup.CloseOnPressOutside | QQC.Popup.CloseOnEscape

    background: Rectangle {
        radius: Theme.radiusLg
        // ĐÚNG công thức kính của cửa sổ (QĐ-037), không phải một tấm riêng.
        // 0.97 là con số của luật CŨ: kính cửa sổ 0.45 rồi hộp này 0.97 nữa chỉ
        // còn ~1.6% ảnh nền, trong khi cả app để lọt 55% — một mảng đen giữa
        // một app trong suốt, đúng bệnh của bảng đồng bộ cũ.
        color: Theme.alpha(Theme.surface,
                           Theme.wallpaper !== "" ? Theme.wallpaperSurfaceAlpha
                                                  : Theme.surfaceAlpha)
        border.width: 1
        // Kính mỏng đi thì cái viền là thứ DUY NHẤT còn nói "hộp hết ở đây".
        border.color: Theme.alpha(Theme.outline, 0.60)
    }

    // Popup kiểu Basic KHÔNG có transition mặc định — thiếu hai khối này thì
    // bảng bật/tắt cụp một cái.
    enter: Transition {
        ParallelAnimation {
            NumberAnimation { property: "opacity"; from: 0; to: 1
                              duration: root.openMs; easing.type: Easing.OutCubic }
            NumberAnimation { property: "scale"; from: 0.92; to: 1
                              duration: root.openMs; easing.type: Easing.OutBack }
        }
    }
    exit: Transition {
        NumberAnimation { property: "opacity"; from: 1; to: 0
                          duration: root.closeMs; easing.type: Easing.InCubic }
    }

    Text {
        id: closeButton

        anchors.right: parent.right
        anchors.top: parent.top
        z: 1
        text: "close"
        color: closeHover.hovered ? Theme.onSurface : Theme.onSurfaceVariant
        font.pixelSize: Math.max(Theme.iconSize - 2, Math.round((Theme.fontSizeMd) * 1.4))
        font.family: Theme.iconFont
        font.variableAxes: ({ "FILL": 1 })
        // Font biến thiên + distance field vẽ vỡ nét icon trên cửa sổ thật (CB-058).
        renderType: Text.NativeRendering

        Behavior on color {
            ColorAnimation { duration: 120; easing.type: Easing.OutCubic }
        }

        HoverHandler { id: closeHover }

        MouseArea {
            anchors.fill: parent
            anchors.margins: -Theme.spacingXs
            cursorShape: Qt.PointingHandCursor
            onClicked: root.close()
        }
    }

    // Lớp kính THỨ HAI, đúng chỗ đọc chữ — QĐ-037. Khung hộp để sáng cho hợp
    // với cả app; khối chữ thì cần một lớp nữa, không thì trang phía sau (đã
    // mờ nhưng vẫn còn lốm đốm màu) hiện lên ngay dưới hàng chữ.
    Rectangle {
        anchors.fill: column
        anchors.margins: -Theme.spacingSm
        radius: Theme.radiusMd
        color: Theme.alpha(Theme.surface, 0.45)
    }

    Column {
        id: column

        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        spacing: Theme.spacingSm

        Item {
            width: root.coverWidth
            height: width * 9 / 16
            anchors.horizontalCenter: parent.horizontalCenter

            // frame/mask cùng cấp cha trực tiếp — xem TrackCard.qml.
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
                    color: Theme.alpha(Theme.primary, 0.14)

                    Text {
                        anchors.centerIn: parent
                        text: "music_note"
                        color: Theme.primary
                        font.pixelSize: Math.max(Theme.iconSize - 2, Math.round((Theme.fontSizeXl) * 1.4))
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
                    clip: true
                }
            }

            Rectangle {
                id: coverMask

                anchors.fill: parent
                radius: Theme.radiusMd
                visible: false
                layer.enabled: true
            }
        }

        Text {
            width: parent.width
            horizontalAlignment: Text.AlignHCenter
            text: root.title !== "" ? root.title : "(không rõ tên)"
            color: Theme.onSurface
            font.pixelSize: Theme.fontSizeLg
            font.family: Theme.fontFamily
            elide: Text.ElideRight
            maximumLineCount: 2
            wrapMode: Text.WordWrap
        }

        Text {
            width: parent.width
            visible: root.artist !== ""
            horizontalAlignment: Text.AlignHCenter
            text: root.artist
            color: Theme.onSurfaceVariant
            font.pixelSize: Theme.fontSizeMd
            font.family: Theme.fontFamily
            elide: Text.ElideRight
        }

        Row {
            anchors.horizontalCenter: parent.horizontalCenter
            spacing: Theme.spacingMd
            topPadding: Theme.spacingXs

            PlayCircle {
                anchors.verticalCenter: parent.verticalCenter
                active: root.active
                loading: root.loading

                onClicked: root.previewRequested()
            }

            IconButton {
                anchors.verticalCenter: parent.verticalCenter
                glyph: "download"
                hoverColor: Theme.primary
                onClicked: root.addRequested()
            }
        }

        UrlRow {
            width: parent.width
            url: root.url
        }
    }
}
