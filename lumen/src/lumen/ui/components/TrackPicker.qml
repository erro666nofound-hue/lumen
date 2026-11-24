import QtQuick
import QtQuick.Controls as QQC

// Chọn track để tải một bài vào. Dùng chung cho thẻ đề xuất và kết quả tìm
// YouTube ở Thư viện: cả hai đều có URL nhưng chưa biết bỏ vào đâu.
//
// Component KHÔNG tự tải — chỉ bắn `trackChosen(playlistId)`, để nơi dùng gọi
// Downloads.addToPlaylist. Giữ đúng nếp của SearchResultList.qml.
//
// QtQuick.Controls PHẢI import có tên miền (as QQC): Qt 6.11 có sẵn một kiểu
// tên SearchField và import trần sẽ âm thầm thay SearchField của dự án bằng
// của Qt, làm mọi signal handler biến mất. qmllint KHÔNG bắt được lỗi này.
QQC.Popup {
    id: root

    // Tên bài đang chờ được bỏ vào track — chỉ để hiện cho người dùng biết
    // mình đang chọn chỗ cho bài nào.
    property string songTitle: ""

    signal trackChosen(int playlistId)

    readonly property int fadeInMs: 160
    readonly property int fadeOutMs: 120
    readonly property int panelWidth: 260
    readonly property int rowHeight: 36
    readonly property int maxRows: 6

    width: root.panelWidth
    height: Math.min(Playlists.count, root.maxRows) * (root.rowHeight + Theme.spacingXs)
        + header.implicitHeight + Theme.spacingMd * 2 + Theme.spacingSm
    padding: Theme.spacingMd
    // modal: bấm ra ngoài CHẮC CHẮN đóng. Với popup không modal, lớp phủ có
    // nhận được cú bấm hay không còn phụ thuộc popup nào đang trên cùng — và
    // bảng này đã từng kẹt lại vĩnh viễn vì chuyện đó.
    modal: true
    dim: false
    // CloseOnPressOutside, KHÔNG phải OutsideParent: bảng này được mở từ một
    // nút trên thẻ chứ không phải nút bật/tắt nằm ngay dưới nó, nên không có
    // chuyện đóng-rồi-mở-lại. Dùng OutsideParent ở đây là bẫy chết người —
    // cha của nó là CẢ MÀN HÌNH, nên "bấm ra ngoài cha" không bao giờ xảy ra
    // và bảng kẹt lại vĩnh viễn (đã xảy ra thật).
    closePolicy: QQC.Popup.CloseOnPressOutside | QQC.Popup.CloseOnEscape

    background: Rectangle {
        // ĐÚNG công thức kính của cửa sổ (QĐ-037/QĐ-039), không phải một tấm
        // riêng. Hộp này KHÔNG phải menu thả xuống: nó mở giữa trang Thư viện,
        // modal, và người dùng ĐỌC một danh sách track trong đó — cùng họ với
        // ColorPicker/WallpaperPicker, không cùng họ với ContextMenu. 0.96 cũ
        // chỉ để lọt ~1.6% ảnh nền, trong khi cả app để lọt 55%.
        color: Theme.alpha(Theme.surface,
                           Theme.wallpaper !== "" ? Theme.wallpaperSurfaceAlpha
                                                  : Theme.surfaceAlpha)
        border.width: 1
        // Kính mỏng đi thì cái viền là thứ DUY NHẤT còn nói "hộp hết ở đây".
        border.color: Theme.alpha(Theme.outline, 0.60)
        radius: Theme.radiusMd
    }

    // Popup style Basic KHÔNG có transition mặc định — thiếu hai khối này thì
    // bảng bật/tắt cụp một cái.
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

    // Đường thoát nhìn thấy được, không phụ thuộc vào closePolicy.
    Text {
        id: closeButton

        anchors.right: parent.right
        anchors.top: parent.top
        text: "close"
        color: closeHover.hovered ? Theme.onSurface : Theme.onSurfaceVariant
        font.pixelSize: Math.max(Theme.iconSize - 2, Math.round((Theme.fontSizeMd) * 1.4))
        font.family: Theme.iconFont
        font.variableAxes: ({ "FILL": 1 })
        // Font biến thiên + distance field vẽ vỡ nét icon trên cửa sổ thật (CB-058).
        renderType: Text.NativeRendering

        Behavior on color {
            ColorAnimation { duration: 120; easing.type: Easing.OutCubic }
        }

        HoverHandler { id: closeHover }

        MouseArea {
            anchors.fill: parent
            anchors.margins: -Theme.spacingXs
            cursorShape: Qt.PointingHandCursor
            onClicked: root.close()
        }
    }

    Text {
        id: header

        anchors.left: parent.left
        anchors.right: closeButton.left
        anchors.rightMargin: Theme.spacingSm
        anchors.top: parent.top
        text: Playlists.count > 0 ? "Tải vào track nào?" : "Chưa có track nào — tạo một track trước."
        color: Theme.onSurfaceVariant
        font.pixelSize: Theme.fontSizeSm
        font.family: Theme.fontFamily
        wrapMode: Text.WordWrap
        elide: Text.ElideRight
        maximumLineCount: 2
    }

    // Lớp kính THỨ HAI, đúng chỗ đọc chữ — QĐ-037. Khung hộp để sáng cho hợp
    // với cả app; danh sách track thì cần một lớp nữa, không thì trang Thư viện
    // phía sau (đã mờ nhưng vẫn còn lốm đốm) hiện lên ngay dưới tên track.
    Rectangle {
        anchors.fill: list
        anchors.margins: -Theme.spacingXs
        radius: Theme.radiusMd
        color: Theme.alpha(Theme.surface, 0.45)
        // Chưa có track nào thì danh sách cao 0 — đừng vẽ một vệt kính trống.
        visible: Playlists.count > 0
    }

    ListView {
        id: list

        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: header.bottom
        anchors.topMargin: Theme.spacingSm
        anchors.bottom: parent.bottom
        model: Playlists
        clip: true
        spacing: Theme.spacingXs

        delegate: Rectangle {
            id: row

            required property string name
            required property int playlistId
            required property int trackCount

            width: list.width
            height: root.rowHeight
            radius: Theme.radiusSm
            color: hover.hovered ? Theme.alpha(Theme.primary, 0.16) : "transparent"

            Behavior on color {
                ColorAnimation { duration: 120; easing.type: Easing.OutCubic }
            }

            HoverHandler { id: hover }

            Text {
                anchors.left: parent.left
                anchors.leftMargin: Theme.spacingSm
                anchors.right: countLabel.left
                anchors.rightMargin: Theme.spacingSm
                anchors.verticalCenter: parent.verticalCenter
                text: "♪  " + row.name
                color: hover.hovered ? Theme.primary : Theme.onSurface
                font.pixelSize: Theme.fontSizeMd
                font.family: Theme.fontFamily
                elide: Text.ElideRight
            }

            Text {
                id: countLabel

                anchors.right: parent.right
                anchors.rightMargin: Theme.spacingSm
                anchors.verticalCenter: parent.verticalCenter
                text: row.trackCount
                color: Theme.onSurfaceVariant
                font.pixelSize: Theme.fontSizeSm
                font.family: Theme.fontFamily
            }

            MouseArea {
                anchors.fill: parent
                cursorShape: Qt.PointingHandCursor
                onClicked: {
                    root.trackChosen(row.playlistId)
                    root.close()
                }
            }
        }
    }
}
