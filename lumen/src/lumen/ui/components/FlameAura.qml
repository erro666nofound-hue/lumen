import QtQuick
import QtQuick.Particles

// Quầng lửa cho bài đang phát.
//
// Cơ chế cố ý làm ĐƠN GIẢN, đúng như chủ dự án mô tả: hạt sinh ra thành một
// dải DÀY ĐẶC ở ĐÁY item, bay thẳng LÊN, và co nhỏ dần rồi biến mất ở nửa sau
// đời của nó. Không mờ dần, không đổi màu — chỉ một màu duy nhất và co lại.
// Bản trước phát hạt ở cả bốn cạnh và vẫn để hở chỗ; một dải đáy đủ dày thì
// vừa kín hơn vừa dễ chỉnh.
//
// MÀU lấy từ bảng màu Noctalia (theo hình nền của máy) qua Theme, không phải
// màu cam đóng cứng — engine đọc bảng màu của theme.
//
// Đặt làm anh em NẰM DƯỚI item cần bao, phủ rộng hơn nó:
//   FlameAura { anchors.fill: rowBg; anchors.margins: -10; running: isPlaying }
//   Rectangle { id: rowBg; ... }   // nền này phải ĐỤC, nếu không hạt lộ vào trong
Item {
    id: root

    property bool running: false
    // Một màu duy nhất, lấy theo hình nền. Nơi dùng có thể đổi nếu cần.
    property color emberColor: Theme.primary
    // Nhiều sắc cho một ngọn lửa. Rỗng = chỉ dùng emberColor.
    //
    // Một ImageParticle chỉ mang ĐƯỢC một màu, nên nhiều sắc nghĩa là nhiều
    // NHÓM hạt, mỗi nhóm một emitter riêng. Đó là lý do khối bên dưới lặp lại
    // bốn lần thay vì một vòng lặp — Emitter/ImageParticle phải khai báo tĩnh
    // để hệ hạt biết trước các nhóm.
    property var emberColors: []
    // Tỉ lệ hạt TRẮNG rắc thêm, trên tổng lượng hạt.
    property real sparkShare: 0.12
    property color sparkColor: "#ffffff"

    readonly property color _tone1: root.emberColors.length > 0
        ? root.emberColors[0] : root.emberColor
    readonly property color _tone2: root.emberColors.length > 1
        ? root.emberColors[1] : root._tone1
    readonly property color _tone3: root.emberColors.length > 2
        ? root.emberColors[2] : root._tone2

    readonly property real _rate: Math.max(30, root.width * root.density)

    // Số hạt mỗi giây trên mỗi pixel bề ngang. Phải theo tỉ lệ chứ không được
    // là số cố định: hàng rộng 1100px và thẻ rộng 150px cần lượng hạt khác hẳn
    // nhau để trông cùng một mật độ.
    //
    // density/particleSize để nơi dùng chỉnh được (bục top 1/2/3 cho hạng 1
    // cháy mạnh hơn hạng 3); mặc định là giá trị đã chỉnh cho hàng nhạc.
    property real density: 1.1

    // Quãng bay (riseSpeed * particleLife) phải LỚN HƠN chiều cao quầng, nếu
    // không hạt sinh ở đáy chỉ leo được một đoạn và phần trên hở toang. Trước
    // đây hai con số này CỐ ĐỊNH (700ms × 86px/s ≈ 60px) nên quầng chỉ vừa cho
    // hàng nhạc thấp; đặt quanh thẻ bục cao ~200px thì lửa đọng hết dưới đáy.
    // Nay suy từ chính chiều cao mình đang bao, còn tốc độ giữ nguyên để trông
    // vẫn là cùng một ngọn lửa dù thẻ cao hay thấp.
    property int riseSpeed: 86
    readonly property real travelFactor: 1.15
    readonly property int particleLife: Math.max(
        420, Math.round(root.height * root.travelFactor / root.riseSpeed * 1000))
    property int particleSize: 11
    // Dải sinh hạt tụt xuống DƯỚI đáy quầng bấy nhiêu pixel. Sinh đúng ở mép
    // thì ngay dưới thẻ trông trống trơn — lửa như bị cắt ngang chân thẻ.
    property int spawnBelow: 0
    readonly property int fadeMs: 220

    visible: opacity > 0.01
    opacity: root.running ? 1 : 0
    clip: false

    Behavior on opacity {
        NumberAnimation { duration: root.fadeMs; easing.type: Easing.OutCubic }
    }

    ParticleSystem {
        id: system

        // Dừng hẳn mô phỏng khi không phát, không chỉ ẩn đi: hạt được tính lại
        // mỗi khung hình, để chạy nền là đốt GPU cho thứ không ai nhìn.
        running: root.running
        anchors.fill: parent

        // Một ImageParticle cho MỖI nhóm màu. Hình tròn ĐẶC một màu (không
        // phải chấm sáng mờ dần của Qt), không biến thiên, không trong suốt dần.
        //
        // KHÔNG entryEffect: hạt phải sinh ra ĐÃ TO SẴN rồi nhỏ dần tới khi tắt.
        // `entryEffect: Scale` cho vòng đời nhỏ → to → nhỏ, nhìn như hạt nảy ra
        // chứ không như tàn lửa bay lên rồi lụi.
        ImageParticle {
            groups: ["t1"]
            source: "../images/dot.png"
            color: root._tone1
            colorVariation: 0.0
            alpha: 1.0
            entryEffect: ImageParticle.None
        }

        ImageParticle {
            groups: ["t2"]
            source: "../images/dot.png"
            color: root._tone2
            colorVariation: 0.0
            alpha: 1.0
            entryEffect: ImageParticle.None
        }

        ImageParticle {
            groups: ["t3"]
            source: "../images/dot.png"
            color: root._tone3
            colorVariation: 0.0
            alpha: 1.0
            entryEffect: ImageParticle.None
        }

        ImageParticle {
            groups: ["spark"]
            source: "../images/dot.png"
            color: root.sparkColor
            colorVariation: 0.0
            alpha: 1.0
            entryEffect: ImageParticle.None
        }

        // Bốn emitter cùng một dải sinh ở ĐÁY, chỉ khác nhóm màu và tỉ lệ.
        component Ember: Emitter {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            anchors.bottomMargin: -root.spawnBelow
            height: 1

            lifeSpan: root.particleLife
            // Biến thiên nhỏ: lệch nhiều thì vài hạt bay vượt hẳn quầng.
            lifeSpanVariation: root.particleLife * 0.18
            sizeVariation: root.particleSize * 0.25
            endSize: 0

            velocity: PointDirection {
                y: -root.riseSpeed
                yVariation: root.riseSpeed * 0.45
                xVariation: 6
            }
        }

        Ember {
            group: "t1"
            emitRate: root._rate * (1 - root.sparkShare) * 0.45
            size: root.particleSize
        }

        Ember {
            group: "t2"
            emitRate: root._rate * (1 - root.sparkShare) * 0.35
            size: root.particleSize * 0.85
        }

        Ember {
            group: "t3"
            emitRate: root._rate * (1 - root.sparkShare) * 0.20
            size: root.particleSize * 0.7
        }

        // Đốm trắng: ít và nhỏ, chỉ để lấy điểm sáng.
        Ember {
            group: "spark"
            emitRate: root._rate * root.sparkShare
            size: root.particleSize * 0.55
        }

    }
}
