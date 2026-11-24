import QtQuick
import QtQuick.Controls as QQC

// Một hàng của trang khám phá: tên nghệ sĩ rồi một dải RecommendCard cuộn
// ngang — dùng trong Repeater lặp qua model Discovery (một hàng/nghệ sĩ).
//
// Đọc Player.previewVideoId/previewBusy/isPlaying trực tiếp để tính
// active/loading cho từng thẻ, giống PodiumRow — RecommendCard không tự biết
// videoId nào Player đang phát. KHÔNG tự gọi Player/Downloads, chỉ bắn
// previewRequested(videoId)/addRequested(url, title, anchor) ra ngoài, nơi dùng
// (LibraryView) nối vào bridge thật.
//
// QtQuick.Controls PHẢI import có tên miền (as QQC) — xem CLAUDE.md mục 5.
Column {
    id: root

    property string artist: ""
    // Danh sách object {videoId, title, uploader, durationText, url, thumbnail, ...}.
    property var songs: []

    signal previewRequested(string videoId)
    // Kèm chính thẻ vừa bấm, để nơi dùng đặt bảng chọn track ngay cạnh nó.
    signal addRequested(string url, string title, var anchor)

    spacing: Theme.spacingSm

    // Thẻ nhỏ lại khi hàng hẹp, để vẫn thấy được vài thẻ chứ không phải một
    // thẻ rưỡi. Đo theo bề ngang của chính hàng này.
    readonly property int narrowBelow: 520
    readonly property int cardWidth: (root.width > 0 && root.width < root.narrowBelow) ? 140 : 168
    readonly property int fadeMs: 240

    opacity: 0
    Component.onCompleted: root.opacity = 1

    Behavior on opacity {
        NumberAnimation { duration: root.fadeMs; easing.type: Easing.OutCubic }
    }

    SectionLabel { text: root.artist }

    // Thẻ đo, không vẽ ra: chiều cao thẻ phụ thuộc bề rộng (ảnh 16:9) và số
    // dòng tên bài, nên đặt cứng một con số là chừa lại cả khoảng trống chết —
    // bản đầu để 236px trong khi thẻ chỉ cao ~150px, mỗi hàng thừa ra gần
    // 90px. Tên hai dòng là trường hợp cao nhất (maximumLineCount: 2).
    RecommendCard {
        id: probe

        width: root.cardWidth
        visible: false
        title: "Đo\nhai dòng"
        uploader: "Đo"
        durationText: "0:00"
    }

    ListView {
        id: list

        width: root.width
        height: probe.height
        orientation: ListView.Horizontal
        spacing: Theme.spacingMd
        clip: true
        model: root.songs

        delegate: RecommendCard {
            id: card

            required property var modelData

            width: root.cardWidth
            title: card.modelData.title
            uploader: card.modelData.uploader
            durationText: card.modelData.durationText
            thumbnail: card.modelData.thumbnail
            active: Player.previewVideoId === card.modelData.videoId && Player.isPlaying
            loading: Player.previewVideoId === card.modelData.videoId && Player.previewBusy

            onPreviewRequested: root.previewRequested(card.modelData.videoId)
            onAddRequested: root.addRequested(
                card.modelData.url, card.modelData.title, card)
        }

        QQC.ScrollBar.horizontal: QQC.ScrollBar { policy: QQC.ScrollBar.AsNeeded }
    }
}
