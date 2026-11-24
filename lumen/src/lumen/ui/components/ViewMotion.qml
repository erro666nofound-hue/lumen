import QtQuick

// Chuyển mục theo design R-1 (khối `.view.enter` của artifact): trang mới mờ
// dần hiện ra, trượt lên 10px và phóng từ 0.985, có nảy (OutBack như dynsle).
// Trang cũ chỉ mờ đi thật nhanh. Gắn vào một view: `ViewMotion { shown: … }`.
// `replay` đổi giá trị thì chạy lại cảnh vào — dùng khi mở track khác trong
// cùng một TrackView.
Item {
    id: root

    property Item target: parent
    property bool shown: false
    property var replay: 0

    readonly property int enterMs: 420
    readonly property int fadeInMs: 260
    readonly property int leaveMs: 140
    readonly property real rise: 10
    readonly property real startScale: 0.985
    // Độ nảy theo Cài đặt › Độ nảy (design R-1).
    readonly property real overshoot: Theme.overshoot

    width: 0
    height: 0

    Translate { id: shift }
    Scale {
        id: zoom
        origin.x: root.target ? root.target.width / 2 : 0
        origin.y: 0
    }

    Component.onCompleted: {
        root.target.transform = [zoom, shift]
        root.target.opacity = root.shown ? 1 : 0
    }
    onShownChanged: root.shown ? enter.restart() : leave.restart()
    onReplayChanged: if (root.shown) enter.restart()

    ParallelAnimation {
        id: enter

        onStarted: leave.stop()

        NumberAnimation {
            target: root.target; property: "opacity"; from: 0; to: 1
            duration: Math.max(1, (root.fadeInMs) * Theme.motionScale); easing.type: Easing.OutCubic
        }
        NumberAnimation {
            target: shift; property: "y"; from: root.rise; to: 0
            duration: Math.max(1, (root.enterMs) * Theme.motionScale); easing.type: Easing.OutBack; easing.overshoot: root.overshoot
        }
        NumberAnimation {
            target: zoom; property: "xScale"; from: root.startScale; to: 1
            duration: Math.max(1, (root.enterMs) * Theme.motionScale); easing.type: Easing.OutBack; easing.overshoot: root.overshoot
        }
        NumberAnimation {
            target: zoom; property: "yScale"; from: root.startScale; to: 1
            duration: Math.max(1, (root.enterMs) * Theme.motionScale); easing.type: Easing.OutBack; easing.overshoot: root.overshoot
        }
    }

    NumberAnimation {
        id: leave

        onStarted: enter.stop()
        target: root.target; property: "opacity"; to: 0
        duration: Math.max(1, (root.leaveMs) * Theme.motionScale); easing.type: Easing.OutCubic
    }
}
