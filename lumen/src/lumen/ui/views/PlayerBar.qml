import QtQuick
import "../components"
import "../components/TimeText.js" as TimeText

// Hòn đảo phát nhạc (R-1, vòng 2): một viên thuốc nổi giữa đáy vùng nội dung.
// Không còn phóng to (bro bỏ, 2026-10-05). Nút ⚙ ở cuối bật một khung nhỏ nảy
// lên phía trên: tua, tốc độ, âm lượng, trộn bài, lặp. Chuột phải vào đảo:
// Mini Lumen / Thoát Lumen.
//
// Item này phủ CẢ vùng nội dung nhưng chỉ đảo và khung nhận chuột.
Item {
    id: root

    objectName: "playerIsland"
    // Giữ tên `open` cho Main (contentBlurStrength) — đảo không còn mở to nữa.
    readonly property bool open: false
    readonly property bool hasTrack: Player.hasTrack
    property bool tuneOpen: false

    signal miniRequested()

    readonly property int pillWidth: 470
    readonly property int pillHeight: 64
    readonly property int pillMargin: 18
    readonly property int pillCover: 44
    readonly property int playSize: 44
    readonly property int tuneWidth: 400
    readonly property int tuneGap: 10
    readonly property int popMs: 520
    readonly property var speeds: [0.5, 0.75, 1, 1.25, 1.5, 2]
    readonly property int reserve: Theme.islandReserve

    property bool _resumeAfterScrub: false

    function speedText(v) { return String(v).replace(".", ",") + "×" }

    Shortcut {
        sequence: "Escape"
        enabled: root.tuneOpen
        onActivated: root.tuneOpen = false
    }

    // Bấm ra ngoài khung là đóng khung.
    MouseArea {
        anchors.fill: parent
        enabled: root.tuneOpen
        onClicked: root.tuneOpen = false
    }

    // ---------------- khung tuỳ chỉnh ----------------
    Rectangle {
        id: tune

        width: Math.min(root.tuneWidth, root.width - Theme.spacingLg * 2)
        height: tuneColumn.implicitHeight + Theme.spacingLg * 2
        x: (root.width - width) / 2
        y: island.y - height - root.tuneGap
        radius: Theme.radiusLg + 2
        color: Theme.alpha(Theme.surface, Math.min(0.94, Theme.surfaceAlpha + 0.14))
        border.width: 1
        border.color: Theme.alpha(Theme.onSurface, 0.08)
        transformOrigin: Item.Bottom
        scale: root.tuneOpen ? 1 : 0.6
        opacity: root.tuneOpen ? 1 : 0
        visible: opacity > 0.01
        Behavior on scale { NumberAnimation { duration: Math.max(1, root.popMs * Theme.motionScale); easing.type: Easing.OutBack; easing.overshoot: Theme.overshoot * 1.3 } }
        Behavior on opacity { NumberAnimation { duration: Math.max(1, 180 * Theme.motionScale); easing.type: Easing.OutCubic } }

        MouseArea { anchors.fill: parent }   // nuốt cú bấm, đừng để lọt xuống "bấm ra ngoài"

        Column {
            id: tuneColumn

            x: Theme.spacingLg
            y: Theme.spacingLg
            width: parent.width - Theme.spacingLg * 2
            spacing: Theme.spacingLg

            Column {
                width: parent.width
                spacing: Theme.spacingXs
                TuneLabel { title: "TUA"; value: TimeText.format(Player.positionMs) + " / " + TimeText.format(Player.durationMs) }
                SeekBar {
                    width: parent.width
                    interactive: root.hasTrack
                    position: Player.positionMs
                    duration: Player.durationMs
                    onScrubStarted: {
                        root._resumeAfterScrub = Player.isPlaying
                        if (Player.isPlaying) Player.toggle()
                    }
                    onScrubFinished: (position) => {
                        Player.seek(position)
                        if (root._resumeAfterScrub) Player.toggle()
                    }
                }
            }

            Column {
                width: parent.width
                spacing: Theme.spacingSm
                TuneLabel { title: "TỐC ĐỘ"; value: root.speedText(Player.speed) }
                Flow {
                    width: parent.width
                    spacing: Theme.spacingXs + 2
                    Repeater {
                        model: root.speeds
                        Rectangle {
                            id: chip
                            required property real modelData
                            readonly property bool on: Math.abs(Player.speed - chip.modelData) < 0.01
                            width: Math.max(52, chipText.implicitWidth + Theme.spacingLg)
                            height: 32
                            radius: height / 2
                            color: chip.on ? Theme.primary : "transparent"
                            border.width: chip.on ? 0 : 1
                            border.color: Theme.alpha(Theme.onSurface, 0.12)
                            scale: chipArea.pressed ? 0.88 : 1
                            Behavior on scale { NumberAnimation { duration: Math.max(1, 90 * Theme.motionScale) } }
                            Text {
                                id: chipText
                                anchors.centerIn: parent
                                text: root.speedText(chip.modelData)
                                color: chip.on ? Theme.onPrimary : Theme.onSurfaceVariant
                                font.pixelSize: Theme.fontSizeSm + 1
                                font.weight: chip.on ? Font.DemiBold : Font.Normal
                                font.family: Theme.fontFamily
                            }
                            MouseArea {
                                id: chipArea
                                anchors.fill: parent
                                cursorShape: Qt.PointingHandCursor
                                onClicked: Player.setSpeed(chip.modelData)
                            }
                        }
                    }
                }
            }

            Column {
                width: parent.width
                spacing: Theme.spacingXs
                TuneLabel { title: "ÂM LƯỢNG"; value: Math.round(Player.volume * 100) + "%" }
                Item {
                    width: parent.width
                    height: Theme.iconSize + 4
                    MIcon {
                        id: volIcon
                        anchors.verticalCenter: parent.verticalCenter
                        name: Player.volume <= 0.001 ? "volume_off" : "volume_up"
                    }
                    RangeSlider {
                        anchors.left: volIcon.right
                        anchors.leftMargin: Theme.spacingSm
                        anchors.right: parent.right
                        anchors.verticalCenter: parent.verticalCenter
                        value: Player.volume
                        onValueRequested: (v) => Player.setVolume(v)
                    }
                }
            }

            Row {
                width: parent.width
                spacing: Theme.spacingSm
                TuneToggle {
                    width: (parent.width - Theme.spacingSm) / 2
                    icon: "shuffle"
                    label: "Trộn bài"
                    on: Player.shuffle
                    onClicked: Player.toggleShuffle()
                }
                TuneToggle {
                    width: (parent.width - Theme.spacingSm) / 2
                    icon: Player.repeatMode === "one" ? "repeat_one" : "repeat"
                    label: Player.repeatMode === "one" ? "Lặp bài này" : (Player.repeatMode === "all" ? "Lặp track" : "Không lặp")
                    on: Player.repeatMode !== "off"
                    onClicked: Player.cycleRepeat()
                }
            }
        }
    }

    // ---------------- viên thuốc ----------------
    Rectangle {
        id: island

        width: Math.min(root.pillWidth, root.width - Theme.spacingLg * 2)
        height: root.pillHeight
        x: (root.width - width) / 2
        y: root.height - height - root.pillMargin
        radius: height / 2
        clip: true
        color: Theme.alpha(Theme.surface, Theme.surfaceAlpha)
        border.width: 1
        border.color: Theme.alpha(Theme.onSurface, 0.08)

        MouseArea {
            anchors.fill: parent
            acceptedButtons: Qt.RightButton
            onClicked: (mouse) => {
                const at = island.mapToItem(null, mouse.x, mouse.y)
                islandMenu.popupAt(island, at.x, at.y)
            }
        }

        RoundedImage {
            id: cover
            anchors.left: parent.left
            anchors.leftMargin: (root.pillHeight - root.pillCover) / 2
            anchors.verticalCenter: parent.verticalCenter
            width: root.pillCover
            height: root.pillCover
            radius: Theme.radiusMd
            source: Player.coverPath === "" ? ""
                : (Player.coverPath.startsWith("http") ? Player.coverPath : "file://" + Player.coverPath)
            MIcon {
                anchors.centerIn: parent
                visible: Player.coverPath === ""
                name: "music_note"
            }
        }

        Column {
            anchors.left: cover.right
            anchors.leftMargin: Theme.spacingMd
            anchors.right: buttons.left
            anchors.rightMargin: Theme.spacingSm
            anchors.verticalCenter: parent.verticalCenter
            spacing: 1
            Text {
                width: parent.width
                text: root.hasTrack ? Player.title : "Chưa phát bài nào"
                color: Theme.onSurface
                font.pixelSize: Theme.fontSizeMd
                font.weight: Font.DemiBold
                font.family: Theme.fontFamily
                elide: Text.ElideRight
            }
            Text {
                width: parent.width
                visible: root.hasTrack
                text: Player.artist !== "" ? Player.artist : "Bài nhập từ ổ cứng"
                color: Theme.onSurfaceVariant
                font.pixelSize: Theme.fontSizeSm
                font.family: Theme.fontFamily
                elide: Text.ElideRight
            }
        }

        Row {
            id: buttons
            anchors.right: parent.right
            anchors.rightMargin: (root.pillHeight - root.playSize) / 2
            anchors.verticalCenter: parent.verticalCenter
            spacing: Theme.spacingXs

            IslandButton { icon: "skip_previous"; enabled: root.hasTrack; anchors.verticalCenter: parent.verticalCenter; onClicked: Player.playPrevious() }
            PlayButton { size: root.playSize; anchors.verticalCenter: parent.verticalCenter }
            IslandButton { icon: "skip_next"; enabled: root.hasTrack; anchors.verticalCenter: parent.verticalCenter; onClicked: Player.playNext() }
            Rectangle {
                width: 1
                height: 26
                anchors.verticalCenter: parent.verticalCenter
                color: Theme.alpha(Theme.onSurface, 0.1)
            }
            IslandButton {
                icon: "tune"
                active: root.tuneOpen
                anchors.verticalCenter: parent.verticalCenter
                onClicked: root.tuneOpen = !root.tuneOpen
            }
        }

        Rectangle {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            anchors.leftMargin: root.pillHeight / 2
            anchors.rightMargin: root.pillHeight / 2
            height: 2
            radius: 1
            color: Theme.alpha(Theme.onSurface, 0.08)
            Rectangle {
                height: parent.height
                radius: 1
                color: Theme.primary
                width: Player.durationMs > 0 ? parent.width * Math.min(1, Player.positionMs / Player.durationMs) : 0
            }
        }
    }

    ContextMenu {
        id: islandMenu
        items: [
            { "label": "Mini Lumen", "icon": "picture_in_picture_alt" },
            { "label": "Thoát Lumen", "icon": "power_settings_new", "danger": true }
        ]
        onChosen: (index) => index === 0 ? root.miniRequested() : App.quit()
    }

    component TuneLabel: Item {
        id: tl
        property string title: ""
        property string value: ""
        width: parent ? parent.width : 0
        height: tlTitle.implicitHeight
        Text {
            id: tlTitle
            text: tl.title
            color: Theme.onSurfaceVariant
            font.pixelSize: Theme.fontSizeSm
            font.letterSpacing: 1
            font.family: Theme.fontFamily
        }
        Text {
            anchors.right: parent.right
            text: tl.value
            color: Theme.onSurface
            font.pixelSize: Theme.fontSizeMd
            font.weight: Font.DemiBold
            font.family: Theme.fontFamily
            font.features: { "tnum": 1 }
        }
    }

    component TuneToggle: Rectangle {
        id: tt
        property string icon: ""
        property string label: ""
        property bool on: false
        signal clicked()
        height: 46
        radius: Theme.radiusMd + 2
        color: tt.on ? Theme.alpha(Theme.primary, 0.16) : Theme.alpha(Theme.onSurface, 0.045)
        border.width: 1
        border.color: tt.on ? Theme.alpha(Theme.primary, 0.3) : Theme.alpha(Theme.onSurface, 0.075)
        scale: ttArea.pressed ? 0.94 : 1
        Behavior on scale { NumberAnimation { duration: Math.max(1, 90 * Theme.motionScale) } }
        Row {
            anchors.left: parent.left
            anchors.leftMargin: Theme.spacingMd
            anchors.verticalCenter: parent.verticalCenter
            spacing: Theme.spacingSm
            MIcon { name: tt.icon; color: tt.on ? Theme.primary : Theme.onSurfaceVariant; anchors.verticalCenter: parent.verticalCenter }
            Text {
                text: tt.label
                color: tt.on ? Theme.primary : Theme.onSurfaceVariant
                font.pixelSize: Theme.fontSizeMd
                font.weight: Font.Medium
                font.family: Theme.fontFamily
                anchors.verticalCenter: parent.verticalCenter
            }
        }
        MouseArea { id: ttArea; anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: tt.clicked() }
    }

    // Nút tròn chỉ có icon; bấm thì lún xuống 0.86.
    component IslandButton: Item {
        id: btn
        property string icon: ""
        property bool active: false
        signal clicked()
        width: 36
        height: 36
        opacity: btn.enabled ? 1 : 0.4
        scale: btnArea.pressed ? 0.86 : 1
        Behavior on scale { NumberAnimation { duration: Math.max(1, 90 * Theme.motionScale); easing.type: Easing.OutCubic } }
        Rectangle {
            anchors.fill: parent
            radius: width / 2
            color: btn.active ? Theme.alpha(Theme.primary, 0.16)
                : (btnArea.containsMouse ? Theme.alpha(Theme.onSurface, 0.08) : "transparent")
        }
        MIcon {
            anchors.centerIn: parent
            name: btn.icon
            size: 22
            color: btn.active ? Theme.primary : (btnArea.containsMouse ? Theme.onSurface : Theme.onSurfaceVariant)
        }
        MouseArea {
            id: btnArea
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: btn.clicked()
        }
    }

    component PlayButton: Item {
        id: play
        property int size: 44
        width: play.size
        height: play.size
        opacity: root.hasTrack ? 1 : 0.4
        scale: playArea.pressed ? 0.86 : 1
        Behavior on scale { NumberAnimation { duration: Math.max(1, 90 * Theme.motionScale); easing.type: Easing.OutCubic } }
        Rectangle { anchors.fill: parent; radius: width / 2; color: Theme.primary }
        MIcon {
            anchors.centerIn: parent
            name: Player.isPlaying ? "pause" : "play_arrow"
            size: play.size * 0.58
            color: Theme.onPrimary
        }
        MouseArea {
            id: playArea
            anchors.fill: parent
            enabled: root.hasTrack
            cursorShape: Qt.PointingHandCursor
            onClicked: Player.toggle()
        }
    }
}
