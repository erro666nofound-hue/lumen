import QtQuick

// Nơi duy nhất trong app hiển thị thông báo cho người dùng.
//
// Mọi tín hiệu lỗi của các bridge phải chảy về đây. Trước khi có nó, app phát
// errorOccurred nhưng KHÔNG có gì lắng nghe — dán trùng một link thì app lặng lẽ
// không tải và cũng không nói gì, người dùng tưởng app hỏng.
//
// Hai cái bẫy QML đã dính ở đây, đừng lặp lại:
//  1. KHÔNG neo (anchors) con trực tiếp của Column theo trục dọc/ngang mà Column
//     quản lý — nó bị bỏ qua và các mục chồng lên nhau. Vì vậy mỗi thông báo được
//     bọc trong một "slot" chiếm hết bề ngang, rồi mới canh giữa BÊN TRONG slot đó.
//  2. Tên role của model KHÔNG được trùng tên property của delegate. Đặt trùng thì
//     `kind: toast.kind` trở thành gán chính nó, giá trị không bao giờ tới nơi.
Item {
    id: root

    readonly property int lifetimeMs: 3600
    readonly property int maxVisible: 3
    readonly property int stackSpacing: Theme.spacingSm

    function showInfo(message) { _push(message, "info") }
    function showError(message) { _push(message, "error") }

    function _push(message, kind) {
        if (!message || message.length === 0)
            return
        while (toastModel.count >= root.maxVisible)
            toastModel.remove(0)
        toastModel.append({ toastText: message, toastKind: kind })
    }

    function _remove(row) {
        if (row >= 0 && row < toastModel.count)
            toastModel.remove(row)
    }

    ListModel { id: toastModel }

    Column {
        id: stack

        anchors.left: parent.left
        anchors.right: parent.right
        // Design R-1: toast rơi xuống từ mép trên, giữa vùng nội dung.
        anchors.top: parent.top
        spacing: root.stackSpacing

        Repeater {
            model: toastModel

            delegate: Item {
                id: slot

                required property int index
                required property string toastText
                required property string toastKind

                width: stack.width
                height: toast.implicitHeight

                Toast {
                    id: toast

                    anchors.horizontalCenter: parent.horizontalCenter
                    message: slot.toastText
                    kind: slot.toastKind

                    onDismissed: root._remove(slot.index)

                    Timer {
                        running: true
                        interval: root.lifetimeMs
                        onTriggered: root._remove(slot.index)
                    }
                }
            }
        }
    }
}
