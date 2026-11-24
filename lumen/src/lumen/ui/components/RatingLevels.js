.pragma library

// Bốn nấc yêu thích, một nguồn sự thật duy nhất.
//
// Trước đây nhãn nằm ở ArtistsView, thang nấc nằm ở ArtistRatingSlider, nên
// thêm một nấc là phải sửa hai chỗ. Màu để dạng TÊN thuộc tính của Theme chứ
// không phải mã màu cứng: file .js `.pragma library` không nhìn thấy Theme,
// còn QML thì tra được bằng Theme[key] (CLAUDE.md mục 5: cấm mã màu cứng).

const STEPS = [-1, 0, 1, 2]
const LABELS = ["Chặn", "Bình thường", "Yêu thích", "Rất yêu thích"]
const TONE_KEYS = ["error", "onSurfaceVariant", "primary", "tertiary"]

// Nấc nào ứng với điểm này. Điểm lạ thì coi như "bình thường".
function indexOf(rating) {
    const i = STEPS.indexOf(rating)
    return i < 0 ? 1 : i
}
