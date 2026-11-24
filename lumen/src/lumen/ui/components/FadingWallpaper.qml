import QtQuick

// Ảnh nền, đổi ảnh thì MỜ DẦN sang ảnh mới thay vì nháy một cái.
//
// Hai lớp ảnh luân phiên: lớp đang hiện mờ đi trong khi lớp mới hiện lên. Một
// lớp duy nhất thì đổi `source` là ảnh cũ biến mất ngay lập tức, còn ảnh mới
// thì chưa đọc xong — người dùng thấy một nháy trống.
Item {
    id: root

    property string source: ""
    property int radius: 0
    property int fadeMs: 320

    // Lớp nào đang cầm ảnh hiện tại.
    property bool _frontIsA: true

    onSourceChanged: {
        if (root._frontIsA)
            layerB.source = root.source
        else
            layerA.source = root.source
        root._frontIsA = !root._frontIsA
    }

    RoundedImage {
        id: layerA

        anchors.fill: parent
        radius: root.radius
        opacity: root._frontIsA ? 1 : 0

        Behavior on opacity {
            NumberAnimation { duration: root.fadeMs; easing.type: Easing.InOutCubic }
        }
    }

    RoundedImage {
        id: layerB

        anchors.fill: parent
        radius: root.radius
        opacity: root._frontIsA ? 0 : 1

        Behavior on opacity {
            NumberAnimation { duration: root.fadeMs; easing.type: Easing.InOutCubic }
        }
    }

    Component.onCompleted: {
        // Lần đầu: đặt thẳng vào lớp A, không chạy hoạt ảnh từ hư không.
        layerA.source = root.source
        root._frontIsA = true
    }
}
