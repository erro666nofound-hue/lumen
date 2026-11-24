import QtQuick
import QtQuick.Effects

// Ảnh bìa ghép của một track (design R-1): 1 bìa thì phủ kín, 2 bìa chia đôi,
// 3 bìa thì bìa đầu chiếm nửa trái, 4 bìa thành lưới 2×2. Không có bìa nào thì
// hiện icon nốt nhạc trên nền kính.
Item {
    id: root

    property var covers: []
    property int radius: Theme.radiusLg
    readonly property int gap: 2
    readonly property int n: Math.min(4, root.covers ? root.covers.length : 0)

    function src(path) {
        return path.startsWith("http") ? path : "file://" + path
    }

    RoundedImage {
        anchors.fill: parent
        radius: root.radius
        visible: root.n <= 1
        source: root.n === 1 ? root.src(root.covers[0]) : ""

        MIcon {
            anchors.centerIn: parent
            visible: root.n === 0
            name: "music_note"
            size: Math.max(Theme.iconSize, root.width * 0.3)
        }
    }

    // Từ 2 bìa trở lên: mỗi ô là một RoundedImage, bo đúng góc ngoài của nó
    // bằng một mặt nạ chung bo theo khung.
    Item {
        anchors.fill: parent
        visible: root.n >= 2
        layer.enabled: root.n >= 2
        layer.effect: MultiEffect {
            maskEnabled: true
            maskSource: maskRect
            autoPaddingEnabled: false
        }

        Repeater {
            model: root.n >= 2 ? root.n : 0

            Image {
                required property int index
                readonly property real half: (root.width - root.gap) / 2
                readonly property bool tall: (root.n === 2) || (root.n === 3 && index === 0)

                x: (root.n === 3 ? (index === 0 ? 0 : half + root.gap)
                    : (index % 2) * (half + root.gap))
                y: root.n === 2 ? 0
                    : (root.n === 3 ? (index === 2 ? half + root.gap : 0)
                       : Math.floor(index / 2) * (half + root.gap))
                width: half
                height: tall ? root.height : half
                source: root.src(root.covers[index])
                fillMode: Image.PreserveAspectCrop
                asynchronous: true
            }
        }
    }

    Rectangle {
        id: maskRect
        anchors.fill: parent
        radius: root.radius
        visible: false
        layer.enabled: true
    }
}
