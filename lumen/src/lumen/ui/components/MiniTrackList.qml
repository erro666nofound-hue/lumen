import QtQuick
import QtQuick.Controls as QQC

// Rail track bên phải Mini Lumen: mỗi track một nút, bấm là phát ngay.
//
// KHÔNG mở ra xem trong track có gì — Mini là chỗ nghe, không phải chỗ quản lý;
// muốn xem từng bài thì đã có cửa sổ lớn. Một tầng, bấm phát luôn.
//
// Bấm một track cũng BẬT LẶP DANH SÁCH luôn: chọn track nghĩa là muốn nghe cả
// track đó, chứ không phải nghe hết rồi im.
//
// QtQuick.Controls PHẢI import có tên miền (as QQC) — xem CLAUDE.md mục 5.
Item {
    id: root

    readonly property int rowHeight: 34
    readonly property real dimmed: 0.6

    // Rail rộng đúng bằng tên track dài nhất, không hơn: mỗi pixel bề ngang ở
    // đây là một pixel bị lấy khỏi khối đang phát. Nút cũng ôm sát chữ chứ
    // không kéo hết bề ngang.
    //
    // Các delegate KHÔNG được lấy bề rộng theo ListView, nếu không thì bề rộng
    // rail vòng lại phụ thuộc chính nó.
    implicitWidth: Math.max(heading.implicitWidth, list.contentItem.childrenRect.width)

    // `MiniSongs` ở đây chỉ dùng để LẤY thứ tự bài của track, không hiện ra —
    // và phải là bridge riêng để không làm đổi track đang mở ở cửa sổ lớn.
    function playTrack(playlistId) {
        MiniSongs.setPlaylist(playlistId)
        const ids = MiniSongs.orderedIds()
        if (ids.length === 0)
            return
        Player.setRepeat("all")
        Player.playPlaylist(playlistId, ids, ids[0])
    }

    Text {
        id: heading

        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        text: "TRACK"
        color: Theme.onSurfaceVariant
        opacity: root.dimmed
        font.pixelSize: Theme.fontSizeSm
        font.family: Theme.fontFamily
        font.letterSpacing: 1
    }

    ListView {
        id: list

        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: heading.bottom
        anchors.topMargin: Theme.spacingSm
        anchors.bottom: parent.bottom
        clip: true
        spacing: Theme.spacingXs
        model: Playlists

        delegate: Rectangle {
            id: row

            required property int playlistId
            required property string name

            readonly property bool active: Player.scopePlaylistId === row.playlistId

            width: label.implicitWidth + Theme.spacingMd * 2
            height: root.rowHeight
            radius: Theme.radiusSm
            color: row.active
                ? Theme.alpha(Theme.primary, 0.18)
                : (hover.hovered ? Theme.alpha(Theme.onSurface, 0.08) : "transparent")
            border.width: 1
            border.color: row.active
                ? Theme.alpha(Theme.primary, 0.45)
                : Theme.alpha(Theme.outline, 0.18)

            Behavior on color {
                ColorAnimation { duration: 120; easing.type: Easing.OutCubic }
            }

            HoverHandler { id: hover }

            Text {
                id: label

                anchors.centerIn: parent
                text: row.name
                color: row.active ? Theme.primary : Theme.onSurface
                font.pixelSize: Theme.fontSizeMd
                font.family: Theme.fontFamily
                elide: Text.ElideRight
            }

            MouseArea {
                anchors.fill: parent
                cursorShape: Qt.PointingHandCursor
                onClicked: root.playTrack(row.playlistId)
            }
        }

        QQC.ScrollBar.vertical: QQC.ScrollBar { policy: QQC.ScrollBar.AsNeeded }
    }
}
