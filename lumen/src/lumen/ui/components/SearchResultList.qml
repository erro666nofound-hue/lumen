import QtQuick
import QtQuick.Controls as QQC

// Danh sách kết quả tìm trên YouTube (model `source`, mặc định `Search`). Bấm một dòng là chọn bài
// đó để tải; component KHÔNG tự tải — chỉ bắn `resultChosen(url)` ra ngoài, để
// nơi dùng quyết định tải vào track nào.
Item {
    id: root

    signal resultChosen(string url)
    // Bộ tìm đứng sau danh sách. Mặc định ô tìm của Thư viện; hộp "Thêm bài"
    // của track dùng bộ riêng (`TrackSearch`) để hai nơi không kéo nhau.
    property var source: Search

    readonly property int rowHeight: 46
    readonly property int thumbWidth: 56
    readonly property int metaWidth: 52
    readonly property int colorMs: 120

    // Ba trạng thái loại trừ nhau: đang tìm / đã tìm mà rỗng / có kết quả.
    Text {
        anchors.centerIn: parent
        visible: root.source.busy
        text: "Đang tìm trên YouTube..."
        color: Theme.onSurfaceVariant
        font.pixelSize: Theme.fontSizeSm
        font.family: Theme.fontFamily
    }

    Text {
        anchors.centerIn: parent
        visible: !root.source.busy && root.source.hasSearched && root.source.count === 0
        text: "Không tìm thấy bài nào."
        color: Theme.onSurfaceVariant
        font.pixelSize: Theme.fontSizeSm
        font.family: Theme.fontFamily
    }

    ListView {
        id: list

        anchors.fill: parent
        visible: !root.source.busy && root.source.count > 0
        model: root.source
        clip: true
        spacing: Theme.spacingXs

        delegate: Item {
            width: list.width
            height: root.rowHeight

            required property string title
            required property string uploader
            required property string durationText
            required property string url
            required property string thumbnail

            Rectangle {
                anchors.fill: parent
                radius: Theme.radiusSm
                color: hover.hovered ? Theme.alpha(Theme.onSurface, 0.08) : "transparent"

                Behavior on color {
                    ColorAnimation { duration: root.colorMs; easing.type: Easing.OutCubic }
                }
            }

            Image {
                id: thumb

                anchors.left: parent.left
                anchors.leftMargin: Theme.spacingXs
                anchors.verticalCenter: parent.verticalCenter
                width: root.thumbWidth
                height: root.thumbWidth * 9 / 16
                source: parent.thumbnail
                fillMode: Image.PreserveAspectCrop
                asynchronous: true
                clip: true
            }

            Column {
                anchors.left: thumb.right
                anchors.leftMargin: Theme.spacingSm
                anchors.right: duration.left
                anchors.rightMargin: Theme.spacingSm
                anchors.verticalCenter: parent.verticalCenter
                spacing: 2

                Text {
                    width: parent.width
                    text: title
                    color: Theme.onSurface
                    font.pixelSize: Theme.fontSizeSm
                    font.family: Theme.fontFamily
                    elide: Text.ElideRight
                }

                Text {
                    width: parent.width
                    text: uploader
                    color: Theme.onSurfaceVariant
                    font.pixelSize: Theme.fontSizeSm
                    font.family: Theme.fontFamily
                    elide: Text.ElideRight
                }
            }

            Text {
                id: duration

                anchors.right: parent.right
                anchors.rightMargin: Theme.spacingSm
                anchors.verticalCenter: parent.verticalCenter
                width: root.metaWidth
                horizontalAlignment: Text.AlignRight
                text: durationText
                color: Theme.onSurfaceVariant
                font.pixelSize: Theme.fontSizeSm
                font.family: Theme.fontFamily
            }

            HoverHandler { id: hover }

            MouseArea {
                anchors.fill: parent
                cursorShape: Qt.PointingHandCursor
                onClicked: root.resultChosen(url)
            }
        }

        QQC.ScrollBar.vertical: QQC.ScrollBar { policy: QQC.ScrollBar.AsNeeded }
    }
}
