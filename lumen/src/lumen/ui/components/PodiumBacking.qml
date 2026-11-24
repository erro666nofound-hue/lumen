import QtQuick
import "MedalColors.js" as MedalColors

// Nền đục + viền kim loại cho thẻ có huy hiệu (bục top 1/2/3). Ba lớp, TỪ
// DƯỚI LÊN:
//   1) Rectangle Theme.surface ĐỤC HẲN -- bắt buộc vì PodiumRow đặt
//      FlameAura ngay phía sau nhóm thẻ; thiếu lớp này thì hạt lửa lộ xuyên
//      qua nền kính mờ (translucent) bình thường của RecommendCard.
//   2) Rectangle gradient ba nấc (sáng->vừa->đậm) phủ toàn thẻ -- khối kim
//      loại thô, màu lấy từ MedalColors.js.
//   3) Rectangle lõm vào đúng `thickness` tô lại `faceColor` (màu nền hiện
//      tại của thẻ, đổi theo hover) -- lộ lớp (2) ra thành viền quanh mép.
// Chỉ hiện khi `medal !== ""`. Nơi dùng (RecommendCard.qml) PHẢI đặt
// component này TRƯỚC Column nội dung để cả ba lớp nằm DƯỚI ảnh/chữ.
Item {
    id: root

    property string medal: ""   // "" | "gold" | "silver" | "bronze"
    property int radius: 0
    property color faceColor: "transparent"

    readonly property int thickness: 3
    readonly property var stops: MedalColors.stopsFor(root.medal)

    visible: root.medal !== ""

    Rectangle {
        anchors.fill: parent
        radius: root.radius
        color: Theme.surface
    }

    Rectangle {
        anchors.fill: parent
        radius: root.radius
        gradient: Gradient {
            orientation: Gradient.Vertical
            GradientStop { position: 0.0; color: root.stops[0] }
            GradientStop { position: 0.55; color: root.stops[1] }
            GradientStop { position: 1.0; color: root.stops[2] }
        }
    }

    Rectangle {
        anchors.fill: parent
        anchors.margins: root.thickness
        radius: Math.max(0, root.radius - root.thickness)
        color: root.faceColor
    }
}
