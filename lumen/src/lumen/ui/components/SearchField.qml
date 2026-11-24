import QtQuick

// Ô nhập dùng chung: dán link YouTube hoặc tìm kiếm trong thư viện.
Rectangle {
    id: root

    // Design R-1: ô nhập là một khung kính bo tròn to, viền mảnh.
    height: Theme.searchFieldHeight + 10
    radius: Theme.radiusLg
    color: Theme.alpha(Theme.onSurface, 0.045)
    border.width: 1
    border.color: input.activeFocus ? Theme.primary : Theme.alpha(Theme.onSurface, 0.075)

    property string placeholder: ""
    property alias text: input.text

    // Cửa tường minh để chỗ khác đưa con trỏ vào ô chữ. Gọi forceActiveFocus()
    // trên chính component thì trúng Item gốc, không trúng TextInput bên trong,
    // và người dùng vẫn phải bấm thêm một phát.
    function takeFocus() {
        input.forceActiveFocus();
    }
    property string glyph: ""

    signal submitted(string text)
    signal cleared()

    // Chỉ có ý nghĩa nội bộ: độ mờ của chữ placeholder khi ô rỗng.
    readonly property real placeholderAlpha: 0.55

    Behavior on border.color {
        ColorAnimation { duration: 140; easing.type: Easing.OutCubic }
    }

    MouseArea {
        anchors.fill: parent
        cursorShape: Qt.IBeamCursor
        onClicked: input.forceActiveFocus()
    }

    Text {
        id: glyphText

        visible: root.glyph !== ""
        text: root.glyph
        color: Theme.onSurfaceVariant
        font.pixelSize: Math.max(Theme.iconSize - 2, Math.round((Theme.fontSizeMd) * 1.4))
        font.family: Theme.iconFont
        font.variableAxes: ({ "FILL": 1 })
        // Font biến thiên + distance field vẽ vỡ nét icon trên cửa sổ thật (CB-058).
        renderType: Text.NativeRendering
        anchors.left: parent.left
        anchors.leftMargin: Theme.spacingMd
        anchors.verticalCenter: parent.verticalCenter
    }

    Item {
        id: contentArea

        anchors.left: parent.left
        anchors.leftMargin: Theme.spacingMd + (root.glyph !== "" ? glyphText.implicitWidth + Theme.spacingSm : 0)
        anchors.right: clearButton.left
        anchors.rightMargin: Theme.spacingSm
        anchors.verticalCenter: parent.verticalCenter
        height: input.implicitHeight

        Text {
            anchors.fill: parent
            verticalAlignment: Text.AlignVCenter
            text: root.placeholder
            color: Theme.alpha(Theme.onSurfaceVariant, root.placeholderAlpha)
            font.pixelSize: Theme.fontSizeMd
            font.family: Theme.fontFamily
            elide: Text.ElideRight
            visible: input.text.length === 0
        }

        TextInput {
            id: input

            anchors.fill: parent
            verticalAlignment: TextInput.AlignVCenter
            color: Theme.onSurface
            font.pixelSize: Theme.fontSizeMd
            font.family: Theme.fontFamily
            selectByMouse: true
            clip: true

            onAccepted: root.submitted(text)

            Keys.onEscapePressed: {
                input.text = ""
                root.cleared()
                input.focus = false
            }
        }
    }

    IconButton {
        id: clearButton

        anchors.right: parent.right
        anchors.rightMargin: Theme.spacingSm
        anchors.verticalCenter: parent.verticalCenter
        visible: input.text.length > 0
        glyph: "close"
        onClicked: {
            input.text = ""
            root.cleared()
        }
    }
}
