import QtQuick
import QtQuick.Effects
import QtQuick.Dialogs as QtDialogs

import "../components"

// Màn hình track: ô tìm trong các bài đã có của track + tên track + danh sách
// bài hát (TrackSongList — mỗi bài một hàng, không phải lưới thẻ như Thư viện).
//
// Khác LibraryView ở chỗ ô tìm KHÔNG tải nhạc (không có nhánh looksLikeUrl) —
// track chỉ chứa bài đã tải sẵn, tìm ở đây chỉ lọc trong TrackSongs. Bên phải
// danh sách là TrackTools (tải mp3 + chọn/xoá nhiều bài), lắp ở T4.3.
Item {
    id: root

    // Cùng một nguồn bề ngang cột nội dung như LibraryView — xem chú thích ở đó.
    readonly property int contentWidth: Math.min(width - Theme.spacingLg * 2, Theme.contentMaxWidth)

    // Chỗ phải chừa ở mép phải hàng trên cùng cho mục tài khoản — Main.qml đặt
    // nó ở góc trên-phải, và nếu không chừa thì nó nằm đè lên chỗ này.
    property int rightReserve: 0
    readonly property int gutter: (width - contentWidth) / 2
    readonly property int topRowWidth: Math.max(160, contentWidth - rightReserve)

    readonly property int toolbarHeight: 44
    readonly property int toolHeight: 34
    readonly property int findOpenWidth: 220
    readonly property var sortKeys: [["custom", "Thứ tự của bạn"], ["title", "Tên"], ["artist", "Nghệ sĩ"],
                                     ["duration", "Thời lượng"], ["added", "Mới thêm"]]
    function sortLabel(key) {
        const hit = root.sortKeys.find(k => k[0] === key)
        return hit ? hit[1] : "Sắp xếp"
    }
    function openAdd(anchor) {
        const at = anchor.mapToItem(root, 0, anchor.height)
        addPop.x = Math.max(Theme.spacingMd, Math.min(at.x, root.width - addPop.width - Theme.spacingMd))
        addPop.y = at.y + Theme.spacingSm
        addPop.open = true
        addInput.text = ""
        TrackSearch.clear()
        addInput.forceActiveFocus()
    }
    // Kết quả tìm được xoá khi hộp đã khuất hẳn (onVisibleChanged), không xoá ở
    // đây — xoá ngay thì hộp co lại giữa lúc đang mờ đi.
    function closeAdd() { addPop.open = false }
    // Ô "Thêm bài": link thì tải luôn vào track này, chữ thường thì tìm (kết quả hiện ngay dưới ô).
    function submitAdd(text) {
        if (text === "")
            return
        if (Downloads.looksLikeUrl(text)) {
            Downloads.addToPlaylist(text, TrackSongs.playlistId)
            root.closeAdd()
        } else {
            TrackSearch.run(text)
        }
    }
    readonly property int blurMs: 180

    // Hộp xác nhận xoá làm MỜ cả trang thay vì phủ một lớp đen. Vùng mờ chính
    // là toàn bộ TrackView — tức mọi thứ TRỪ thanh bên trái và thanh phát,
    // đúng yêu cầu của chủ dự án.
    // Mờ nền cho MỌI lớp tương tác nổi lên, không riêng hộp xoá — mở ô tải
    // nhạc mà nền vẫn nét thì hai chỗ hành xử khác nhau vô cớ.
    property real blurStrength: (confirmSheet.open || trackTools.downloadOpen) ? 1.0 : 0.0

    Behavior on blurStrength {
        NumberAnimation { duration: root.blurMs; easing.type: Easing.OutCubic }
    }

    // Main.qml không thể gọi thẳng Downloads.noticeOccurred (đó là signal của
    // một QObject Python, QML không gọi signal như hàm) -- bắn tín hiệu riêng
    // này ra ngoài, Main.qml nối vào toasts.showInfo.
    signal noticeRequested(string message)

    // Từ nút ⋯ (R-1) — Main mở hộp đổi tên / xác nhận xoá track như menu thanh bên.
    signal renameTrackRequested()
    signal deleteTrackRequested()

    // Dán link thì tải luôn; gõ tên bài thì tìm trên YouTube.
    function startDownload(text) {
        if (Downloads.looksLikeUrl(text)) {
            // addToPlaylist chứ không phải add: bài phải rơi vào ĐÚNG track đang
            // mở, vào thư mục riêng của nó. Chính tầng Python lo việc thêm vào
            // track, QML không tự thêm nữa (trước đây làm ở onTrackAdded và bị
            // trùng lặp với tầng dưới).
            Downloads.addToPlaylist(text, TrackSongs.playlistId)
        } else {
            // Không phải link -> tìm trên YouTube. Kết quả hiện ngay trong
            // popup của công cụ tải; bấm một kết quả sẽ quay lại nhánh URL ở trên.
            Search.run(text)
        }
    }

    // Cả trang nằm trong một item riêng để làm mờ được một lượt. Bật layer chỉ
    // khi thật sự cần: layer luôn bật tốn GPU vô ích. Ngưỡng nhỏ thay vì so 0
    // để tránh bật/tắt nhấp nháy trong lúc animation chạy.
    Item {
        id: page

        anchors.fill: parent

        layer.enabled: root.blurStrength > 0.01
        layer.effect: MultiEffect {
            blurEnabled: true
            blur: root.blurStrength
            blurMax: 40
            autoPaddingEnabled: false
        }

        // Đầu trang track theo design R-1: bìa ghép to, chữ TRACK nhỏ, tên lớn,
        // số bài + tổng thời lượng, nút Phát và Trộn bài.
        Item {
            id: trackTitle

            readonly property var info: TrackSongs.count >= 0 && TrackSongs.playlistId >= 0
                ? TrackSongs.summary() : ({ "covers": [], "totalMs": 0, "count": 0 })
            readonly property int coverSize: root.width < 640 ? 104 : 140
            readonly property bool playingHere: Player.scopePlaylistId === TrackSongs.playlistId

            function minutes(ms) {
                const m = Math.round(ms / 60000)
                return m >= 60 ? Math.floor(m / 60) + " giờ " + (m % 60) + " phút" : m + " phút"
            }

            anchors.top: parent.top
            anchors.topMargin: Theme.spacingXl
            anchors.left: parent.left
            anchors.leftMargin: root.gutter
            width: root.contentWidth
            height: trackTitle.coverSize

            Mosaic {
                id: headerCover
                width: trackTitle.coverSize
                height: trackTitle.coverSize
                radius: Theme.radiusLg
                covers: trackTitle.info.covers
            }

            Column {
                anchors.left: headerCover.right
                anchors.leftMargin: Theme.spacingXl
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                spacing: Theme.spacingXs

                Text {
                    text: "TRACK"
                    color: Theme.onSurfaceVariant
                    font.pixelSize: Theme.fontSizeSm
                    font.letterSpacing: 1.4
                    font.family: Theme.fontFamily
                }
                Text {
                    width: parent.width
                    text: TrackSongs.playlistName
                    color: Theme.onSurface
                    font.pixelSize: root.width < 640 ? 30 : 40
                    font.weight: Font.Bold
                    font.family: Theme.fontFamily
                    elide: Text.ElideRight
                }
                Text {
                    text: trackTitle.info.count + " bài · " + trackTitle.minutes(trackTitle.info.totalMs)
                    color: Theme.onSurfaceVariant
                    font.pixelSize: Theme.fontSizeMd
                    font.family: Theme.fontFamily
                }
            }
        }

        // Thanh công cụ của track — design vòng 2 R-1: [Phát][Trộn] … ô tìm (bấm
        // mới mở rộng) · sắp xếp · cụm [Thêm bài][Sửa][Chọn][⟳][⋯]. Không còn cột
        // công cụ dọc bên trái; Sửa / Chọn hiện một thanh nổi ở đáy.
        Item {
            id: toolbar

            anchors.top: trackTitle.bottom
            anchors.topMargin: Theme.spacingLg
            anchors.left: parent.left
            anchors.leftMargin: root.gutter
            width: root.contentWidth
            height: root.toolbarHeight

            Row {
                anchors.left: parent.left
                anchors.verticalCenter: parent.verticalCenter
                spacing: Theme.spacingSm

                PillButton {
                    filled: true
                    icon: trackTitle.playingHere && Player.isPlaying ? "pause" : "play_arrow"
                    label: trackTitle.playingHere && Player.isPlaying ? "Đang phát" : "Phát"
                    enabled: trackTitle.info.count > 0
                    onClicked: {
                        if (trackTitle.playingHere) {
                            Player.toggle()
                        } else {
                            Player.setRepeat("all")
                            Player.playPlaylist(TrackSongs.playlistId, Playlists.orderedIds(TrackSongs.playlistId), -1)
                        }
                    }
                }
                PillButton {
                    icon: "shuffle"
                    label: "Trộn"
                    enabled: trackTitle.info.count > 0
                    onClicked: {
                        if (!Player.shuffle)
                            Player.toggleShuffle()
                        Player.setRepeat("all")
                        Player.playPlaylist(TrackSongs.playlistId, Playlists.orderedIds(TrackSongs.playlistId), -1)
                    }
                }
            }

            Row {
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                spacing: Theme.spacingSm

                // Ô tìm: một viên tròn có kính lúp, bấm vào mới giãn ra.
                Rectangle {
                    id: findBox

                    readonly property bool open: findInput.activeFocus || findInput.text !== ""
                    width: findBox.open ? root.findOpenWidth : root.toolHeight
                    height: root.toolHeight
                    radius: height / 2
                    color: "transparent"
                    border.width: 1
                    border.color: findInput.activeFocus ? Theme.primary : Theme.alpha(Theme.onSurface, 0.12)
                    clip: true
                    anchors.verticalCenter: parent.verticalCenter
                    Behavior on width { NumberAnimation { duration: Math.max(1, 380 * Theme.motionScale); easing.type: Easing.OutBack; easing.overshoot: Theme.overshoot } }

                    MIcon {
                        id: findIcon
                        x: (root.toolHeight - width) / 2
                        anchors.verticalCenter: parent.verticalCenter
                        name: "search"
                        size: 19
                    }
                    TextInput {
                        id: findInput
                        anchors.left: findIcon.right
                        anchors.leftMargin: Theme.spacingXs
                        anchors.right: parent.right
                        anchors.rightMargin: Theme.spacingMd
                        anchors.verticalCenter: parent.verticalCenter
                        color: Theme.onSurface
                        font.pixelSize: Theme.fontSizeMd
                        font.family: Theme.fontFamily
                        clip: true
                        onTextChanged: TrackSongs.setSearch(findInput.text)
                        Keys.onEscapePressed: { findInput.text = ""; findInput.focus = false }
                        Text {
                            visible: findInput.text === "" && findBox.open
                            text: "Tìm trong track"
                            color: Theme.onSurfaceVariant
                            font: findInput.font
                        }
                    }
                    MouseArea {
                        anchors.fill: parent
                        visible: !findBox.open
                        cursorShape: Qt.PointingHandCursor
                        onClicked: findInput.forceActiveFocus()
                    }
                }

                // Sắp xếp: một nút thả menu thay cho dãy chip.
                Rectangle {
                    id: sortButton
                    width: sortRow.implicitWidth + Theme.spacingMd * 2
                    height: root.toolHeight
                    radius: height / 2
                    color: sortArea.containsMouse ? Theme.alpha(Theme.onSurface, 0.05) : "transparent"
                    border.width: 1
                    border.color: Theme.alpha(Theme.onSurface, 0.12)
                    anchors.verticalCenter: parent.verticalCenter
                    Row {
                        id: sortRow
                        anchors.centerIn: parent
                        spacing: Theme.spacingXs
                        MIcon { name: "swap_vert"; size: 18; anchors.verticalCenter: parent.verticalCenter }
                        Text {
                            text: root.sortLabel(TrackSongs.sortKey)
                            color: Theme.onSurfaceVariant
                            font.pixelSize: Theme.fontSizeSm + 1
                            font.family: Theme.fontFamily
                            anchors.verticalCenter: parent.verticalCenter
                        }
                        MIcon { name: "expand_more"; size: 18; anchors.verticalCenter: parent.verticalCenter }
                    }
                    MouseArea {
                        id: sortArea
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            const at = sortButton.mapToItem(null, 0, sortButton.height)
                            sortMenu.popupAt(sortButton, at.x, at.y)
                        }
                    }
                }

                // Cụm công cụ.
                Rectangle {
                    width: toolRow.implicitWidth + 8
                    height: root.toolHeight + 8
                    radius: height / 2
                    color: Theme.alpha(Theme.onSurface, 0.045)
                    border.width: 1
                    border.color: Theme.alpha(Theme.onSurface, 0.075)
                    anchors.verticalCenter: parent.verticalCenter

                    Row {
                        id: toolRow
                        anchors.centerIn: parent
                        spacing: 2

                        ToolButton {
                            id: addTool
                            icon: "add"; label: "Thêm bài"
                            on: addPop.open
                            onClicked: addPop.open ? root.closeAdd() : root.openAdd(addTool)
                        }
                        ToolButton {
                            icon: "edit"; label: "Sửa"
                            on: TrackSongs.editMode
                            onClicked: {
                                TrackSongs.setSelectionMode(false)
                                TrackSongs.setEditMode(!TrackSongs.editMode)
                            }
                        }
                        ToolButton {
                            icon: "checklist"; label: "Chọn"
                            on: TrackSongs.selectionMode
                            onClicked: {
                                TrackSongs.setEditMode(false)
                                TrackSongs.setSelectionMode(!TrackSongs.selectionMode)
                            }
                        }
                        ToolButton {
                            id: moreTool
                            icon: "more_horiz"
                            onClicked: {
                                const at = moreTool.mapToItem(null, 0, moreTool.height)
                                toolsMenu.popupAt(moreTool, at.x, at.y)
                            }
                        }
                    }
                }
            }
        }

        TrackSortBar {
            id: sortBar

            anchors.top: toolbar.bottom
            anchors.topMargin: Theme.spacingSm
            anchors.horizontalCenter: parent.horizontalCenter
            width: root.contentWidth
            // Vòng 2 R-1: dãy chip thay bằng nút sắp xếp trên thanh công cụ.
            visible: false

            sortKey: TrackSongs.sortKey
            sortDescending: TrackSongs.sortDescending

            onSortRequested: (key) => TrackSongs.setSort(key)
        }

        // Trạng thái các việc đang tải VÀO ĐÚNG TRACK NÀY.
        //
        // Repeater lấy model là danh sách jobId (đổi rất hiếm) chứ KHÔNG phải
        // danh sách object: lấy object thì mỗi nhịp tiến độ lại thay cả mảng,
        // Repeater dựng lại toàn bộ hàng và animation viền khởi động lại liên
        // tục — đúng cái giật đã thấy.
        QtObject {
            id: downloads

            property var jobIds: []
            // Tăng mỗi khi tiến độ đổi, để các hàng đọc lại jobInfo().
            property int tick: 0

            // CHỈ gán jobIds khi TẬP id thật sự đổi. `pendingChanged` bắn mỗi
            // nhịp tiến độ, và gán một mảng MỚI (dù nội dung y hệt) là đủ để
            // Repeater dựng lại toàn bộ delegate — animation viền khởi động
            // lại liên tục, nhìn thành giật. `tick` mới là thứ đổi mỗi nhịp,
            // và nó chỉ làm chữ cập nhật chứ không đụng tới cấu trúc.
            function reload() {
                const next = TrackSongs.playlistId >= 0
                    ? Downloads.pendingIdsFor(TrackSongs.playlistId) : []
                if (next.length !== downloads.jobIds.length
                        || next.some((id, i) => id !== downloads.jobIds[i]))
                    downloads.jobIds = next
                downloads.tick = downloads.tick + 1
            }
        }

        Component.onCompleted: downloads.reload()

        Connections {
            target: Downloads
            function onPendingChanged() { downloads.reload() }
        }

        Connections {
            target: TrackSongs
            function onPlaylistChanged() { downloads.reload() }
        }

        Component {
            id: pendingRows

            Column {
                width: ListView.view ? ListView.view.width : 0
                spacing: Theme.spacingXs
                topPadding: downloads.jobIds.length > 0 ? Theme.spacingXs : 0

                Repeater {
                    model: downloads.jobIds

                    PendingSongRow {
                        id: pending

                        required property int modelData

                        readonly property var info: downloads.tick >= 0
                            ? Downloads.jobInfo(pending.modelData) : ({})

                        width: parent.width
                        height: 44
                        title: pending.info.title !== undefined ? pending.info.title : ""
                        artist: pending.info.artist !== undefined ? pending.info.artist : ""
                        durationText: pending.info.durationText !== undefined
                            ? pending.info.durationText : ""
                        thumbnail: pending.info.thumbnail !== undefined ? pending.info.thumbnail : ""
                        progress: pending.info.progress !== undefined ? pending.info.progress : 0
                        detail: pending.info.detail !== undefined ? pending.info.detail : ""
                    }
                }
            }
        }

        // Vì sao nút nắm vắng mặt. Ẩn nó đi mà không nói gì là lỗi đã gặp
        // thật (CB-043): chủ dự án chỉ thấy kéo-thả tự nhiên chết, không thấy
        // lý do và không biết bấm gì để bật lại. Câu chữ do bridge nói, không
        // phải QML tự đoán — chỉ có bridge biết đang vướng cái nào trong ba cái.
        Text {
            id: reorderHint

            anchors.top: sortBar.visible ? sortBar.bottom : toolbar.bottom
            anchors.topMargin: Theme.spacingSm
            anchors.horizontalCenter: parent.horizontalCenter
            width: root.contentWidth
            visible: TrackSongs.editMode && TrackSongs.reorderBlockedReason !== ""
            text: TrackSongs.reorderBlockedReason
            color: Theme.onSurfaceVariant
            font.pixelSize: Theme.fontSizeSm
            font.family: Theme.fontFamily
            wrapMode: Text.WordWrap
        }

        Item {
            id: content

            anchors.top: reorderHint.visible
                ? reorderHint.bottom
                : (sortBar.visible ? sortBar.bottom : toolbar.bottom)
            anchors.topMargin: Theme.spacingMd
            anchors.bottom: parent.bottom
            anchors.horizontalCenter: parent.horizontalCenter
            width: root.contentWidth

            // Lớp kính thứ hai sau danh sách bài — chỗ đọc chữ (QĐ-037, design R-1).
            Rectangle {
                anchors.fill: trackSongList
                anchors.margins: -Theme.spacingXs
                anchors.bottomMargin: Theme.islandReserve - Theme.spacingXs
                visible: TrackSongs.count > 0
                radius: Theme.radiusLg
                color: Theme.alpha(Theme.onSurface, 0.045)
                border.width: 1
                border.color: Theme.alpha(Theme.onSurface, 0.07)
            }

            TrackSongList {
                id: trackSongList

                anchors.top: parent.top
                anchors.left: parent.left
                // Vòng 3 R-1: không còn cột công cụ bên trái nên danh sách không
                // nhường lề nữa — trước đây chế độ Chọn đẩy cả danh sách sang phải.
                anchors.right: parent.right
                anchors.bottom: parent.bottom

                // Bài đang tải nằm NGAY DƯỚI bài cuối cùng và cuộn cùng danh
                // sách — trước đây nó bị ghim ở đáy khung nhìn (ngay trên thanh
                // phát) nên tách rời khỏi chỗ nó sẽ xuất hiện khi tải xong.
                footer: pendingRows
                footerHasContent: downloads.jobIds.length > 0

                // Bài đang tải lại (dòng đã có sẵn trong danh sách) không đi qua
                // `pendingRows`: nó tự sáng lên tại chỗ. Cùng một `tick`, hai đường vẽ.
                installLookup: (trackId) => Downloads.jobForTrack(trackId)
                downloadTick: downloads.tick

                model: TrackSongs
                playerIsPlaying: Player.isPlaying
                selectionMode: TrackSongs.selectionMode
                reorderable: TrackSongs.canReorder
                editMode: TrackSongs.editMode

                onPlayRequested: (trackId) => Player.playPlaylist(TrackSongs.playlistId, TrackSongs.orderedIds(), trackId)
                onToggleRequested: Player.toggle()
                onSelectionToggled: (trackId) => TrackSongs.toggleSelected(trackId)
                onMoveRequested: (from, to) => TrackSongs.moveSong(from, to)
                onRenameRequested: (trackId, title) => TrackSongs.renameSong(trackId, title)
                onMenuRequested: (trackId, sceneX, sceneY) => {
                    songMenu.trackId = trackId
                    songMenu.popupAt(trackSongList, sceneX, sceneY)
                }
                onCoverChangeRequested: (trackId) => {
                    coverPicker.trackId = trackId
                    coverPicker.open()
                }
                // Enter đã lưu tên rồi, giờ đóng chế độ sửa. Chủ dự án không
                // phải quay lại bấm cái bút lần thứ hai.
                onRenameCommitted: TrackSongs.setEditMode(false)
            }

            TrackTools {
                id: trackTools

                // Design R-1: lúc thường không có cột công cụ — mọi việc nằm trong
                // nút ⋯ ở đầu trang. Cột chỉ hiện khi đang sửa / chọn để xoá, vì
                // thanh xác nhận xoá và nút thoát chế độ nằm ở đây.
                // Vòng 2 R-1: không còn cột công cụ — Sửa / Chọn / Thêm bài nằm trên thanh công cụ.
                visible: false
                anchors.top: parent.top
                anchors.left: parent.left
                selectionMode: TrackSongs.selectionMode
                selectedCount: TrackSongs.selectedCount
                editMode: TrackSongs.editMode

                // Hai chế độ loại trừ nhau: đang sửa mà bật chọn-để-xoá thì
                // hàng vừa có ô tick vừa có tay nắm, bấm đâu cũng không rõ.
                onSelectionModeToggled: (on) => {
                    if (on)
                        TrackSongs.setEditMode(false)
                    TrackSongs.setSelectionMode(on)
                }
                onEditModeToggled: (on) => {
                    if (on)
                        TrackSongs.setSelectionMode(false)
                    TrackSongs.setEditMode(on)
                }
                onDeleteRequested: {
                    confirmSheet.titles = TrackSongs.selectedTitles()
                    confirmSheet.open = true
                }
                onDownloadRequested: (text) => root.startDownload(text)
                onImportRequested: mp3Picker.open()
            }

            // Hộp chọn file của hệ điều hành. Nó trả về `file://...` với dấu
            // cách mã hoá; tầng Python nhận cả hai dạng (core/mp3_import.py).
            //
            // Không có gì ở đây quyết định bài đi đâu: `TrackSongs.playlistId`
            // là track ĐANG MỞ, đúng thứ nút "+" vừa được bấm trong.
            QtDialogs.FileDialog {
                id: mp3Picker

                title: "Chọn file mp3 để nhập"
                fileMode: QtDialogs.FileDialog.OpenFiles
                nameFilters: ["Nhạc mp3 (*.mp3)"]
                onAccepted: Imports.importFiles(mp3Picker.selectedFiles, TrackSongs.playlistId)
            }

            // Hộp chọn ảnh bìa. `trackId` được đặt NGAY TRƯỚC khi mở: hộp thoại
            // không mang theo thông tin nào về bài vừa bấm.
            QtDialogs.FileDialog {
                id: coverPicker

                property int trackId: -1

                title: "Chọn ảnh bìa cho bài này"
                fileMode: QtDialogs.FileDialog.OpenFile
                nameFilters: ["Ảnh (*.jpg *.jpeg *.png *.webp)"]
                onAccepted: TrackSongs.setCover(coverPicker.trackId, coverPicker.selectedFile)
            }

        EmptyState {
            anchors.top: parent.top
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            // Hàng "đang tải" là footer của ListView và VẪN được vẽ khi danh
            // sách rỗng — nhưng ô trống này phủ kín cả vùng và nằm đè lên nó.
            // Track rỗng mà đang tải thì phải thấy animation, không phải thấy
            // câu "chưa có bài nào".
            visible: TrackSongs.count === 0 && TrackSongs.searchText === ""
                     && downloads.jobIds.length === 0
            glyph: "music_note"
            title: "Track này chưa có bài nào"
            subtitle: "Bấm vào mục bên trái để tìm nhạc trên YouTube và tải về, hoặc dán link."
        }

        EmptyState {
            anchors.top: parent.top
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            visible: TrackSongs.count === 0 && TrackSongs.searchText !== ""
            glyph: "search"
            title: "Không có bài nào khớp"
            subtitle: "Thử một từ khoá khác."
        }
    }
    }

    // Nằm NGOÀI `page` nên không bị lớp mờ ăn vào — nếu để bên trong thì
    // chính hộp thoại cũng bị làm mờ cùng nội dung phía sau.
    DeleteConfirmSheet {
        id: confirmSheet

        anchors.fill: parent
        z: 50

        onCancelled: confirmSheet.open = false
        onConfirmed: {
            confirmSheet.open = false
            TrackSongs.removeSelected()
            TrackSongs.setSelectionMode(false)
        }
    }

    // Nút ⋯ ở đầu trang track (design R-1): gom công cụ của cột cũ + việc của track.
    ContextMenu {
        id: toolsMenu

        items: [
            { "label": "Đổi tên track", "icon": "drive_file_rename_outline" },
            { "label": "Xoá track", "icon": "delete", "danger": true }
        ]

        onChosen: (index) => {
            if (index === 0)
                root.renameTrackRequested()
            else
                root.deleteTrackRequested()
        }
    }

    ContextMenu {
        id: sortMenu
        items: root.sortKeys.map(k => ({ "label": k[1], "icon": TrackSongs.sortKey === k[0] ? "radio_button_checked" : "radio_button_unchecked" }))
        onChosen: (index) => TrackSongs.setSort(root.sortKeys[index][0])
    }

    // "Thêm bài": dán link YouTube hoặc gõ tên bài để tìm, hoặc chọn mp3 trên máy.
    MouseArea {
        anchors.fill: parent
        visible: addPop.open
        z: 40
        onClicked: root.closeAdd()
    }
    Rectangle {
        id: addPop

        // Rộng ra khi có kết quả tìm, để tên bài đọc được.
        readonly property int baseWidth: 340
        readonly property int searchWidth: 480
        readonly property int resultsHeight: 300

        // Mở/đóng và đổi cỡ đều có chuyển động: đóng thì mờ + thu lại chứ không
        // biến mất, hiện/ẩn kết quả tìm thì hộp giãn/co có nảy nhẹ.
        property bool open: false
        readonly property int resizeMs: 320
        readonly property int fadeMs: 160

        visible: opacity > 0.01
        opacity: open ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: Math.max(1, addPop.fadeMs * Theme.motionScale); easing.type: Easing.OutCubic } }
        onVisibleChanged: if (!visible) TrackSearch.clear()
        clip: true
        z: 41
        width: TrackSearch.hasSearched ? searchWidth : baseWidth
        height: addColumn.implicitHeight + Theme.spacingLg * 2
        // Rộng ra thì kéo vào trong nếu tràn mép phải.
        onWidthChanged: x = Math.max(Theme.spacingMd, Math.min(x, root.width - width - Theme.spacingMd))
        Behavior on width { NumberAnimation { duration: Math.max(1, addPop.resizeMs * Theme.motionScale); easing.type: Easing.OutBack; easing.overshoot: Theme.overshoot * 0.6 } }
        Behavior on height { NumberAnimation { duration: Math.max(1, addPop.resizeMs * Theme.motionScale); easing.type: Easing.OutBack; easing.overshoot: Theme.overshoot * 0.6 } }
        radius: Theme.radiusLg
        // Hộp thoáng qua ⇒ đục (QĐ-040).
        color: Theme.surfaceVariant
        border.width: 1
        border.color: Theme.alpha(Theme.onSurface, 0.08)
        transformOrigin: Item.TopLeft
        scale: open ? 1 : 0.82
        Behavior on scale { NumberAnimation { duration: Math.max(1, 340 * Theme.motionScale); easing.type: Easing.OutBack; easing.overshoot: Theme.overshoot } }
        MouseArea { anchors.fill: parent }

        Column {
            id: addColumn
            x: Theme.spacingLg
            y: Theme.spacingLg
            width: parent.width - Theme.spacingLg * 2
            spacing: Theme.spacingMd

            Text {
                text: "Thêm bài vào " + TrackSongs.playlistName
                color: Theme.onSurface
                font.pixelSize: Theme.fontSizeMd
                font.weight: Font.DemiBold
                font.family: Theme.fontFamily
            }
            Rectangle {
                width: parent.width
                height: 42
                radius: Theme.radiusMd
                color: Theme.alpha(Theme.onSurface, 0.06)
                border.width: 1
                border.color: addInput.activeFocus ? Theme.primary : Theme.alpha(Theme.onSurface, 0.08)
                MIcon { id: linkIcon; x: Theme.spacingMd; anchors.verticalCenter: parent.verticalCenter; name: "search"; size: 19 }
                TextInput {
                    id: addInput
                    objectName: "addInput"
                    anchors.left: linkIcon.right
                    anchors.leftMargin: Theme.spacingSm
                    anchors.right: addGo.left
                    anchors.rightMargin: Theme.spacingSm
                    anchors.verticalCenter: parent.verticalCenter
                    color: Theme.onSurface
                    font.pixelSize: Theme.fontSizeMd
                    font.family: Theme.fontFamily
                    clip: true
                    onAccepted: addGo.clicked()
                    onTextChanged: if (text.trim() === "") TrackSearch.clear()
                    Keys.onEscapePressed: root.closeAdd()
                    Text { visible: addInput.text === ""; text: "Dán link hoặc tìm bài"; color: Theme.onSurfaceVariant; font: addInput.font }
                }
                PillButton {
                    id: addGo
                    anchors.right: parent.right
                    anchors.rightMargin: 4
                    anchors.verticalCenter: parent.verticalCenter
                    filled: true
                    label: addInput.text.trim() === "" || Downloads.looksLikeUrl(addInput.text.trim()) ? "Tải" : "Tìm"
                    scale: 0.85
                    onClicked: root.submitAdd(addInput.text.trim())
                }
            }
            SearchResultList {
                objectName: "addSearchResults"
                source: TrackSearch
                visible: TrackSearch.hasSearched
                width: parent.width
                height: visible ? addPop.resultsHeight : 0

                onResultChosen: (url) => {
                    Downloads.addToPlaylist(url, TrackSongs.playlistId)
                    root.closeAdd()
                }
            }
            Text {
                visible: !TrackSearch.hasSearched
                width: parent.width
                horizontalAlignment: Text.AlignHCenter
                text: "hoặc"
                color: Theme.onSurfaceVariant
                font.pixelSize: Theme.fontSizeSm
                font.family: Theme.fontFamily
            }
            PillButton {
                visible: !TrackSearch.hasSearched
                anchors.horizontalCenter: parent.horizontalCenter
                icon: "upload_file"
                label: "Chọn file mp3 trên máy"
                onClicked: { root.closeAdd(); mp3Picker.open() }
            }
        }
    }

    // Thanh nổi của chế độ Sửa / Chọn (design vòng 2), thay cột công cụ cũ.
    Rectangle {
        id: modebar

        readonly property bool on: TrackSongs.selectionMode || TrackSongs.editMode
        z: 30
        width: modeRow.implicitWidth + Theme.spacingLg + 6
        height: 52
        radius: height / 2
        x: (root.width - width) / 2
        y: root.height - Theme.islandReserve - height - Theme.spacingSm
        color: Theme.surfaceVariant
        border.width: 1
        border.color: Theme.alpha(Theme.onSurface, 0.08)
        opacity: modebar.on ? 1 : 0
        visible: opacity > 0.01
        transform: Translate { y: modebar.on ? 0 : 30; Behavior on y { NumberAnimation { duration: Math.max(1, 520 * Theme.motionScale); easing.type: Easing.OutBack; easing.overshoot: Theme.overshoot * 1.3 } } }
        Behavior on opacity { NumberAnimation { duration: Math.max(1, 180 * Theme.motionScale) } }

        Row {
            id: modeRow
            x: Theme.spacingLg
            anchors.verticalCenter: parent.verticalCenter
            spacing: Theme.spacingSm

            MIcon {
                visible: TrackSongs.editMode
                name: "edit"
                anchors.verticalCenter: parent.verticalCenter
            }
            Text {
                anchors.verticalCenter: parent.verticalCenter
                text: TrackSongs.editMode ? "Đang sửa" : TrackSongs.selectedCount + " bài đã chọn"
                color: Theme.onSurface
                font.pixelSize: Theme.fontSizeMd
                font.weight: Font.DemiBold
                font.family: Theme.fontFamily
            }
            Text {
                visible: TrackSongs.editMode
                anchors.verticalCenter: parent.verticalCenter
                text: "gõ tên mới · bấm ảnh để đổi bìa · kéo hàng để xếp"
                color: Theme.onSurfaceVariant
                font.pixelSize: Theme.fontSizeSm
                font.family: Theme.fontFamily
            }
            PillButton {
                visible: TrackSongs.selectionMode
                label: "Chọn hết"
                scale: 0.85
                anchors.verticalCenter: parent.verticalCenter
                onClicked: TrackSongs.selectAll()
            }
            PillButton {
                visible: TrackSongs.selectionMode
                icon: "remove_circle"
                label: "Bỏ khỏi track"
                enabled: TrackSongs.selectedCount > 0
                scale: 0.85
                anchors.verticalCenter: parent.verticalCenter
                onClicked: {
                    confirmSheet.titles = TrackSongs.selectedTitles()
                    confirmSheet.open = true
                }
            }
            PillButton {
                filled: true
                label: "Xong"
                scale: 0.85
                anchors.verticalCenter: parent.verticalCenter
                onClicked: {
                    TrackSongs.setSelectionMode(false)
                    TrackSongs.setEditMode(false)
                }
            }
        }
    }

    // Một nút trong cụm công cụ: icon (+ chữ), tô màu nhấn khi đang bật.
    component ToolButton: Rectangle {
        id: tb
        property string icon: ""
        property string label: ""
        property bool on: false
        property bool busy: false
        signal clicked()
        width: tbRow.implicitWidth + (tb.label === "" ? 0 : Theme.spacingMd * 2)
        implicitWidth: width
        height: root.toolHeight
        radius: height / 2
        color: tb.on ? Theme.primary : (tbArea.containsMouse ? Theme.alpha(Theme.onSurface, 0.06) : "transparent")
        scale: tbArea.pressed ? 0.88 : 1
        Behavior on scale { NumberAnimation { duration: Math.max(1, 90 * Theme.motionScale) } }
        Row {
            id: tbRow
            anchors.centerIn: parent
            spacing: Theme.spacingXs
            leftPadding: tb.label === "" ? (root.toolHeight - Theme.iconSize + 1) / 2 : 0
            rightPadding: tb.label === "" ? (root.toolHeight - Theme.iconSize + 1) / 2 : 0
            MIcon {
                name: tb.icon
                size: 19
                color: tb.on ? Theme.onPrimary : (tbArea.containsMouse ? Theme.onSurface : Theme.onSurfaceVariant)
                anchors.verticalCenter: parent.verticalCenter
                RotationAnimation on rotation { running: tb.busy; loops: Animation.Infinite; from: 0; to: 360; duration: 900 }
            }
            Text {
                visible: tb.label !== ""
                text: tb.label
                color: tb.on ? Theme.onPrimary : (tbArea.containsMouse ? Theme.onSurface : Theme.onSurfaceVariant)
                font.pixelSize: Theme.fontSizeSm + 1
                font.weight: Font.Medium
                font.family: Theme.fontFamily
                anchors.verticalCenter: parent.verticalCenter
            }
        }
        MouseArea { id: tbArea; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: tb.clicked() }
    }

    // Menu chuột phải cho một bài trong track.
    ContextMenu {
        id: songMenu

        property int trackId: -1

        items: [
            { "label": "Phát bài này", "icon": "play_arrow" },
            { "label": "Đổi tên", "icon": "edit" },
            { "label": "Xoá khỏi track", "icon": "remove_circle", "danger": true }
        ]

        onChosen: (index) => {
            if (index === 0)
                Player.playPlaylist(TrackSongs.playlistId, TrackSongs.orderedIds(), songMenu.trackId)
            else if (index === 1)
                TrackSongs.startRenaming(songMenu.trackId)
            else
                TrackSongs.removeTrack(songMenu.trackId)
        }
    }
}
