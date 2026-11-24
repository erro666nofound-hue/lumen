import QtQuick
import QtQuick.Controls as QQC

// "Nhạc của tôi": mọi bài từng tải, KỂ CẢ bài đã xoá khỏi máy.
//
// Lưới thẻ ngang (ảnh | tên) thay cho danh sách một dòng: sổ này dài, thẻ ngang
// cho nhiều bài lên cùng một màn mà vẫn có ảnh. Bấm một thẻ thì bảng chi tiết
// NỔI lên ngay cạnh thẻ đó — chèn bảng vào giữa lưới sẽ đẩy mọi thẻ bên dưới
// nhảy chỗ và làm chính bài đang xem trôi khỏi tầm nhìn.
//
// Ảnh là URL https theo video id, không phải file trên máy: bài đã xoá thì
// không còn bìa nào trên đĩa (xem HistoryBridge.ThumbnailRole).
Column {
    id: root

    signal addRequested(string url, string title)
    // Kèm item mỏ neo (để đặt bảng chọn track ngay cạnh) và thông tin bài đã
    // biết sẵn (để hàng "đang tải" hiện đủ ngay, không chờ downloader dò).
    signal addRequestedBeside(string url, string title, var anchor, var facts)
    signal previewRequested(string videoId)

    // Nơi dùng (Main) làm mờ nền theo cờ này.
    readonly property bool detailOpen: detail.visible

    // Bảng chọn track đã đóng -> bảng chi tiết được phép tự đóng trở lại.
    function releaseHold() { detail.holdOpen = false }

    spacing: Theme.spacingSm

    // Thẻ đủ rộng để đọc được tên, và số cột suy ra từ đó — không đặt cứng số
    // cột, vì cửa sổ thu nhỏ được (xem "Lumen thu gọn" trong ROADMAP).
    // Thẻ hẹp lại khi cột nội dung hẹp: giữ 230px thì chỉ còn một cột và mục
    // "Nhạc của tôi" dài lê thê.
    readonly property int narrowBelow: 520
    readonly property int cardMinWidth: (root.width > 0 && root.width < root.narrowBelow) ? 180 : 230
    readonly property int cardSpacing: Theme.spacingSm
    readonly property int columns: Math.max(
        1, Math.floor((root.width + root.cardSpacing) / (root.cardMinWidth + root.cardSpacing)))
    readonly property int cardWidth: Math.floor(
        (root.width - root.cardSpacing * (root.columns - 1)) / root.columns)

    // Bài đang mở bảng chi tiết; -1 = không mở gì.
    property int expandedIndex: -1
    readonly property int rowCount: Math.ceil(History.count / root.columns)
    readonly property var expandedEntry: (root.expandedIndex >= 0
        && root.expandedIndex < History.count) ? History.get(root.expandedIndex) : null

    // Đổi số cột (kéo cửa sổ) làm chỉ số ô đổi nghĩa -- đóng bảng lại cho chắc,
    // thay vì để nó trỏ sang bài khác.
    onColumnsChanged: detail.close()

    Text {
        visible: History.count === 0
        text: "Chưa tải bài nào."
        color: Theme.onSurfaceVariant
        font.pixelSize: Theme.fontSizeSm
        font.family: Theme.fontFamily
    }

    Repeater {
        model: root.rowCount

        // Một hàng thẻ, và ngay dưới nó là bảng chi tiết nếu bài đang mở nằm
        // trong hàng này.
        Column {
            id: gridRow

            required property int index

            width: root.width
            spacing: root.cardSpacing

            Row {
                spacing: root.cardSpacing

                Repeater {
                    model: root.columns

                    HistoryCard {
                        id: card

                        required property int index

                        readonly property int flatIndex: gridRow.index * root.columns + card.index
                        readonly property var entry: card.flatIndex < History.count
                            ? History.get(card.flatIndex) : null

                        visible: card.entry !== null
                        width: root.cardWidth
                        title: card.entry ? card.entry.title : ""
                        artist: card.entry ? card.entry.artist : ""
                        thumbnail: card.entry ? card.entry.thumbnail : ""
                        stillOwned: card.entry ? card.entry.stillOwned : false
                        selected: root.expandedIndex === card.flatIndex

                        onClicked: {
                            if (root.expandedIndex === card.flatIndex) {
                                detail.close()
                                return
                            }
                            root.expandedIndex = card.flatIndex
                            detail.openBeside(card)
                        }
                    }
                }
            }
        }
    }

    // MỘT bảng nổi dùng chung cho cả lưới, không phải mỗi hàng một cái: chỉ
    // xem được một bài tại một thời điểm, và Popup nằm trong lớp phủ của cửa sổ
    // nên nó không thuộc về hàng nào cả.
    HistoryDetail {
        id: detail

        title: root.expandedEntry ? root.expandedEntry.title : ""
        artist: root.expandedEntry ? root.expandedEntry.artist : ""
        thumbnail: root.expandedEntry ? root.expandedEntry.thumbnail : ""
        url: root.expandedEntry ? root.expandedEntry.url : ""
        videoId: root.expandedEntry ? root.expandedEntry.sourceId : ""
        active: root.expandedEntry !== null
            && Player.previewVideoId === root.expandedEntry.sourceId && Player.isPlaying
        loading: root.expandedEntry !== null
            && Player.previewVideoId === root.expandedEntry.sourceId && Player.previewBusy

        onClosed: root.expandedIndex = -1
        onPreviewRequested: if (root.expandedEntry) root.previewRequested(root.expandedEntry.sourceId)
        onAddRequested: if (root.expandedEntry) {
            // Bảng chọn track phải nằm CẠNH bảng chi tiết chứ không nổi lơ lửng
            // giữa lưới, và bảng chi tiết phải Ở LẠI trong lúc chọn — nếu không
            // người dùng mất luôn ngữ cảnh bài mình vừa bấm.
            detail.holdOpen = true
            root.addRequestedBeside(
                root.expandedEntry.url, root.expandedEntry.title, detail.contentItem, {
                    "title": root.expandedEntry.title,
                    "artist": root.expandedEntry.artist,
                    "durationText": "",
                    "thumbnail": root.expandedEntry.thumbnail,
                })
        }

        // Giữ mở trong lúc bảng chọn track đang bật: cú bấm lên bảng đó là "bấm
        // ra ngoài" với bảng này, và nếu không giữ thì nó tự đóng mất.
        property bool holdOpen: false
        closePolicy: detail.holdOpen
            ? QQC.Popup.CloseOnEscape
            : (QQC.Popup.CloseOnPressOutside | QQC.Popup.CloseOnEscape)

        // Mở cạnh thẻ vừa bấm, rồi kẹp lại trong cửa sổ để không thò ra ngoài
        // mép — thẻ ở cột cuối hoặc gần đáy màn hình rất dễ đẩy bảng ra khỏi màn.
        function openBeside(card) {
            const scene = card.mapToItem(null, 0, 0)
            const win = card.Window.window
            const gap = Theme.spacingSm
            let px = scene.x + card.width + gap
            if (px + detail.width > win.width - gap)
                px = scene.x - detail.width - gap        // không đủ chỗ bên phải thì sang trái
            let py = scene.y + card.height / 2 - detail.height / 2
            py = Math.max(gap, Math.min(py, win.height - detail.height - gap))
            detail.parent = card.Window.contentItem
            detail.x = Math.max(gap, px)
            detail.y = py
            detail.open()
        }
    }
}
