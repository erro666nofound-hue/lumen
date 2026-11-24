import QtQuick
import QtQuick.Window
import "components"

// Mini Lumen — design vòng 2 R-1: một ĐĨA THAN quay bên trong vòng sóng nhạc,
// cạnh đó là tên bài và nút điều khiển. Vòng 3: hàng trên là dải MỌI track
// (track gắn phím tắt mang chữ phím), nút tốc độ đổi hàng đó thành các nấc
// tốc độ. Cửa sổ riêng, Hyprland quản kích thước.
Window {
    id: root

    title: "Mini Lumen"
    transientParent: null
    width: 460
    height: 230
    minimumWidth: 420
    minimumHeight: 220
    color: "transparent"

    signal hidden()
    signal openFullRequested()

    readonly property int designWidth: 460
    readonly property int designHeight: 230
    readonly property real maxScale: 1.8
    readonly property int discSize: 168
    readonly property int vinylSize: 116
    readonly property int labelSize: 54
    readonly property int ringGap: 6
    readonly property int bars: 48
    readonly property var nextUp: Player.trackId >= 0 ? Player.upNext(1) : []
    readonly property int chipMaxWidth: 170
    readonly property var speeds: [0.5, 0.75, 1, 1.25, 1.5, 2]
    // Bấm nút tốc độ thì hàng trên đổi từ dải track sang các nấc tốc độ.
    property bool speedOpen: false

    function speedText(v) { return String(v).replace(".", ",") + "×" }
    // Ô phím tắt (t1/t2/t3) đang gắn với track này, "" nếu không có.
    function slotOf(playlistId) {
        for (const key of ["t1", "t2", "t3"]) {
            if (HotKeys.slots[key] === playlistId)
                return key
        }
        return ""
    }

    Shortcut {
        sequence: "Escape"
        onActivated: root.speedOpen ? root.speedOpen = false : root.close()
    }
    Shortcut {
        sequence: "Space"
        onActivated: {
            if (Player.hasTrack) {
                Player.toggle()
                return
            }
            // Chưa nạp bài nào: chạy track đầu tiên trên thanh bên, như bấm vào nó.
            const first = Playlists.firstPlayable()
            if (first < 0)
                return
            Player.setRepeat("all")
            Player.playPlaylist(first, Playlists.orderedIds(first), -1)
        }
    }

    // Đóng = ẩn, không thoát: Mini là một cách nhìn của app, không phải app.
    onClosing: (event) => {
        event.accepted = false
        root.hide()
        root.hidden()
    }

    FadingWallpaper {
        anchors.fill: parent
        radius: Theme.radiusLg
        source: Theme.wallpaperIsImage ? "file://" + Theme.wallpaper : ""
    }

    Rectangle {
        id: panel

        anchors.fill: parent
        radius: Theme.radiusLg + 6
        color: Theme.alpha(Theme.surface, Theme.wallpaper !== "" ? Theme.wallpaperSurfaceAlpha : Theme.surfaceAlpha)
        border.width: 1
        border.color: Theme.alpha(Theme.onSurface, 0.1)

        // Cả cụm có kích thước "thiết kế" 460×230, căn giữa và co giãn theo cửa
        // sổ: Hyprland có thể cấp cho Mini bất cứ khung nào (lát gạch hay nổi).
        Item {
            id: stage

            width: root.designWidth
            height: root.designHeight
            anchors.centerIn: parent
            scale: Math.min(root.maxScale, panel.width / root.designWidth, panel.height / root.designHeight)

            // ---- hàng trên: MỌI track (cuộn ngang) — hoặc các nấc tốc độ ----
            // Track gắn ô phím tắt đứng cùng hàng, mang chữ phím ở đuôi.
            Item {
                id: quick

                x: Theme.spacingLg
                y: Theme.spacingLg
                width: parent.width - Theme.spacingLg * 2
                height: 34

                ListView {
                    id: trackStrip
                    objectName: "miniTrackStrip"

                    anchors.fill: parent
                    orientation: ListView.Horizontal
                    spacing: Theme.spacingSm
                    clip: true
                    boundsBehavior: Flickable.StopAtBounds
                    // Cuộn do WheelHandler bên dưới lo. Để Flickable tự xử lý
                    // thì nó nuốt cú lăn dọc mà không nhúc nhích dải ngang.
                    interactive: false
                    model: Playlists
                    opacity: root.speedOpen ? 0 : 1
                    visible: opacity > 0
                    Behavior on opacity { NumberAnimation { duration: Math.max(1, 120 * Theme.motionScale) } }

                    delegate: Rectangle {
                        id: chip

                        required property int playlistId
                        required property string name
                        required property int trackCount
                        readonly property string slotKey: root.slotOf(chip.playlistId)
                        readonly property string combo: chip.slotKey !== "" ? (HotKeys.binds[chip.slotKey] || "") : ""
                        readonly property bool on: Player.scopePlaylistId === chip.playlistId

                        width: Math.min(root.chipMaxWidth, chipRow.implicitWidth + Theme.spacingMd * 2)
                        height: quick.height
                        radius: Theme.radiusMd
                        opacity: chip.trackCount > 0 ? 1 : 0.45
                        color: chip.on ? Theme.alpha(Theme.primary, 0.18) : Theme.alpha(Theme.onSurface, chipArea.containsMouse ? 0.1 : 0.06)
                        scale: chipArea.pressed ? 0.92 : 1
                        Behavior on scale { NumberAnimation { duration: Math.max(1, 90 * Theme.motionScale) } }

                        Row {
                            id: chipRow

                            x: Theme.spacingMd
                            anchors.verticalCenter: parent.verticalCenter
                            spacing: Theme.spacingXs
                            MIcon {
                                visible: chip.on && Player.isPlaying
                                anchors.verticalCenter: parent.verticalCenter
                                name: "graphic_eq"
                                size: 16
                                color: Theme.primary
                            }
                            Text {
                                width: Math.min(implicitWidth, root.chipMaxWidth - Theme.spacingMd * 2 - keyHint.implicitWidth - Theme.spacingLg * 2)
                                anchors.verticalCenter: parent.verticalCenter
                                text: chip.name
                                color: chip.on ? Theme.primary : Theme.onSurface
                                font.pixelSize: Theme.fontSizeSm + 1
                                font.weight: Font.DemiBold
                                font.family: Theme.fontFamily
                                elide: Text.ElideRight
                            }
                            Text {
                                id: keyHint
                                visible: chip.combo !== ""
                                anchors.verticalCenter: parent.verticalCenter
                                text: chip.combo !== "" ? chip.combo.split(" + ").pop() : ""
                                color: Theme.onSurfaceVariant
                                font.pixelSize: Theme.fontSizeSm - 1
                                font.family: Theme.fontFamily
                            }
                        }
                        MouseArea {
                            id: chipArea
                            anchors.fill: parent
                            hoverEnabled: true
                            enabled: chip.trackCount > 0
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                if (chip.on) {
                                    Player.toggle()
                                    return
                                }
                                Player.setRepeat("all")
                                Player.playPlaylist(chip.playlistId, Playlists.orderedIds(chip.playlistId), -1)
                            }
                        }
                    }
                }

                // Rê chuột vào dải rồi lăn (dọc hay ngang) hoặc vuốt touchpad
                // trái/phải để xem hết các track bị cắt.
                WheelHandler {
                    target: null
                    enabled: !root.speedOpen
                    acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
                    onWheel: (event) => {
                        const room = trackStrip.contentWidth - trackStrip.width
                        if (room <= 0)
                            return
                        // Touchpad gửi pixelDelta: bám theo ngón tay, không trượt.
                        const pixels = event.pixelDelta.x !== 0 || event.pixelDelta.y !== 0
                        const dx = pixels
                            ? (event.pixelDelta.x !== 0 ? event.pixelDelta.x : event.pixelDelta.y)
                            : (event.angleDelta.x !== 0 ? event.angleDelta.x : event.angleDelta.y)
                        const from = stripSlide.running ? stripSlide.to : trackStrip.contentX
                        const to = Math.max(0, Math.min(room, from - dx))
                        stripSlide.stop()
                        if (pixels) {
                            trackStrip.contentX = to
                        } else {
                            stripSlide.to = to
                            stripSlide.start()
                        }
                    }
                }
                NumberAnimation {
                    id: stripSlide
                    target: trackStrip
                    property: "contentX"
                    duration: Math.max(1, 160 * Theme.motionScale)
                    easing.type: Easing.OutCubic
                }

                Row {
                    id: speedRow

                    spacing: Theme.spacingSm
                    opacity: root.speedOpen ? 1 : 0
                    visible: opacity > 0
                    Behavior on opacity { NumberAnimation { duration: Math.max(1, 120 * Theme.motionScale) } }

                    Repeater {
                        model: root.speeds

                        Rectangle {
                            id: speedChip

                            required property real modelData
                            readonly property bool on: Math.abs(Player.speed - speedChip.modelData) < 0.01

                            width: (quick.width - Theme.spacingSm * (root.speeds.length - 1)) / root.speeds.length
                            height: quick.height
                            radius: Theme.radiusMd
                            color: speedChip.on ? Theme.primary : Theme.alpha(Theme.onSurface, speedArea.containsMouse ? 0.1 : 0.06)
                            scale: speedArea.pressed ? 0.92 : 1
                            Behavior on scale { NumberAnimation { duration: Math.max(1, 90 * Theme.motionScale) } }

                            Text {
                                anchors.centerIn: parent
                                text: root.speedText(speedChip.modelData)
                                color: speedChip.on ? Theme.onPrimary : Theme.onSurface
                                font.pixelSize: Theme.fontSizeSm + 1
                                font.weight: Font.DemiBold
                                font.family: Theme.fontFamily
                            }
                            MouseArea {
                                id: speedArea
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    Player.setSpeed(speedChip.modelData)
                                    root.speedOpen = false
                                }
                            }
                        }
                    }
                }
            }

            // ---- đĩa than trong vòng sóng ----
            Item {
                id: disc

                x: Theme.spacingSm
                anchors.bottom: parent.bottom
                anchors.bottomMargin: -Theme.spacingSm
                width: root.discSize
                height: root.discSize

                Canvas {
                    id: ring

                    property var levels: []
                    property real phase: 0

                    anchors.fill: parent

                    Timer {
                        interval: 33
                        repeat: true
                        running: root.visible
                        onTriggered: {
                            const dt = 0.033
                            ring.phase += dt
                            const next = []
                            for (let i = 0; i < root.bars; i++) {
                                const t = Player.isPlaying
                                    ? 0.15 + 0.85 * Math.pow(Math.abs(Math.sin(ring.phase * (2 + (i % 5) * 0.4) + i * 1.3) * Math.sin(ring.phase * 1.2 + i * 0.5)), 1.3)
                                    : 0
                                const now = ring.levels.length === root.bars ? ring.levels[i] : 0
                                next.push(now + (t - now) * Math.min(1, dt * (Player.isPlaying ? 12 : 5)))
                            }
                            ring.levels = next
                            ring.requestPaint()
                        }
                    }

                    onPaint: {
                        const ctx = getContext("2d")
                        ctx.reset()
                        if (ring.levels.length !== root.bars)
                            return
                        const cx = width / 2, cy = height / 2, base = root.vinylSize / 2 + root.ringGap
                        ctx.lineCap = "round"
                        ctx.lineWidth = 3.5
                        ctx.strokeStyle = Theme.primary
                        for (let i = 0; i < root.bars; i++) {
                            const a = i / root.bars * Math.PI * 2 - Math.PI / 2
                            const len = 3 + ring.levels[i] * 16
                            ctx.globalAlpha = 0.45 + 0.55 * ring.levels[i]
                            ctx.beginPath()
                            ctx.moveTo(cx + Math.cos(a) * base, cy + Math.sin(a) * base)
                            ctx.lineTo(cx + Math.cos(a) * (base + len), cy + Math.sin(a) * (base + len))
                            ctx.stroke()
                        }
                    }
                }

                // Đĩa: nền đen + rãnh đồng tâm + nhãn là ảnh bìa; quay khi đang phát.
                Rectangle {
                    id: vinyl

                    anchors.centerIn: parent
                    width: root.vinylSize
                    height: root.vinylSize
                    radius: width / 2
                    color: Theme.alpha(Theme.shadow, 0.92)

                    Repeater {
                        model: 7
                        Rectangle {
                            required property int index
                            anchors.centerIn: parent
                            width: root.labelSize + 8 + index * ((root.vinylSize - root.labelSize - 10) / 7)
                            height: width
                            radius: width / 2
                            color: "transparent"
                            border.width: 1
                            border.color: Theme.alpha(Theme.onSurface, 0.06)
                        }
                    }

                    RoundedImage {
                        anchors.centerIn: parent
                        width: root.labelSize
                        height: root.labelSize
                        radius: root.labelSize / 2
                        source: Player.coverPath === "" ? ""
                            : (Player.coverPath.startsWith("http") ? Player.coverPath : "file://" + Player.coverPath)
                        MIcon {
                            anchors.centerIn: parent
                            visible: Player.coverPath === ""
                            name: "music_note"
                        }
                    }

                    RotationAnimation on rotation {
                        running: Player.isPlaying && root.visible
                        loops: Animation.Infinite
                        from: vinyl.rotation
                        to: vinyl.rotation + 360
                        duration: 6000
                    }
                }
            }

            // ---- tên bài + điều khiển ----
            Column {
                anchors.left: disc.right
                anchors.leftMargin: Theme.spacingSm
                anchors.right: parent.right
                anchors.rightMargin: Theme.spacingLg
                anchors.bottom: parent.bottom
                anchors.bottomMargin: Theme.spacingLg
                spacing: Theme.spacingXs

                Text {
                    width: parent.width
                    visible: root.nextUp.length > 0
                    text: root.nextUp.length > 0 ? "Tiếp theo · " + root.nextUp[0].title : ""
                    color: Theme.onSurfaceVariant
                    font.pixelSize: Theme.fontSizeSm
                    font.family: Theme.fontFamily
                    elide: Text.ElideRight
                }
                Text {
                    width: parent.width
                    text: Player.hasTrack ? Player.title : "Chưa phát bài nào"
                    color: Theme.onSurface
                    font.pixelSize: Theme.fontSizeLg
                    font.weight: Font.Bold
                    font.family: Theme.fontFamily
                    elide: Text.ElideRight
                }
                Text {
                    width: parent.width
                    visible: Player.hasTrack
                    text: Player.artist !== "" ? Player.artist : "Bài nhập từ ổ cứng"
                    color: Theme.onSurfaceVariant
                    font.pixelSize: Theme.fontSizeSm + 1
                    font.family: Theme.fontFamily
                    elide: Text.ElideRight
                }
                Item { width: 1; height: Theme.spacingXs }
                Row {
                    spacing: Theme.spacingXs
                    MiniButton { icon: "skip_previous"; onClicked: Player.playPrevious() }
                    Rectangle {
                        width: 44
                        height: 44
                        radius: 22
                        color: Theme.primary
                        scale: playArea.pressed ? 0.86 : 1
                        Behavior on scale { NumberAnimation { duration: Math.max(1, 90 * Theme.motionScale) } }
                        MIcon { anchors.centerIn: parent; name: Player.isPlaying ? "pause" : "play_arrow"; size: 26; color: Theme.onPrimary }
                        MouseArea { id: playArea; anchors.fill: parent; enabled: Player.hasTrack; cursorShape: Qt.PointingHandCursor; onClicked: Player.toggle() }
                    }
                    MiniButton { icon: "skip_next"; onClicked: Player.playNext() }
                    Rectangle {
                        id: speedPill
                        width: 52
                        height: 30
                        anchors.verticalCenter: parent.verticalCenter
                        radius: height / 2
                        color: root.speedOpen ? Theme.alpha(Theme.primary, 0.18)
                            : Theme.alpha(Theme.onSurface, speedPillArea.containsMouse ? 0.1 : 0.06)
                        scale: speedPillArea.pressed ? 0.86 : 1
                        Behavior on scale { NumberAnimation { duration: Math.max(1, 90 * Theme.motionScale) } }
                        Text {
                            anchors.centerIn: parent
                            text: root.speedText(Player.speed)
                            color: root.speedOpen || Math.abs(Player.speed - 1) > 0.01 ? Theme.primary : Theme.onSurface
                            font.pixelSize: Theme.fontSizeSm + 1
                            font.weight: Font.DemiBold
                            font.family: Theme.fontFamily
                        }
                        MouseArea {
                            id: speedPillArea
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.speedOpen = !root.speedOpen
                        }
                    }
                    MiniButton { icon: "open_in_full"; onClicked: root.openFullRequested() }
                    MiniButton { icon: "close"; onClicked: root.close() }
                }
            }
        }

        ToastOverlay {
            id: toasts
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.topMargin: Theme.spacingSm
            height: Theme.rowHeight * 2
        }

        Connections {
            target: Player
            function onErrorOccurred(message) { toasts.showError(message) }
        }
        // MiniSongs vẫn sống (app.py nối nó) dù Mini mới không còn danh sách bài:
        // lỗi của nó vẫn phải có người nghe.
        Connections {
            target: MiniSongs
            function onErrorOccurred(message) { toasts.showError(message) }
        }
    }

    component MiniButton: Item {
        id: mb
        property string icon: ""
        signal clicked()
        width: 36
        height: 36
        anchors.verticalCenter: parent ? parent.verticalCenter : undefined
        scale: mbArea.pressed ? 0.86 : 1
        Behavior on scale { NumberAnimation { duration: Math.max(1, 90 * Theme.motionScale) } }
        Rectangle { anchors.fill: parent; radius: width / 2; color: mbArea.containsMouse ? Theme.alpha(Theme.onSurface, 0.08) : "transparent" }
        MIcon { anchors.centerIn: parent; name: mb.icon; size: 21; color: mbArea.containsMouse ? Theme.onSurface : Theme.onSurfaceVariant }
        MouseArea { id: mbArea; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: mb.clicked() }
    }
}
