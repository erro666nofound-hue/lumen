import QtQuick
import QtQuick.Controls as QQC
import QtQuick.Dialogs

// Bảng chọn nền: ảnh đã từng chọn, và một ô "từ máy".
//
// Ảnh đã chọn được NHỚ LẠI: lần sau chỉ bấm vào ảnh, không phải mở thư mục và
// đi tìm lại từ đầu.
//
// QtQuick.Controls PHẢI import có tên miền (as QQC) — xem CLAUDE.md mục 5.
QQC.Popup {
    id: root

    readonly property int tileWidth: 190
    readonly property int tileHeight: 108
    readonly property int openMs: 160
    readonly property real dimmed: 0.7

    // Bảng ÔM SÁT số ô đang có: một ô thì một cột, từ hai ô trở lên thì hai
    // cột. Cố định hai cột thì lúc mới dùng, bảng hở một nửa khoảng trống.
    readonly property int tileCount: 1 + Theme.wallpapers.length
    readonly property int columns: Math.min(2, Math.max(1, root.tileCount))

    width: root.padding * 2 + root.columns * root.tileWidth
        + (root.columns - 1) * Theme.spacingSm
    height: Math.min(column.implicitHeight + padding * 2, root.parent ? root.parent.height - 40 : 600)
    padding: Theme.spacingMd
    modal: true
    dim: false
    closePolicy: QQC.Popup.CloseOnPressOutside | QQC.Popup.CloseOnEscape

    background: Rectangle {
        radius: Theme.radiusLg
        // ĐÚNG công thức kính của cửa sổ (QĐ-037), không phải một tấm riêng.
        // 0.97 là con số của luật CŨ: kính cửa sổ 0.45 rồi hộp này 0.97 nữa chỉ
        // còn ~1.6% ảnh nền, trong khi cả app để lọt 55% — một mảng đen giữa
        // một app trong suốt, đúng bệnh của bảng đồng bộ cũ.
        color: Theme.alpha(Theme.surface,
                           Theme.wallpaper !== "" ? Theme.wallpaperSurfaceAlpha
                                                  : Theme.surfaceAlpha)
        border.width: 1
        // Kính mỏng đi thì cái viền là thứ DUY NHẤT còn nói "hộp hết ở đây".
        border.color: Theme.alpha(Theme.outline, 0.60)
    }

    enter: Transition {
        NumberAnimation { property: "opacity"; from: 0; to: 1
                          duration: root.openMs; easing.type: Easing.OutCubic }
    }
    exit: Transition {
        NumberAnimation { property: "opacity"; from: 1; to: 0
                          duration: root.openMs; easing.type: Easing.InCubic }
    }

    QQC.ScrollView {
        anchors.fill: parent
        contentWidth: availableWidth
        clip: true

        Column {
            id: column

            width: root.columns * root.tileWidth + (root.columns - 1) * Theme.spacingSm
            spacing: Theme.spacingSm

            Flow {
                width: parent.width
                spacing: Theme.spacingSm

                // Ô mở thư mục đứng đầu, để lần đầu dùng thì thấy ngay.
                WallpaperTile {
                    width: root.tileWidth
                    height: root.tileHeight
                    label: "Từ máy…"
                    glyph: "add"

                    onPicked: fileDialog.open()
                }

                Repeater {
                    model: Theme.wallpapers

                    WallpaperTile {
                        required property string modelData

                        width: root.tileWidth
                        height: root.tileHeight
                        // Bỏ đuôi file và vân tay nội dung ở cuối tên bản sao,
                        // chỉ để lại cái tên người dùng nhận ra.
                        label: modelData.split("/").pop()
                            .replace(/\.[^.]+$/, "").replace(/-[0-9a-f]{8}$/, "")
                        source: "file://" + modelData
                        active: Theme.wallpaper === modelData
                        removable: true

                        onPicked: Theme.setWallpaper(modelData)
                        onRemoved: Theme.forgetWallpaper(modelData)
                    }
                }
            }

            TextButton {
                label: "Bỏ nền"
                visible: Theme.wallpaper !== ""
                danger: true
                onClicked: Theme.setWallpaper("")
            }
        }
    }

    FileDialog {
        id: fileDialog

        title: "Chọn ảnh nền cho Lumen"
        nameFilters: ["Ảnh (*.png *.jpg *.jpeg *.webp *.bmp)"]

        onAccepted: Theme.setWallpaper(fileDialog.selectedFile.toString())
    }
}
