.pragma library

// Bảng màu kim loại CỐ ĐỊNH cho bục top 1/2/3 (vàng/bạc/đồng) -- KHÔNG lấy
// theo Theme, đây là chủ ý của chủ dự án: huy chương phải ra huy chương,
// không đổi theo hình nền người dùng như mọi màu khác trong app. Ngoại lệ
// này chỉ áp dụng cho ba màu vật liệu này.
//
// Dùng chung giữa PodiumBacking.qml (viền thẻ) và PodiumRow.qml (huy hiệu số
// hạng) qua đúng một chỗ để hai nơi không lệch màu.
//
// Mỗi mảng ba nấc [sáng, vừa, đậm] -- dùng làm GradientStop 0.0/0.55/1.0
// theo chiều dọc để ra cảm giác ánh kim (sáng trên, đậm dưới).
var PALETTES = {
    gold: ["#fff3c4", "#c9971e", "#7a4e0a"],
    silver: ["#f2f4f7", "#9aa3ad", "#565c64"],
    bronze: ["#e3a469", "#a8621f", "#5b3410"]
};

// Màu chữ số hạng đọc được trên nền gradient tương ứng ở trên.
var TEXT_COLORS = {
    gold: "#4a2f00",
    silver: "#2b2f33",
    bronze: "#fff1e0"
};

// Bảng màu NGỌN LỬA, tách khỏi bảng màu kim loại ở trên. Kim loại phải đúng
// sắc huy chương (hơi tối, có chiều sâu) còn lửa thì phải SÁNG mới ra tàn lửa —
// dùng chung một bảng thì lửa nhìn như bùn.
//
// Mỗi hạng ba sắc: sáng nhất, sắc chính, và một sắc ngả cam/lạnh cho có chiều.
var FLAMES = {
    gold: ["#ffe08a", "#ffb020", "#ff7a1a"],
    silver: ["#ffffff", "#cfdaea", "#93a7c4"],
    bronze: ["#ffc27a", "#ef8a35", "#ff5f1a"]
};

// Hạt trắng rắc thêm vào MỌI ngọn lửa — vài đốm sáng trắng làm cả đám sống hẳn
// lên, giống tàn lửa thật.
var SPARK = "#ffffff";

function flamesFor(medal) {
    return FLAMES[medal] || ["#ffffff", "#ffffff", "#ffffff"];
}

function stopsFor(medal) {
    return PALETTES[medal] || ["transparent", "transparent", "transparent"];
}

function textFor(medal) {
    return TEXT_COLORS[medal] || "#000000";
}
