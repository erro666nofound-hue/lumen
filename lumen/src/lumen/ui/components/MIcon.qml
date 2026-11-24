import QtQuick

// Một icon của bộ dynsle: Material Symbols Rounded, tô đặc (FILL 1). Tên icon
// là chữ ("play_arrow", "music_note"), font tự ghép thành hình. Chỗ nào muốn
// nét viền (mục chưa chọn ở thanh bên) thì đặt filled: false. QĐ-041.
Text {
    id: root

    property string name: ""
    property real size: Theme.iconSize
    property bool filled: true

    text: root.name
    font.family: Theme.iconFont
    font.pixelSize: root.size
    font.variableAxes: ({ "FILL": root.filled ? 1 : 0, "wght": 400, "GRAD": 0, "opsz": 24 })
    // Font biến thiên + distance field vẽ vỡ nét icon trên cửa sổ thật (CB-058).
    renderType: Text.NativeRendering
    color: Theme.onSurfaceVariant
    horizontalAlignment: Text.AlignHCenter
    verticalAlignment: Text.AlignVCenter
}
