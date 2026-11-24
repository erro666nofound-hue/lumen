.pragma library

// Định dạng thời lượng cho cả thanh phát lẫn Mini Lumen.
//
// Trước đây hàm này nằm trong PlayerBar; Mini Lumen cần đúng cách hiển thị ấy,
// mà chép thêm một bản là mở đường cho hai chỗ lệch nhau.

// Player báo bằng mili-giây. Bài từ một tiếng trở lên hiện h:mm:ss, còn lại m:ss.
function format(ms) {
    const totalSeconds = Math.max(0, Math.floor(ms / 1000))
    const hours = Math.floor(totalSeconds / 3600)
    const minutes = Math.floor((totalSeconds % 3600) / 60)
    const seconds = totalSeconds % 60
    const paddedSeconds = seconds < 10 ? "0" + seconds : String(seconds)
    if (hours > 0) {
        const paddedMinutes = minutes < 10 ? "0" + minutes : String(minutes)
        return hours + ":" + paddedMinutes + ":" + paddedSeconds
    }
    return minutes + ":" + paddedSeconds
}
