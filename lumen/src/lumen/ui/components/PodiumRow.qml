import QtQuick

import "MedalColors.js" as MedalColors

// Bục "Most Recommend": hạng 2 bên trái, hạng 1 GIỮA và to hơn hẳn, hạng 3 bên
// phải. Ba thẻ canh đáy chung nên hạng 1 tự nhô cao hơn — không cần hằng số
// "độ nhô" riêng.
//
// Mỗi bệ gồm bốn lớp, TỪ DƯỚI LÊN: quầng lửa -> nền kim loại đục -> thẻ ->
// vệt loé. Nền kim loại (PodiumBacking) phải RỘNG HƠN thẻ đúng `medalRim` để
// lộ ra thành viền, và nó đục hẳn để hạt lửa không xuyên qua mặt thẻ — chủ dự
// án đã yêu cầu rõ: lửa chỉ được ở QUANH, không được thấy trong bài đang nghe.
//
// Ba bệ dùng chung một component nội tuyến `Medalist` thay vì chép ba lần: bản
// trước là ba khối gần như y hệt nhau dài 174 dòng, sửa một chỗ phải sửa ba.
//
// Đọc Player.previewVideoId/previewBusy/isPlaying trực tiếp để tính
// active/loading (RecommendCard không tự biết Player đang phát videoId nào).
// Vẫn KHÔNG tự gọi Player.preview/Downloads — chỉ bắn signal ra ngoài.
//
// Huy hiệu số hạng là con CỦA CHÍNH BỆ, không neo qua id sang một cấp cha
// khác: Qt Quick anchors chỉ áp dụng giữa cha/con hoặc anh em CÙNG cha trực
// tiếp. Neo vào "cháu cách một cấp" lặng lẽ không có tác dụng, không một cảnh
// báo runtime nào — đã dính thật một lần, cả ba huy hiệu rơi về toạ độ (0,0).
Item {
    id: root

    // Tối đa 3 object (videoId/title/uploader/durationText/url/thumbnail),
    // ĐÃ xếp hạng 1,2,3 theo đúng thứ tự index — xem Discovery.podium.
    property var songs: []

    signal previewRequested(string videoId)
    // Kèm chính thẻ vừa bấm, để nơi dùng đặt bảng chọn track ngay cạnh nó.
    signal addRequested(string url, string title, var anchor)

    // Bục co theo bề ngang CỦA CHÍNH NÓ, không theo một ngưỡng chung của cả
    // cửa sổ: thứ quyết định vừa hay không là cột nội dung còn lại sau thanh
    // bên, chứ không phải bề ngang cửa sổ.
    //
    // Ba mức: đủ chỗ -> bày ngang như bục thật; chật -> vẫn ba thẻ ngang nhưng
    // thu nhỏ theo tỉ lệ; quá chật -> xếp chồng, hạng 1 nằm trên, hạng 2 và 3
    // chia đôi hàng dưới. Trước khi có mức này, bục cứng 588px và ở cửa sổ hẹp
    // nó tràn ra ngoài cả hai phía — hạng 2 chui vào sau thanh bên.
    readonly property int fullWidth: 588
    readonly property int stackBelow: 430
    readonly property bool stacked: root.width > 0 && root.width < root.stackBelow

    readonly property real fit: root.width <= 0
        ? 1 : Math.min(1, root.width / root.fullWidth)
    readonly property int smallWidth: root.stacked
        ? Math.max(120, Math.floor((root.width - root.gap) / 2))
        : Math.max(112, Math.round(160 * root.fit))
    readonly property int largeWidth: root.stacked
        ? Math.min(220, root.width)
        : Math.max(154, Math.round(220 * root.fit))
    // Khi xếp chồng, khe dọc phải chừa thêm nửa huy hiệu: huy hiệu nhô lên
    // khỏi mép trên thẻ, thiếu chỗ là số 2 và 3 chạm vào đáy thẻ hạng 1.
    readonly property int gap: Theme.spacingLg
    readonly property int stackGap: Theme.spacingLg + root.badgeSize / 2
    readonly property int badgeSize: 26
    // Thẻ bục cao hơn thẻ thường ~30%. Chiều cao thẻ suy từ nội dung, nên chỉnh
    // qua khung ảnh (xem RecommendCard.coverScale) — số này chọn để phần TỔNG
    // tăng khoảng 30%, không phải để riêng ảnh tăng 30%.
    readonly property real coverBoost: 1.55
    readonly property real hoverScale: 1.06
    readonly property int hoverMs: 160
    // Chiều cao BỆ ĐỨNG của từng hạng. Nó vừa là "lãnh địa" của hạng đó, vừa
    // là thứ nhấc thẻ lên những độ cao khác nhau — nên chân và đỉnh ba thẻ tự
    // so le, không cần con số bù riêng.
    readonly property var plinthFor: ({ 1: 64, 2: 44, 3: 28 })
    // Bề ngang lãnh địa mỗi hạng. Chia đều hết chỗ có: trước đây ba thẻ dính
    // vào nhau ở giữa còn hai bên trống trơn.
    readonly property int plotWidth: Math.floor(root.width / 3)
    readonly property int medalRim: 3
    readonly property int auraMargin: Theme.spacingSm
    readonly property int fadeMs: 260

    function songAt(index) {
        return (root.songs && root.songs.length > index) ? root.songs[index] : null
    }

    height: stage.height + root.badgeSize / 2 + root.auraMargin

    opacity: 0
    Component.onCompleted: root.opacity = 1

    Behavior on opacity {
        NumberAnimation { duration: root.fadeMs; easing.type: Easing.OutCubic }
    }

    // Một bệ của bục: thẻ + viền kim loại + quầng lửa + vệt loé + huy hiệu.
    component Medalist: Item {
        id: pedestal

        required property var song
        required property int rank
        required property string medal
        // 1.0 = cháy mạnh nhất (hạng 1). Ngọn lửa nhỏ dần theo thứ hạng, nên
        // nhìn cả bục là biết ngay ai nhất mà không cần đọc số.
        required property real burn
        property bool large: false

        readonly property bool present: pedestal.song !== null

        // Lãnh địa rộng bằng nhau; thẻ canh giữa trong đó, bệ trải hết.
        width: root.stacked ? (pedestal.large ? root.largeWidth : root.smallWidth) : root.plotWidth
        height: card.height + root.plinthFor[pedestal.rank]
        visible: pedestal.present
        // Hạng cao đứng trên: hạng 1 không bao giờ bị hai hạng kia che, kể cả
        // khi quầng lửa của chúng lấn sang. Rê chuột thì nhấc hẳn lên trước.
        z: (card.hovered ? 10 : 0) + (4 - pedestal.rank)

        PodiumPlinth {
            // Rộng hơn thẻ một chút, KHÔNG trải hết lãnh địa: trải hết thì ba
            // bệ chạm nhau thành một dải sàn, mất luôn cảm giác từng khối riêng.
            anchors.horizontalCenter: parent.horizontalCenter
            // Rộng hơn hẳn thẻ (lửa phun dày ở chân thẻ, bệ hẹp thì bị nuốt
            // gần hết), NHƯNG kẹp trong lãnh địa của mình: không kẹp thì ba bệ
            // chồng lên nhau 50-80px và bệ hạng 1 bị hai bệ kia vẽ đè lên —
            // chúng khai báo sau nên luôn nằm trên.
            width: Math.min(card.width * 1.55, pedestal.width - Theme.spacingSm)
            anchors.bottom: parent.bottom
            height: root.plinthFor[pedestal.rank]
            medal: pedestal.medal
            rank: pedestal.rank
            intensity: pedestal.burn
        }

        // Chỉ cụm THẺ phóng to khi rê chuột, bệ đứng yên: bệ là mặt đất của
        // hạng đó, phóng theo thì cả bục nhấp nhô như đang thở.
        //
        // transformOrigin ở ĐÁY để thẻ nở LÊN TRÊN, không thụt xuống ăn vào bệ.
        Item {
            id: cardGroup

            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.bottom: parent.bottom
            anchors.bottomMargin: root.plinthFor[pedestal.rank]
            transformOrigin: Item.Bottom
            scale: card.hovered ? root.hoverScale : 1

            Behavior on scale {
                NumberAnimation { duration: root.hoverMs; easing.type: Easing.OutBack }
            }

        FlameAura {
            anchors.fill: card
            anchors.margins: -root.auraMargin
            running: pedestal.present
            // Lửa mang màu chính của kim loại: hạng 1 cháy vàng, hạng 2 bạc,
            // hạng 3 đồng. Đây là ngoại lệ có chủ ý so với quy tắc "màu lấy
            // theo hình nền" — cùng lý do huy chương không đổi màu theo theme.
            emberColor: MedalColors.flamesFor(pedestal.medal)[0]
            // Ba sắc cho mỗi hạng, cộng đốm trắng — xem MedalColors.FLAMES.
            emberColors: MedalColors.flamesFor(pedestal.medal)
            sparkColor: MedalColors.SPARK
            // Bục cháy mạnh hơn hàng nhạc thường: dày hơn, hạt to hơn, bay
            // nhanh hơn, và sinh ở DƯỚI chân thẻ để không hở khoảng trống.
            density: 2.2 * pedestal.burn
            particleSize: Math.round(15 * (0.8 + 0.35 * pedestal.burn))
            riseSpeed: Math.round(130 * (0.85 + 0.3 * pedestal.burn))
            spawnBelow: root.auraMargin + 6
        }

        PodiumBacking {
            anchors.fill: card
            anchors.margins: -root.medalRim
            medal: pedestal.medal
            radius: Theme.radiusLg + root.medalRim
            // Đục hẳn: đây là thứ chặn hạt lửa lọt vào trong mặt thẻ. Màu theo
            // hạng nằm ở THÂN thẻ (RecommendCard.tintColor), không ở đây — lớp
            // này bị thẻ che gần hết nên tô ở đây gần như không thấy gì.
            faceColor: Theme.surface
        }

        RecommendCard {
            id: card

            anchors.horizontalCenter: parent.horizontalCenter
            anchors.bottom: parent.bottom
            width: pedestal.large ? root.largeWidth : root.smallWidth
            large: pedestal.large
            coverScale: root.coverBoost
            tintColor: MedalColors.stopsFor(pedestal.medal)[1]
            // Cả BỆ phóng to, không phóng riêng thẻ — xem RecommendCard.growOnHover.
            growOnHover: false
            title: pedestal.present ? pedestal.song.title : ""
            uploader: pedestal.present ? pedestal.song.uploader : ""
            durationText: pedestal.present ? pedestal.song.durationText : ""
            thumbnail: pedestal.present ? pedestal.song.thumbnail : ""
            active: pedestal.present && Player.previewVideoId === pedestal.song.videoId
                && Player.isPlaying
            loading: pedestal.present && Player.previewVideoId === pedestal.song.videoId
                && Player.previewBusy

            onPreviewRequested: root.previewRequested(pedestal.song.videoId)
            onAddRequested: root.addRequested(
                pedestal.song.url, pedestal.song.title, card)
        }

        ShineOverlay {
            anchors.fill: card
            radius: Theme.radiusLg
            running: cardHover.hovered
        }

        // Đặt SAU ShineOverlay: vệt loé không được quét đè lên nút bấm.
        HoverHandler { id: cardHover }

        Rectangle {
            anchors.horizontalCenter: card.horizontalCenter
            anchors.top: card.top
            anchors.topMargin: -root.badgeSize / 2
            width: root.badgeSize
            height: root.badgeSize
            radius: width / 2
            border.width: 2
            border.color: Theme.surface
            gradient: Gradient {
                orientation: Gradient.Vertical
                GradientStop { position: 0.0; color: MedalColors.stopsFor(pedestal.medal)[0] }
                GradientStop { position: 0.55; color: MedalColors.stopsFor(pedestal.medal)[1] }
                GradientStop { position: 1.0; color: MedalColors.stopsFor(pedestal.medal)[2] }
            }

            Text {
                anchors.centerIn: parent
                text: pedestal.rank
                color: MedalColors.textFor(pedestal.medal)
                font.pixelSize: Theme.fontSizeSm
                font.family: Theme.fontFamily
                font.bold: true
            }
        }
        }
    }

    // Toạ độ đặt tay thay vì anchors: hai cách bày (ngang / xếp chồng) cần hai
    // bộ neo khác hẳn nhau, mà anchors không tắt bật theo điều kiện được cho gọn.
    Item {
        id: stage

        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        width: root.stacked
            ? Math.min(root.width, root.smallWidth * 2 + root.gap)
            : root.plotWidth * 3
        height: root.stacked
            ? first.height + root.stackGap + Math.max(second.height, third.height)
            : first.height

        Behavior on width {
            NumberAnimation { duration: root.fadeMs; easing.type: Easing.OutCubic }
        }

        Medalist {
            id: first

            x: root.stacked ? (stage.width - width) / 2 : root.plotWidth
            y: root.stacked ? 0 : stage.height - height
            song: root.songAt(0)
            rank: 1
            medal: "gold"
            burn: 1.0
            large: true
        }

        Medalist {
            id: second

            x: root.stacked ? 0 : 0
            y: stage.height - height
            song: root.songAt(1)
            rank: 2
            medal: "silver"
            burn: 0.66
        }

        Medalist {
            id: third

            x: root.stacked ? stage.width - width : root.plotWidth * 2
            y: stage.height - height
            song: root.songAt(2)
            rank: 3
            medal: "bronze"
            burn: 0.42
        }
    }
}
