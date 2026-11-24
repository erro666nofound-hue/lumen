import QtQuick
import QtQuick.Controls as QQC

import "../components"

// Trang khám phá: thư viện không còn là lưới bài đã
// tải, mà là nơi app tự đề xuất nhạc theo các nghệ sĩ người dùng hay tải —
// bục "Most Recommend" + một hàng cuộn ngang mỗi nghệ sĩ + "Nhạc của tôi" ở
// cuối. Ô tìm trên cùng đổi vai thành tìm thẳng trên YouTube: có kết quả thì
// thay TOÀN BỘ phần khám phá bằng SearchResultList cho tới khi ô tìm bị xoá.
//
// Cả khối nội dung nằm trong MỘT Flickable vì bục + nhiều hàng nghệ sĩ dễ cao
// hơn khung nhìn nhiều — khác bản cũ (TrackGrid tự cuộn qua GridView).
//
// QtQuick.Controls PHẢI import có tên miền (as QQC) — xem CLAUDE.md mục 5,
// bug thật: import trần âm thầm thay SearchField của dự án bằng của Qt.
Item {
    id: root

    readonly property int contentWidth: Math.min(width - Theme.spacingLg * 2, Theme.contentMaxWidth)

    // Chỗ phải chừa ở mép phải hàng trên cùng cho mục tài khoản — Main.qml đặt
    // nó ở góc trên-phải, và nếu không chừa thì nó nằm đè lên chỗ này.
    property int rightReserve: 0
    readonly property int gutter: (width - contentWidth) / 2
    readonly property int topRowWidth: Math.max(160, contentWidth - rightReserve)
    readonly property int fadeMs: 160
    // Lề giữa khung và bục: lửa phun cao hơn thẻ, sát quá thì viền cắt ngang tàn lửa.
    readonly property int podiumFramePad: Theme.spacingLg
    readonly property int podiumLabelPad: 12

    // Main dựng animation bài bay vào track: LibraryView không tự làm được
    // vì nó không thấy thanh bên, mà bài phải bay XUYÊN QUA cả hai.
    signal downloadStarted(var anchor, int playlistId, string thumbnail)

    // Bấm một thẻ track ở lưới "Track của bạn" (R-1) — Main mở track đó.
    signal playlistOpened(int playlistId)

    // Main làm mờ khu nội dung khi bảng chi tiết "Nhạc của tôi" mở — cùng cách
    // đã dùng cho hộp xoá track. LibraryView không tự làm mờ mình được: chính
    // nó nằm TRONG vùng cần mờ.
    // MỘT cờ duy nhất cho MỘT lớp mờ duy nhất (đặt ở Main.qml). Thêm điều kiện
    // vào đây chứ KHÔNG thêm lớp mờ mới, nếu không hai lớp chồng nhau sẽ làm
    // nền tối gấp đôi và mờ gấp đôi khi cả hai bảng cùng mở.
    //
    // Bản thân các bảng nổi KHÔNG bị mờ theo: QQC.Popup vẽ trong lớp phủ của
    // cửa sổ, nằm ngoài cây bị lớp mờ bọc.
    readonly property bool overlayOpen: historyList.detailOpen || trackPicker.visible

    // CỬA DUY NHẤT gọi Discovery trong file này — mỗi nghệ sĩ ~1.4s mạng,
    // nên gom về một chỗ cho dễ thấy ai đang gọi.
    function refreshDiscovery(force) {
        Discovery.refresh(force)
    }

    Component.onCompleted: root.refreshDiscovery(false)

    // Bấm "↓" trên một thẻ đề xuất hoặc chọn một kết quả tìm YouTube đều đi
    // qua đây: nhớ URL/tên bài đang chờ rồi mở TrackPicker. Component picker
    // không tự tải -- Downloads.addToPlaylist chỉ chạy sau khi người dùng
    // chọn track ở trackChosen bên dưới.
    function openPicker(url, title) {
        trackPicker.pendingUrl = url
        trackPicker.songTitle = title
        trackPicker.pendingFacts = { "title": title }
        trackPicker.pendingThumb = ""
        trackPicker.parent = root
        trackPicker.x = (root.width - trackPicker.width) / 2
        trackPicker.y = (root.height - trackPicker.height) / 2
        trackPicker.open()
    }

    // Mở bảng chọn track SÁT CẠNH một bảng khác (bảng chi tiết "Nhạc của tôi"),
    // thay vì nổi giữa màn hình rời rạc với thứ vừa bấm. Ưu tiên bên phải, hết
    // chỗ thì sang trái, rồi kẹp trong cửa sổ.
    // `facts` = tên/tác giả/thời lượng/ảnh mà nơi gọi ĐÃ BIẾT. Truyền xuống để
    // hàng "đang tải" trong track hiện đủ ngay thay vì chờ downloader dò xong.
    function openPickerBeside(url, title, anchor, facts) {
        trackPicker.pendingUrl = url
        trackPicker.songTitle = title
        trackPicker.pendingAnchor = anchor
        trackPicker.pendingFacts = facts || { "title": title }
        trackPicker.pendingThumb = trackPicker.pendingFacts.thumbnail || ""
        const gap = Theme.spacingSm
        const window = anchor.Window.window
        const scene = anchor.mapToItem(null, 0, 0)
        trackPicker.parent = anchor.Window.contentItem
        let px = scene.x + anchor.width + gap
        if (px + trackPicker.width > window.width - gap)
            px = scene.x - trackPicker.width - gap
        trackPicker.x = Math.max(gap, px)
        trackPicker.y = Math.max(gap, Math.min(
            scene.y, window.height - trackPicker.height - gap))
        trackPicker.open()
    }

    // Lời chào + dòng thống kê ở đầu Thư viện (design R-1).
    Column {
        id: greeting

        readonly property int hour: new Date().getHours()
        readonly property var stats: Playlists.count >= 0 ? Playlists.libraryStats() : ({})

        anchors.top: parent.top
        anchors.topMargin: Theme.spacingXl
        anchors.left: parent.left
        anchors.leftMargin: root.gutter
        width: root.contentWidth
        spacing: Theme.spacingXs

        Text {
            text: greeting.hour < 11 ? "Sáng nay nghe gì?" : (greeting.hour < 18 ? "Chiều nay nghe gì?" : "Tối nay nghe gì?")
            color: Theme.onSurface
            font.pixelSize: 32
            font.weight: Font.Bold
            font.family: Theme.fontFamily
        }
        Text {
            readonly property int minutes: Math.round((greeting.stats.totalMs || 0) / 60000)
            text: (greeting.stats.tracks || 0) + " track · " + (greeting.stats.songs || 0) + " bài · "
                + (minutes >= 60 ? Math.floor(minutes / 60) + " giờ " + (minutes % 60) + " phút" : minutes + " phút") + " nhạc"
            color: Theme.onSurfaceVariant
            font.pixelSize: Theme.fontSizeMd
            font.family: Theme.fontFamily
        }
    }

    SearchField {
        id: searchField

        anchors.top: greeting.bottom
        anchors.topMargin: Theme.spacingLg
        anchors.left: parent.left
        anchors.leftMargin: root.gutter
        width: root.contentWidth
        placeholder: "Dán link YouTube hoặc gõ tên bài để tìm"
        glyph: "link"

        // Design R-1: dán link YouTube là tải luôn (hỏi chọn track), gõ chữ là tìm.
        onSubmitted: (text) => {
            const link = text.trim()
            if (/^(https?:\/\/)?(www\.|m\.|music\.)?(youtube\.com|youtu\.be)\//i.test(link)) {
                root.openPicker(link, "")
                searchField.text = ""
            } else {
                Search.run(text)
            }
        }
        onCleared: Search.clear()
    }

    Item {
        id: body

        anchors.top: searchField.bottom
        anchors.topMargin: Theme.spacingLg
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom

        Item {
            id: searchPane

            anchors.fill: parent
            opacity: Search.hasSearched ? 1 : 0
            visible: opacity > 0.01

            Behavior on opacity {
                NumberAnimation { duration: Math.max(1, (root.fadeMs) * Theme.motionScale); easing.type: Easing.OutCubic }
            }

            SearchResultList {
                anchors.top: parent.top
                anchors.bottom: parent.bottom
                anchors.horizontalCenter: parent.horizontalCenter
                width: root.contentWidth

                onResultChosen: (url) => root.openPicker(url, "")
            }
        }

        Flickable {

            bottomMargin: Theme.islandReserve
            id: flick

            anchors.fill: parent
            opacity: Search.hasSearched ? 0 : 1
            visible: opacity > 0.01
            contentWidth: width
            contentHeight: discoverColumn.height + Theme.spacingXl
            clip: true
            boundsBehavior: Flickable.StopAtBounds

            Behavior on opacity {
                NumberAnimation { duration: Math.max(1, (root.fadeMs) * Theme.motionScale); easing.type: Easing.OutCubic }
            }

            QQC.ScrollBar.vertical: QQC.ScrollBar { policy: QQC.ScrollBar.AsNeeded }

            Column {
                id: discoverColumn

                anchors.horizontalCenter: parent.horizontalCenter
                width: root.contentWidth
                spacing: Theme.spacingXl

                // Lời chào + lưới "Track của bạn" — design R-1.
                Column {
                    width: parent.width
                    spacing: Theme.spacingLg


                    Text {
                        visible: Playlists.count > 0
                        text: "TRACK CỦA BẠN"
                        color: Theme.onSurfaceVariant
                        font.pixelSize: Theme.fontSizeSm
                        font.weight: Font.DemiBold
                        font.letterSpacing: 1.2
                        font.family: Theme.fontFamily
                    }

                    Flow {
                        id: trackGrid

                        readonly property int cardWidth: 156

                        width: parent.width
                        spacing: Theme.spacingMd

                        Repeater {
                            model: Playlists

                            Item {
                                id: card

                                required property int playlistId
                                required property string name
                                required property int trackCount
                                readonly property var info: card.trackCount >= 0 ? Playlists.cardFor(card.playlistId) : ({})

                                width: trackGrid.cardWidth
                                height: cardColumn.height + Theme.spacingMd * 2

                                Rectangle {
                                    anchors.fill: parent
                                    radius: Theme.radiusLg
                                    color: cardArea.containsMouse ? Theme.alpha(Theme.onSurface, 0.06) : "transparent"
                                }

                                Column {
                                    id: cardColumn
                                    x: Theme.spacingMd
                                    y: Theme.spacingMd + (cardArea.containsMouse ? -3 : 0)
                                    width: parent.width - Theme.spacingMd * 2
                                    spacing: Theme.spacingSm
                                    Behavior on y { NumberAnimation { duration: Math.max(1, (380) * Theme.motionScale); easing.type: Easing.OutBack; easing.overshoot: Theme.overshoot } }

                                    Mosaic {
                                        width: parent.width
                                        height: parent.width
                                        radius: Theme.radiusMd
                                        covers: card.info.covers || []
                                    }
                                    Text {
                                        width: parent.width
                                        text: card.name
                                        color: Theme.onSurface
                                        font.pixelSize: Theme.fontSizeMd + 1
                                        font.weight: Font.DemiBold
                                        font.family: Theme.fontFamily
                                        elide: Text.ElideRight
                                    }
                                    Text {
                                        width: parent.width
                                        topPadding: -Theme.spacingXs
                                        text: card.trackCount + " bài · " + Math.round((card.info.totalMs || 0) / 60000) + " phút"
                                        color: Theme.onSurfaceVariant
                                        font.pixelSize: Theme.fontSizeSm
                                        font.family: Theme.fontFamily
                                    }
                                }

                                MouseArea {
                                    id: cardArea
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: root.playlistOpened(card.playlistId)
                                }
                            }
                        }
                    }
                }

                // Trang khám phá (QĐ-041: không còn khoá theo gói).
                Column {
                    id: discoverPane

                    width: parent.width
                    spacing: Theme.spacingXl

                    Text {
                        visible: Discovery.state === "loading" && Discovery.count > 0
                        width: parent.width
                        horizontalAlignment: Text.AlignHCenter
                        text: "Đang cập nhật thêm gợi ý..."
                        color: Theme.onSurfaceVariant
                        font.pixelSize: Theme.fontSizeSm
                        font.family: Theme.fontFamily
                    }

                    EmptyState {
                        visible: Discovery.state === "loading" && Discovery.count === 0
                        width: parent.width
                        height: 260
                        glyph: "music_note"
                        title: "Đang tìm nhạc bạn hay nghe..."
                        subtitle: "Lần đầu có thể mất khoảng một phút — lần sau sẽ gần như tức thì."
                    }

                    EmptyState {
                        visible: Discovery.state === "empty"
                        width: parent.width
                        height: 260
                        glyph: "music_note"
                        title: "Chưa có gợi ý nào"
                        subtitle: "Tải vài bài trước để Lumen biết bạn hay nghe gì."
                    }

                    // "learning" = đã có nhạc, nhưng mỗi nghệ sĩ mới 1-3 bài nên
                    // chưa đủ để đoán gu. Đề xuất lúc này chỉ là đoán mò, nên trang
                    // chỉ còn lời mời + "Nhạc của tôi" ở dưới.
                    EmptyState {
                        visible: Discovery.state === "learning"
                        width: parent.width
                        height: 260
                        glyph: "music_note"
                        title: "Lumen đang làm quen với gu của bạn"
                        subtitle: "Tải thêm vài bài của một nghệ sĩ bạn thích — "
                            + "đủ 4 bài là Lumen bắt đầu gợi ý."
                    }

                    Column {
                        visible: Discovery.state === "error"
                        width: parent.width
                        spacing: Theme.spacingMd

                        EmptyState {
                            width: parent.width
                            height: 220
                            glyph: "priority_high"
                            title: "Không tải được đề xuất"
                            subtitle: "Kiểm tra mạng rồi thử lại."
                        }

                        Rectangle {
                            id: retryButton

                            anchors.horizontalCenter: parent.horizontalCenter
                            width: retryLabel.implicitWidth + Theme.spacingLg * 2
                            height: 36
                            radius: Theme.radiusSm
                            color: Theme.alpha(Theme.primary, retryArea.containsMouse ? 0.28 : 0.16)

                            Behavior on color {
                                ColorAnimation { duration: Math.max(1, (120) * Theme.motionScale); easing.type: Easing.OutCubic }
                            }

                            Text {
                                id: retryLabel

                                anchors.centerIn: parent
                                text: "Thử lại"
                                color: Theme.primary
                                font.pixelSize: Theme.fontSizeSm
                                font.family: Theme.fontFamily
                            }

                            MouseArea {
                                id: retryArea

                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: root.refreshDiscovery(true)
                            }
                        }
                    }

                    // Design R-1: một dải "Gợi ý cho bạn" thay cho bục MOST RECOMMEND
                    // và các kệ theo nghệ sĩ.
                    Column {
                        visible: Discovery.strip.length > 0
                        width: parent.width
                        spacing: Theme.spacingMd

                        Item {
                            width: parent.width
                            height: recCaption.implicitHeight

                            Text {
                                id: recCaption
                                text: "GỢI Ý CHO BẠN"
                                color: Theme.onSurfaceVariant
                                font.pixelSize: Theme.fontSizeSm
                                font.weight: Font.DemiBold
                                font.letterSpacing: 1.2
                                font.family: Theme.fontFamily
                            }
                            Text {
                                anchors.right: parent.right
                                text: "từ những nhạc sĩ bạn hay nghe"
                                color: Theme.onSurfaceVariant
                                font.pixelSize: Theme.fontSizeSm
                                font.family: Theme.fontFamily
                            }
                        }

                        RecStrip {
                            width: parent.width
                            songs: Discovery.strip
                            onPreviewRequested: (videoId) => Player.preview(videoId)
                            onAddRequested: (url, title, anchor) =>
                                root.openPickerBeside(url, title, anchor, {
                                    "title": anchor.title,
                                    "artist": anchor.uploader,
                                    "durationText": anchor.durationText,
                                    "thumbnail": anchor.thumbnail,
                                })
                        }
                    }
                }

                Column {
                    width: parent.width
                    spacing: Theme.spacingMd

                    SectionLabel { text: "Nhạc của tôi" }

                    HistoryList {
                        id: historyList

                        width: parent.width

                        onAddRequested: (url, title) => root.openPicker(url, title)
                        onPreviewRequested: (videoId) => Player.preview(videoId)
                        onAddRequestedBeside: (url, title, anchor, facts) =>
                            root.openPickerBeside(url, title, anchor, facts)
                    }
                }
            }
        }
    }

    TrackPicker {
        id: trackPicker

        property string pendingUrl: ""
        property var pendingAnchor: null
        property string pendingThumb: ""
        property var pendingFacts: ({})

        parent: root
        x: (root.width - width) / 2
        y: (root.height - height) / 2

        onTrackChosen: (playlistId) => {
            Downloads.addToPlaylist(
                trackPicker.pendingUrl, playlistId, trackPicker.pendingFacts)
            if (trackPicker.pendingAnchor)
                root.downloadStarted(
                    trackPicker.pendingAnchor, playlistId, trackPicker.pendingThumb)
        }
        // Bảng chi tiết đang bị giữ mở vì bảng này; thả ra khi nó đóng.
        onClosed: historyList.releaseHold()
    }
}
