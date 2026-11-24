import QtQuick
import QtQuick.Controls as QQC
import QtQuick.Effects

// Danh sách bài hát trong một track: mỗi bài MỘT HÀNG (ảnh bìa, tên bài, thời
// lượng, tác giả theo đúng thứ tự đó), KHÔNG có hàng tiêu đề cột -- yêu cầu rõ
// ràng của chủ dự án ("không ghi các cái chữ kiểu tên nhạc, thời lượng, tác
// giả thành các cột"). Đây là danh sách, không phải bảng.
//
// Hợp đồng ra ngoài (property/signal) giống hệt TrackGrid.qml để TrackView đổi
// qua lại dễ dàng -- xem file đó để đối chiếu khi cần. Component này KHÔNG gọi
// thẳng Player, chỉ bắn tín hiệu ra ngoài, y hệt TrackGrid.
//
// QtQuick.Controls PHẢI import có tên miền (as QQC) -- xem CLAUDE.md muc 5 và
// chú thích đầu TrackGrid.qml: "import QtQuick.Controls" trần sẽ âm thầm thay
// SearchField của dự án bằng kiểu cùng tên có sẵn trong Qt 6.11.
Item {
    id: root

    // Dữ liệu danh sách -- TrackView truyền TrackSongs vào.
    property var model
    // Trạng thái phát toàn cục, TrackView truyền Player.isPlaying vào (xem
    // TrackGrid.qml về lý do không đọc thẳng context property Player ở đây).
    property bool playerIsPlaying: false
    // Đang ở chế độ chọn nhiều bài (TrackTools bật).
    property bool selectionMode: false

    // Phần gắn NGAY SAU bài cuối cùng và cuộn cùng danh sách. TrackView dùng
    // nó cho các bài đang tải — đặt ngoài ListView thì chúng bị ghim ở đáy
    // khung nhìn chứ không nằm dưới bài cuối.
    property alias footer: list.footer

    // Footer có nội dung hay không. Cần biết, vì danh sách tự ẩn khi không có
    // bài nào — mà footer sống BÊN TRONG nó, nên track rỗng thì hàng "đang
    // tải" không có chỗ nào để tồn tại. Chỗ dùng phải nói ra.
    property bool footerHasContent: false

    // Cho phép kéo thả đổi thứ tự. Chỉ bật khi danh sách đang ở ĐÚNG thứ tự
    // thật của track (TrackSongs.canReorder), không thì "chỗ thả" vô nghĩa.
    property bool reorderable: false
    // Chế độ sửa: nắm chỗ trống của hàng để kéo, tên bài thành ô sửa được.
    property bool editMode: false
    // Bài nào đang được cài về. Một HÀM do nơi dùng đưa xuống (`trackId` →
    // thông tin việc tải), chứ không đọc thẳng `Downloads` ở đây — cùng lý do
    // TrackGrid.qml không đọc `Player`: file này chỉ biết vẽ.
    property var installLookup: null
    // Đổi mỗi nhịp tiến độ. `installLookup` là hàm, gọi nó không tự chạy lại
    // khi có tin mới — cái này mới là thứ kéo binding chạy lại.
    property int downloadTick: 0

    signal playRequested(int trackId)
    signal toggleRequested()
    signal selectionToggled(int trackId)
    signal moveRequested(int from, int to)
    signal renameRequested(int trackId, string title)
    signal menuRequested(int trackId, real sceneX, real sceneY)
    // Xin đổi ảnh bìa của một bài. Danh sách chỉ chuyển tiếp — hộp chọn file
    // do TrackView mở.
    signal coverChangeRequested(int trackId)
    // Gõ Enter trong ô tên: đã lưu xong, xin đóng chế độ sửa.
    signal renameCommitted()

    // Rỗng thì ẩn để nhường chỗ cho EmptyState — nhưng đang tải thì vẫn phải
    // hiện, nếu không hàng chờ ở footer biến mất cùng danh sách.
    visible: root.model && (root.model.count > 0 || root.footerHasContent)

    // Các hằng số dưới đây chỉ có ý nghĩa bên trong component này.
    readonly property int rowHeight: 60
    readonly property int rowSpacing: Theme.spacingXs
    readonly property int scrollBarWidth: 4
    // Bộ từ vựng animation dùng chung toàn dự án -- mọi Behavior/Transition
    // trong file này PHẢI tham chiếu 4 hằng số dưới đây, không tự chế số mới.
    readonly property int animColorMs: 120
    readonly property int animAppearMs: 160
    readonly property int animDisappearMs: 120
    readonly property int animSlideMs: 200
    readonly property int handleWidth: 22
    readonly property int liftShadowDrop: 4

    // -- Trạng thái một cú kéo -------------------------------------------
    // -1 = không kéo gì. `dropIndex` là chỗ sẽ thả, tính lại theo từng nhịp
    // chuột và được vẽ ra bằng một vạch, để người dùng thấy TRƯỚC khi thả.
    property int dragIndex: -1
    property int dropIndex: -1
    property real dragY: 0
    // Vị trí tấm thẻ đang bay, tính trong khung nhìn. Là thuộc tính THƯỜNG chứ
    // không phải binding: lúc thả tay còn phải chạy hoạt ảnh trên chính nó, mà
    // gán vào một thuộc tính đang có binding là phá binding vĩnh viễn.
    property real liftY: 0
    // Khe trống có trượt hay không. Lúc vừa cầm bài lên thì KHÔNG: khe phải
    // hiện ngay tại chỗ bài đó, chứ không bò từ ngoài màn hình vào.
    property bool holeAnimated: false
    // Chính cái hàng đang bị nhấc, để vẽ lại nó bay theo con trỏ.
    property var dragItem: null
    // Khoảng cách từ mép trên hàng tới chỗ ngón tay bấm — giữ nguyên khoảng đó
    // suốt cú kéo thì hàng không bị giật lên khi vừa nhấc.
    property real dragOffset: 0

    readonly property real slotHeight: root.rowHeight + root.rowSpacing

    // Chỗ sẽ thả, tính theo GIỮA tấm thẻ đang cầm — không phải theo con trỏ.
    //
    // Tính theo con trỏ là sai: người ta nắm vào đâu trên hàng cũng được, nên
    // cùng một vị trí thẻ lại ra hai kết quả khác nhau. Tệ nhất là hai vị trí
    // đầu: nắm vào giữa hàng thì con trỏ không bao giờ lên đủ cao để ra số 0.
    function slotAt(viewY) {
        const middle = viewY - root.dragOffset + root.rowHeight / 2 + list.contentY
        const raw = Math.floor(middle / root.slotHeight)
        return Math.max(0, Math.min(list.count - 1, raw))
    }

    // Hàng này phải dịch đi bao nhiêu để chừa khe trống ở chỗ sắp thả.
    function shiftFor(index) {
        if (root.dragIndex < 0 || root.dropIndex < 0 || index === root.dragIndex)
            return 0
        if (root.dragIndex < root.dropIndex && index > root.dragIndex && index <= root.dropIndex)
            return -root.slotHeight
        if (root.dragIndex > root.dropIndex && index >= root.dropIndex && index < root.dragIndex)
            return root.slotHeight
        return 0
    }

    // Thả tay: đóng khe trống và dời bài NGAY (không hoạt ảnh — các hàng đã
    // đứng đúng chỗ từ lúc dãn ra), rồi cho tấm thẻ đang cầm ĐÁP XUỐNG chỗ đó.
    function endDrag() {
        const from = root.dragIndex
        const to = root.dropIndex
        root.dragIndex = -1
        root.dropIndex = -1
        if (from >= 0 && to >= 0 && to !== from)
            root.moveRequested(from, to)
        if (root.dragItem) {
            // Tính đích từ SỐ THỨ TỰ, không đọc `y` của hàng: ngay sau khi dời
            // chỗ, ListView chưa kịp xếp lại nên `y` vẫn là chỗ CŨ — thẻ sẽ bay
            // ngược về chỗ vừa nhấc lên thay vì đáp xuống chỗ mới.
            const landed = to >= 0 ? to : from
            landing.to = landed * root.slotHeight - list.contentY
            landing.start()
        } else {
            root.cancelDrag()
        }
    }

    function cancelDrag() {
        root.dragIndex = -1
        root.dropIndex = -1
        root.dragItem = null
    }

    ListView {

        id: list

        anchors.fill: parent
        // Đang kéo một bài thì danh sách KHÔNG được cuộn. `preventStealing`
        // trên tay nắm vẫn không đủ: đo được cú kéo bị huỷ ngay ở nhịp chuột
        // thứ hai vì Flickable giành mất. Tắt hẳn cuộn trong lúc kéo mới dứt
        // điểm, và tắt xong thì cuộn-bằng-cách-giữ-rồi-kéo ở chỗ khác vẫn
        // nguyên vẹn.
        interactive: root.dragIndex < 0
        // KHÔNG clip: lửa của bài đang phát phủ rộng hơn hàng, clip sẽ cắt cụt
        // tàn lửa đúng ở mép hàng và trông như bị xén.
        clip: false
        model: root.model
        spacing: root.rowSpacing
        // Đệm đáy để hàng cuối cuộn hết lên khỏi hòn đảo phát nhạc (R-1).
        bottomMargin: Theme.islandReserve

        // Thêm/xoá/xếp lại bài phải trượt-mờ, không nhảy cụp -- yêu cầu của
        // chủ dự án cho mọi chuyển động trên màn hình.
        add: Transition {
            NumberAnimation { property: "opacity"; from: 0; to: 1; duration: root.animAppearMs; easing.type: Easing.OutCubic }
        }
        remove: Transition {
            ParallelAnimation {
                NumberAnimation { property: "opacity"; to: 0; duration: root.animDisappearMs; easing.type: Easing.InCubic }
                NumberAnimation { property: "scale"; to: 0.92; duration: root.animDisappearMs; easing.type: Easing.InCubic }
            }
        }
        displaced: Transition {
            NumberAnimation { properties: "y"; duration: root.animSlideMs; easing.type: Easing.OutCubic }
        }
        // Dời chỗ thì các hàng KHÔNG chạy: chúng đã dãn ra đứng sẵn ở chỗ cuối
        // cùng trong lúc kéo. Để `displaced` lo tiếp là chúng chạy lại lần nữa
        // một quãng vô hình, thành ra giật. `displaced` vẫn giữ nguyên cho lúc
        // thêm/xoá bài.
        moveDisplaced: Transition {}

        delegate: TrackSongRow {
            id: row

            // PHẢI khai `required property int index`. TrackSongRow lấy dữ liệu
            // bằng `required property`, và khi delegate dùng required property
            // thì Qt KHÔNG bơm `index`/`model` vào ngữ cảnh nữa — viết
            // `property int rowIndex: index` trần thì mọi hàng đều ra 0, tức là
            // kéo hàng nào cũng hoá thành kéo hàng đầu. Không có cảnh báo nào.
            required property int index

            property int rowIndex: row.index
            number: row.index + 1

            width: list.width
            height: root.rowHeight

            selectionMode: root.selectionMode
            playerIsPlaying: root.playerIsPlaying

            editMode: root.editMode
            reorderable: root.reorderable
            shift: root.shiftFor(row.rowIndex)
            // Thả tay là khe đóng TỨC THÌ: các hàng đã đứng sẵn ở chỗ cuối cùng.
            shiftAnimated: root.dragIndex >= 0
            renaming: root.editMode && row.trackId === (root.model ? root.model.editingTrackId : -1)

            // `downloadTick` đứng trong biểu thức chỉ để làm nó phụ thuộc vào
            // nhịp tiến độ; giá trị của nó không dùng vào việc gì.
            readonly property var installJob: (root.installLookup && root.downloadTick >= 0)
                ? root.installLookup(row.trackId) : ({})

            installing: row.installJob.jobId !== undefined
            installProgress: row.installJob.progress !== undefined
                ? row.installJob.progress : 0

            onRenameRequested: (newTitle) => root.renameRequested(row.trackId, newTitle)
            onCoverChangeRequested: root.coverChangeRequested(row.trackId)
            onRenameCommitted: root.renameCommitted()
            onMenuRequested: (sceneX, sceneY) => root.menuRequested(row.trackId, sceneX, sceneY)

            // Hàng gửi toạ độ SCENE; quy về hệ của danh sách ở đây.
            onDragStarted: (sceneY) => {
                landing.stop()
                // Đặt khe TRƯỚC khi bật hoạt ảnh: gán `dropIndex` làm binding
                // chạy ngay tại đây, nên khe nhảy đúng chỗ, không trượt.
                root.holeAnimated = false
                root.dragIndex = row.rowIndex
                root.dropIndex = row.rowIndex
                root.holeAnimated = true
                root.dragY = list.mapFromItem(null, 0, sceneY).y
                root.dragOffset = root.dragY - (row.y - list.contentY)
                root.liftY = root.dragY - root.dragOffset
                root.dragItem = row
            }
            onDragMoved: (sceneY) => {
                root.dragY = list.mapFromItem(null, 0, sceneY).y
                root.liftY = root.dragY - root.dragOffset
                root.dropIndex = root.slotAt(root.dragY)
            }
            onDragReleased: root.endDrag()
            onDragCanceled: root.cancelDrag()

            onActivated: {
                if (root.selectionMode)
                    root.selectionToggled(trackId)
                else if (isPlaying)
                    root.toggleRequested()
                else
                    root.playRequested(trackId)
            }
            onSelectionToggled: root.selectionToggled(trackId)
        }


        // Khe trống, tối màu, nằm ở chỗ bài sẽ rơi xuống. Các hàng khác dãn ra
        // nhường chỗ cho nó, nên nhìn là biết ngay bài sẽ nằm đâu.
        Rectangle {
            parent: list.contentItem
            visible: root.dragIndex >= 0
            y: root.dropIndex * root.slotHeight

            Behavior on y {
                enabled: root.holeAnimated
                NumberAnimation { duration: root.animSlideMs; easing.type: Easing.OutCubic }
            }
            width: list.width
            height: root.rowHeight
            radius: Theme.radiusSm
            color: Theme.alpha(Theme.shadow, 0.45)
            border.width: 1
            border.color: Theme.alpha(Theme.onSurface, 0.08)
            z: -1
        }

        // Bài đang được NHẤC LÊN: chính hàng đó được vẽ lại, bay theo con trỏ.
        //
        // `hideSource` giấu hàng gốc đi, nên chỗ cũ thành hõm trống — đúng cảm
        // giác nhấc một vật ra khỏi chỗ của nó. Vẽ lại bằng ảnh của hàng thật
        // chứ không dựng một hàng giả: dựng giả là hai chỗ phải sửa mỗi lần
        // hàng đổi hình.
        Item {
            id: lifted

            parent: list
            visible: root.dragItem !== null
            width: root.dragItem ? root.dragItem.width : 0
            height: root.rowHeight
            y: root.liftY
            z: 20
            // Nhấc lên thì to hơn một chút, như đang ở gần mắt hơn.
            scale: root.dragIndex >= 0 ? 1.03 : 1

            Behavior on scale {
                NumberAnimation { duration: root.animAppearMs; easing.type: Easing.OutCubic }
            }

            // Bóng đổ, vẽ bằng một hình mờ lệch xuống dưới chứ KHÔNG dùng
            // MultiEffect: bọc `layer.effect` quanh nền thẻ làm cả thẻ render
            // rỗng — thẻ bay lên trong suốt và hiện nội dung của hàng nằm dưới
            // nó. Đã thấy tận mắt trên ảnh chụp.
            Rectangle {
                anchors.fill: parent
                anchors.topMargin: root.liftShadowDrop
                anchors.leftMargin: Theme.spacingXs
                anchors.rightMargin: Theme.spacingXs
                radius: Theme.radiusSm
                color: Theme.alpha(Theme.shadow, 0.5)
            }

            // Nền ĐỤC: hàng thật vốn trong suốt, nên nếu bay lên mà không có
            // nền riêng thì nhìn xuyên thấy hàng nằm dưới, chữ chồng chữ.
            Rectangle {
                anchors.fill: parent
                radius: Theme.radiusSm
                color: Theme.surface
                border.width: 1
                border.color: Theme.alpha(Theme.primary, 0.45)
            }

            ShaderEffectSource {
                anchors.fill: parent
                sourceItem: root.dragItem
                hideSource: true
                live: true
            }
        }

        // Thẻ đang cầm đáp xuống đúng khe trống rồi mới biến mất.
        NumberAnimation {
            id: landing

            target: root
            property: "liftY"
            duration: root.animSlideMs
            easing.type: Easing.OutCubic

            onFinished: {
                root.cancelDrag()
                root.holeAnimated = false
            }
        }

        QQC.ScrollBar.vertical: QQC.ScrollBar {
            id: vbar

            policy: QQC.ScrollBar.AsNeeded
            width: root.scrollBarWidth
            opacity: vbar.active ? 0.8 : 0

            contentItem: Rectangle {
                implicitWidth: root.scrollBarWidth
                radius: implicitWidth / 2
                color: Theme.alpha(Theme.onSurface, 0.3)
            }
            background: Item {}

            Behavior on opacity {
                NumberAnimation { duration: 150; easing.type: Easing.OutCubic }
            }
        }
    }
}
