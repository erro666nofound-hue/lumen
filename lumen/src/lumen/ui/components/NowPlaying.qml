import QtQuick
import QtQuick.Effects

// Cụm "đang phát" bên trái PlayerBar: bìa album bo góc + tên bài / nghệ sĩ.
// Không đọc thẳng Player — nhận dữ liệu qua property để tái dùng được cho
// Mini Lumen.
Item {
    id: root

    property bool hasTrack: false
    property string title: ""
    property string artist: ""
    property string coverPath: ""

    // Mini Lumen là chỗ NGHE chính nên bìa ở đó to hơn hẳn trong thanh phát.
    property int coverSize: Theme.coverSize

    // Chỉ có ý nghĩa nội bộ: khoảng cách giữa bìa và khối chữ.
    readonly property int textSpacing: Theme.spacingMd

    readonly property string _displayTitle: root.hasTrack ? root.title : qsTr("Chưa phát bài nào")
    readonly property string _displayArtist: root.hasTrack ? root.artist : ""

    implicitHeight: root.coverSize

    // Ảnh bìa vuông, bo góc thật (clip theo mặt nạ) — Rectangle không thể clip
    // con theo radius nên phải dùng layer effect + maskSource, y hệt TrackCard.qml.
    //
    // coverContainer là item TRUNG GIAN, chính nó mới là con thật sự của root.
    // coverFrame và coverMask nằm CÙNG một cấp bên trong coverContainer nên
    // anchors.fill giữa chúng hợp lệ. Nếu coverMask bị kéo ra ngoài coverContainer
    // (dù vẫn anchor xuyên cấp đúng vị trí) thì layer bị mask xoá trắng, không có
    // cảnh báo runtime nào — đã từng làm hỏng build một lần, xem TrackCard.qml.
    Item {
        id: coverContainer

        width: root.coverSize
        height: root.coverSize
        anchors.left: parent.left
        anchors.verticalCenter: parent.verticalCenter

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
                visible: root.coverPath === ""
                anchors.fill: parent
                color: Theme.alpha(Theme.primary, 0.14)

                Text {
                    anchors.centerIn: parent
                    text: "music_note"
                    color: Theme.primary
                    font.pixelSize: Math.max(Theme.iconSize - 2, Math.round((Theme.fontSizeLg) * 1.4))
                    font.family: Theme.iconFont
                    font.variableAxes: ({ "FILL": 1 })
                    // Font biến thiên + distance field vẽ vỡ nét icon trên cửa sổ thật (CB-058).
                    renderType: Text.NativeRendering
                }
            }

            Image {
                visible: root.coverPath !== ""
                anchors.fill: parent
                // Nghe thử dùng ảnh bìa TRÊN MẠNG (không tải gì về máy), còn
                // nhạc đã tải thì là đường dẫn trên đĩa và cần tiền tố file://.
                source: root.coverPath === ""
                    ? ""
                    : (root.coverPath.startsWith("http") ? root.coverPath : "file://" + root.coverPath)
                fillMode: Image.PreserveAspectCrop
                asynchronous: true
            }
        }

        // Mặt nạ bo góc cho coverFrame — không hiển thị, chỉ dùng làm maskSource.
        Rectangle {
            id: coverMask

            anchors.fill: coverFrame
            radius: Theme.radiusSm
            visible: false
            layer.enabled: true
        }
    }

    Column {
        anchors.left: coverContainer.right
        anchors.leftMargin: root.textSpacing
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        spacing: Theme.spacingXs / 2

        Text {
            width: parent.width
            text: root._displayTitle
            color: Theme.onSurface
            font.pixelSize: Theme.fontSizeMd
            font.family: Theme.fontFamily
            elide: Text.ElideRight
        }

        Text {
            width: parent.width
            text: root._displayArtist
            color: Theme.onSurfaceVariant
            font.pixelSize: Theme.fontSizeSm
            font.family: Theme.fontFamily
            elide: Text.ElideRight
        }
    }
}
