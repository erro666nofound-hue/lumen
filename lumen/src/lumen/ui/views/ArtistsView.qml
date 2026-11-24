import QtQuick
import QtQuick.Controls as QQC

import "../components"

// Mục "Nhạc sĩ": mọi kênh có nhạc trong máy, kèm chỗ để tự đánh giá.
//
// Trước đó app CHỈ suy mức yêu thích từ số bài đã tải. Suy thì hay sai — tải 5
// bài của một kênh remix không có nghĩa là thích kênh đó, mà thích một nghệ sĩ
// lắm khi mới tải đúng một bài. Trang này để nói thẳng, và lời nói thẳng đè lên
// phép đoán (xem core/artist_prefs.py).
//
// QtQuick.Controls PHẢI import có tên miền (as QQC) — xem CLAUDE.md mục 5.
Item {
    id: root

    readonly property int contentWidth: Math.min(width - Theme.spacingLg * 2, Theme.contentMaxWidth)

    // Chỗ phải chừa ở mép phải hàng trên cùng cho mục tài khoản — Main.qml đặt
    // nó ở góc trên-phải, và nếu không chừa thì nó nằm đè lên chỗ này.
    property int rightReserve: 0
    readonly property int gutter: (width - contentWidth) / 2
    readonly property int topRowWidth: Math.max(160, contentWidth - rightReserve)
    readonly property int minCardWidth: 200
    readonly property int cardHeight: 76
    readonly property int podiumWidth: 620
    readonly property var plinthHeights: [96, 128, 72]
    readonly property int podiumHeight: 300

    // Tên nhạc sĩ đang mở bảng chi tiết; "" = không mở gì. Nơi dùng (Main) làm
    // mờ nền theo cờ này.
    property string openName: ""
    readonly property bool detailOpen: detail.visible

    // Mở bảng chi tiết SÁT CẠNH ô vừa bấm, rồi kẹp trong cửa sổ để không thò ra
    // ngoài mép — ô ở cột cuối rất dễ đẩy bảng ra khỏi màn.
    function openFor(card) {
        root.openName = card.name
        detail.artistName = card.name
        detail.avatar = card.avatar
        detail.rating = card.rating
        detail.rated = card.rated
        detail.songs = Artists.songsOf(card.name)

        const window = card.Window.window
        const gap = Theme.spacingSm
        const scene = card.mapToItem(null, 0, 0)
        // Mép trái khu nội dung: bảng không được lấn sang thanh bên. Kẹp vào
        // giữa hai mép này chứ không kẹp vào mép cửa sổ — lật sang trái mà kẹp
        // theo cửa sổ thì bảng nằm đè lên thanh bên.
        const leftEdge = root.mapToItem(null, 0, 0).x + gap
        detail.parent = card.Window.contentItem
        let px = scene.x + card.width + gap
        if (px + detail.width > window.width - gap)
            px = scene.x - detail.width - gap
        detail.x = Math.max(leftEdge, Math.min(px, window.width - detail.width - gap))
        detail.y = Math.max(gap, Math.min(scene.y, window.height - detail.height - gap))
        detail.open()
    }

    Text {
        id: heading

        anchors.top: parent.top
        anchors.topMargin: Theme.spacingXl
        anchors.left: parent.left
        anchors.leftMargin: root.gutter
        width: root.topRowWidth
        text: "Nhạc sĩ"
        color: Theme.onSurface
        font.pixelSize: 32
        font.weight: Font.Bold
        font.family: Theme.fontFamily
    }

    Text {
        id: hint

        anchors.top: heading.bottom
        anchors.topMargin: Theme.spacingXs
        anchors.horizontalCenter: parent.horizontalCenter
        width: root.contentWidth
        text: "Xếp theo số bài bạn đã tải. Bấm vào một người để chấm điểm."
        color: Theme.onSurfaceVariant
        font.pixelSize: Theme.fontSizeMd
        font.family: Theme.fontFamily
        wrapMode: Text.WordWrap
    }

    // Lọc trong các nhạc sĩ Lumen đã biết — lọc ngay từng phím, không cần Enter.
    SearchField {
        id: searchField

        anchors.top: hint.bottom
        anchors.topMargin: Theme.spacingLg
        anchors.horizontalCenter: parent.horizontalCenter
        width: root.contentWidth
        placeholder: "Tìm nhạc sĩ"
        // Design R-1 không có ô tìm ở màn này.
        visible: false
        height: 0
        glyph: "search"

        onTextChanged: Artists.setSearch(searchField.text)
        onCleared: Artists.setSearch("")
    }

    GridView {

        bottomMargin: Theme.islandReserve
        id: grid

        anchors.top: searchField.bottom
        anchors.topMargin: Theme.spacingLg
        anchors.bottom: parent.bottom
        anchors.bottomMargin: Theme.spacingLg
        anchors.horizontalCenter: parent.horizontalCenter
        width: root.contentWidth
        model: Artists
        clip: true
        cellWidth: width / Math.max(1, Math.floor(width / root.minCardWidth))
        cellHeight: root.cardHeight

        // Bục top 3 + chữ TẤT CẢ NHẠC SĨ, cuộn cùng lưới (design R-1).
        header: Column {
            width: grid.width
            spacing: Theme.spacingLg
            bottomPadding: Theme.spacingMd

            // Bục KHÔNG dùng Row + anchors: một MouseArea cao theo cột chứa nó
            // từng làm vòng polish() vô tận, đóng băng bố cục CẢ cửa sổ (CB-059).
            // Ba ô đặt tay bằng x/y, chiều cao bục cố định.
            Item {
                id: podium

                readonly property var topArtists: Artists.count >= 0 ? Artists.top(3) : []
                readonly property var order: [1, 0, 2]
                readonly property int stepWidth: (podium.width - Theme.spacingMd * 2) / 3

                visible: podium.topArtists.length > 0
                anchors.horizontalCenter: parent.horizontalCenter
                width: Math.min(root.podiumWidth, grid.width)
                height: root.podiumHeight

                Repeater {
                    model: podium.order

                    Item {
                        id: step

                        required property int modelData
                        required property int index
                        readonly property var who: podium.topArtists.length > step.modelData ? podium.topArtists[step.modelData] : null
                        readonly property bool first: step.modelData === 0
                        readonly property int face: step.first ? 108 : 84
                        // Đủ các trường openFor() đọc, để bấm bục là mở thẻ nhạc sĩ.
                        readonly property string name: step.who ? step.who.name : ""
                        readonly property string avatar: step.who ? step.who.avatar : ""
                        readonly property int rating: step.who ? step.who.rating : 0
                        readonly property bool rated: step.who ? step.who.rated : false

                        x: step.index * (podium.stepWidth + Theme.spacingMd)
                        y: podium.height - stepColumn.implicitHeight
                        width: podium.stepWidth
                        height: stepColumn.implicitHeight
                        opacity: step.who ? 1 : 0

                        Column {
                            id: stepColumn

                            width: parent.width
                            spacing: Theme.spacingSm

                            Rectangle {
                                anchors.horizontalCenter: parent.horizontalCenter
                                width: step.face + 6
                                height: width
                                radius: width / 2
                                color: "transparent"
                                border.width: 3
                                border.color: step.first ? Theme.primary : Theme.alpha(Theme.onSurface, 0.08)
                                scale: stepArea.containsMouse ? 1.04 : 1
                                Behavior on scale { NumberAnimation { duration: Math.max(1, (420) * Theme.motionScale); easing.type: Easing.OutBack; easing.overshoot: Theme.overshoot } }

                                CircleAvatar {
                                    anchors.centerIn: parent
                                    width: step.face
                                    height: step.face
                                    avatar: step.avatar
                                    name: step.name
                                    letterSize: Theme.fontSizeXl
                                }
                            }
                            Text {
                                width: parent.width
                                horizontalAlignment: Text.AlignHCenter
                                text: step.name
                                color: Theme.onSurface
                                font.pixelSize: Theme.fontSizeMd + 0.5
                                font.weight: Font.DemiBold
                                font.family: Theme.fontFamily
                                elide: Text.ElideRight
                            }
                            Text {
                                width: parent.width
                                horizontalAlignment: Text.AlignHCenter
                                text: step.who ? step.who.songCount + " bài" : ""
                                color: Theme.onSurfaceVariant
                                font.pixelSize: Theme.fontSizeSm
                                font.family: Theme.fontFamily
                            }
                            Rectangle {
                                width: parent.width
                                height: root.plinthHeights[step.modelData]
                                radius: Theme.radiusLg
                                color: step.first ? Theme.alpha(Theme.primary, 0.16) : Theme.alpha(Theme.onSurface, 0.045)
                                border.width: 1
                                border.color: Theme.alpha(Theme.onSurface, 0.075)

                                Text {
                                    anchors.centerIn: parent
                                    text: step.modelData + 1
                                    color: step.first ? Theme.primary : Theme.onSurfaceVariant
                                    font.pixelSize: 34
                                    font.weight: Font.Bold
                                    font.family: Theme.fontFamily
                                }
                            }
                        }

                        MouseArea {
                            id: stepArea
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            enabled: step.who !== null
                            onClicked: root.openFor(step)
                        }
                    }
                }
            }

            Text {
                text: "TẤT CẢ NHẠC SĨ"
                color: Theme.onSurfaceVariant
                font.pixelSize: Theme.fontSizeSm
                font.weight: Font.DemiBold
                font.letterSpacing: 1.2
                font.family: Theme.fontFamily
            }
        }
        delegate: Item {
            id: cell

            required property string name
            required property int songCount
            required property int rating
            required property bool rated
            required property string avatar

            width: grid.cellWidth
            height: grid.cellHeight

            ArtistCard {
                anchors.fill: parent
                anchors.margins: Theme.spacingXs
                name: cell.name
                songCount: cell.songCount
                rating: cell.rating
                rated: cell.rated
                avatar: cell.avatar
                selected: root.openName === cell.name

                onClicked: root.openFor(cell)
            }
        }

        QQC.ScrollBar.vertical: QQC.ScrollBar { policy: QQC.ScrollBar.AsNeeded }
    }

    Text {
        anchors.centerIn: grid
        width: root.contentWidth
        horizontalAlignment: Text.AlignHCenter
        visible: Artists.count === 0
        text: searchField.text.length > 0
            ? "Không có nhạc sĩ nào tên như vậy."
            : "Chưa có nhạc sĩ nào — tải vài bài trước đã."
        color: Theme.onSurfaceVariant
        font.pixelSize: Theme.fontSizeMd
        font.family: Theme.fontFamily
        wrapMode: Text.WordWrap
    }

    // Mở rộng danh sách bài làm bảng cao thêm; không kéo lên thì đuôi bảng thò
    // xuống dưới đáy cửa sổ.
    Connections {
        target: detail

        function onHeightChanged() {
            if (!detail.visible || !detail.parent)
                return
            const gap = Theme.spacingSm
            detail.y = Math.max(gap, Math.min(
                detail.y, detail.parent.height - detail.height - gap))
        }
    }

    ArtistDetail {
        id: detail

        onClosed: root.openName = ""
        onRatingPicked: (value) => {
            Artists.setRating(root.openName, value)
            detail.rating = value
            detail.rated = true
        }
        onRatingCleared: {
            Artists.clearRating(root.openName)
            detail.rated = false
        }
    }
}
