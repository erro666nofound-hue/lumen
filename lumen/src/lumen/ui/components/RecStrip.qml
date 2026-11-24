import QtQuick

// Dải "Gợi ý cho bạn" theo design R-1: thẻ 16:9 xếp ngang, nút "Tải" đặc ở
// góc ảnh, tên hai dòng, "kênh · lượt xem". Bấm ảnh = nghe thử.
Item {
    id: root

    property var songs: []
    signal previewRequested(string videoId)
    signal addRequested(string url, string title, var anchor)

    readonly property int cardWidth: 200
    readonly property int thumbHeight: Math.round(root.cardWidth * 9 / 16)
    readonly property int addHeight: 30

    function views(n) {
        if (!n || n <= 0) return ""
        if (n >= 1e6) return (n / 1e6).toFixed(n >= 1e7 ? 0 : 1).replace(".", ",") + " triệu lượt xem"
        return Math.round(n / 1e3) + " nghìn lượt xem"
    }

    height: root.thumbHeight + 76

    ListView {
        anchors.fill: parent
        orientation: ListView.Horizontal
        spacing: Theme.spacingMd + 2
        clip: true
        model: root.songs
        boundsBehavior: Flickable.StopAtBounds

        delegate: Item {
            id: card

            required property var modelData
            // openPickerBeside() đọc bốn trường này từ "anchor".
            readonly property string title: card.modelData.title
            readonly property string uploader: card.modelData.uploader
            readonly property string durationText: card.modelData.durationText
            readonly property string thumbnail: card.modelData.thumbnail

            width: root.cardWidth
            height: root.height

            RoundedImage {
                id: thumb
                width: parent.width
                height: root.thumbHeight
                radius: Theme.radiusLg
                source: card.thumbnail

                MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.previewRequested(card.modelData.videoId)
                }

                Rectangle {
                    anchors.right: parent.right
                    anchors.bottom: parent.bottom
                    anchors.margins: Theme.spacingSm
                    width: addRow.implicitWidth + Theme.spacingMd * 2
                    height: root.addHeight
                    radius: height / 2
                    // Nút nhỏ thoáng qua ⇒ đục (QĐ-040).
                    color: addArea.containsMouse ? Theme.primary : Theme.surfaceVariant
                    scale: addArea.pressed ? 0.86 : 1
                    Behavior on scale { NumberAnimation { duration: 90; easing.type: Easing.OutCubic } }

                    Row {
                        id: addRow
                        anchors.centerIn: parent
                        spacing: 2
                        MIcon {
                            name: "add"
                            size: 18
                            color: addArea.containsMouse ? Theme.onPrimary : Theme.onSurface
                            anchors.verticalCenter: parent.verticalCenter
                        }
                        Text {
                            text: "Tải"
                            color: addArea.containsMouse ? Theme.onPrimary : Theme.onSurface
                            font.pixelSize: Theme.fontSizeSm + 1
                            font.weight: Font.DemiBold
                            font.family: Theme.fontFamily
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }
                    MouseArea {
                        id: addArea
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.addRequested(card.modelData.url, card.title, card)
                    }
                }
            }
            Text {
                id: titleText
                anchors.top: thumb.bottom
                anchors.topMargin: Theme.spacingSm
                width: parent.width
                text: card.title
                color: Theme.onSurface
                font.pixelSize: Theme.fontSizeMd
                font.weight: Font.Medium
                font.family: Theme.fontFamily
                wrapMode: Text.Wrap
                maximumLineCount: 2
                elide: Text.ElideRight
                lineHeight: 1.1
            }
            Text {
                anchors.top: titleText.bottom
                anchors.topMargin: 2
                width: parent.width
                text: card.uploader + (root.views(card.modelData.viewCount) !== "" ? " · " + root.views(card.modelData.viewCount) : "")
                color: Theme.onSurfaceVariant
                font.pixelSize: Theme.fontSizeSm
                font.family: Theme.fontFamily
                elide: Text.ElideRight
            }
        }
    }
}
