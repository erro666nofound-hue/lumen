import QtQuick
import QtQuick.Effects

// Một hàng trong danh sách bài của track: [ô tick] ảnh bìa · tên · thời lượng ·
// tác giả. Tách khỏi TrackSongList chỉ vì độ dài file.
//
// Delegate nằm ở FILE RIÊNG thì không còn tự thấy `model.*` nữa — Qt 6 bắt phải
// khai báo `required property` đúng tên từng role, và ListView sẽ tự bơm vào.
// Thiếu một cái là hàng đó im lặng trống trơn, không có cảnh báo.
Item {
    id: row

    required property int trackId
    required property string title
    required property string artist
    required property string durationText
    required property string coverPath
    required property bool isPlaying
    required property bool selected
    // Bài nhập từ mp3 trên máy: không có link, nên đồng bộ KHÔNG mang nó đi
    // được (F-5a′). Hàng phải nói ra, không được im.
    required property bool localOnly
    // Ngày bài vào thư viện, đã thành chữ ("hôm nay", "3 ngày"). Hiện thường
    // trực: chip "Mới thêm" sắp theo đúng con số này, không hiện ra thì bấm
    // chip xong người dùng không có căn cứ nào để biết nó sắp đúng hay sai.
    required property string addedText
    // Số lần nghe (design R-1: cột "N lần").
    required property int playCount
    // Số thứ tự trong danh sách; TrackSongList gán.
    property int number: 0

    // Do nơi dùng truyền vào (không phải role của model).
    property bool selectionMode: false
    property bool playerIsPlaying: false
    // Chế độ sửa: nắm chỗ trống của hàng để kéo, tên bài thành ô sửa được.
    property bool editMode: false
    property bool reorderable: false
    // Được nhắm để đổi tên ngay (menu chuột phải), khác với chỉ bật chế độ sửa.
    property bool renaming: false
    // Bài này ĐANG được cài về (đồng bộ mang cái vỏ về trước, mp3 theo sau; hay
    // nút "Tải lại N bài thiếu file"). Hàng đã nằm sẵn trong danh sách, nên nó
    // không mọc thêm một hàng "đang tải" ở cuối như bài dán link — nó mặc đúng
    // bộ đồ của PendingSongRow ngay tại chỗ.
    property bool installing: false
    property real installProgress: 0
    // Đẩy hàng lên/xuống để MỞ KHE TRỐNG khi đang kéo một bài khác.
    //
    // Dùng transform chứ không ghi vào `y`: `y` do ListView quản, ghi đè vào là
    // đánh nhau với bố cục của nó.
    property real shift: 0
    // Trượt hay nhảy tức thì. Không tự suy từ `shift`: lúc Behavior xét
    // `enabled` thì `shift` vẫn đang mang giá trị CŨ, nên mọi phép thử dựa
    // trên nó đều ra "đang kéo" kể cả khi vừa thả tay.
    property bool shiftAnimated: true

    // Lề trong của nhãn "máy này" — số riêng của component này, không dùng
    // chung nên không lên Theme.
    readonly property int badgePadding: 6

    transform: Translate { y: row.shift }

    // Chỉ trượt trong LÚC kéo. Khi thả tay, khe trống phải đóng lại tức thì:
    // các hàng lúc đó đã đứng sẵn ở chỗ cuối cùng rồi, cho chúng chạy thêm lần
    // nữa là thừa và trông như giật hai nhịp.
    Behavior on shift {
        enabled: row.shiftAnimated
        NumberAnimation { duration: row.animSlideMs; easing.type: Easing.OutCubic }
    }

    signal activated()
    signal selectionToggled()
    signal renameRequested(string title)
    signal menuRequested(real sceneX, real sceneY)
    // Toạ độ SCENE, để danh sách tự quy về hệ của nó — hàng không biết gì về
    // vị trí cuộn của danh sách.
    // Bấm vào ảnh bìa lúc đang sửa = xin đổi bìa. Hàng KHÔNG tự mở hộp chọn
    // file: nó không biết gì về đĩa, chỉ báo ra cho TrackView.
    signal coverChangeRequested()
    // Gõ Enter trong ô tên = lưu XONG và thoát luôn chế độ sửa.
    signal renameCommitted()

    signal dragStarted(real sceneY)
    signal dragMoved(real sceneY)
    signal dragReleased()
    signal dragCanceled()

    // Kích thước và nhịp animation của một hàng. Trước đây nằm ở TrackSongList
    // (khi hàng còn là delegate nội tuyến); giờ hàng là component riêng nên
    // chúng thuộc về đây.
    readonly property int checkboxSize: 20
    readonly property int coverSize: 44
    readonly property int durationWidth: 56
    readonly property int artistWidth: 160
    readonly property int addedWidth: 84
    readonly property int moreSize: 32
    readonly property int numberWidth: 28
    readonly property int playingBarWidth: 3
    readonly property real playingBarHeightFactor: 0.6

    readonly property int animColorMs: 120
    readonly property int animAppearMs: 160
    readonly property int animDisappearMs: 120
    readonly property int animSlideMs: 200

    // Lửa hạt cho bài đang phát. Khai báo TRƯỚC nền hàng để nằm phía dưới,
    // và phủ rộng hơn hàng để tàn lửa liếm ra ngoài mép.
    FlameAura {
        anchors.fill: parent
        anchors.margins: -Theme.spacingSm
        running: row.isPlaying
    }

        // Nền hàng: trong suốt bình thường, mờ nhẹ khi hover, tô màu chính
        // khi đang phát. Không dùng border như TrackCard -- danh sách dày
        // hàng, viền sẽ rối mắt.
        // Lớp ĐỤC cho bài đang phát. Bắt buộc phải đục: lửa nằm phía dưới hàng,
        // nếu nền hàng trong suốt thì thấy hạt lửa XUYÊN QUA bài nhạc. Chủ dự
        // án muốn lửa chỉ là quầng bao quanh, không lộ vào trong.
        Rectangle {
            anchors.fill: parent
            radius: Theme.radiusMd
            visible: isPlaying
            color: Theme.surface
        }

        Rectangle {
            anchors.fill: parent
            radius: Theme.radiusMd
            color: isPlaying
                ? Theme.alpha(Theme.primary, 0.12)
                : (rowHover.hovered ? Theme.alpha(Theme.onSurface, 0.06) : "transparent")

            Behavior on color {
                ColorAnimation { duration: row.animColorMs; easing.type: Easing.OutCubic }
            }
        }

        // Dấu hiệu "đang phát": vạch dọc mảnh sát mép trái -- kín đáo hơn
        // huy hiệu ♪ của TrackCard, hợp dáng danh sách hơn.
        Rectangle {
            id: playingBar

            anchors.left: parent.left
            anchors.verticalCenter: parent.verticalCenter
            width: row.playingBarWidth
            height: row.height * row.playingBarHeightFactor
            radius: width / 2
            color: Theme.primary
            opacity: isPlaying ? 1 : 0
            visible: playingBar.opacity > 0.01

            Behavior on opacity {
                NumberAnimation {
                    duration: isPlaying ? row.animAppearMs : row.animDisappearMs
                    easing.type: isPlaying ? Easing.OutCubic : Easing.InCubic
                }
            }
        }

        // Ô tick chọn bài -- mờ dần ra/vào theo chế độ chọn thay vì cụp
        // tắt, để không giật khi bật/tắt TrackTools. Bộ màu copy nguyên
        // từ TrackCard.qml (đã chỉnh để đọc được trên cả nền sáng lẫn tối).
        Rectangle {
            id: checkbox

            anchors.left: parent.left
            anchors.leftMargin: Theme.spacingSm
            anchors.verticalCenter: parent.verticalCenter
            width: row.checkboxSize
            height: row.checkboxSize
            radius: Theme.radiusSm
            color: selected === true ? Theme.primary : Theme.alpha(Theme.shadow, 0.55)
            border.width: selected === true ? 0 : 1
            border.color: Theme.alpha(Theme.onSurface, 0.85)
            opacity: row.selectionMode ? 1 : 0
            visible: checkbox.opacity > 0.01

            Behavior on opacity {
                NumberAnimation {
                    duration: row.selectionMode ? row.animAppearMs : row.animDisappearMs
                    easing.type: row.selectionMode ? Easing.OutCubic : Easing.InCubic
                }
            }

            Behavior on color {
                ColorAnimation { duration: row.animColorMs; easing.type: Easing.OutCubic }
            }

            Text {
                visible: selected === true
                anchors.centerIn: parent
                text: "check"
                color: Theme.onPrimary
                font.pixelSize: Math.max(Theme.iconSize - 2, Math.round((Theme.fontSizeSm) * 1.4))
                font.family: Theme.iconFont
                font.variableAxes: ({ "FILL": 1 })
                // Font biến thiên + distance field vẽ vỡ nét icon trên cửa sổ thật (CB-058).
                renderType: Text.NativeRendering
            }

            MouseArea {
                // z cao hơn MouseArea toàn hàng bên dưới -- nuốt sự kiện
                // tại đây, không để lọt xuống thành "bấm hàng = phát bài".
                anchors.fill: parent
                z: 10
                cursorShape: Qt.PointingHandCursor
                onClicked: row.selectionToggled()
            }
        }

        // Vòng 3 R-1: không còn tay nắm ⠿ — trong chế độ sửa, nắm vào CHỖ TRỐNG
        // nào của hàng cũng kéo được. Khai TRƯỚC khối tên bài nên ô sửa tên và
        // nút đổi ảnh bìa vẫn nằm trên, bấm vào đó là sửa chứ không kéo. Chỉ
        // nhấc hàng lên khi chuột đã đi quá ngưỡng kéo: bấm một cái rồi thả không
        // làm hàng nảy lên.
        MouseArea {
            id: dragArea

            property real pressSceneY: 0
            property bool dragging: false

            anchors.fill: parent
            enabled: row.editMode && row.reorderable
            hoverEnabled: true
            cursorShape: dragArea.dragging ? Qt.ClosedHandCursor : Qt.OpenHandCursor
            // BẮT BUỘC: danh sách là một Flickable, và Flickable sẽ cướp
            // cú giữ-rồi-kéo để cuộn ngay khi đi quá ngưỡng. Không chặn ở
            // đây thì kéo bài hoá thành cuộn danh sách — đúng lỗi đã gặp.
            preventStealing: true

            onPressed: (mouse) => {
                dragArea.pressSceneY = row.mapToItem(null, 0, mouse.y).y
                dragArea.dragging = false
            }
            onPositionChanged: (mouse) => {
                if (!dragArea.pressed)
                    return
                const sceneY = row.mapToItem(null, 0, mouse.y).y
                if (!dragArea.dragging) {
                    if (Math.abs(sceneY - dragArea.pressSceneY) < Qt.styleHints.startDragDistance)
                        return
                    dragArea.dragging = true
                    row.dragStarted(dragArea.pressSceneY)
                }
                row.dragMoved(sceneY)
            }
            onReleased: {
                if (dragArea.dragging)
                    row.dragReleased()
                dragArea.dragging = false
            }
            onCanceled: {
                if (dragArea.dragging)
                    row.dragCanceled()
                dragArea.dragging = false
            }
        }

        // Tác giả -- bề rộng cố định, canh mép phải hàng.
        // Design R-1: nút "⋯" cuối hàng, hiện khi rê chuột; mở cùng menu với chuột phải.
        IconButton {
            id: moreButton
            z: 2
            anchors.right: parent.right
            anchors.rightMargin: Theme.spacingSm
            anchors.verticalCenter: parent.verticalCenter
            width: row.moreSize
            height: row.moreSize
            opacity: rowHover.hovered && !row.editMode ? 1 : 0
            enabled: !row.editMode
            glyph: "more_horiz"
            onClicked: {
                const at = moreButton.mapToItem(null, moreButton.width / 2, moreButton.height)
                row.menuRequested(at.x, at.y)
            }
        }

        Text {
            id: artistLabel

            // Nghệ sĩ nay nằm dưới tên bài (R-1); cột này chỉ giữ chỗ cho nút ⋯.
            visible: false
            anchors.right: moreButton.left
            anchors.rightMargin: 0
            anchors.verticalCenter: parent.verticalCenter
            width: 0
            text: artist
            color: Theme.onSurfaceVariant
            font.pixelSize: Theme.fontSizeSm
            font.family: Theme.fontFamily
            elide: Text.ElideRight
        }

        // Ngày thêm -- đứng giữa tên bài và thời lượng.
        Text {
            id: addedLabel

            anchors.right: durationLabel.left
            anchors.rightMargin: Theme.spacingMd
            anchors.verticalCenter: parent.verticalCenter
            width: row.addedWidth
            horizontalAlignment: Text.AlignRight
            // R-1 hiện số lần nghe; riêng khi đang xếp "Mới thêm" thì hiện ngày
            // thêm — không thì bấm chip xong không có căn cứ thấy nó xếp đúng.
            text: TrackSongs.sortKey === "added" ? row.addedText : row.playCount + " lần"
            color: Theme.onSurfaceVariant
            font.pixelSize: Theme.fontSizeSm
            font.family: Theme.fontFamily
            elide: Text.ElideRight
        }

        // Thời lượng -- bề rộng cố định, chữ số canh phải trong ô của nó.
        Text {
            id: durationLabel

            anchors.right: artistLabel.left
            anchors.rightMargin: Theme.spacingMd
            anchors.verticalCenter: parent.verticalCenter
            width: row.durationWidth
            horizontalAlignment: Text.AlignRight
            text: durationText
            color: Theme.onSurfaceVariant
            font.pixelSize: Theme.fontSizeSm
            font.family: Theme.fontFamily
        }

        // Ảnh bìa + tên bài đi chung một khối để chỉ cần MỘT Behavior
        // trượt khi ô tick hiện/ẩn -- cả cụm dịch sang phải cùng nhau.
        // Số thứ tự; bài đang phát thì thành ba vạch sóng nhạc (design R-1).
        Item {
            x: Theme.spacingSm + (row.selectionMode ? row.checkboxSize + Theme.spacingSm : 0)
            width: row.numberWidth
            height: parent.height

            Text {
                anchors.centerIn: parent
                visible: !isPlaying
                text: row.number
                color: Theme.onSurfaceVariant
                font.pixelSize: Theme.fontSizeSm + 1
                font.family: Theme.fontFamily
            }
            EqualizerBars {
                anchors.centerIn: parent
                visible: isPlaying
                playing: row.playerIsPlaying
                barCount: 3
                barWidth: 3
                gap: 2
                height: 14
            }
        }

        Item {
            id: titleRow

            anchors.left: parent.left
            anchors.leftMargin: Theme.spacingSm + row.numberWidth + Theme.spacingSm
                + (row.selectionMode ? row.checkboxSize + Theme.spacingSm : 0)
            anchors.right: addedLabel.left
            anchors.rightMargin: Theme.spacingMd
            anchors.verticalCenter: parent.verticalCenter
            height: row.coverSize

            Behavior on anchors.leftMargin {
                NumberAnimation { duration: row.animSlideMs; easing.type: Easing.OutCubic }
            }

            // Ảnh bìa vuông nhỏ, bo góc thật (clip theo mặt nạ). Cấu trúc
            // coverContainer -> coverFrame + coverMask copy nguyên từ
            // TrackCard.qml/NowPlaying.qml: coverFrame và coverMask PHẢI
            // cùng cấp bên trong coverContainer, lệch ra ngoài là layer
            // render rỗng trắng không cảnh báo gì -- xem chú thích đầy đủ
            // ở TrackCard.qml, bug này đã tốn công sửa một lần rồi.
            Item {
                id: coverContainer

                anchors.left: parent.left
                anchors.verticalCenter: parent.verticalCenter
                width: row.coverSize
                height: row.coverSize

                Item {
                    id: coverFrame

                    anchors.fill: parent
                    layer.enabled: true
                    layer.effect: MultiEffect {
                        maskEnabled: true
                        maskSource: coverMask
                        autoPaddingEnabled: false
                    }

                    Rectangle {
                        visible: coverPath === ""
                        anchors.fill: parent
                        color: Theme.alpha(Theme.primary, 0.14)

                        Text {
                            anchors.centerIn: parent
                            text: "music_note"
                            color: Theme.primary
                            font.pixelSize: Math.max(Theme.iconSize - 2, Math.round((Theme.fontSizeSm) * 1.4))
                            font.family: Theme.iconFont
                            font.variableAxes: ({ "FILL": 1 })
                            // Font biến thiên + distance field vẽ vỡ nét icon trên cửa sổ thật (CB-058).
                            renderType: Text.NativeRendering
                        }
                    }

                    Image {
                        visible: coverPath !== ""
                        anchors.fill: parent
                        source: coverPath !== "" ? "file://" + coverPath : ""
                        fillMode: Image.PreserveAspectCrop
                        asynchronous: true
                    }
                }

                // Mặt nạ bo góc cho coverFrame -- không hiển thị, chỉ
                // dùng làm maskSource.
                Rectangle {
                    id: coverMask

                    anchors.fill: coverFrame
                    radius: Theme.radiusSm
                    visible: false
                    layer.enabled: true
                }

                // Cửa đổi ảnh bìa. Nằm NGOÀI coverFrame (không nằm trong lớp
                // bị mặt nạ cắt), nếu không thì MultiEffect nuốt mất nó.
                Rectangle {
                    id: coverEdit

                    anchors.fill: parent
                    radius: Theme.radiusSm
                    color: Theme.alpha("#000000", coverEditArea.containsMouse ? 0.62 : 0.42)
                    opacity: row.editMode ? 1 : 0
                    visible: coverEdit.opacity > 0.01

                    Behavior on opacity {
                        NumberAnimation {
                            duration: row.editMode ? row.animAppearMs : row.animDisappearMs
                            easing.type: row.editMode ? Easing.OutCubic : Easing.InCubic
                        }
                    }

                    Behavior on color {
                        ColorAnimation { duration: row.animColorMs; easing.type: Easing.OutCubic }
                    }

                    Text {
                        anchors.centerIn: parent
                        text: "edit"
                        color: "#ffffff"
                        font.pixelSize: Math.max(Theme.iconSize - 2, Math.round((Theme.fontSizeSm) * 1.4))
                        font.family: Theme.iconFont
                        font.variableAxes: ({ "FILL": 1 })
                        // Font biến thiên + distance field vẽ vỡ nét icon trên cửa sổ thật (CB-058).
                        renderType: Text.NativeRendering
                    }

                    MouseArea {
                        id: coverEditArea

                        anchors.fill: parent
                        enabled: row.editMode
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: row.coverChangeRequested()
                    }
                }
            }

            // Nhãn "chỉ có ở máy này". Đứng SÁT phải, và tên bài co lại
            // nhường chỗ cho nó -- lời hứa của F-5a′ là giao diện phải nói
            // thật rằng nhóm bài này không được sao lưu.
            Rectangle {
                id: localBadge

                visible: row.localOnly && !row.editMode
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                width: localBadgeText.implicitWidth + row.badgePadding * 2
                height: localBadgeText.implicitHeight + row.badgePadding
                radius: Theme.radiusSm
                color: Theme.alpha(Theme.onSurface, 0.08)

                Text {
                    id: localBadgeText

                    anchors.centerIn: parent
                    text: "máy này"
                    color: Theme.alpha(Theme.onSurface, 0.55)
                    font.pixelSize: Theme.fontSizeSm
                    font.family: Theme.fontFamily
                }
            }

            // Tên bài -- chiếm hết phần còn lại bên phải ảnh bìa.
            Text {
                id: artistUnder
                visible: !row.editMode
                anchors.left: coverContainer.right
                anchors.leftMargin: Theme.spacingMd
                anchors.right: localBadge.visible ? localBadge.left : parent.right
                anchors.rightMargin: localBadge.visible ? Theme.spacingSm : 0
                anchors.top: parent.verticalCenter
                anchors.topMargin: 1
                text: artist !== "" ? artist : "Bài nhập từ ổ cứng"
                color: Theme.onSurfaceVariant
                font.pixelSize: Theme.fontSizeSm + 0.5
                font.family: Theme.fontFamily
                elide: Text.ElideRight
            }
            Text {
                visible: !row.editMode
                anchors.left: coverContainer.right
                anchors.leftMargin: Theme.spacingMd
                anchors.right: localBadge.visible ? localBadge.left : parent.right
                anchors.rightMargin: localBadge.visible ? Theme.spacingSm : 0
                anchors.bottom: parent.verticalCenter
                anchors.bottomMargin: 1
                text: title
                color: isPlaying ? Theme.primary : Theme.onSurface
                font.pixelSize: Theme.fontSizeMd + 0.5
                font.weight: Font.Medium
                font.family: Theme.fontFamily
                elide: Text.ElideRight

                Behavior on color {
                    ColorAnimation { duration: row.animColorMs; easing.type: Easing.OutCubic }
                }
            }

            // Ô sửa tên. Chỉ đổi CHỮ HIỂN THỊ — tên nghệ sĩ và file nhạc không
            // đụng tới (xem TrackRepository.rename).
            Rectangle {
                visible: row.editMode
                anchors.left: coverContainer.right
                anchors.leftMargin: Theme.spacingSm
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                height: row.coverSize - Theme.spacingXs
                radius: Theme.radiusSm
                color: titleInput.activeFocus
                    ? Theme.alpha(Theme.onSurface, 0.12)
                    : Theme.alpha(Theme.onSurface, 0.06)
                border.width: 1
                border.color: titleInput.activeFocus
                    ? Theme.alpha(Theme.primary, 0.55)
                    : Theme.alpha(Theme.outline, 0.25)

                TextInput {
                    id: titleInput

                    // Tắt chế độ sửa là ô nhập ngừng nhận phím. Chỉ ẩn đi thôi
                    // thì nó VẪN GIỮ con trỏ: gõ tiếp vào một ô vô hình, và chữ
                    // gõ ra sẽ được ghi lại lúc mất focus — đúng cái lỗi "tên
                    // bài tự nhiên có khoảng trống".
                    enabled: row.editMode

                    anchors.fill: parent
                    anchors.leftMargin: Theme.spacingSm
                    anchors.rightMargin: Theme.spacingSm
                    verticalAlignment: TextInput.AlignVCenter
                    text: title
                    color: Theme.onSurface
                    font.pixelSize: Theme.fontSizeMd
                    font.family: Theme.fontFamily
                    selectByMouse: true
                    clip: true

                    // Gán lại SAU khi báo ra ngoài: lúc đó model đã đổi (hoặc
                    // đã từ chối), nên ô nhập luôn khớp với sự thật.
                    function commit() {
                        if (titleInput.text.trim().length > 0 && titleInput.text !== title)
                            row.renameRequested(titleInput.text)
                        titleInput.text = title
                    }

                    onEditingFinished: titleInput.commit()

                    // Enter: lưu rồi ĐÓNG chế độ sửa luôn, không bắt quay lại
                    // bấm cái bút lần nữa. `commit()` chạy trước để tên mới kịp
                    // xuống database — đóng chế độ sửa sẽ gán lại text từ model,
                    // đảo thứ tự là gõ xong mất chữ.
                    Keys.onReturnPressed: {
                        titleInput.commit()
                        row.renameCommitted()
                    }
                    Keys.onEnterPressed: {
                        titleInput.commit()
                        row.renameCommitted()
                    }

                    // Được nhắm thì con trỏ vào thẳng ô này và bôi sẵn cả tên —
                    // người dùng gõ là thay, không phải xoá tay từng chữ.
                    onVisibleChanged: if (visible && row.renaming) titleInput.grabName()

                    function grabName() {
                        titleInput.forceActiveFocus()
                        titleInput.selectAll()
                    }

                    // Trả text về TRƯỚC rồi mới bỏ focus: bỏ focus sẽ gọi
                    // commit(), và lúc đó text đã khớp model nên không ghi gì.
                    Connections {
                        target: row
                        function onEditModeChanged() {
                            if (row.editMode)
                                return
                            titleInput.text = row.title
                            titleInput.focus = false
                        }
                    }
                    Keys.onEscapePressed: {
                        titleInput.text = title
                        titleInput.focus = false
                    }
                }
            }
        }

        HoverHandler {
            id: rowHover
            cursorShape: row.editMode ? Qt.OpenHandCursor : Qt.PointingHandCursor
        }

        MouseArea {
            anchors.fill: parent
            acceptedButtons: Qt.LeftButton | Qt.RightButton
            // Trong chế độ sửa, bấm vào hàng là để đặt con trỏ vào ô tên, không
            // phải để phát nhạc. Chuột phải thì luôn mở menu.
            enabled: !row.editMode
            // Đang chọn nhiều thì bấm bất kỳ đâu trên hàng là chọn/bỏ
            // chọn, KHÔNG phát nhạc -- bấm nhầm ra phát nhạc lúc đang xoá
            // rất khó chịu. Đúng bài đang nạp thì chỉ toggle (tránh nhảy
            // về 0:00). Cùng logic TrackGrid+TrackCard đang dùng.
            // Hàng chỉ báo "vừa được bấm"; TrackSongList quyết định phát,
            // toggle hay chọn — giữ mọi luật ở một chỗ duy nhất.
            onClicked: (mouse) => {
                if (mouse.button === Qt.RightButton) {
                    const at = row.mapToItem(null, mouse.x, mouse.y)
                    row.menuRequested(at.x, at.y)
                } else {
                    row.activated()
                }
            }
        }

        // ---- đang cài về ---------------------------------------------------
        //
        // Hai thứ, đúng hai thứ mà PendingSongRow dùng, để bài về theo đường
        // đồng bộ trông y như bài dán link: phần trăm đè lên ảnh bìa (chỗ duy
        // nhất luôn trống) và hai vạch chạy quanh viền. Khai SAU cùng nên nó
        // nằm trên mọi thứ khác của hàng, kể cả vùng bấm.
        Rectangle {
            visible: row.installing
            anchors.left: coverContainer.left
            anchors.verticalCenter: coverContainer.verticalCenter
            width: row.coverSize
            height: row.coverSize
            radius: Theme.radiusSm
            color: Theme.alpha(Theme.shadow, 0.62)

            Text {
                anchors.centerIn: parent
                // Dấu ba chấm cho quãng chưa có số: yt-dlp im lặng vài giây đầu
                // trong lúc dò video, và một số 0% đứng yên đọc ra là treo.
                text: row.installProgress > 0
                    ? Math.round(row.installProgress * 100) + "%" : "…"
                color: Theme.onSurface
                font.pixelSize: Theme.fontSizeSm
                font.family: Theme.fontFamily
            }
        }

        RunningBorder {
            anchors.fill: parent
            visible: row.installing
            running: row.installing
            // radiusSm chứ không radiusMd của PendingSongRow: bo theo NỀN của
            // chính hàng này, không thì viền chạy lệch khỏi mép hàng.
            radius: Theme.radiusSm
            color: Theme.primary
        }
    }
