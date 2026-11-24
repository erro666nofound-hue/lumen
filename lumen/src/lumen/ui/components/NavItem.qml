import QtQuick
import QtQuick.Controls as QQC

// Một dòng mục trong thanh bên (Library, Playlists, mood...).
Item {
    id: root

    height: Theme.navItemHeight

    property string glyph: ""
    property string label: ""
    property int count: -1
    property bool active: false
    // Dải icon: giấu chữ, chỉ còn ký hiệu; tên hiện ra khi rê chuột.
    property bool compact: false

    signal clicked()

    // Nền "đang chọn" do ô sáng TRƯỢT của thanh bên vẽ (Sidebar.qml), không vẽ ở đây.
    readonly property color _activeBg: "transparent"
    readonly property color _hoverBg: Theme.alpha(Theme.onSurface, 0.06)
    readonly property color _textColor: root.active ? Theme.primary : Theme.onSurfaceVariant

    Rectangle {
        id: background

        anchors.fill: parent
        radius: Theme.radiusMd
        color: root.active
            ? root._activeBg
            : (mouseArea.containsMouse ? root._hoverBg : "transparent")

        Behavior on color {
            ColorAnimation { duration: 140; easing.type: Easing.OutCubic }
        }
    }

    Row {
        anchors.left: parent.left
        anchors.leftMargin: root.compact ? 0 : Theme.spacingMd
        anchors.right: root.compact ? parent.right : undefined
        anchors.verticalCenter: parent.verticalCenter
        spacing: root.compact ? 0 : Theme.spacingSm

        Text {
            text: root.glyph
            color: root._textColor
            font.pixelSize: Math.max(Theme.iconSize - 2, Math.round((Theme.fontSizeMd) * 1.4))
            font.family: Theme.iconFont
            // Như dynsle: mục đang chọn tô đặc, mục khác chỉ nét viền.
            font.variableAxes: ({ "FILL": root.active ? 1 : 0 })
            // Font biến thiên + distance field vẽ vỡ nét icon trên cửa sổ thật (CB-058).
            renderType: Text.NativeRendering
            anchors.verticalCenter: parent.verticalCenter

            Behavior on color {
                ColorAnimation { duration: 140; easing.type: Easing.OutCubic }
            }
        }

        Text {
            visible: !root.compact
            text: root.label
            font.weight: Font.Medium
            color: root._textColor
            font.pixelSize: Theme.fontSizeMd
            font.family: Theme.fontFamily
            anchors.verticalCenter: parent.verticalCenter

            Behavior on color {
                ColorAnimation { duration: 140; easing.type: Easing.OutCubic }
            }
        }
    }

    Text {
        visible: root.count >= 0 && !root.compact
        text: root.count
        color: Theme.onSurfaceVariant
        font.pixelSize: Theme.fontSizeSm
        font.family: Theme.fontFamily
        anchors.right: parent.right
        anchors.rightMargin: Theme.spacingMd
        anchors.verticalCenter: parent.verticalCenter
    }

    MouseArea {
        id: mouseArea

        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: root.clicked()
    }

    QQC.ToolTip {
        visible: root.compact && root.label !== "" && mouseArea.containsMouse
        text: root.label
        delay: 300
    }
}
