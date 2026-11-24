import QtQuick

// Cài đặt › Phím tắt (vòng 2 R-1). Bấm ô phím → ô "đang nghe" → gõ tổ hợp.
// Lumen kiểm trùng (với mọi phím Hyprland đang giữ + phím khác của chính
// Lumen), ghi vào cấu hình Hyprland và nạp lại; từ chối thì nói vì sao ngay
// dưới dòng đó. Esc huỷ, Backspace/Delete bỏ phím.
SettingsCard {
    id: root

    property string listening: ""
    property var errors: ({})
    property var oks: ({})

    title: "PHÍM TẮT"

    function playlistName(id) {
        const hit = Playlists.simpleList().find(p => p.id === id)
        return hit ? hit.name : "Chọn track"
    }
    function setMsg(action, err) {
        const e = Object.assign({}, root.errors), o = Object.assign({}, root.oks)
        e[action] = err
        o[action] = err === "" ? "Đã đặt và nạp lại Hyprland." : ""
        root.errors = e
        root.oks = o
    }

    Repeater {
        model: HotKeys.actions

        SettingsRow {
            id: row

            required property var modelData
            readonly property string action: row.modelData[0]
            readonly property bool isSlot: row.modelData[2]
            readonly property string combo: HotKeys.binds[row.action] || ""
            readonly property bool listen: root.listening === row.action

            label: row.modelData[1]
            hint: (root.errors[row.action] || "") !== "" ? "⛔ " + root.errors[row.action]
                : ((root.oks[row.action] || "") !== "" ? "✓ " + root.oks[row.action]
                   : (row.isSlot ? "Phát track: " + root.playlistName(HotKeys.slots[row.action] || -1) : ""))

            Row {
                spacing: Theme.spacingSm

                PillButton {
                    visible: row.isSlot
                    icon: "queue_music"
                    label: "Đổi track"
                    scale: 0.9
                    onClicked: {
                        const lists = Playlists.simpleList()
                        slotMenu.action = row.action
                        slotMenu.ids = lists.map(p => p.id)
                        slotMenu.items = lists.map(p => ({ "label": p.name, "icon": (HotKeys.slots[row.action] === p.id) ? "radio_button_checked" : "radio_button_unchecked" }))
                        const at = mapToItem(null, 0, height)
                        slotMenu.popupAt(this, at.x, at.y)
                    }
                }

                Rectangle {
                    id: keyButton

                    width: Math.max(170, keyText.implicitWidth + Theme.spacingLg * 2)
                    height: 38
                    radius: Theme.radiusMd
                    color: Theme.alpha(Theme.onSurface, keyArea.containsMouse ? 0.07 : 0.035)
                    border.width: row.listen || (root.errors[row.action] || "") !== "" ? 2 : 1
                    border.color: row.listen ? Theme.primary
                        : ((root.errors[row.action] || "") !== "" ? Theme.error : Theme.alpha(Theme.onSurface, 0.1))
                    focus: row.listen

                    SequentialAnimation on border.width {
                        running: row.listen
                        loops: Animation.Infinite
                        NumberAnimation { to: 3; duration: 600 }
                        NumberAnimation { to: 2; duration: 600 }
                    }

                    Text {
                        id: keyText
                        anchors.centerIn: parent
                        text: row.listen ? "Gõ tổ hợp phím…" : (row.combo !== "" ? row.combo : "Chưa đặt")
                        color: row.listen ? Theme.primary : (row.combo !== "" ? Theme.onSurface : Theme.onSurfaceVariant)
                        font.pixelSize: Theme.fontSizeMd
                        font.weight: row.combo !== "" && !row.listen ? Font.DemiBold : Font.Normal
                        font.family: Theme.fontFamily
                    }

                    Keys.onPressed: (event) => {
                        if (!row.listen)
                            return
                        event.accepted = true
                        const k = event.key
                        if (k === Qt.Key_Shift || k === Qt.Key_Control || k === Qt.Key_Alt || k === Qt.Key_Meta
                                || k === Qt.Key_Super_L || k === Qt.Key_Super_R || k === Qt.Key_AltGr)
                            return
                        if (k === Qt.Key_Escape) {
                            root.listening = ""
                            return
                        }
                        if (k === Qt.Key_Backspace || k === Qt.Key_Delete) {
                            root.setMsg(row.action, HotKeys.clearBind(row.action))
                            root.listening = ""
                            return
                        }
                        const why = HotKeys.tryBind(row.action, k, event.modifiers)
                        root.setMsg(row.action, why)
                        if (why === "")
                            root.listening = ""
                    }

                    MouseArea {
                        id: keyArea
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            root.listening = row.listen ? "" : row.action
                            if (root.listening !== "")
                                keyButton.forceActiveFocus()
                        }
                    }
                }
            }
        }
    }

    ContextMenu {
        id: slotMenu
        property string action: ""
        property var ids: []
        onChosen: (index) => HotKeys.setSlot(slotMenu.action, slotMenu.ids[index])
    }
}
