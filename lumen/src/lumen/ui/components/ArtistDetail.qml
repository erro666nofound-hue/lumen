import QtQuick
import QtQuick.Controls as QQC

// Bảng chi tiết một nhạc sĩ: ảnh kênh, thanh kéo mức độ yêu thích, và các bài
// của họ đang có trong máy.
//
// NỔI cạnh ô vừa bấm, không đẩy bảng giãn ra — cùng lối với bảng chi tiết
// "Nhạc của tôi". Danh sách bài đã gộp trùng ở tầng dữ liệu: cùng một bài nằm
// trong hai track vẫn chỉ hiện một lần (xem history.songs_of_artist).
//
// QtQuick.Controls PHẢI import có tên miền (as QQC) — xem CLAUDE.md mục 5.
QQC.Popup {
    id: root

    property string artistName: ""
    property string avatar: ""
    property int rating: 0
    property bool rated: false
    property var songs: []

    signal ratingPicked(int value)
    signal ratingCleared()

    readonly property int panelWidth: 396
    readonly property int avatarSize: 64
    readonly property int songColumns: 3
    // Thu gọn chỉ hai hàng; mở hết cũng dừng ở bốn hàng rồi cuộn, không thì
    // nhạc sĩ nhiều bài sẽ đẩy bảng dài quá màn hình.
    readonly property int collapsedRows: 2
    readonly property int expandedRows: 4
    readonly property int titleHeight: 16
    readonly property int boxPadding: Theme.spacingSm
    readonly property int openMs: 200
    readonly property int closeMs: 140

    property bool expanded: false

    readonly property real cellWidth:
        (root.panelWidth - root.padding * 2 - root.boxPadding * 2) / root.songColumns
    readonly property real cellHeight: root.cellWidth - Theme.spacingSm
        + Theme.spacingXs + root.titleHeight
    readonly property int songRows: Math.ceil(root.songs.length / root.songColumns)
    readonly property int shownRows: Math.min(
        root.songRows, root.expanded ? root.expandedRows : root.collapsedRows)
    readonly property bool hasMore: root.songRows > root.collapsedRows

    width: root.panelWidth
    height: column.implicitHeight + padding * 2
    padding: Theme.spacingLg
    modal: true
    dim: false
    closePolicy: QQC.Popup.CloseOnPressOutside | QQC.Popup.CloseOnEscape

    // Mở bảng của nhạc sĩ khác thì phải về lại trạng thái thu gọn.
    onAboutToShow: root.expanded = false

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

    enter: Transition {
        ParallelAnimation {
            NumberAnimation { property: "opacity"; from: 0; to: 1
                              duration: root.openMs; easing.type: Easing.OutCubic }
            NumberAnimation { property: "scale"; from: 0.94; to: 1
                              duration: root.openMs; easing.type: Easing.OutBack }
        }
    }
    exit: Transition {
        NumberAnimation { property: "opacity"; from: 1; to: 0
                          duration: root.closeMs; easing.type: Easing.InCubic }
    }

    Column {
        id: column

        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        spacing: Theme.spacingMd

        Row {
            spacing: Theme.spacingSm

            CircleAvatar {
                width: root.avatarSize
                height: root.avatarSize
                avatar: root.avatar
                name: root.artistName
                letterSize: Theme.fontSizeXl
            }

            Column {
                anchors.verticalCenter: parent.verticalCenter
                spacing: 2

                Text {
                    text: root.artistName
                    color: Theme.onSurface
                    font.pixelSize: Theme.fontSizeLg
                    font.family: Theme.fontFamily
                }

                Text {
                    text: root.songs.length > 0
                        ? root.songs.length + " bài trong máy"
                        : "chưa có bài nào"
                    color: Theme.onSurfaceVariant
                    font.pixelSize: Theme.fontSizeSm
                    font.family: Theme.fontFamily
                }
            }
        }

        ArtistRatingSlider {
            width: parent.width
            rating: root.rating
            rated: root.rated

            onRatingPicked: (value) => root.ratingPicked(value)
            onRatingCleared: root.ratingCleared()
        }

        // Hộp nhạc: tách hẳn khỏi phần đánh giá ở trên để mắt biết đây là một
        // khối khác, không phải phần đuôi của thanh kéo.
        Rectangle {
            width: parent.width
            height: songBox.implicitHeight + root.boxPadding * 2
            visible: root.songs.length > 0
            radius: Theme.radiusMd
            // Lớp kính thứ hai — QĐ-037. Trước là onSurface 0.05, một lớp
            // LÀM SÁNG: nó không che gì cả, và khi khung hộp còn đục 0.97
            // thì không ai thấy. Khung sáng rồi thì danh sách bài cần lớp này.
            color: Theme.alpha(Theme.surface, 0.45)
            border.width: 1
            border.color: Theme.alpha(Theme.outline, 0.18)

            Column {
                id: songBox

                anchors.fill: parent
                anchors.margins: root.boxPadding
                spacing: Theme.spacingXs

                GridView {
                    width: parent.width
                    height: root.shownRows * root.cellHeight
                    model: root.songs
                    clip: true
                    interactive: root.expanded
                    cellWidth: root.cellWidth
                    cellHeight: root.cellHeight

                    Behavior on height {
                        NumberAnimation { duration: 160; easing.type: Easing.OutCubic }
                    }

                    delegate: Item {
                        id: songCell

                        required property var modelData

                        width: GridView.view.cellWidth
                        height: GridView.view.cellHeight

                        RoundedImage {
                            id: cover

                            anchors.top: parent.top
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.rightMargin: Theme.spacingSm
                            height: width
                            source: songCell.modelData.coverPath !== ""
                                ? "file://" + songCell.modelData.coverPath : ""
                        }

                        Text {
                            anchors.top: cover.bottom
                            anchors.topMargin: Theme.spacingXs
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.rightMargin: Theme.spacingSm
                            height: root.titleHeight
                            text: songCell.modelData.title
                            color: Theme.onSurfaceVariant
                            font.pixelSize: Theme.fontSizeSm
                            font.family: Theme.fontFamily
                            elide: Text.ElideRight
                        }
                    }

                    QQC.ScrollBar.vertical: QQC.ScrollBar { policy: QQC.ScrollBar.AsNeeded }
                }

                Text {
                    id: toggle

                    width: parent.width
                    visible: root.hasMore
                    horizontalAlignment: Text.AlignHCenter
                    text: root.expanded
                        ? "Thu gọn"
                        : "Xem tất cả " + root.songs.length + " bài"
                    color: toggleHover.hovered ? Theme.primary : Theme.onSurfaceVariant
                    font.pixelSize: Theme.fontSizeSm
                    font.family: Theme.fontFamily

                    HoverHandler { id: toggleHover }

                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.expanded = !root.expanded
                    }
                }
            }
        }
    }
}
