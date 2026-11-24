import QtQuick

// Vòng sóng nhạc của dynsle: 56 vạch đầu tròn ngồi quanh viền ảnh bìa (cả bốn
// góc bo), mỗi vạch chĩa thẳng ra ngoài. dynsle đọc cava thật; Lumen chưa có
// luồng phổ âm, nên vạch nhảy theo một nhịp giả — đang phát thì nhảy, dừng thì
// lặng dần về sát viền. Chỉ vẽ khi `running` (màn Đang phát mở), đỡ tốn CPU.
Canvas {
    id: root

    // Hình chữ nhật ảnh bìa, toạ độ trong Canvas này.
    property real artX: 0
    property real artY: 0
    property real artSize: 0
    property real artRadius: Theme.radiusLg
    property bool playing: false
    property bool running: false
    property color barColor: Theme.primary

    readonly property int barCount: 56
    readonly property real barWidth: 4
    readonly property real gap: 9
    readonly property real minLength: 3
    readonly property real maxLength: 22
    readonly property int frameMs: 33

    property var levels: []
    property real phase: 0

    function target(i) {
        if (!root.playing)
            return 0
        const a = Math.abs(Math.sin(root.phase * (2.1 + (i % 7) * 0.37) + i * 1.7)
                           * Math.sin(root.phase * 1.3 + i * 0.45))
        return 0.18 + 0.82 * Math.pow(a, 1.4) * (0.55 + 0.45 * Math.sin(root.phase * 5.2 + i))
    }

    Timer {
        interval: root.frameMs
        repeat: true
        running: root.running && root.visible
        onTriggered: {
            const dt = root.frameMs / 1000
            root.phase += dt
            const next = []
            const k = Math.min(1, dt * (root.playing ? 14 : 5))
            for (let i = 0; i < root.barCount; i++) {
                const now = root.levels.length === root.barCount ? root.levels[i] : 0
                next.push(now + (Math.max(0, root.target(i)) - now) * k)
            }
            root.levels = next
            root.requestPaint()
        }
    }

    onPaint: {
        const ctx = getContext("2d")
        ctx.reset()
        if (root.artSize <= 0 || root.levels.length !== root.barCount)
            return
        const r = Math.min(root.artRadius, root.artSize / 2)
        const side = root.artSize - 2 * r
        const arc = Math.PI * r / 2
        const segs = [side, arc, side, arc, side, arc, side, arc]
        const perimeter = 4 * side + 4 * arc
        const x0 = root.artX, y0 = root.artY, w = root.artSize, h = root.artSize
        ctx.lineCap = "round"
        ctx.lineWidth = root.barWidth
        ctx.strokeStyle = root.barColor
        for (let i = 0; i < root.barCount; i++) {
            let d = (i + 0.5) / root.barCount * perimeter
            let k = 0
            while (k < 7 && d > segs[k]) { d -= segs[k]; k++ }
            let px, py, nx, ny
            const corner = (cx, cy, a0) => {
                const a = a0 + d / r
                px = cx + Math.cos(a) * r; py = cy + Math.sin(a) * r
                nx = Math.cos(a); ny = Math.sin(a)
            }
            switch (k) {
            case 0: px = x0 + r + d; py = y0; nx = 0; ny = -1; break
            case 1: corner(x0 + w - r, y0 + r, -Math.PI / 2); break
            case 2: px = x0 + w; py = y0 + r + d; nx = 1; ny = 0; break
            case 3: corner(x0 + w - r, y0 + h - r, 0); break
            case 4: px = x0 + w - r - d; py = y0 + h; nx = 0; ny = 1; break
            case 5: corner(x0 + r, y0 + h - r, Math.PI / 2); break
            case 6: px = x0; py = y0 + h - r - d; nx = -1; ny = 0; break
            default: corner(x0 + r, y0 + r, Math.PI); break
            }
            const level = root.levels[i]
            const len = root.minLength + level * (root.maxLength - root.minLength)
            ctx.globalAlpha = 0.45 + 0.55 * level
            ctx.beginPath()
            ctx.moveTo(px + nx * root.gap, py + ny * root.gap)
            ctx.lineTo(px + nx * (root.gap + len), py + ny * (root.gap + len))
            ctx.stroke()
        }
    }
}
