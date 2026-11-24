import QtQuick

import "TimeText.js" as TimeText

// Khối "đang phát" của Mini Lumen: bìa có lửa, tên bài, thanh tua, nút điều
// khiển, và hàng trộn/lặp/tốc độ/âm lượng.
//
// Tách khỏi MiniWindow vì cửa sổ đó còn phải lo khung, đầu cửa sổ và danh sách
// track — gộp cả vào một file thì vượt ngân sách 250 dòng và khó đọc.
Column {
    id: root

    property int coverSize: 132
    property int auraMargin: 20
    property int buttonSize: 26

    readonly property real disabledOpacity: 0.4
    readonly property bool hasTrack: Player.hasTrack

    // Trạng thái phát trước khi kéo tua, để thả ra biết có nên phát tiếp không.
    property bool _resumeAfterScrub: false

    spacing: Theme.spacingSm

        // Cao hơn chính tấm bìa đúng bằng tầm lửa liếm xuống dưới. Không chừa
        // chỗ đó thì hạt lửa tràn xuống đè lên tên bài — đã thấy trên ảnh chụp.
        Item {
            id: coverBox

            anchors.horizontalCenter: parent.horizontalCenter
            width: root.coverSize
            height: root.coverSize + root.auraMargin

            Item {
                id: cover

                anchors.top: parent.top
                anchors.horizontalCenter: parent.horizontalCenter
                width: root.coverSize
                height: root.coverSize

                // Lửa CHÁY sau bìa khi đang phát. Cùng bộ hạt với bục top 1/2/3,
                // nhưng lấy màu theo theme chứ không theo màu huy chương.
                FlameAura {
                    anchors.fill: parent
                    anchors.margins: -root.auraMargin
                    running: Player.isPlaying
                    emberColor: Theme.primary
                    emberColors: [Theme.primary, Theme.tertiary, Theme.secondary]
                    sparkColor: "#ffffff"
                    density: 1.6
                    particleSize: 13
                }

                RoundedImage {
                    anchors.fill: parent
                    radius: Theme.radiusLg
                    source: Player.coverPath !== "" ? "file://" + Player.coverPath : ""
                }

                Text {
                    anchors.centerIn: parent
                    visible: Player.coverPath === ""
                    text: "music_note"
                    color: Theme.alpha(Theme.onSurface, 0.35)
                    font.pixelSize: Math.max(Theme.iconSize - 2, Math.round((Theme.fontSizeXl * 2) * 1.4))
                    font.family: Theme.iconFont
                    font.variableAxes: ({ "FILL": 1 })
                    // Font biến thiên + distance field vẽ vỡ nét icon trên cửa sổ thật (CB-058).
                    renderType: Text.NativeRendering
                }
            }
        }

        Text {
            width: parent.width
            horizontalAlignment: Text.AlignHCenter
            text: root.hasTrack ? Player.title : "Chưa phát bài nào"
            color: Theme.onSurface
            font.pixelSize: Theme.fontSizeLg
            font.family: Theme.fontFamily
            elide: Text.ElideRight
        }

        Text {
            width: parent.width
            horizontalAlignment: Text.AlignHCenter
            visible: root.hasTrack
            text: Player.artist
            color: Theme.onSurfaceVariant
            font.pixelSize: Theme.fontSizeSm
            font.family: Theme.fontFamily
            elide: Text.ElideRight
        }

        Item {
            width: parent.width
            height: seek.implicitHeight + elapsed.implicitHeight + Theme.spacingXs
            opacity: root.hasTrack ? 1 : root.disabledOpacity

            SeekBar {
                id: seek

                width: parent.width
                anchors.top: parent.top
                position: Player.positionMs
                duration: Player.durationMs
                interactive: root.hasTrack

                // Im tiếng trong lúc kéo rồi phát tiếp khi thả — cùng luật
                // với thanh phát dưới cửa sổ chính.
                onScrubStarted: {
                    root._resumeAfterScrub = Player.isPlaying
                    if (Player.isPlaying) Player.toggle()
                }
                onScrubFinished: (value) => {
                    Player.seek(value)
                    if (root._resumeAfterScrub) Player.toggle()
                }
            }

            Text {
                id: elapsed

                anchors.left: parent.left
                anchors.bottom: parent.bottom
                text: TimeText.format(Player.positionMs)
                color: Theme.onSurfaceVariant
                font.pixelSize: Theme.fontSizeSm
                font.family: Theme.fontFamily
            }

            Text {
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                text: TimeText.format(Player.durationMs)
                color: Theme.onSurfaceVariant
                font.pixelSize: Theme.fontSizeSm
                font.family: Theme.fontFamily
            }
        }

        // MỘT hàng duy nhất: tua/phát/tua rồi tới trộn, lặp, tốc độ, âm lượng.
        // Tách hai hàng làm khối điều khiển cao gấp đôi trong một cửa sổ vốn đã
        // nhỏ, mà chẳng rõ nghĩa hơn.
        Row {
            anchors.horizontalCenter: parent.horizontalCenter
            spacing: Theme.spacingMd

            TransportControls {
                anchors.verticalCenter: parent.verticalCenter
                playing: Player.isPlaying
                interactive: root.hasTrack

                onPlayPauseRequested: Player.toggle()
                onNextRequested: Player.playNext()
                onPreviousRequested: Player.playPrevious()
            }

            // Nhóm phụ nằm trong hộp riêng, nền khác hẳn: ⏮⏯⏭ là "đi tới đi
            // lui trong bài", còn trộn/lặp/tốc độ/âm lượng là "cách phát" —
            // hai loại việc khác nhau thì đừng trông như một dãy.
            Rectangle {
                anchors.verticalCenter: parent.verticalCenter
                width: extras.implicitWidth + Theme.spacingSm * 2
                height: extras.implicitHeight + Theme.spacingXs * 2
                radius: Theme.radiusMd
                color: Theme.alpha(Theme.onSurface, 0.08)
                border.width: 1
                border.color: Theme.alpha(Theme.outline, 0.22)

                Row {
                    id: extras

                    anchors.centerIn: parent
                    spacing: Theme.spacingXs
                    opacity: root.hasTrack ? 1 : root.disabledOpacity

                    IconToggleButton {
                        width: root.buttonSize
                        height: root.buttonSize
                        enabled: root.hasTrack
                        glyph: "shuffle"
                        active: Player.shuffle
                        onClicked: Player.toggleShuffle()
                    }

                    IconToggleButton {
                        width: root.buttonSize
                        height: root.buttonSize
                        enabled: root.hasTrack
                        glyph: "repeat"
                        active: Player.repeatMode !== "off"
                        activeBgAlpha: Player.repeatMode === "one" ? 0.32 : 0.16
                        badge: Player.repeatMode === "one" ? "1" : ""
                        onClicked: Player.cycleRepeat()
                    }

                    PlaybackSpeedButton {
                        anchors.verticalCenter: parent.verticalCenter
                        height: root.buttonSize
                        interactive: root.hasTrack
                        speed: Player.speed
                        onSpeedRequested: (rate) => Player.setSpeed(rate)
                    }

                    VolumeButton {
                        anchors.verticalCenter: parent.verticalCenter
                        height: root.buttonSize
                        interactive: root.hasTrack
                        value: Player.volume
                        onValueRequested: (value) => Player.setVolume(value)
                    }
                }
            }
        }
}
