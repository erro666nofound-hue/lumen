import QtQuick
import QtQuick.Effects

// Một thẻ bài đề xuất trên trang khám phá: ảnh thu nhỏ YouTube + tên
// bài + kênh + thời lượng. Dùng lại ở PodiumRow (bục top 3, property `large`
// to hơn) và ArtistShelf (hàng cuộn ngang theo nghệ sĩ).
//
// KHÔNG tự gọi Player/Downloads — chỉ bắn previewRequested()/addRequested(),
// nơi dùng (LibraryView) nối vào bridge thật, giống nếp SearchResultList và
// HistoryList. `active`/`loading` do nơi dùng tự tính từ Player.previewVideoId
// (thẻ không tự biết videoId của chính nó thuộc bài nào của Player).
//
// Nút phát/tải nằm trên ảnh thu nhỏ, nền có thể sáng hoặc tối tuỳ ảnh — dùng
// lại đúng "nền shadow đậm + viền onSurface sáng" đã tự kiểm chứng tương phản
// tốt với mọi ảnh bìa trong TrackCard.qml (mục checkbox).
Rectangle {
    id: root

    property string title: ""
    property string uploader: ""
    property string durationText: ""
    property string thumbnail: ""
    // Player.previewVideoId đúng bài này VÀ đang phát (không phải tạm dừng).
    property bool active: false
    // Đang bóc luồng để nghe thử ĐÚNG bài này (~4s).
    property bool loading: false
    // Hạng 1 trên bục: to hơn rõ rệt, không chỉ đổi mỗi bề rộng do nơi dùng cấp.
    property bool large: false
    // Nhân chiều cao KHUNG ẢNH. Chiều cao thẻ suy từ nội dung, nên muốn thẻ
    // cao hơn thì cho ảnh cao hơn — vừa được chiều cao, vừa được ảnh to.
    property real coverScale: 1.0
    // Màu pha vào THÂN thẻ. Bục dùng nó để nhìn thẻ là biết hạng, không phải
    // nhìn mỗi cái viền. "transparent" = giữ nguyên nền kính mờ mặc định.
    property color tintColor: "transparent"
    property real tintStrength: 0.34
    // Tự phóng to khi rê chuột. Bục TẮT cái này và tự phóng cả bệ, vì viền kim
    // loại với quầng lửa là anh em của thẻ — phóng mỗi thẻ thì chúng đứng yên
    // và bố cục vỡ ra.
    property bool growOnHover: true
    readonly property bool hovered: hover.hovered

    readonly property real hoverScale: 1.05

    signal previewRequested()
    signal addRequested()

    readonly property int pad: Theme.spacingSm
    readonly property int thumbRadius: Theme.radiusMd
    readonly property int controlSize: root.large ? 44 : 34
    readonly property int addSize: 26
    readonly property int appearMs: 220
    readonly property int hoverMs: 140

    height: content.implicitHeight + root.pad * 2
    radius: Theme.radiusLg
    // MỘT binding duy nhất cho scale, gộp cả lúc xuất hiện lẫn lúc rê chuột.
    //
    // Trước đây có hai chỗ tranh nhau: binding hover ở đây, và
    // `Component.onCompleted: root.scale = 1` của animation xuất hiện. Gán mệnh
    // lệnh vào một property đang có binding sẽ PHÁ binding đó vĩnh viễn, nên
    // thẻ không bao giờ to ra khi rê chuột. Bẫy này dự án đã dính một lần rồi —
    // xem chú thích trong VolumeButton.qml.
    scale: (root.appeared ? 1 : 0.94)
        * ((root.growOnHover && hover.hovered) ? root.hoverScale : 1)
    // Nổi lên trên khi phóng to, không thì thẻ bên cạnh cắt mất phần thò ra.
    z: hover.hovered ? 1 : 0

    Behavior on scale {
        NumberAnimation { duration: root.hoverMs; easing.type: Easing.OutBack }
    }
    color: root.tintColor.a > 0
        ? Qt.tint(Theme.alpha(Theme.onSurface, hover.hovered ? 0.10 : 0.07),
                  Qt.rgba(root.tintColor.r, root.tintColor.g, root.tintColor.b,
                          root.tintStrength))
        : Theme.alpha(Theme.onSurface, hover.hovered ? 0.08 : 0.05)
    border.width: root.active ? 2 : 1
    border.color: root.active ? Theme.primary : Theme.alpha(Theme.outline, 0.22)

    Behavior on color {
        ColorAnimation { duration: root.hoverMs; easing.type: Easing.OutCubic }
    }

    Behavior on border.color {
        ColorAnimation { duration: root.hoverMs; easing.type: Easing.OutCubic }
    }

    // Xuất hiện mềm khi thẻ được tạo (delegate mới của ListView/Repeater).
    // `appeared` là property thường, KHÔNG ai bind vào nó — nên gán được an toàn.
    property bool appeared: false

    opacity: 0

    Component.onCompleted: { root.opacity = 1; root.appeared = true }

    Behavior on opacity {
        NumberAnimation { duration: root.appearMs; easing.type: Easing.OutCubic }
    }

    HoverHandler { id: hover }

    Column {
        id: content

        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.margins: root.pad
        spacing: Theme.spacingXs

        Item {
            id: thumbBox

            width: parent.width
            height: width * 9 / 16 * root.coverScale

            // coverFrame/coverMask cùng cấp cha, không xuyên qua Column — xem
            // chú thích thực nghiệm ở TrackCard.qml về vì sao maskSource xuyên
            // nhiều cấp cha không đáng tin cậy.
            Item {
                id: thumbFrame

                anchors.fill: parent
                layer.enabled: true
                layer.effect: MultiEffect {
                    maskEnabled: true
                    maskSource: thumbMask
                    autoPaddingEnabled: false
                }

                // Luôn vẽ trước Image: khi chưa tải xong/không có thumbnail,
                // Image trong suốt để lộ đúng ô này ra, không cần theo dõi status.
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
                id: thumbMask

                anchors.fill: thumbFrame
                radius: root.thumbRadius
                visible: false
                layer.enabled: true
            }

            PlayCircle {
                anchors.centerIn: parent
                large: root.large
                active: root.active
                loading: root.loading
                shown: hover.hovered

                onClicked: root.previewRequested()
            }

            Rectangle {
                id: addCircle

                anchors.top: parent.top
                anchors.right: parent.right
                anchors.margins: Theme.spacingXs
                width: root.addSize
                height: root.addSize
                radius: width / 2
                color: Theme.alpha(Theme.shadow, 0.55)
                border.width: 1
                border.color: Theme.alpha(Theme.onSurface, 0.85)
                opacity: hover.hovered ? 1 : 0
                visible: opacity > 0.01

                Behavior on opacity {
                    NumberAnimation { duration: root.hoverMs; easing.type: Easing.OutCubic }
                }

                Text {
                    anchors.centerIn: parent
                    text: "download"
                    color: Theme.onSurface
                    font.pixelSize: Math.max(Theme.iconSize - 2, Math.round((Theme.fontSizeSm) * 1.4))
                    font.family: Theme.iconFont
                    font.variableAxes: ({ "FILL": 1 })
                    // Font biến thiên + distance field vẽ vỡ nét icon trên cửa sổ thật (CB-058).
                    renderType: Text.NativeRendering
                }

                MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.addRequested()
                }
            }
        }

        Text {
            width: parent.width
            text: root.title
            color: Theme.onSurface
            font.pixelSize: root.large ? Theme.fontSizeLg : Theme.fontSizeMd
            font.family: Theme.fontFamily
            elide: Text.ElideRight
            wrapMode: Text.WordWrap
            maximumLineCount: 2
        }

        Item {
            width: parent.width
            height: durationLabel.implicitHeight

            Text {
                anchors.left: parent.left
                anchors.right: durationLabel.left
                anchors.rightMargin: Theme.spacingXs
                text: root.uploader
                color: Theme.onSurfaceVariant
                font.pixelSize: Theme.fontSizeSm
                font.family: Theme.fontFamily
                elide: Text.ElideRight
            }

            Text {
                id: durationLabel

                anchors.right: parent.right
                text: root.durationText
                color: Theme.onSurfaceVariant
                font.pixelSize: Theme.fontSizeSm
                font.family: Theme.fontFamily
            }
        }
    }
}
