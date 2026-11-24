import QtQuick
import QtQuick.Controls as QQC
import QtQuick.Effects

import "../components"

// Thanh bên: điều hướng Thư viện + danh sách track do người dùng tự tạo.
Item {
    id: root

    // Thanh bên là thành phần DUY NHẤT đo theo bề ngang CỬA SỔ, không theo bề
    // ngang của chính nó — vì chính nó quyết định cột nội dung còn lại rộng bao
    // nhiêu. Mọi thành phần khác tự đo lấy mình (xem "Lumen thu gọn" ROADMAP).
    readonly property int windowWidth: root.Window.window ? root.Window.window.width : 0

    readonly property int narrowBelow: 760
    readonly property int railBelow: 620
    readonly property int narrowWidth: 168
    readonly property int railWidth: 56
    readonly property int brandHeight: 52
    readonly property int logoSize: 30
    readonly property int captionHeight: 34
    readonly property int captionButton: 26
    // Chiều cao hàng chân (mục tài khoản) để căn nút Mini cho ngang hàng.
    property int footerButtonRoom: Theme.searchFieldHeight
    // Main đặt mục tài khoản ở chân thanh bên (R-1); chừa chỗ cho nó.
    property int footerReserve: Theme.spacingMd

    // Dải icon: chỉ còn ký hiệu, tên bài hiện khi rê chuột.
    readonly property bool rail: root.windowWidth > 0 && root.windowWidth < root.railBelow

    width: root.rail
        ? root.railWidth
        : (root.windowWidth > 0 && root.windowWidth < root.narrowBelow
            ? root.narrowWidth : Theme.sidebarWidth)

    Behavior on width {
        NumberAnimation { duration: 180; easing.type: Easing.OutCubic }
    }

    // -1 = đang ở Thư viện. Dùng id thật thay vì index để không lệch khi
    // danh sách Playlists đổi thứ tự/độ dài.
    property int currentPlaylistId: -1
    // Đang mở mục "Nhạc sĩ" — nó không phải track nên không dùng chung
    // currentPlaylistId được.
    property bool artistsActive: false
    property bool settingsActive: false
    property bool historyActive: false

    readonly property int fadeInMs: 160
    readonly property int fadeOutMs: 120

    // Đổi giá trị mỗi lần Downloads báo có thay đổi, để các binding
    // `downloading` bên dưới tính lại — slot thường không tự phát tín hiệu.
    property int pendingTick: 0

    Connections {
        target: Downloads
        function onPendingChanged() { root.pendingTick = root.pendingTick + 1 }
    }

    // Tâm hàng của một track, theo toạ độ cửa sổ — dùng cho animation bài bay
    // vào track. Trả về null khi track đó không có trên thanh bên.
    function rowCenterFor(playlistId) {
        for (let i = 0; i < trackRows.count; i++) {
            const row = trackRows.itemAt(i)
            if (row && row.playlistId === playlistId)
                return row.mapToItem(null, row.width / 2, row.height / 2)
        }
        return null
    }

    // Một ô sáng chung trượt tới mục đang chọn (vượt qua chút rồi bật về), thay
    // cho từng mục tự sáng — bro muốn chuyển mục thấy "đi" chứ không "nháy".
    property Item activeItem: null
    // Bật trong lúc ô sáng trượt sang mục mới, để Behavior chỉ chạy khi đổi mục.
    property bool sliding: false
    onActiveItemChanged: { root.sliding = true; slideTimer.restart() }
    Timer { id: slideTimer; interval: Math.max(1, 600 * Theme.motionScale); onTriggered: root.sliding = false }
    // Chiều cao vùng chân (mục tài khoản + nút Mini) mà danh sách track chừa ra.
    readonly property int footerHeight: Theme.spacingMd + root.footerButtonRoom + Theme.spacingMd
    // Độ dài dải mờ ở mép vùng cuộn.
    readonly property int fadeEdge: 28
    // Track vừa được chọn nằm ngoài vùng nhìn thì cuộn tới nó.
    function reveal(row) {
        const top = row.y, bottom = row.y + row.height
        let target = trackScroll.contentY
        if (top < trackScroll.contentY)
            target = top
        else if (bottom > trackScroll.contentY + trackScroll.height)
            target = bottom - trackScroll.height
        if (target === trackScroll.contentY)
            return
        revealAnim.to = target
        revealAnim.restart()
    }
    function track(item, on) {
        if (on)
            root.activeItem = item
        else if (root.activeItem === item)
            root.activeItem = null
    }

    // Vòng 2 R-1: mở Cài đặt thì danh sách chính trượt ra trái, danh sách mục
    // cài đặt trượt vào từ phải (có nút ← để quay lại).
    property bool settingsMode: false
    property string settingsPage: "look"
    readonly property var settingsPages: [["look", "palette", "Giao diện"], ["keys", "keyboard", "Phím tắt"],
                                          ["store", "folder_open", "Kho nhạc"],
                                          ["about", "info", "Giới thiệu"]]
    readonly property real paneShift: root.settingsMode ? -root.width : 0
    signal settingsPageSelected(string page)
    signal settingsBack()

    signal librarySelected()
    signal artistsSelected()
    signal settingsSelected()
    signal historySelected()
    signal miniRequested()
    signal playlistSelected(int playlistId)
    // Bấm thùng rác trên một track -- bắn thẳng ra Main.qml kèm tên/số bài
    // NGAY LÚC bấm (không tự giữ state ở đây nữa). Hộp xác nhận giờ phải phủ
    // TOÀN MÀN HÌNH thay vì bó hẹp trong Theme.sidebarWidth (208px), nên nó
    // sống ở Main.qml -- nơi có cả thanh bên, khu nội dung và thanh phát để
    // tính đúng vùng cần làm mờ. Main.qml chịu trách nhiệm chụp lại tên/số
    // bài vào property riêng của nó trước khi model biến mất sau khi xoá.
    signal deleteTrackRequested(int playlistId, string name, int songCount)
    signal trackMenuRequested(int playlistId, string name, int songCount, real sceneX, real sceneY)

    Rectangle {
        id: divider

        anchors.right: parent.right
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        width: 1
        color: Theme.alpha(Theme.outline, Theme.dividerAlpha)
    }

    // Một khung chung cho ô sáng + điều hướng + danh sách track, để hiệu ứng mờ
    // dần ở mép vùng cuộn phủ được cả ô sáng. Mục tài khoản và nút Mini nằm
    // NGOÀI khung: danh sách dừng ngay trên chúng, không còn trôi dưới chúng.
    Item {
        id: mainPane

        anchors.fill: parent
        // LUÔN bật: bật/tắt theo "có tràn không" làm lớp hiệu ứng bị dựng lại giữa
        // lúc cửa sổ đổi cỡ và app sập (segfault trong geometryChange, đo 2026-10-16).
        // Không tràn thì mặt nạ đặc toàn phần, nhìn như không có hiệu ứng.
        layer.enabled: true
        layer.effect: MultiEffect {
            maskEnabled: true
            maskSource: fadeMask
            // 0.5 + 1.0 = độ đặc của mặt nạ đi thẳng ra độ đặc của hình (dải mờ đều).
            // 0.0 + 1.0 thì mọi điểm ≥ 0 đều giữ nguyên — đã thử, không mờ gì cả.
            maskThresholdMin: 0.5
            maskSpreadAtMin: 1.0
        }

        Rectangle {
            id: slider

            transform: Translate {
                x: root.paneShift
                Behavior on x { NumberAnimation { duration: Math.max(1, 520 * Theme.motionScale); easing.type: Easing.OutBack; easing.overshoot: Theme.overshoot * 0.8 } }
            }
            opacity: root.settingsMode ? 0 : 1
            Behavior on opacity { NumberAnimation { duration: Math.max(1, 220 * Theme.motionScale) } }

            // Mọi mục đều là con trực tiếp của navColumn ⇒ cộng y là đủ, và binding
            // tự chạy lại khi danh sách track xê dịch.
            readonly property real slideOvershoot: Theme.overshoot * 1.3

            // Hàng track nằm trong vùng cuộn: vị trí trừ đi phần đã cuộn, và bị cắt
            // ở hai mép vùng cuộn để ô sáng không đè lên chữ TRACK hay mục tài khoản.
            readonly property bool onRow: root.activeItem !== null && root.activeItem.playlistId !== undefined
            readonly property real rawY: !root.activeItem ? 0
                : slider.onRow ? trackScroll.y + root.activeItem.y - trackScroll.contentY
                : navColumn.y + root.activeItem.y
            readonly property real rawH: root.activeItem ? root.activeItem.height : 0
            readonly property real clipTop: slider.onRow ? Math.max(slider.rawY, trackScroll.y) : slider.rawY
            readonly property real clipBottom: slider.onRow
                ? Math.min(slider.rawY + slider.rawH, trackScroll.y + trackScroll.height) : slider.rawY + slider.rawH

            visible: root.activeItem !== null && slider.clipBottom > slider.clipTop
            x: (slider.onRow ? trackScroll.x : navColumn.x) + (root.activeItem ? root.activeItem.x : 0)
            y: slider.clipTop
            width: root.activeItem ? root.activeItem.width : 0
            height: Math.max(0, slider.clipBottom - slider.clipTop)
            radius: Theme.radiusMd
            color: Theme.alpha(Theme.primary, 0.16)

            // Chỉ nảy khi ĐỔI mục; lúc cuộn thì bám sát hàng, không trễ theo.
            Behavior on y {
                enabled: root.sliding
                NumberAnimation { duration: Math.max(1, 420 * Theme.motionScale); easing.type: Easing.OutBack; easing.overshoot: slider.slideOvershoot }
            }
            Behavior on height {
                enabled: root.sliding
                NumberAnimation { duration: Math.max(1, 260 * Theme.motionScale); easing.type: Easing.OutCubic }
            }
        }

        Column {
            id: navColumn

            transform: Translate {
                x: root.paneShift
                Behavior on x { NumberAnimation { duration: Math.max(1, 520 * Theme.motionScale); easing.type: Easing.OutBack; easing.overshoot: Theme.overshoot * 0.8 } }
            }
            opacity: root.settingsMode ? 0 : 1
            Behavior on opacity { NumberAnimation { duration: Math.max(1, 220 * Theme.motionScale) } }

            anchors.left: parent.left
            anchors.right: parent.right
            anchors.rightMargin: Theme.spacingSm + divider.width
            anchors.top: parent.top
            anchors.margins: Theme.spacingSm
            spacing: Theme.spacingXs

            // Logo như design R-1: ô màu nhấn bo tròn mang icon sóng nhạc + chữ Lumen.
            Row {
                height: root.brandHeight
                leftPadding: root.rail ? (parent.width - root.logoSize) / 2 : Theme.spacingSm
                spacing: Theme.spacingMd

                Rectangle {
                    width: root.logoSize
                    height: root.logoSize
                    radius: Theme.radiusSm
                    color: Theme.primary
                    anchors.verticalCenter: parent.verticalCenter

                    MIcon {
                        anchors.centerIn: parent
                        name: "graphic_eq"
                        size: root.logoSize * 0.64
                        color: Theme.onPrimary
                    }
                }
                Text {
                    visible: !root.rail
                    text: "Lumen"
                    color: Theme.onSurface
                    font.pixelSize: Theme.fontSizeLg + 3
                    font.weight: Font.Bold
                    font.family: Theme.fontFamily
                    anchors.verticalCenter: parent.verticalCenter
                }
            }

            NavItem {
                width: parent.width
                compact: root.rail
                glyph: "library_music"
                label: "Thư viện"
                // Mở Cài đặt cũng là rời Thư viện — thiếu vế này thì hai mục cùng sáng.
                active: root.currentPlaylistId < 0 && !root.artistsActive && !root.settingsActive && !root.historyActive
                onActiveChanged: root.track(this, active)
                Component.onCompleted: root.track(this, active)
                onClicked: root.librarySelected()
            }

            NavItem {
                width: parent.width
                compact: root.rail
                glyph: "mic_external_on"
                label: "Nhạc sĩ"
                active: root.artistsActive
                onActiveChanged: root.track(this, active)
                Component.onCompleted: root.track(this, active)
                onClicked: root.artistsSelected()
            }

            NavItem {
                width: parent.width
                compact: root.rail
                glyph: "history"
                label: "Lịch sử"
                active: root.historyActive
                onActiveChanged: root.track(this, active)
                Component.onCompleted: root.track(this, active)
                onClicked: root.historySelected()
            }

            NavItem {
                width: parent.width
                compact: root.rail
                glyph: "settings"
                label: "Cài đặt"
                active: root.settingsActive
                onActiveChanged: root.track(this, active)
                Component.onCompleted: root.track(this, active)
                onClicked: root.settingsSelected()
            }

            // Chữ TRACK + nút "+" tạo track ngay cạnh (design R-1).
            Item {
                id: trackCaption

                width: parent.width
                height: root.captionHeight

                SectionLabel {
                    visible: !root.rail
                    anchors.left: parent.left
                    anchors.leftMargin: Theme.spacingMd
                    anchors.verticalCenter: parent.verticalCenter
                    text: "Track"
                }
                IconButton {
                    anchors.right: root.rail ? undefined : parent.right
                    anchors.horizontalCenter: root.rail ? parent.horizontalCenter : undefined
                    anchors.rightMargin: Theme.spacingXs
                    anchors.verticalCenter: parent.verticalCenter
                    width: root.captionButton
                    height: root.captionButton
                    glyph: "add"
                    onClicked: createPopup.opened ? createPopup.close() : createPopup.open()
                }
            }


            // Ô nhập tên track dùng QQC.Popup -- bắt chước sát VolumeButton.qml,
            // mẫu chuẩn của dự án cho tương tác kiểu này. Popup đè đúng lên vị trí
            // NavItem "+ Tạo track" (parent + x/y = 0,0 + cùng kích thước) nên nhìn
            // vẫn như một dòng trong danh sách chứ không phải bảng nổi lơ lửng, và
            // tự đóng khi bấm ra ngoài hoặc Esc -- không cần tự dò activeFocus nữa.
            QQC.Popup {
                id: createPopup

                parent: trackCaption
                x: 0
                y: 0
                width: trackCaption.width
                height: Theme.navItemHeight
                // OutsideParent chứ không phải OutsidePress -- xem chú thích trong
                // VolumeButton.qml: đã đo bằng probe thật, CloseOnPressOutside làm
                // bấm lại chính NavItem đóng-rồi-mở-lại-ngay nên không bao giờ đóng
                // được. OutsideParent coi cú bấm lên NavItem là "trong phạm vi cha"
                // nên NavItem.onClicked toggle đúng.
                closePolicy: QQC.Popup.CloseOnPressOutsideParent | QQC.Popup.CloseOnEscape
                padding: 0
                background: Rectangle {
                    color: Theme.alpha(Theme.surfaceVariant, 0.96)
                    border.width: 1
                    border.color: Theme.alpha(Theme.outline, 0.5)
                    radius: Theme.radiusMd
                }

                // onOpened, không phải onClicked của NavItem: đây mới là thời điểm
                // TextInput thật sự đã tồn tại trong Popup và sẵn sàng nhận focus.

                // Popup style Basic KHÔNG có transition mặc định (đã kiểm chứng trong
                // /usr/lib/qt6/qml/QtQuick/Controls/Basic/Popup.qml) — thiếu hai khối
                // này thì bảng bật/tắt cụp một cái.
                enter: Transition {
                    ParallelAnimation {
                            NumberAnimation { property: "opacity"; from: 0; to: 1
                                                      duration: root.fadeInMs; easing.type: Easing.OutCubic }
                            NumberAnimation { property: "scale"; from: 0.92; to: 1
                                                      duration: root.fadeInMs; easing.type: Easing.OutCubic }
                    }
                }
                exit: Transition {
                    NumberAnimation { property: "opacity"; from: 1; to: 0
                                              duration: root.fadeOutMs; easing.type: Easing.InCubic }
                }

                onOpened: createInput.forceActiveFocus()
                // Đóng xong luôn xoá sạch để lần mở sau trống trơn.
                onClosed: createInput.text = ""

                Rectangle {
                    anchors.fill: parent
                    radius: Theme.radiusSm
                    color: Theme.alpha(Theme.onSurface, 0.06)

                    TextInput {
                        id: createInput

                        anchors.fill: parent
                        anchors.leftMargin: Theme.spacingMd
                        anchors.rightMargin: Theme.spacingMd
                        verticalAlignment: TextInput.AlignVCenter
                        color: Theme.onSurface
                        font.pixelSize: Theme.fontSizeMd
                        font.family: Theme.fontFamily
                        selectByMouse: true
                        clip: true

                        onAccepted: {
                            const newId = Playlists.create(text)
                            if (newId >= 0) {
                                createPopup.close()
                                root.playlistSelected(newId)
                            }
                            // newId < 0: Playlists tự bắn errorOccurred, Popup giữ
                            // mở để người dùng sửa lại (closePolicy không tự đóng
                            // khi accepted, chỉ đóng khi bấm ra ngoài/Esc/gọi close()).
                        }
                    }
                }
            }
        }

        Flickable {
            id: trackScroll
            objectName: "trackScroll"

            transform: Translate {
                x: root.paneShift
                Behavior on x { NumberAnimation { duration: Math.max(1, 520 * Theme.motionScale); easing.type: Easing.OutBack; easing.overshoot: Theme.overshoot * 0.8 } }
            }
            opacity: root.settingsMode ? 0 : 1
            Behavior on opacity { NumberAnimation { duration: Math.max(1, 220 * Theme.motionScale) } }

            anchors.left: parent.left
            anchors.leftMargin: Theme.spacingSm
            anchors.right: parent.right
            anchors.rightMargin: Theme.spacingSm + divider.width
            anchors.top: navColumn.bottom
            anchors.topMargin: navColumn.spacing
            anchors.bottom: parent.bottom
            anchors.bottomMargin: root.footerHeight
            contentWidth: width
            contentHeight: trackColumn.height
            clip: true
            boundsBehavior: Flickable.StopAtBounds

            NumberAnimation {
                id: revealAnim
                target: trackScroll
                property: "contentY"
                duration: Math.max(1, 260 * Theme.motionScale)
                easing.type: Easing.OutCubic
            }

            Column {
                id: trackColumn

                width: trackScroll.width
                spacing: navColumn.spacing

                Text {
                    visible: Playlists.count === 0
                    anchors.left: parent.left
                    anchors.leftMargin: Theme.spacingMd
                    anchors.right: parent.right
                    anchors.rightMargin: Theme.spacingMd
                    text: "Chưa có track nào"
                    color: Theme.onSurfaceVariant
                    font.pixelSize: Theme.fontSizeSm
                    font.family: Theme.fontFamily
                    wrapMode: Text.WordWrap
                }

                Repeater {
                    id: trackRows

                    model: Playlists

                    TrackNavItem {
                        // Để rowCenterFor() tìm được đúng hàng.
                        readonly property int playlistId: model.playlistId

                        compact: root.rail
                        width: trackColumn.width
                        label: model.name
                        count: model.trackCount
                        covers: model.trackCount >= 0 ? Playlists.cardFor(model.playlistId).covers : []
                        active: root.currentPlaylistId === model.playlistId
                        onActiveChanged: { root.track(this, active); if (active) root.reveal(this) }
                        Component.onCompleted: root.track(this, active)
                        // Scope, không phải currentPlaylistId: một track có thể đang
                        // MỞ trên màn hình mà không PHÁT (hoặc ngược lại, đang phát
                        // từ track A trong lúc màn hình đứng ở track B).
                        playing: Player.scopePlaylistId === model.playlistId && Player.isPlaying
                        // Đọc lại mỗi khi danh sách việc tải đổi (xem pendingTick).
                        downloading: root.pendingTick >= 0
                            && Downloads.isDownloadingInto(model.playlistId)

                        onMenuRequested: (sceneX, sceneY) => root.trackMenuRequested(
                            model.playlistId, model.name, model.trackCount, sceneX, sceneY)
                        onClicked: root.playlistSelected(model.playlistId)

                        onPlayToggled: {
                            if (Player.scopePlaylistId === model.playlistId) {
                                // Track này đã là track đang phát -- chỉ tạm dừng/tiếp
                                // tục đúng bài đang nằm ở đó, không nhảy về đầu danh
                                // sách.
                                Player.toggle()
                            } else {
                                Player.setRepeat("all")
                                Player.playPlaylist(model.playlistId, Playlists.orderedIds(model.playlistId), -1)
                            }
                        }

                        onDeleteRequested: root.deleteTrackRequested(model.playlistId, model.name, model.trackCount)
                    }
                }

            }
        }
    }

    // Mặt nạ cho hiệu ứng mờ dần: chỉ kênh alpha có nghĩa, màu không bao giờ hiện
    // ra. Mép dưới vùng cuộn mờ khi còn track phía dưới; mép trên mờ khi đã cuộn.
    Item {
        id: fadeMask

        // Mốc dải màu phải nằm trong 0..1 và tăng dần — lúc cửa sổ vừa dựng
        // (cao 0) chúng vượt 1 và đảo thứ tự, và app sập (đo được, exit 139).
        readonly property real h: Math.max(1, mainPane.height)
        readonly property real fadeSpan: Math.min(0.25, root.fadeEdge / fadeMask.h)
        readonly property real topAt: Math.min(1, Math.max(0, trackScroll.y / fadeMask.h))
        readonly property real topIn: Math.min(1, fadeMask.topAt + fadeMask.fadeSpan)
        readonly property real bottomAt: Math.min(1, Math.max(fadeMask.topIn, (trackScroll.y + trackScroll.height) / fadeMask.h))
        readonly property real bottomIn: Math.max(fadeMask.topIn, fadeMask.bottomAt - fadeMask.fadeSpan)
        // Một bước rất ngắn để mép trên vùng cuộn là một vạch cắt, không phải dốc.
        readonly property real edgeStep: 1 / fadeMask.h

        anchors.fill: mainPane
        visible: false
        layer.enabled: true

        Rectangle {
            anchors.fill: parent
            gradient: Gradient {
                // Đặc tới SÁT mép trên vùng cuộn rồi mới tụt — thiếu mốc này thì dải
                // mờ kéo từ đỉnh cửa sổ xuống, làm mờ luôn các mục điều hướng.
                GradientStop { position: 0.0; color: Qt.rgba(1, 1, 1, 1) }
                GradientStop { position: fadeMask.topAt; color: Qt.rgba(1, 1, 1, 1) }
                GradientStop { position: Math.min(fadeMask.topIn, fadeMask.topAt + fadeMask.edgeStep); color: Qt.rgba(1, 1, 1, trackScroll.atYBeginning ? 1 : 0) }
                GradientStop { position: fadeMask.topIn; color: Qt.rgba(1, 1, 1, 1) }
                GradientStop { position: fadeMask.bottomIn; color: Qt.rgba(1, 1, 1, 1) }
                GradientStop { position: fadeMask.bottomAt; color: Qt.rgba(1, 1, 1, trackScroll.atYEnd ? 1 : 0) }
                GradientStop { position: 1.0; color: Qt.rgba(1, 1, 1, 0) }
            }
        }
    }

    // Thoát hẳn đứng RIÊNG một dòng ở đáy, không giấu trong cài đặt: nó không
    // phải một tuỳ chọn, nó là một hành động. Và đứng xa dấu ✕ của thanh tiêu
    // đề để không ai bấm nhầm — ✕ chỉ ẩn, nút này mới tắt thật.
    // Mini Lumen phải với tới được TỪ TRONG APP, không chỉ bằng phím tắt:
    // phím tắt do trình quản lý cửa sổ giữ, mà Windows thì không có nó.
    // Khoảng trống giữa danh sách track và nhóm nút dưới cùng — trước đây trơ
    // trọi. Mấy vạch nhạc lấp vào đó, và tiện thể cho biết có đang phát không
    // mà không phải liếc xuống thanh phát.
    Item {
        id: pulseSlot
        // Design R-1 không có cột sóng nhạc giữa thanh bên.
        visible: false

        anchors.top: mainPane.top
        anchors.topMargin: trackScroll.y + trackColumn.height
        anchors.bottom: parent.bottom
        anchors.bottomMargin: root.footerReserve
        anchors.left: parent.left
        anchors.right: parent.right

        // Chật quá thì thôi, đừng chen: danh sách track dài là hết chỗ.
        readonly property int roomNeeded: 72

        EqualizerBars {
            anchors.centerIn: parent
            visible: pulseSlot.height >= pulseSlot.roomNeeded
            playing: Player.isPlaying
            // Dải icon hẹp chỉ còn 40px lọt lòng — năm vạch là tràn.
            barCount: root.rail ? 3 : 5
        }
    }




    // Nút Mini Lumen cạnh mục tài khoản ở chân thanh bên (design R-1).
    // "Thoát Lumen" chuyển vào Cài đặt › Về Lumen.
    IconButton {
        anchors.right: parent.right
        anchors.rightMargin: Theme.spacingMd
        anchors.bottom: parent.bottom
        anchors.bottomMargin: Theme.spacingMd + (root.footerButtonRoom - root.captionButton) / 2
        width: root.captionButton + Theme.spacingSm
        height: root.captionButton + Theme.spacingSm
        glyph: "picture_in_picture_alt"
        onClicked: root.miniRequested()
    }

    // ---------------- danh sách mục cài đặt ----------------
    Item {
        id: settingsPane

        // Cùng khung với navColumn (nay nằm trong mainPane nên không neo thẳng được).
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.margins: Theme.spacingSm
        anchors.rightMargin: Theme.spacingSm + divider.width
        height: settingsColumn.height
        visible: opacity > 0.01
        opacity: root.settingsMode ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: Math.max(1, 220 * Theme.motionScale) } }
        transform: Translate {
            x: root.settingsMode ? 0 : root.width
            Behavior on x { NumberAnimation { duration: Math.max(1, 520 * Theme.motionScale); easing.type: Easing.OutBack; easing.overshoot: Theme.overshoot * 0.8 } }
        }

        Rectangle {
            id: settingsSlider
            property Item on: null
            visible: settingsSlider.on !== null
            width: parent.width
            height: settingsSlider.on ? settingsSlider.on.height : 0
            y: settingsColumn.y + (settingsSlider.on ? settingsSlider.on.y : 0)
            radius: Theme.radiusMd
            color: Theme.alpha(Theme.primary, 0.16)
            Behavior on y { NumberAnimation { duration: Math.max(1, 420 * Theme.motionScale); easing.type: Easing.OutBack; easing.overshoot: Theme.overshoot * 1.3 } }
        }

        Column {
            id: settingsColumn
            width: parent.width
            spacing: Theme.spacingXs

            NavItem {
                width: parent.width
                compact: root.rail
                glyph: "arrow_back"
                label: "Cài đặt"
                onClicked: root.settingsBack()
            }
            Item { width: 1; height: Theme.spacingSm }

            Repeater {
                model: root.settingsPages
                NavItem {
                    id: pageItem
                    required property var modelData
                    width: settingsColumn.width
                    compact: root.rail
                    glyph: pageItem.modelData[1]
                    label: pageItem.modelData[2]
                    active: root.settingsPage === pageItem.modelData[0]
                    onActiveChanged: if (active) settingsSlider.on = pageItem
                    Component.onCompleted: if (active) settingsSlider.on = pageItem
                    onClicked: root.settingsPageSelected(pageItem.modelData[0])
                }
            }
        }
    }
}
