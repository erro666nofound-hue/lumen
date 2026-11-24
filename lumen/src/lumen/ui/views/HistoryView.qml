import QtQuick
import QtQuick.Controls as QQC
import QtQuick.Effects
import "../components"
import "../components/TimeText.js" as TimeText

// Màn Lịch sử theo design R-1: những bài đã nghe gần đây, nhóm theo ngày
// (Hôm nay, Hôm qua, Thứ Sáu, 2/10…), mới nhất ở trên. Bấm một hàng là phát
// bài đó trong track chứa nó.
Item {
    id: root

    readonly property int contentWidth: Math.min(width - Theme.spacingLg * 2, Theme.contentMaxWidth)
    readonly property int gutter: (width - contentWidth) / 2
    readonly property int rowHeight: 60
    readonly property int cover: 44
    readonly property int timeWidth: 52

    Flickable {
        id: flick

        anchors.fill: parent
        contentWidth: width
        contentHeight: column.height
        bottomMargin: Theme.islandReserve
        clip: true
        boundsBehavior: Flickable.StopAtBounds

        QQC.ScrollBar.vertical: QQC.ScrollBar { policy: QQC.ScrollBar.AsNeeded }

        Column {
            id: column

            x: root.gutter
            width: root.contentWidth
            topPadding: Theme.spacingXl
            spacing: Theme.spacingXl

            Column {
                spacing: Theme.spacingXs

                Text {
                    text: "Lịch sử"
                    color: Theme.onSurface
                    font.pixelSize: 32
                    font.weight: Font.Bold
                    font.family: Theme.fontFamily
                }
                Text {
                    text: "Những gì bạn nghe gần đây, mới nhất ở trên."
                    color: Theme.onSurfaceVariant
                    font.pixelSize: Theme.fontSizeMd
                    font.family: Theme.fontFamily
                }
            }

            Text {
                visible: Listened.days.length === 0
                text: "Chưa nghe bài nào. Phát một bài là nó hiện ở đây."
                color: Theme.onSurfaceVariant
                font.pixelSize: Theme.fontSizeMd
                font.family: Theme.fontFamily
            }

            Repeater {
                model: Listened.days

                Column {
                    id: day

                    required property var modelData

                    width: column.width
                    spacing: Theme.spacingSm

                    Text {
                        text: day.modelData.label
                        color: Theme.onSurface
                        font.pixelSize: Theme.fontSizeMd + 1
                        font.weight: Font.DemiBold
                        font.family: Theme.fontFamily
                    }

                    // Lớp kính thứ hai — chỗ đọc chữ (QĐ-037).
                    Rectangle {
                        width: parent.width
                        height: rows.height + Theme.spacingXs * 2
                        radius: Theme.radiusLg
                        color: Theme.alpha(Theme.onSurface, 0.045)
                        border.width: 1
                        border.color: Theme.alpha(Theme.onSurface, 0.075)

                        Column {
                            id: rows

                            x: Theme.spacingXs
                            y: Theme.spacingXs
                            width: parent.width - Theme.spacingXs * 2

                            Repeater {
                                model: day.modelData.rows

                                Item {
                                    id: row

                                    required property var modelData
                                    readonly property bool current: Player.trackId === row.modelData.id

                                    width: rows.width
                                    height: root.rowHeight

                                    Rectangle {
                                        anchors.fill: parent
                                        radius: Theme.radiusMd
                                        color: row.current ? Theme.alpha(Theme.primary, 0.16)
                                            : (area.containsMouse ? Theme.alpha(Theme.onSurface, 0.05) : "transparent")
                                    }
                                    Text {
                                        id: timeText
                                        x: Theme.spacingSm
                                        width: root.timeWidth
                                        anchors.verticalCenter: parent.verticalCenter
                                        text: row.modelData.time
                                        color: Theme.onSurfaceVariant
                                        font.pixelSize: Theme.fontSizeSm + 0.5
                                        font.family: Theme.fontFamily
                                        font.features: { "tnum": 1 }
                                    }
                                    RoundedImage {
                                        id: coverImage
                                        anchors.left: timeText.right
                                        anchors.leftMargin: Theme.spacingSm
                                        anchors.verticalCenter: parent.verticalCenter
                                        width: root.cover
                                        height: root.cover
                                        radius: Theme.radiusMd
                                        source: row.modelData.coverPath === "" ? ""
                                            : (row.modelData.coverPath.startsWith("http") ? row.modelData.coverPath
                                                                                          : "file://" + row.modelData.coverPath)
                                        MIcon {
                                            anchors.centerIn: parent
                                            visible: row.modelData.coverPath === ""
                                            name: "music_note"
                                        }
                                    }
                                    Text {
                                        anchors.left: coverImage.right
                                        anchors.leftMargin: Theme.spacingMd
                                        anchors.right: durationText.left
                                        anchors.rightMargin: Theme.spacingMd
                                        anchors.bottom: parent.verticalCenter
                                        anchors.bottomMargin: 1
                                        text: row.modelData.title
                                        color: row.current ? Theme.primary : Theme.onSurface
                                        font.pixelSize: Theme.fontSizeMd + 0.5
                                        font.weight: Font.Medium
                                        font.family: Theme.fontFamily
                                        elide: Text.ElideRight
                                    }
                                    Text {
                                        anchors.left: coverImage.right
                                        anchors.leftMargin: Theme.spacingMd
                                        anchors.right: durationText.left
                                        anchors.rightMargin: Theme.spacingMd
                                        anchors.top: parent.verticalCenter
                                        anchors.topMargin: 1
                                        text: row.modelData.artist !== "" ? row.modelData.artist : "Bài nhập từ ổ cứng"
                                        color: Theme.onSurfaceVariant
                                        font.pixelSize: Theme.fontSizeSm + 0.5
                                        font.family: Theme.fontFamily
                                        elide: Text.ElideRight
                                    }
                                    Text {
                                        id: durationText
                                        anchors.right: parent.right
                                        anchors.rightMargin: Theme.spacingMd
                                        anchors.verticalCenter: parent.verticalCenter
                                        text: TimeText.format(row.modelData.durationMs)
                                        color: Theme.onSurfaceVariant
                                        font.pixelSize: Theme.fontSizeSm + 0.5
                                        font.family: Theme.fontFamily
                                    }
                                    MouseArea {
                                        id: area
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
                                        enabled: row.modelData.playlistId >= 0
                                        onClicked: {
                                            const pid = row.modelData.playlistId
                                            Player.playPlaylist(pid, Playlists.orderedIds(pid), row.modelData.id)
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
