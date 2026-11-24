import QtQuick
import QtQuick.Controls as QQC
import QtQuick.Dialogs

import "../components"

// Cài đặt, chia theo mục: Giao diện · Nền · Đồng bộ · Về Lumen.
//
// Không tự bịa danh sách màu hay danh sách nền — lấy từ `Theme.presets` và
// `Theme.gradients`, tức thẳng từ core/, để giao diện và lõi không lệch nhau.
//
// QtQuick.Controls PHẢI import có tên miền (as QQC) — xem CLAUDE.md mục 5.
Item {
    id: root

    // Nút "Thu nhỏ" ở nhóm MINI LUMEN (design R-1) — Main mở Mini.
    signal miniRequested()

    // Vòng 2 R-1: thanh bên đổi thành danh sách mục cài đặt; mỗi lần một trang.
    property string page: "look"
    function pageTitle() {
        return ({ "look": "Giao diện", "keys": "Phím tắt",
                  "store": "Kho nhạc", "about": "Giới thiệu" })[root.page] || "Cài đặt"
    }
    function pageHint() {
        return ({ "look": "Màu, kính và chuyển động.",
                  "keys": "Dùng được cả khi Lumen đang ẩn. Bấm ô phím rồi gõ tổ hợp mới; Esc để huỷ.",
                  "store": "Nhạc nằm ở đâu trên máy này.", "about": "" })[root.page] || ""
    }

    // Có hộp nổi nào của TRANG NÀY đang mở không — Main.qml đọc để làm mờ trang
    // phía sau, đúng như LibraryView.overlayOpen và ArtistsView.detailOpen.
    //
    // Thiếu nó thì trang Cài đặt đứng SẮC NÉT sau bảng chọn màu / chọn nền, và
    // cách chữa sai là đắp một tấm tối lên bảng — "blur đen" sinh ra đúng kiểu
    // đó: không phải chọn nhầm màu, mà là lấy một hình chữ nhật tối che một lớp
    // mờ CÒN THIẾU. Xem `01 Hiến pháp/UI surfaces and blur`.
    readonly property bool overlayOpen: picker.visible

    readonly property int contentWidth: Math.min(width - Theme.spacingXl * 2, 720)
    readonly property int chipHeight: 32
    readonly property int shadeSize: 36
    readonly property int wallSideFrom: 460
    readonly property int wallColumns: 3
    // Lưới chọn nền luôn có nền ĐANG dùng, kể cả khi nó được đặt từ trước khi
    // Lumen biết nhớ danh sách ảnh.
    readonly property var wallChoices: Theme.wallpaperIsImage && Theme.wallpapers.indexOf(Theme.wallpaper) < 0
        ? [Theme.wallpaper].concat(Theme.wallpapers) : Theme.wallpapers

    // Tên ảnh nền người dùng nhận ra: bỏ đuôi file và vân tay nội dung ở cuối
    // tên bản sao.
    function wallName(path) {
        return path.split("/").pop().replace(/\.[^.]+$/, "").replace(/-[0-9a-f]{8}$/, "")
    }
    // Màu dựng sẵn mà màu chủ đạo hiện tại thuộc về (chính nó hoặc một sắc độ
    // của nó); null khi đang theo hình nền máy hoặc màu tự pha.
    readonly property var shadeFamily: Theme.followNoctalia ? null
        : (Theme.presets.find((p) => p.shades.indexOf(Theme.accent) >= 0) || null)
    property var lastShades: []
    onShadeFamilyChanged: if (root.shadeFamily) root.lastShades = root.shadeFamily.shades
    readonly property real dimmed: 0.7

    QQC.ScrollView {
        anchors.fill: parent
        contentWidth: availableWidth
        clip: true

        Column {
            width: root.width
            spacing: Theme.spacingXl
            topPadding: Theme.spacingLg
            bottomPadding: Theme.islandReserve

            Column {
                x: (root.width - root.contentWidth) / 2
                width: root.contentWidth
                spacing: Theme.spacingXs

                Text {
                    text: root.pageTitle()
                    color: Theme.onSurface
                    font.pixelSize: 32
                    font.weight: Font.Bold
                    font.family: Theme.fontFamily
                }
                Text {
                    text: root.pageHint()
                    color: Theme.onSurfaceVariant
                    font.pixelSize: Theme.fontSizeMd
                    font.family: Theme.fontFamily
                }
            }

            KeysPage {
                visible: root.page === "keys"
                x: (root.width - root.contentWidth) / 2
                width: root.contentWidth
            }

            Item {
                visible: root.page === "store"
                x: (root.width - root.contentWidth) / 2
                width: root.contentWidth
                height: storeCard.height

                SettingsCard {
                    id: storeCard

                    width: parent.width
                    title: "KHO NHẠC"

                    // Bài có trong thư viện mà máy này chưa có file. KHÔNG phải
                    // lỗi và KHÔNG được nuốt: đây là danh sách "cần tải lại từ
                    // link gốc", và không nói ra thì người dùng thấy bài
                    // rồi bấm vào lại im lặng. `Downloads.missingCount` hỏi
                    // thẳng database.
                    SettingsRow {
                        width: parent.width
                        visible: Downloads.missingCount > 0
                        label: "⚠ " + Downloads.missingCount + " bài chưa có file"
                        hint: "File nhạc của những bài này không còn trên máy. "
                            + "Tải lại từ link YouTube gốc để nghe được."

                        TextButton {
                            label: "Tải lại tất cả"
                            onClicked: Downloads.redownloadMissing()
                        }
                    }
                }
            }

            Item {
                visible: root.page === "look"
                x: (root.width - root.contentWidth) / 2
                width: root.contentWidth
                height: wallpaperCard.height

                SettingsCard {
                    id: wallpaperCard

                    width: parent.width
                    title: "NỀN"

                    // Vòng 3 R-1: nền đứng ĐẦU trang Giao diện, như bảng chọn nền
                    // của shell — trái là nền đang dùng, phải là lưới lựa chọn,
                    // bấm một ô là đổi ngay (không còn hộp nổi riêng).
                    Item {
                        id: wallBox

                        readonly property bool side: width >= root.wallSideFrom
                        readonly property real previewW: side ? Math.round(width * 0.44) : width
                        readonly property real previewH: Math.round(previewW * 9 / 16)
                        readonly property real gridW: side ? width - previewW - Theme.spacingLg : width
                        readonly property real tileW: (gridW - Theme.spacingSm * (root.wallColumns - 1)) / root.wallColumns
                        readonly property real tileH: Math.round(tileW * 9 / 16)

                        width: parent.width
                        height: Theme.spacingMd * 2 + (side
                            ? Math.max(previewBox.height, wallGrid.height)
                            : previewBox.height + Theme.spacingMd + wallGrid.height)

                        Item {
                            id: previewBox

                            y: Theme.spacingMd
                            width: wallBox.previewW
                            height: wallBox.previewH + Theme.spacingSm + previewCaption.height

                            Rectangle {
                                width: wallBox.previewW
                                height: wallBox.previewH
                                radius: Theme.radiusMd
                                color: Theme.alpha(Theme.onSurface, 0.06)

                                RoundedImage {
                                    anchors.fill: parent
                                    radius: Theme.radiusMd
                                    source: Theme.wallpaperIsImage ? "file://" + Theme.wallpaper : ""
                                }
                                Rectangle {
                                    anchors.fill: parent
                                    radius: Theme.radiusMd
                                    color: "transparent"
                                    border.width: 2
                                    border.color: Theme.alpha(Theme.primary, 0.7)
                                }
                                Text {
                                    anchors.centerIn: parent
                                    visible: Theme.wallpaper === ""
                                    text: "Chưa có nền"
                                    color: Theme.onSurfaceVariant
                                    opacity: root.dimmed
                                    font.pixelSize: Theme.fontSizeMd
                                    font.family: Theme.fontFamily
                                }
                            }

                            Text {
                                id: previewCaption

                                y: wallBox.previewH + Theme.spacingSm
                                width: wallBox.previewW
                                text: Theme.wallpaper === "" ? "Đang dùng: không nền"
                                    : "Đang dùng: " + root.wallName(Theme.wallpaper)
                                color: Theme.onSurfaceVariant
                                font.pixelSize: Theme.fontSizeSm + 1
                                font.family: Theme.fontFamily
                                elide: Text.ElideRight
                            }
                        }

                        Flow {
                            id: wallGrid

                            x: wallBox.side ? wallBox.previewW + Theme.spacingLg : 0
                            y: wallBox.side ? Theme.spacingMd : previewBox.y + previewBox.height + Theme.spacingMd
                            width: wallBox.gridW
                            spacing: Theme.spacingSm

                            // Ô mở thư mục đứng đầu, để lần đầu dùng thì thấy ngay.
                            WallpaperTile {
                                width: wallBox.tileW
                                height: wallBox.tileH
                                label: "Từ máy…"
                                glyph: "add_photo_alternate"
                                onPicked: wallpaperDialog.open()
                            }

                            WallpaperTile {
                                width: wallBox.tileW
                                height: wallBox.tileH
                                label: "Không nền"
                                glyph: "hide_image"
                                active: Theme.wallpaper === ""
                                onPicked: Theme.setWallpaper("")
                            }

                            Repeater {
                                model: root.wallChoices

                                WallpaperTile {
                                    required property string modelData

                                    width: wallBox.tileW
                                    height: wallBox.tileH
                                    label: root.wallName(modelData)
                                    source: "file://" + modelData
                                    active: Theme.wallpaper === modelData
                                    removable: true

                                    onPicked: Theme.setWallpaper(modelData)
                                    onRemoved: Theme.forgetWallpaper(modelData)
                                }
                            }
                        }
                    }
                }
            }

            Item {
                visible: root.page === "look"
                x: (root.width - root.contentWidth) / 2
                width: root.contentWidth
                height: appearanceCard.height

                SettingsCard {
                    id: appearanceCard

                    width: parent.width
                    title: "GIAO DIỆN"

                    SettingsRow {
                        width: parent.width
                        label: "Nguồn màu"
                        hint: Theme.followNoctalia
                            ? "Lumen đổi màu theo hình nền máy: đổi hình nền là Lumen đổi theo."
                            : "Lumen đang dùng màu bạn chọn."

                        Row {
                            spacing: Theme.spacingSm

                            Repeater {
                                model: [
                                    { "follow": true, "label": "Theo hình nền máy" },
                                    { "follow": false, "label": "Tự chọn màu" }
                                ]

                                Rectangle {
                                    required property var modelData

                                    readonly property bool chosen: Theme.followNoctalia === modelData.follow

                                    width: chipText.implicitWidth + Theme.spacingLg
                                    height: root.chipHeight
                                    radius: height / 2
                                    color: chosen
                                        ? Theme.alpha(Theme.primary, 0.18)
                                        : Theme.alpha(Theme.onSurface, chipHover.hovered ? 0.10 : 0.05)
                                    border.width: 1
                                    border.color: chosen
                                        ? Theme.alpha(Theme.primary, 0.5)
                                        : Theme.alpha(Theme.outline, 0.25)

                                    Behavior on color {
                                        ColorAnimation { duration: 120; easing.type: Easing.OutCubic }
                                    }

                                    HoverHandler { id: chipHover }

                                    Text {
                                        id: chipText

                                        anchors.centerIn: parent
                                        text: modelData.label
                                        color: parent.chosen ? Theme.primary : Theme.onSurfaceVariant
                                        font.pixelSize: Theme.fontSizeMd
                                        font.family: Theme.fontFamily
                                    }

                                    MouseArea {
                                        anchors.fill: parent
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: Theme.setFollowNoctalia(modelData.follow)
                                    }
                                }
                            }
                        }
                    }

                    SettingsRow {
                        width: parent.width
                        label: "Màu chủ đạo"
                        stacked: true
                        hint: "Cả app đổi theo màu này. Bấm một màu để chọn sắc độ đậm nhạt của nó; dấu + để tự pha màu."

                        // Vòng 3 R-1: bấm một màu thì hàng dưới mở ra các sắc độ
                        // của chính màu đó (tối → sáng), bấm sắc nào là đổi luôn.
                        // Item đặt tay chứ không Column: con của positioner không
                        // được lấy kích thước từ positioner (CB-059).
                        Item {
                            id: colourBox

                            width: parent.width
                            height: presetFlow.height + (root.shadeFamily ? Theme.spacingMd + shadeBox.height : 0)
                            Behavior on height { NumberAnimation { duration: Math.max(1, 160 * Theme.motionScale); easing.type: Easing.OutCubic } }

                            Flow {
                                id: presetFlow

                                width: colourBox.width
                                spacing: Theme.spacingSm

                                Repeater {
                                    model: Theme.presets

                                    ColorSwatch {
                                        required property var modelData

                                        tone: modelData.color
                                        label: modelData.name
                                        // Cả họ màu sáng lên: đang dùng một sắc độ của
                                        // Cam thì ô Cam vẫn là ô được chọn.
                                        active: root.shadeFamily !== null && root.shadeFamily.color === modelData.color

                                        // Chọn màu là tự chuyển sang chế độ tự chỉnh —
                                        // bấm màu rồi thấy không đổi gì thì rất khó hiểu.
                                        onPicked: {
                                            Theme.setFollowNoctalia(false)
                                            Theme.setAccent(modelData.color)
                                        }
                                    }
                                }

                                ColorSwatch {
                                    id: customSwatch

                                    tone: Theme.alpha(Theme.onSurface, 0.08)
                                    active: !Theme.followNoctalia && root.shadeFamily === null

                                    onPicked: picker.open()

                                    Text {
                                        anchors.centerIn: parent
                                        visible: !customSwatch.active
                                        text: "add"
                                        color: Theme.onSurfaceVariant
                                        font.pixelSize: Math.max(Theme.iconSize - 2, Math.round((Theme.fontSizeLg) * 1.4))
                                        font.family: Theme.iconFont
                                        font.variableAxes: ({ "FILL": 1 })
                                        // Font biến thiên + distance field vẽ vỡ nét icon trên cửa sổ thật (CB-058).
                                        renderType: Text.NativeRendering
                                    }

                                    Rectangle {
                                        anchors.fill: parent
                                        anchors.margins: Theme.spacingXs
                                        visible: customSwatch.active
                                        radius: Theme.radiusSm
                                        color: Theme.accent
                                    }
                                }
                            }

                            Item {
                                id: shadeBox

                                y: presetFlow.height + Theme.spacingMd
                                width: colourBox.width
                                height: shadeTitle.height + Theme.spacingSm + root.shadeSize
                                opacity: root.shadeFamily ? 1 : 0
                                visible: opacity > 0.01
                                Behavior on opacity { NumberAnimation { duration: Math.max(1, 160 * Theme.motionScale) } }

                                Text {
                                    id: shadeTitle

                                    text: root.shadeFamily ? "Sắc độ của " + root.shadeFamily.name.toLowerCase() : ""
                                    color: Theme.onSurfaceVariant
                                    font.pixelSize: Theme.fontSizeSm + 1
                                    font.family: Theme.fontFamily
                                }

                                Row {
                                    y: shadeTitle.height + Theme.spacingSm
                                    spacing: Theme.spacingXs

                                    Repeater {
                                        // Giữ hàng cũ trong lúc mờ đi, không thì hàng rỗng
                                        // ngay khi chuyển sang "Theo hình nền máy".
                                        model: root.shadeFamily ? root.shadeFamily.shades : root.lastShades

                                        Rectangle {
                                            id: shade

                                            required property string modelData
                                            required property int index
                                            readonly property bool on: !Theme.followNoctalia && Theme.accent === shade.modelData

                                            width: root.shadeSize
                                            height: root.shadeSize
                                            radius: Theme.radiusSm
                                            color: shade.modelData
                                            border.width: shade.on ? 2 : 0
                                            border.color: Theme.onSurface
                                            scale: shadeArea.pressed ? 0.86 : (shadeArea.containsMouse && !shade.on ? 1.08 : 1)
                                            Behavior on scale { NumberAnimation { duration: Math.max(1, 90 * Theme.motionScale) } }

                                            Text {
                                                anchors.centerIn: parent
                                                visible: shade.on
                                                text: "check"
                                                color: Qt.color(shade.modelData).hslLightness > 0.5 ? "#141018" : "#ffffff"
                                                font.pixelSize: Theme.fontSizeLg + 2
                                                font.family: Theme.iconFont
                                                font.variableAxes: ({ "FILL": 1 })
                                                // Font biến thiên + distance field vẽ vỡ nét icon trên cửa sổ thật (CB-058).
                                                renderType: Text.NativeRendering
                                            }
                                            MouseArea {
                                                id: shadeArea
                                                anchors.fill: parent
                                                hoverEnabled: true
                                                cursorShape: Qt.PointingHandCursor
                                                onClicked: {
                                                    Theme.setFollowNoctalia(false)
                                                    Theme.setAccent(shade.modelData)
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                    SettingsRow {
                        label: "Độ trong của kính"
                        hint: "Kính càng trong thì càng thấy hình nền phía sau."

                        Segmented {
                            options: [["dac", "Đặc"], ["mo", "Mờ"], ["kinh", "Kính"]]
                            current: Theme.glass
                            onPicked: (value) => Theme.setFeel("glass", value)
                        }
                    }

                    SettingsRow {
                        label: "Độ nảy"
                        hint: "Bấm vào thanh nhạc ở dưới để thấy nó nảy."

                        Segmented {
                            options: [["khong", "Không"], ["vua", "Vừa"], ["nhieu", "Nhiều"]]
                            current: Theme.bounce
                            onPicked: (value) => Theme.setFeel("bounce", value)
                        }
                    }

                    SettingsRow {
                        label: "Tốc độ hiệu ứng"

                        Segmented {
                            options: [["tat", "Tắt"], ["nhanh", "Nhanh"], ["vua", "Vừa"], ["cham", "Chậm rãi"]]
                            current: Theme.speed
                            onPicked: (value) => Theme.setFeel("speed", value)
                        }
                    }
                }
            }

            SettingsCard {
                visible: false
                x: (root.width - root.contentWidth) / 2
                width: root.contentWidth
                title: "MINI LUMEN"

                SettingsRow {
                    label: "Thu nhỏ thành một viên nổi"
                    hint: "Chỉ còn bài đang phát và nút điều khiển."

                    PillButton {
                        icon: "picture_in_picture_alt"
                        label: "Thu nhỏ"
                        onClicked: root.miniRequested()
                    }
                }
            }

            SettingsCard {
                visible: root.page === "about"
                x: (root.width - root.contentWidth) / 2
                width: root.contentWidth
                title: "VỀ LUMEN"

                Repeater {
                    model: [
                        { "label": "Phiên bản", "value": App.version },
                        { "label": "Thư mục nhạc", "value": App.musicDir + "   (" + App.musicDirInfo + ")" },
                        { "label": "Dữ liệu", "value": App.dataDir + "   (" + App.dataDirInfo + ")" }
                    ]

                    Row {
                        required property var modelData

                        width: parent.width
                        spacing: Theme.spacingMd

                        Text {
                            width: 120
                            text: modelData.label
                            color: Theme.onSurfaceVariant
                            font.pixelSize: Theme.fontSizeSm
                            font.family: Theme.fontFamily
                        }

                        Text {
                            width: parent.width - 120 - Theme.spacingMd
                            text: modelData.value
                            color: Theme.onSurface
                            font.pixelSize: Theme.fontSizeSm
                            font.family: Theme.fontFamily
                            elide: Text.ElideMiddle
                        }
                    }
                }
            }
        }
    }

    ColorPicker {
        id: picker

        anchors.centerIn: parent
        hue: 0.72
        saturation: 0.62
        lightness: 0.68

        onAccepted: (color) => {
            Theme.setFollowNoctalia(false)
            Theme.setAccent(color)
        }
    }

    FileDialog {
        id: wallpaperDialog

        title: "Chọn ảnh nền cho Lumen"
        nameFilters: ["Ảnh (*.png *.jpg *.jpeg *.webp *.bmp)"]

        onAccepted: Theme.setWallpaper(wallpaperDialog.selectedFile.toString())
    }
}
