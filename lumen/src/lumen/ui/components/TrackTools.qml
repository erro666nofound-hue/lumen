import QtQuick
import QtQuick.Controls as QQC

// Hộp công cụ BÊN TRÁI danh sách track: tải mp3 + bật/tắt chế độ chọn để xoá.
// Đây là hành động của cả track, không phải của một bài, nên tách khỏi danh
// sách — TrackView nối nó vào TrackSongs và Downloads.
//
// Thanh xác nhận xoá nằm NGANG, BÊN PHẢI thùng rác (|N  Xoá  Huỷ|) và cố ý đặt
// NGOÀI hộp kính: nó chỉ hiện lúc đang chọn, nếu nhét vào trong thì hộp phải
// phình ra co lại mỗi lần bật/tắt chế độ chọn, kéo theo cả danh sách bên cạnh.
//
// QtQuick.Controls import có tên miền (as QQC) — Qt 6.11 có kiểu SearchField
// trùng tên component dự án và import module thắng component cùng thư mục.
Item {
    id: root

    property bool selectionMode: false
    property bool editMode: false
    property int selectedCount: 0
    property bool busy: false

    signal downloadRequested(string text)
    signal importRequested()
    signal selectionModeToggled(bool on)
    signal editModeToggled(bool on)
    signal deleteRequested()

    // Popup sống trong lớp phủ của CỬA SỔ, không phải trong cây con này — nó
    // KHÔNG mờ đi hay ẩn theo cha. Đổi sang Thư viện khi bảng tải còn mở thì
    // bảng đó trôi nổi trên màn hình kia. `visible` của Item đã tính cả tổ
    // tiên, nên chỉ cần theo dõi ở đây.
    onVisibleChanged: if (!root.visible) downloadPopup.close()

    // Ô nhập link đang mở hay đóng — property thường, đồng bộ hai chiều với
    // Popup bằng gán tay trong onVisibleChanged (KHÔNG bind ngược lại, gán mệnh
    // lệnh vào property đang có binding sẽ phá binding đó).
    property bool downloadOpen: false

    // Kích thước riêng của hộp công cụ.
    readonly property int buttonSize: 40
    readonly property int downloadFieldWidth: 360
    readonly property int resultsHeight: 260
    // Popup phình ra khi đang tìm hoặc đã có kết quả.
    readonly property bool showingResults: Search.busy || Search.hasSearched
    readonly property int trashGlyphWidth: 15
    readonly property int trashGlyphHeight: 18
    readonly property int actionBarHeight: 32
    readonly property int actionPadding: Theme.spacingSm

    // Từ vựng animation dùng chung của dự án.
    readonly property int colorMs: 120
    readonly property int fadeInMs: 160
    readonly property int fadeOutMs: 120
    readonly property int slideMs: 200

    width: box.width
    height: box.height
    enabled: !root.busy

    GlassPanel {
        id: box

        width: buttonColumn.width + root.actionPadding * 2
        height: buttonColumn.height + root.actionPadding * 2
        padding: root.actionPadding

        Column {
            id: buttonColumn

            spacing: Theme.spacingSm

            // -- Tải mp3 -----------------------------------------------------
            Rectangle {
                id: downloadButton

                width: root.buttonSize
                height: root.buttonSize
                radius: Theme.radiusSm
                color: downloadArea.containsMouse || root.downloadOpen
                    ? Theme.alpha(Theme.onSurface, 0.10) : "transparent"

                Behavior on color {
                    ColorAnimation { duration: root.colorMs; easing.type: Easing.OutCubic }
                }

                Text {
                    anchors.centerIn: parent
                    text: "download"
                    color: root.downloadOpen ? Theme.primary : Theme.onSurface
                    font.pixelSize: Math.max(Theme.iconSize - 2, Math.round((Theme.fontSizeLg) * 1.4))
                    font.family: Theme.iconFont
                    font.variableAxes: ({ "FILL": 1 })
                    // Font biến thiên + distance field vẽ vỡ nét icon trên cửa sổ thật (CB-058).
                    renderType: Text.NativeRendering

                    Behavior on color {
                        ColorAnimation { duration: root.colorMs; easing.type: Easing.OutCubic }
                    }
                }

                MouseArea {
                    id: downloadArea

                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: downloadPopup.opened ? downloadPopup.close() : downloadPopup.open()
                }
            }

            // -- Nhập mp3 có sẵn trên máy -------------------------------------
            // Cửa thứ hai vào track, không đi qua mạng và không tốn hạn mức
            // gói. Bài vào bằng đường này KHÔNG được sao lưu — hàng của nó
            // mang nhãn "máy này" để nói ra điều đó.
            Rectangle {
                id: importButton

                width: root.buttonSize
                height: root.buttonSize
                radius: Theme.radiusSm
                color: importArea.containsMouse
                    ? Theme.alpha(Theme.onSurface, 0.10) : "transparent"

                Behavior on color {
                    ColorAnimation { duration: root.colorMs; easing.type: Easing.OutCubic }
                }

                Text {
                    anchors.centerIn: parent
                    text: "add"
                    color: Theme.onSurface
                    font.pixelSize: Math.max(Theme.iconSize - 2, Math.round((Theme.fontSizeLg) * 1.4))
                    font.family: Theme.iconFont
                    font.variableAxes: ({ "FILL": 1 })
                    // Font biến thiên + distance field vẽ vỡ nét icon trên cửa sổ thật (CB-058).
                    renderType: Text.NativeRendering
                }

                MouseArea {
                    id: importArea

                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.importRequested()
                }
            }

            // -- Sửa: đổi tên bài + kéo đổi thứ tự ----------------------------
            Rectangle {
                id: editButton

                width: root.buttonSize
                height: root.buttonSize
                radius: Theme.radiusSm
                color: editArea.containsMouse || root.editMode
                    ? Theme.alpha(Theme.onSurface, 0.10) : "transparent"

                Behavior on color {
                    ColorAnimation { duration: root.colorMs; easing.type: Easing.OutCubic }
                }

                Text {
                    anchors.centerIn: parent
                    text: "edit"
                    color: root.editMode ? Theme.primary : Theme.onSurface
                    font.pixelSize: Math.max(Theme.iconSize - 2, Math.round((Theme.fontSizeLg) * 1.4))
                    font.family: Theme.iconFont
                    font.variableAxes: ({ "FILL": 1 })
                    // Font biến thiên + distance field vẽ vỡ nét icon trên cửa sổ thật (CB-058).
                    renderType: Text.NativeRendering

                    Behavior on color {
                        ColorAnimation { duration: root.colorMs; easing.type: Easing.OutCubic }
                    }
                }

                MouseArea {
                    id: editArea

                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.editModeToggled(!root.editMode)
                }
            }

            // -- Bật/tắt chế độ chọn để xoá ----------------------------------
            Rectangle {
                id: trashButton

                width: root.buttonSize
                height: root.buttonSize
                radius: Theme.radiusSm
                color: root.selectionMode
                    ? Theme.alpha(Theme.primary, 0.16)
                    : (trashArea.containsMouse ? Theme.alpha(Theme.onSurface, 0.10) : "transparent")

                Behavior on color {
                    ColorAnimation { duration: root.colorMs; easing.type: Easing.OutCubic }
                }

                TrashGlyph {
                    anchors.centerIn: parent
                    // Cao hơn rộng: thùng rác vuông trông như cái nồi.
                    width: root.trashGlyphWidth
                    height: root.trashGlyphHeight
                    color: root.selectionMode ? Theme.primary : Theme.onSurfaceVariant

                    Behavior on color {
                        ColorAnimation { duration: root.colorMs; easing.type: Easing.OutCubic }
                    }
                }

                MouseArea {
                    id: trashArea

                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.selectionModeToggled(!root.selectionMode)
                }
            }
        }
    }

    // -- Thanh |N  Xoá  Huỷ| trượt ra từ thùng rác --------------------------
    TrackToolsActionBar {
        id: actionBar

        z: 5
        anchors.left: box.right
        anchors.leftMargin: Theme.spacingSm
        anchors.verticalCenter: box.verticalCenter
        height: root.actionBarHeight

        count: root.selectedCount
        // Trượt ra khi bật, thu về khi tắt — không bật/tắt visible cụp một cái.
        opacity: root.selectionMode ? 1 : 0
        x: box.width + (root.selectionMode ? Theme.spacingSm : -Theme.spacingLg)
        visible: opacity > 0.01

        onDeleteClicked: root.deleteRequested()
        onCancelClicked: root.selectionModeToggled(false)

        Behavior on opacity {
            NumberAnimation {
                duration: root.selectionMode ? root.fadeInMs : root.fadeOutMs
                easing.type: root.selectionMode ? Easing.OutCubic : Easing.InCubic
            }
        }
        Behavior on x {
            NumberAnimation { duration: root.slideMs; easing.type: Easing.OutCubic }
        }
    }

    QQC.Popup {
        id: downloadPopup

        parent: downloadButton
        x: root.width + Theme.spacingSm
        y: 0
        width: root.downloadFieldWidth
        // Cao thêm khi có kết quả tìm kiếm; lúc chỉ có ô nhập thì gọn như cũ.
        height: Theme.searchFieldHeight
            + (root.showingResults ? root.resultsHeight + Theme.spacingSm : 0)

        Behavior on height {
            NumberAnimation { duration: root.slideMs; easing.type: Easing.OutCubic }
        }
        closePolicy: QQC.Popup.CloseOnPressOutsideParent | QQC.Popup.CloseOnEscape
        padding: 0
        background: Rectangle {
            color: Theme.alpha(Theme.surfaceVariant, 0.96)
            border.width: 1
            border.color: Theme.alpha(Theme.outline, 0.5)
            radius: Theme.radiusMd
        }

        // Popup của style Basic KHÔNG có transition mặc định (đã kiểm chứng
        // trong /usr/lib/qt6/qml/QtQuick/Controls/Basic/Popup.qml) — thiếu hai
        // khối này thì nó bật/tắt cụp một cái.
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

        // `visible` chứ KHÔNG phải `opened`: Popup.opened chỉ thành true SAU KHI
        // animation mở chạy xong, nên nền mờ đi trễ hẳn một nhịp so với ô nhập.
        // `visible` bật ngay lúc gọi open().
        onVisibleChanged: root.downloadOpen = downloadPopup.visible
        // Mở ra là gõ được ngay, không phải bấm thêm phát nữa vào ô chữ.
        // Dùng `onOpened` chứ không phải `onVisibleChanged`: lúc mới `visible`
        // popup chưa nằm hẳn trong scene, focus đặt vào có thể rơi mất.
        onOpened: downloadField.takeFocus()
        onClosed: {
            downloadField.text = ""
            Search.clear()
        }

        SearchField {
            id: downloadField

            width: parent.width
            placeholder: "Dán link, hoặc gõ tên bài để tìm"
            glyph: "download"

            // Dán link thì tải thẳng và đóng; gõ tên bài thì GIỮ popup mở để
            // hiện kết quả ngay bên dưới.
            onSubmitted: (text) => {
                root.downloadRequested(text)
                if (Downloads.looksLikeUrl(text))
                    downloadPopup.close()
            }
            onCleared: {
                Search.clear()
                downloadPopup.close()
            }
        }

        SearchResultList {
            anchors.top: downloadField.bottom
            anchors.topMargin: Theme.spacingSm
            anchors.left: parent.left
            anchors.right: parent.right
            height: root.showingResults ? root.resultsHeight : 0
            visible: height > 1

            // Bấm một kết quả = tải bài đó. URL nên nhánh looksLikeUrl ở
            // TrackView sẽ tự nhận ra và tải vào đúng track đang mở.
            onResultChosen: (url) => {
                root.downloadRequested(url)
                downloadPopup.close()
            }
        }
    }
}
