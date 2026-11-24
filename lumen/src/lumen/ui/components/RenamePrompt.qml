import QtQuick
import QtQuick.Controls as QQC

// Hộp đổi tên: một ô nhập đã điền sẵn tên cũ, bôi sẵn để gõ là thay.
//
// QtQuick.Controls PHẢI import có tên miền (as QQC) — xem CLAUDE.md mục 5.
QQC.Popup {
    id: root

    property string heading: ""
    property string original: ""

    signal accepted(string name)

    readonly property int panelWidth: 320
    readonly property int openMs: 160

    width: root.panelWidth
    height: column.implicitHeight + padding * 2
    padding: Theme.spacingLg
    modal: true
    dim: true
    closePolicy: QQC.Popup.CloseOnPressOutside | QQC.Popup.CloseOnEscape

    // Điền lại tên cũ mỗi lần mở, không giữ chữ của lần trước.
    onAboutToShow: {
        input.text = root.original
        input.forceActiveFocus()
        input.selectAll()
    }

    background: Rectangle {
        radius: Theme.radiusLg
        color: Theme.alpha(Theme.surfaceVariant, 0.98)
        border.width: 1
        border.color: Theme.alpha(Theme.outline, 0.45)
    }

    enter: Transition {
        NumberAnimation { property: "opacity"; from: 0; to: 1
                          duration: root.openMs; easing.type: Easing.OutCubic }
    }
    exit: Transition {
        NumberAnimation { property: "opacity"; from: 1; to: 0
                          duration: root.openMs; easing.type: Easing.InCubic }
    }

    function commit() {
        const name = input.text.trim()
        if (name.length === 0 || name === root.original) {
            root.close()
            return
        }
        root.accepted(name)
        root.close()
    }

    Column {
        id: column

        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        spacing: Theme.spacingMd

        Text {
            text: root.heading
            color: Theme.onSurface
            font.pixelSize: Theme.fontSizeLg
            font.family: Theme.fontFamily
        }

        Rectangle {
            width: parent.width
            height: Theme.searchFieldHeight
            radius: Theme.radiusMd
            color: Theme.alpha(Theme.onSurface, 0.06)
            border.width: 1
            border.color: input.activeFocus
                ? Theme.primary
                : Theme.alpha(Theme.outline, 0.35)

            TextInput {
                id: input

                anchors.fill: parent
                anchors.leftMargin: Theme.spacingMd
                anchors.rightMargin: Theme.spacingMd
                verticalAlignment: TextInput.AlignVCenter
                color: Theme.onSurface
                font.pixelSize: Theme.fontSizeMd
                font.family: Theme.fontFamily
                selectByMouse: true
                clip: true

                onAccepted: root.commit()
                Keys.onEscapePressed: root.close()
            }
        }

        Row {
            anchors.right: parent.right
            spacing: Theme.spacingSm

            TextButton {
                label: "Huỷ"
                onClicked: root.close()
            }

            TextButton {
                label: "Đổi tên"
                onClicked: root.commit()
            }
        }
    }
}
