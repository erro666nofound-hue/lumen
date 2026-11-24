import QtQuick

// Hàng chip chọn cách sắp xếp các bài trong một track.
//
// Không gọi thẳng TrackSongs.setSort(...) — chỉ bắn `sortRequested` ra ngoài,
// nơi dùng (TrackView) tự nối vào bridge. Cùng lối với LibrarySortBar.
//
// "Thứ tự của bạn" đứng đầu vì nó là mặc định, và là thứ tự DUY NHẤT cho phép
// kéo thả đổi chỗ — bấm chip khác là khoá kéo thả lại (xem TrackSongs.canReorder).
Row {
    id: root

    property string sortKey: "custom"
    property bool sortDescending: false

    signal sortRequested(string key)

    spacing: Theme.spacingSm

    Repeater {
        model: [
            { "key": "custom", "label": "Thứ tự của bạn" },
            { "key": "title", "label": "Tên" },
            { "key": "artist", "label": "Nghệ sĩ" },
            { "key": "duration", "label": "Thời lượng" },
            { "key": "added", "label": "Mới thêm" }
        ]

        SortChip {
            required property var modelData

            anchors.verticalCenter: parent.verticalCenter
            label: modelData.label
            active: root.sortKey === modelData.key
            descending: root.sortDescending

            onClicked: root.sortRequested(modelData.key)
        }
    }
}
