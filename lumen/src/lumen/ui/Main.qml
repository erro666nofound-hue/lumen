import QtQuick
import QtQuick.Window
import QtQuick.Effects

import "components"
import "views"

Window {
    id: root

    // Kích thước chỉ có tác dụng khi cửa sổ ở chế độ nổi. Dưới tiling,
    // Hyprland quyết định và app tuân theo — đó là hành vi mong muốn.
    width: 1040
    height: 660
    // Giới hạn nhỏ nhất mà bố cục THẬT SỰ chịu được — đã quét từng cỡ, tới
    // 320px vẫn không thành phần nào tràn biên (xem "Lumen thu gọn" ROADMAP).
    //
    // Trước đây để 720x480, tức là các chế độ thu gọn dưới 720px (dải icon ở
    // 620px, thanh phát rút gọn ở 560px) KHÔNG BAO GIỜ với tới được bằng cách
    // kéo cửa sổ — làm ra rồi không ai dùng được.
    minimumWidth: 360
    minimumHeight: 400
    visible: true

    // Đóng cửa sổ chỉ ẨN. Lumen phải sống tiếp thì nhạc mới chạy tiếp và phím
    // tắt mới gọi lại được — thoát hẳn nằm ở bảng sau nút bánh răng, và ở
    // `lumen --quit`. Chặn ở đây thì cả nút ✕ lẫn lệnh đóng của Hyprland đều
    // đi qua cùng một luật.
    onClosing: (event) => {
        event.accepted = false
        root.hide()
    }
    title: "Lumen"

    // Nền trong suốt để Hyprland áp blur lên vùng phía sau.
    color: "transparent"

    // Mini Lumen bật/tắt bằng ĐÚNG một thuộc tính, để phím tắt (đi qua socket
    // vào tận Python) chỉ cần lật nó, không phải biết gì về QML bên trong.
    property bool miniOpen: false

    // Mở cái này là đóng cái kia: hai cửa sổ cùng lúc thì không biết nhìn vào
    // đâu, và Mini vốn được làm ra để thay hẳn cửa sổ lớn lúc chỉ muốn nghe.
    onMiniOpenChanged: {
        if (root.miniOpen) {
            mini.show()
            // XIN BÀN PHÍM, không chỉ hiện ra. Thiếu dòng này thì Mini nổi lên
            // nhưng phím vẫn thuộc về cửa sổ đang focus trước đó — bấm Esc hay
            // Space là bay sang app khác. Đo được: mở Mini xong, cửa sổ đang
            // focus vẫn là app khác.
            mini.raise()
            mini.requestActivate()
            root.hide()
        } else {
            mini.hide()
        }
    }

    // Đưa cửa sổ lớn ra trước và dẹp Mini. Phía Python (lệnh `show` qua socket)
    // cũng đi đúng đường này.
    function showFull() {
        root.miniOpen = false
        root.show()
        root.raise()
        root.requestActivate()
    }

    MiniWindow {
        id: mini

        onHidden: root.miniOpen = false
        onOpenFullRequested: root.showFull()
    }

    // Nền riêng của Lumen, vẽ DƯỚI mọi thứ. Không có thì để trong suốt như cũ
    // và Hyprland lo phần hình nền phía sau.
    FadingWallpaper {
        anchors.fill: parent
        source: Theme.wallpaperIsImage ? "file://" + Theme.wallpaper : ""
    }

    // -1 = đang ở Thư viện, >= 0 = id track đang mở. Một nguồn duy nhất quyết
    // định LibraryView hay TrackView đang hiển thị.
    property int activePlaylistId: -1
    // Mục "Nhạc sĩ" là màn hình THỨ BA, không phải track nên không nhét vào
    // activePlaylistId được. Mở nó thì hai màn kia cùng ẩn.
    property bool artistsOpen: false
    property bool settingsOpen: false
    // Màn Lịch sử nghe (design R-1).
    property bool historyOpen: false
    // Trang cài đặt đang mở (vòng 2 R-1).
    property string settingsPage: "look"

    // Thời lượng chuyển giữa Thư viện và Track.
    readonly property int viewSwitchMs: 180
    // Thời lượng làm mờ nền khi hộp xác nhận xoá TRACK (không phải xoá vài bài
    // trong track -- đó là DeleteConfirmSheet, tự lo lấy trong TrackView) mở
    // ra. Cùng số với TrackView.blurMs để hai chỗ mờ giống nhau.
    readonly property int contentBlurMs: 180

    // Track đang chờ xác nhận xoá -- chụp lại tên/số bài NGAY LÚC Sidebar bắn
    // deleteTrackRequested, vì sau khi Playlists.remove() chạy thì hàng model
    // biến mất và không còn cách nào đọc lại tên từ đó nữa (lý do y hệt chú
    // thích cũ từng nằm ở Sidebar.qml, chỉ chuyển chỗ giữ state theo dialog).
    property int _trackDeleteId: -1
    property string _trackDeleteName: ""
    property int _trackDeleteSongCount: -1

    // Vùng mờ khi hộp xoá track mở: toàn bộ khu vực CHROME + NỘI DUNG (Thư
    // viện/Track), tức mọi thứ TRỪ thanh bên trái và thanh phát dưới -- đúng
    // yêu cầu của chủ dự án, và đúng nghĩa cụm từ này đã dùng khi TrackView tự
    // làm mờ chính nó cho DeleteConfirmSheet (xem TrackView.qml): "toàn bộ"
    // luôn ngầm định KHÔNG tính WindowChrome, vì chrome chỉ là thanh tiêu đề
    // mỏng, tách biệt hẳn khỏi luồng nội dung mà hộp xác nhận đang che.

    property real contentBlurStrength:
        (trackDeleteConfirm.open || libraryView.overlayOpen || artistsView.detailOpen
            || settingsView.overlayOpen || playerBar.open)
            ? 1.0 : 0.0

    Behavior on contentBlurStrength {
        NumberAnimation { duration: root.contentBlurMs; easing.type: Easing.OutCubic }
    }

    // Đang gõ chữ ở đâu đó (ô tìm kiếm, ô nhập tên track...) hay không. Dùng
    // để tắt phím tắt Space bên dưới -- KHÔNG được xoá property này dù trông
    // như không dùng ở đâu khác, xem chú thích tại Shortcut.
    // Kiểu nhập chữ (TextInput/TextField/TextArea) đều có property
    // cursorPosition; Item thường thì không -- dùng đặc điểm đó để phân biệt
    // "đang gõ chữ" với "đang focus một Item/Button/NavItem bình thường".
    readonly property bool typing: root.activeFocusItem !== null
        && root.activeFocusItem.cursorPosition !== undefined

    // Không viền, và cũng KHÔNG tự cài cơ chế kéo/resize nào.
    // Hyprland toàn quyền: vị trí, kích thước, bo góc, blur, SUPER + kéo để di chuyển.
    // App chỉ chịu trách nhiệm vẽ nội dung bên trong hình chữ nhật được cấp.
    flags: Qt.Window | Qt.FramelessWindowHint

    // Space = phát/tạm dừng. "Shortcut" ở đây là kiểu gốc của module QtQuick
    // (QQuickShortcut, export "QtQuick/Shortcut") -- ĐÃ TỰ KIỂM CHỨNG bằng
    // cách nạp QML thật: "QQC.Shortcut" (tên miền QtQuick.Controls) KHÔNG PHẢI
    // một kiểu tồn tại, dù đọc rất hợp lý -- QtQuick.Controls không có kiểu
    // Shortcut nào cả, Shortcut nằm sẵn trong QtQuick nền tảng đã import ở đầu
    // file. Dùng QQC.Shortcut làm engine.load() thất bại hoàn toàn (không root
    // object nào được tạo) và qmllint KHÔNG báo lỗi gì. Đừng "sửa lại" thành
    // QQC.Shortcut tưởng là đúng chuẩn của dự án -- đã đo, sai.
    //
    // Shortcut mặc định bắt phím ở phạm vi cả cửa sổ, nên PHẢI tắt khi đang gõ
    // chữ (enabled: !root.typing) -- nếu không, gõ dấu cách trong ô tìm kiếm
    // hoặc ô nhập tên track sẽ bị nuốt thành toggle nhạc thay vì gõ ra khoảng
    // trắng. Đừng "dọn dẹp" property typing hay điều kiện enabled này.
    Shortcut {
        sequence: "Space"
        enabled: !root.typing
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

    Rectangle {
        id: surfaceLayer

        anchors.fill: parent
        // Một lớp làm HAI việc: phủ kính cho app, và làm dịu nền người dùng
        // chọn để chữ còn đọc được. Có nền riêng thì phải mỏng hẳn đi, không
        // thì nền đó gần như vô hình.
        color: Theme.alpha(Theme.surface,
                           Theme.wallpaper !== "" ? Theme.wallpaperSurfaceAlpha
                                                  : Theme.surfaceAlpha)
    }

    // Không còn dải tiêu đề chiếm chỗ (bro, 2026-10-05: lệch khoảng cách) — chỉ
    // nút ✕ nổi ở góc trên-phải, trên mọi thứ.
    WindowChrome {
        id: chrome

        z: 60

        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        height: Theme.headerHeight
    }

    Sidebar {
        id: sidebar

        anchors.top: parent.top
        anchors.topMargin: Theme.spacingMd
        anchors.left: parent.left
        anchors.bottom: parent.bottom

        footerReserve: Theme.spacingMd
        currentPlaylistId: root.activePlaylistId
        artistsActive: root.artistsOpen
        settingsActive: root.settingsOpen
        historyActive: root.historyOpen
        settingsMode: root.settingsOpen
        settingsPage: root.settingsPage
        onSettingsPageSelected: (page) => root.settingsPage = page
        onSettingsBack: root.settingsOpen = false
        onHistorySelected: {
            root.historyOpen = true
            root.settingsOpen = false
            root.artistsOpen = false
            Listened.refresh()
        }
        onLibrarySelected: {
            root.activePlaylistId = -1
            root.artistsOpen = false
            root.settingsOpen = false
            root.historyOpen = false
        }
        onMiniRequested: root.miniOpen = true
        onSettingsSelected: {
            root.settingsOpen = true
            root.artistsOpen = false
            root.historyOpen = false
        }
        onPlaylistSelected: (playlistId) => {
            root.activePlaylistId = playlistId
            root.artistsOpen = false
            root.settingsOpen = false
            root.historyOpen = false
            TrackSongs.setPlaylist(playlistId)
        }
        onArtistsSelected: {
            root.artistsOpen = true
            root.settingsOpen = false
            root.historyOpen = false
            Artists.refresh()
        }
        onTrackMenuRequested: (playlistId, name, songCount, sceneX, sceneY) => {
            trackMenu.playlistId = playlistId
            trackMenu.trackName = name
            trackMenu.songCount = songCount
            trackMenu.popupAt(sidebar, sceneX, sceneY)
        }
        onDeleteTrackRequested: (playlistId, name, songCount) => {
            root._trackDeleteId = playlistId
            root._trackDeleteName = name
            root._trackDeleteSongCount = songCount
            trackDeleteConfirm.open = true
        }
    }

    LibraryView {
        id: libraryView

        onPlaylistOpened: (playlistId) => {
            root.activePlaylistId = playlistId
            root.artistsOpen = false
            root.settingsOpen = false
            root.historyOpen = false
            TrackSongs.setPlaylist(playlistId)
        }

        // Bài vừa chọn bay từ thẻ vào đúng hàng track ở thanh bên. Nối ở Main
        // vì đây là nơi duy nhất thấy được CẢ thẻ lẫn thanh bên.
        onDownloadStarted: (anchor, playlistId, thumbnail) => {
            const target = sidebar.rowCenterFor(playlistId)
            if (!target)
                return
            const from = anchor.mapToItem(null, anchor.width / 2, anchor.height / 2)
            flyToTrack.thumbnail = thumbnail
            flyToTrack.launch(from.x, from.y, target.x, target.y, playlistId)
        }

        anchors.top: parent.top
        anchors.left: sidebar.right
        anchors.right: parent.right
        anchors.bottom: parent.bottom

        // Mờ chuyển thay vì bật/tắt cụp. visible vẫn phải theo opacity: chỉ
        // opacity 0 thôi thì view ẩn VẪN nhận chuột và chặn view đang hiện.
        visible: opacity > 0.01

        // R-1: chuyển mục có nảy như design.
        ViewMotion {
            shown: root.activePlaylistId < 0 && !root.artistsOpen && !root.settingsOpen && !root.historyOpen
        }

        // Làm mờ nội dung khi trackDeleteConfirm mở -- xem contentBlurStrength
        // ở trên. layer chỉ bật khi thật sự cần (ngưỡng nhỏ thay vì so 0 để
        // tránh nhấp nháy giữa lúc animation chạy), giống hệt cách TrackView tự
        // làm mờ "page" của chính nó cho DeleteConfirmSheet.
        layer.enabled: root.contentBlurStrength > 0.01
        layer.effect: MultiEffect {
            blurEnabled: true
            blur: root.contentBlurStrength
            blurMax: 40
            autoPaddingEnabled: false
        }
    }

    TrackView {
        id: trackView

        onRenameTrackRequested: {
            trackMenu.playlistId = root.activePlaylistId
            trackMenu.trackName = TrackSongs.playlistName
            renamePrompt.original = TrackSongs.playlistName
            renamePrompt.open()
        }
        onDeleteTrackRequested: {
            root._trackDeleteId = root.activePlaylistId
            root._trackDeleteName = TrackSongs.playlistName
            root._trackDeleteSongCount = TrackSongs.count
            trackDeleteConfirm.open = true
        }


        anchors.top: parent.top
        anchors.left: sidebar.right
        anchors.right: parent.right
        anchors.bottom: parent.bottom

        visible: opacity > 0.01

        // R-1: chuyển mục có nảy như design.
        ViewMotion {
            shown: root.activePlaylistId >= 0 && !root.artistsOpen && !root.settingsOpen && !root.historyOpen
            replay: root.activePlaylistId
        }

        // TrackView không tự bắn được signal của đối tượng Python, nên nó bắn
        // tín hiệu riêng và Main nối vào cùng một chỗ thông báo như mọi thứ khác.
        onNoticeRequested: (message) => toasts.showInfo(message)


        // Cùng lớp mờ như LibraryView ở trên -- TrackView có thể ĐANG hiển thị
        // khi người dùng bấm thùng rác một track KHÁC trên thanh bên, nên phải
        // mờ theo contentBlurStrength y hệt. Lồng bên trong lớp mờ RIÊNG của
        // TrackView cho DeleteConfirmSheet của chính nó (property blurStrength,
        // xem TrackView.qml) -- hai lớp độc lập, không xung đột.
        layer.enabled: root.contentBlurStrength > 0.01
        layer.effect: MultiEffect {
            blurEnabled: true
            blur: root.contentBlurStrength
            blurMax: 40
            autoPaddingEnabled: false
        }
    }

    FlyToTrack {
        id: flyToTrack
    }

    ArtistsView {
        id: artistsView


        // Cùng MỘT lớp mờ với hai màn kia (xem contentBlurStrength) — thêm lớp
        // mới sẽ chồng lên nhau khi nhiều bảng cùng mở.
        layer.enabled: root.contentBlurStrength > 0.01
        layer.effect: MultiEffect {
            blurEnabled: true
            blur: root.contentBlurStrength
            blurMax: 40
            autoPaddingEnabled: false
        }

        anchors.top: parent.top
        anchors.left: sidebar.right
        anchors.right: parent.right
        anchors.bottom: parent.bottom

        // visible theo opacity: chỉ hạ opacity thì màn ẩn vẫn ăn chuột.
        visible: opacity > 0.01

        // R-1: chuyển mục có nảy như design.
        ViewMotion {
            shown: root.artistsOpen && !root.settingsOpen && !root.historyOpen
        }
    }

    ToastOverlay {
        id: toasts

        anchors.left: sidebar.right
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.topMargin: Theme.spacingMd
        height: Theme.rowHeight * 3
        z: 100
    }

    // Mọi thông báo của tầng Python đổ về một chỗ duy nhất.
    Connections {
        target: Downloads
        function onErrorOccurred(message) { toasts.showError(message) }
        function onNoticeOccurred(message) { toasts.showInfo(message) }
    }

    // Nhập mp3 từ máy. Cùng một chỗ đổ thông báo với Downloads, nhưng bridge
    // khác nên phải nối riêng — nút "+" bấm mà im lặng thì không ai biết bài
    // đã vào hay chưa.
    Connections {
        target: Imports
        function onErrorOccurred(message) { toasts.showError(message) }
        function onNoticeOccurred(message) { toasts.showInfo(message) }
    }

    Connections {
        target: Library
        function onErrorOccurred(message) { toasts.showError(message) }
    }

    Connections {
        target: Player
        function onErrorOccurred(message) { toasts.showError(message) }
    }

    Connections {
        target: Playlists
        function onErrorOccurred(message) { toasts.showError(message) }
        // Track đang mở bị xoá (từ nơi khác, hoặc tự xoá) -> quay về Thư viện
        // để không kẹt ở một màn hình trống rỗng không id nào trỏ tới.
        function onCountChanged() {
            if (root.activePlaylistId >= 0 && Playlists.nameFor(root.activePlaylistId) === "")
                root.activePlaylistId = -1
        }
    }

    Connections {
        target: TrackSongs
        function onErrorOccurred(message) { toasts.showError(message) }
    }

    // Tìm trên YouTube hỏng (mạng chết, YouTube đổi giao diện) — không nói thì
    // người dùng gõ tên bài rồi ngồi nhìn danh sách rỗng, tưởng không có bài.
    Connections {
        target: Search
        function onErrorOccurred(message) { toasts.showError(message) }
    }

    Connections {
        target: TrackSearch
        function onErrorOccurred(message) { toasts.showError(message) }
    }

    // Lưu đánh giá nhạc sĩ hỏng: không nói thì thanh kéo bật về chỗ cũ mà không
    // ai hiểu vì sao.
    Connections {
        target: Artists
        function onErrorOccurred(message) { toasts.showError(message) }
    }

    HistoryView {
        id: historyView

        anchors.top: parent.top
        anchors.left: sidebar.right
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        visible: opacity > 0.01

        layer.enabled: root.contentBlurStrength > 0.01
        layer.effect: MultiEffect {
            blurEnabled: true
            blur: root.contentBlurStrength
            blurMax: 40
            autoPaddingEnabled: false
        }

        ViewMotion {
            shown: root.historyOpen && !root.settingsOpen
        }
    }

    SettingsView {
        id: settingsView

        page: root.settingsPage

        onMiniRequested: root.miniOpen = true

        // CÙNG lớp mờ với LibraryView / TrackView / ArtistsView. Thiếu nó suốt
        // từ đầu, và không ai thấy vì tới F-5h mới có hộp nổi mở TỪ Cài đặt:
        // trang Cài đặt xuyên thẳng qua bảng, sắc nét. Cách chữa sai là đắp
        // thêm một tấm tối lên bảng — ra "blur đen", trong khi cả app blur sáng.
        layer.enabled: root.contentBlurStrength > 0.01
        layer.effect: MultiEffect {
            blurEnabled: true
            blur: root.contentBlurStrength
            blurMax: 40
            autoPaddingEnabled: false
        }

        anchors.top: parent.top
        anchors.left: sidebar.right
        anchors.right: parent.right
        anchors.bottom: parent.bottom

        // visible theo opacity: chỉ hạ opacity thì màn ẩn vẫn ăn chuột.
        visible: opacity > 0.01

        // R-1: chuyển mục có nảy như design.
        ViewMotion {
            shown: root.settingsOpen
        }
    }

    // Hòn đảo phát nhạc (R-1): nổi trên vùng nội dung, không chiếm một dải riêng.
    // z trên các view, dưới các hộp nổi và toast.
    PlayerBar {
        id: playerBar

        onMiniRequested: root.miniOpen = true

        anchors.top: parent.top
        anchors.left: sidebar.right
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        z: 5
    }

    // Hộp xác nhận xoá CẢ MỘT TRACK -- sống ở đây (không phải trong
    // Sidebar.qml) và phủ đúng vùng chrome+nội dung ở trên (không phải toàn
    // bộ Window) để thẻ căn giữa đúng khu vực đang bị làm mờ, và để thanh bên
    // + thanh phát nằm NGOÀI phạm vi anchors.fill nên vẫn nhận được chuột bình
    // thường trong lúc hộp mở (đúng yêu cầu: chỉ nội dung mờ, hai thanh kia
    // không bị khoá). z cao hơn hai view nhưng thấp hơn ToastOverlay (z: 100)
    // -- giữ đúng thứ tự đã có giữa DeleteConfirmSheet và toast trong TrackView.
    TrackDeleteConfirm {
        id: trackDeleteConfirm

        anchors.top: parent.top
        anchors.left: sidebar.right
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        z: 50

        trackName: root._trackDeleteName
        songCount: root._trackDeleteSongCount

        onCancelled: trackDeleteConfirm.open = false
        onConfirmed: {
            trackDeleteConfirm.open = false
            const wasOpen = root.activePlaylistId === root._trackDeleteId
            Playlists.remove(root._trackDeleteId)
            // Playlists.countChanged ở trên cũng tự đưa về Thư viện khi track
            // đang mở biến mất -- gán thêm ở đây để chuyển ngay lập tức, không
            // đợi round-trip qua signal countChanged của Python.
            if (wasOpen) root.activePlaylistId = -1
        }
    }

    // Menu chuột phải cho một track ở thanh bên.
    ContextMenu {
        id: trackMenu

        property int playlistId: -1
        property string trackName: ""
        property int songCount: 0

        items: [
            { "label": "Mở track", "icon": "open_in_full" },
            { "label": "Đổi tên", "icon": "edit" },
            { "label": "Xoá track", "icon": "delete", "danger": true }
        ]

        onChosen: (index) => {
            if (index === 0) {
                root.activePlaylistId = trackMenu.playlistId
                root.artistsOpen = false
                root.settingsOpen = false
                root.historyOpen = false
                TrackSongs.setPlaylist(trackMenu.playlistId)
            } else if (index === 1) {
                renamePrompt.original = trackMenu.trackName
                renamePrompt.open()
            } else {
                root._trackDeleteId = trackMenu.playlistId
                root._trackDeleteName = trackMenu.trackName
                root._trackDeleteSongCount = trackMenu.songCount
                trackDeleteConfirm.open = true
            }
        }
    }

    RenamePrompt {
        id: renamePrompt

        anchors.centerIn: parent
        heading: "Đổi tên track"

        onAccepted: (name) => Playlists.rename(trackMenu.playlistId, name)
    }
}
