import QtQuick
import QtQuick.Controls as QQC

// Menu chuột phải dùng chung.
//
// Nhận một danh sách mục `{ label, danger }` và bắn ra số thứ tự mục được chọn.
// Không tự gọi việc gì — nơi dùng quyết định mỗi mục làm gì, nên cùng một menu
// dùng được cho bài hát, track, hay bất cứ thứ gì sau này.
//
// QtQuick.Controls PHẢI import có tên miền (as QQC) — xem CLAUDE.md mục 5.
QQC.Popup {
    id: root

    property var items: []

    signal chosen(int index)

    readonly property int itemHeight: 32
    readonly property int minWidth: 150
    readonly property int openMs: 120

    // Mở SÁT chỗ bấm, rồi kẹp trong cửa sổ để không thò ra ngoài mép — bấm ở
    // gần đáy màn hình là menu tràn ra ngoài ngay.
    function popupAt(item, sceneX, sceneY) {
        root.parent = item.Window.contentItem
        const window = item.Window.window
        const gap = Theme.spacingXs
        root.x = Math.max(gap, Math.min(sceneX, window.width - root.width - gap))
        root.y = Math.max(gap, Math.min(sceneY, window.height - root.height - gap))
        root.open()
    }

    width: Math.max(root.minWidth, column.implicitWidth + padding * 2)
    height: column.implicitHeight + padding * 2
    padding: Theme.spacingXs
    modal: true
    dim: false
    closePolicy: QQC.Popup.CloseOnPressOutside | QQC.Popup.CloseOnEscape

    background: Rectangle {
        radius: Theme.radiusMd + 2
        // Chrome thoáng qua ⇒ ĐỤC (QĐ-040), như menu của design R-1.
        color: Theme.surfaceVariant
        border.width: 1
        border.color: Theme.alpha(Theme.outline, 0.45)
    }

    enter: Transition {
        ParallelAnimation {
            NumberAnimation { property: "opacity"; from: 0; to: 1
                              duration: Math.max(1, (root.openMs) * Theme.motionScale); easing.type: Easing.OutCubic }
            // Bung ra có nảy như design R-1.
            NumberAnimation { property: "scale"; from: 0.82; to: 1
                              duration: Math.max(1, (root.openMs * 2) * Theme.motionScale); easing.type: Easing.OutBack; easing.overshoot: Theme.overshoot }
        }
    }
    exit: Transition {
        NumberAnimation { property: "opacity"; from: 1; to: 0
                          duration: Math.max(1, (root.openMs) * Theme.motionScale); easing.type: Easing.InCubic }
    }

    Column {
        id: column

        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top

        Repeater {
            model: root.items

            Rectangle {
                id: entry

                required property int index
                required property var modelData

                width: column.width
                height: root.itemHeight
                radius: Theme.radiusSm
                color: hover.hovered ? Theme.alpha(Theme.onSurface, 0.07) : "transparent"

                HoverHandler { id: hover }

                // Icon tuỳ chọn ở đầu mục (khoá "icon" trong model) — design R-1.
                MIcon {
                    id: entryIcon
                    visible: entry.modelData.icon !== undefined
                    anchors.left: parent.left
                    anchors.leftMargin: Theme.spacingSm + 2
                    anchors.verticalCenter: parent.verticalCenter
                    name: entry.modelData.icon !== undefined ? entry.modelData.icon : ""
                    size: Theme.iconSize - 1
                    color: entry.modelData.danger ? Theme.error : Theme.onSurfaceVariant
                }

                Text {
                    anchors.left: entryIcon.visible ? entryIcon.right : parent.left
                    anchors.right: parent.right
                    anchors.leftMargin: Theme.spacingSm + 2
                    anchors.rightMargin: Theme.spacingSm
                    anchors.verticalCenter: parent.verticalCenter
                    text: entry.modelData.label
                    color: entry.modelData.danger ? Theme.error : Theme.onSurface
                    font.pixelSize: Theme.fontSizeMd
                    font.family: Theme.fontFamily
                    elide: Text.ElideRight
                }

                MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        root.close()
                        root.chosen(entry.index)
                    }
                }
            }
        }
    }
}
