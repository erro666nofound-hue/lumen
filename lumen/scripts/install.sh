#!/bin/bash
set -euo pipefail

# Xác định đường dẫn repo
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "📦 Kiểm tra dependencies..."

# Kiểm tra các công cụ cần thiết
check_command() {
  if ! command -v "$1" &> /dev/null; then
    return 1
  fi
  return 0
}

# Kiểm tra python3
if ! check_command python3; then
  echo "❌ python3 không được tìm thấy"
  echo "   Chạy: sudo pacman -Syu --needed python"
  exit 1
fi

# Kiểm tra ffmpeg
if ! check_command ffmpeg; then
  echo "❌ ffmpeg không được tìm thấy"
  echo "   Chạy: sudo pacman -Syu --needed ffmpeg"
  exit 1
fi

# Kiểm tra yt-dlp
if ! check_command yt-dlp; then
  echo "❌ yt-dlp không được tìm thấy"
  echo "   Chạy: sudo pacman -Syu --needed yt-dlp"
  exit 1
fi

# Kiểm tra Python modules
check_python_module() {
  python3 -c "import $1" 2>/dev/null && return 0 || return 1
}

missing_modules=()

if ! check_python_module "PySide6"; then
  missing_modules+=("pyside6")
else
  # `import PySide6` không nạp thư viện Qt; QtCore + QtQml mới nạp thật. Hỏng ở
  # đây mà PySide6 vẫn có = pyside6 và qt6 lệch phiên bản (cập nhật dở, vd.
  # `pacman -S pyside6` kéo bản build cho Qt mới về một máy còn Qt cũ).
  if ! qt_error="$(python3 -c "import PySide6.QtCore, PySide6.QtQml" 2>&1)"; then
    echo "❌ PySide6 có nhưng không nạp được Qt:"
    echo "   $(printf '%s\n' "$qt_error" | tail -1)"
    echo "   Gói hệ thống đang lệch phiên bản. Cập nhật cả máy rồi chạy lại ./install.sh:"
    echo "   sudo pacman -Syu"
    exit 1
  fi
fi

if ! check_python_module "mpv"; then
  missing_modules+=("python-mpv")
fi

if ! check_python_module "mutagen"; then
  missing_modules+=("python-mutagen")
fi

if ! check_python_module "yt_dlp"; then
  missing_modules+=("yt-dlp")
fi

# Mọi icon của R-1 là chữ trong font Material Symbols Rounded — thiếu font thì
# icon hiện thành chữ "graphic_eq", "play_arrow"...
# Đọc HẾT danh sách rồi mới so: `fc-list | grep -q` dưới `pipefail` báo hỏng
# oan khi grep thoát sớm làm fc-list bị cắt ống.
fonts="$(fc-list : family 2>/dev/null || true)"
if [[ "$fonts" != *"Material Symbols Rounded"* ]]; then
  missing_modules+=("ttf-material-symbols-variable")
fi

if [ ${#missing_modules[@]} -gt 0 ]; then
  echo "❌ Thiếu gói:"
  for mod in "${missing_modules[@]}"; do
    echo "   - $mod"
  done
  echo "   Chạy: sudo pacman -Syu --needed ${missing_modules[*]}"
  exit 1
fi

echo "✓ Tất cả dependencies đã được tìm thấy"

# Tạo thư mục cần thiết
echo "📂 Tạo thư mục..."
mkdir -p "$HOME/.local/bin"
mkdir -p "$HOME/.local/share/icons/hicolor/scalable/apps"
mkdir -p "$HOME/.local/share/applications"

# ── Shim khởi chạy ───────────────────────────────────────────────────────────
# VÌ SAO CẦN SHIM: đường dẫn repo có thể chứa ký tự đặc biệt của shell (: > & ...).
# Theo Desktop Entry spec, launcher phải BỎ QUOTE của Exec rồi mới chạy — nhiều
# launcher (trong đó có Noctalia) ghép các phần đã bỏ quote lại thành một lệnh
# shell, khiến '>' bị hiểu là redirect và app im lặng không mở.
# Shim này nằm ở đường dẫn sạch, quote đường dẫn repo đúng một lần và cố định.
echo "🔗 Cài shim khởi chạy..."
SHIM="$HOME/.local/bin/lumen"
cat > "$SHIM" <<SHIM_EOF
#!/bin/sh
# Sinh tự động bởi scripts/install.sh — không sửa tay, chạy lại install.sh để cập nhật.
exec /usr/bin/python3 "$REPO/run.py" "\$@"
SHIM_EOF
chmod +x "$SHIM"
"$SHIM" --help >/dev/null 2>&1 || { echo "❌ Shim không chạy được: $SHIM"; exit 1; }
echo "   ✓ $SHIM (đã test chạy được)"

# ── Icon theme ───────────────────────────────────────────────────────────────
# KHÔNG BAO GIỜ tạo ~/.local/share/icons/hicolor/index.theme.
# Đã thử một lần và hỏng nặng: theo icon theme spec, index.theme được tìm theo thứ tự
# ưu tiên của search path và CÁI ĐẦU TIÊN TÌM THẤY THẮNG. ~/.local/share/icons đứng
# trước /usr/share/icons, nên một index.theme tối giản ở đó THAY THẾ file của hệ thống
# (khai báo 650 thư mục) và làm biến mất icon của mọi app có icon PNG theo cỡ.
# Chỉ cần copy file icon vào đúng chỗ là đủ — đã kiểm chứng bằng QIcon.fromTheme.
ICON_THEME="$HOME/.local/share/icons/hicolor"

echo "🎨 Cài icon..."
cp "$REPO/packaging/icons/com.toast.Lumen.svg" "$ICON_THEME/scalable/apps/"

# Tạo desktop entry — Exec trỏ vào shim, không bao giờ trỏ thẳng vào repo
echo "🚀 Tạo desktop entry..."
sed "s|__EXEC__|$SHIM|g" "$REPO/packaging/com.toast.Lumen.desktop" \
  > "$HOME/.local/share/applications/com.toast.Lumen.desktop"

# Cập nhật cache — KHÔNG nuốt lỗi, vì chính lỗi bị nuốt đã che mất bug icon
echo "🔄 Cập nhật cache..."
# Không chạy gtk-update-icon-cache: thư mục này cố ý không có index.theme nên lệnh đó
# luôn báo "No theme index file", và cache sinh ra ở đây cũng sẽ che mất thư mục hệ thống.
if command -v update-desktop-database &> /dev/null; then
  update-desktop-database "$HOME/.local/share/applications" || \
    echo "   ⚠️  update-desktop-database báo lỗi"
fi

# Tự kiểm chứng: desktop entry phải hợp lệ và Exec phải chạy được
if command -v desktop-file-validate &> /dev/null; then
  desktop-file-validate "$HOME/.local/share/applications/com.toast.Lumen.desktop" || \
    echo "   ⚠️  desktop entry không hợp lệ"
fi

# Không đụng cấu hình Hyprland ở đây: phím tắt bro tự đặt trong Cài đặt › Phím tắt,
# và luật cửa sổ Mini app tự ghi vào ~/.config/hypr/custom/lumen-keys.lua mỗi lần mở.
echo ""
echo "✨ Cài đặt hoàn tất!"
echo ""
echo "📋 Tóm tắt:"
echo "   ✓ Desktop entry: $HOME/.local/share/applications/com.toast.Lumen.desktop"
echo "   ✓ Icon: $HOME/.local/share/icons/hicolor/scalable/apps/com.toast.Lumen.svg"
echo "   ✓ Lệnh chạy: $HOME/.local/bin/lumen"
echo "   ✓ Dữ liệu app: $HOME/.local/share/lumen/"
echo "   ✓ Cấu hình: $HOME/.config/lumen/"
echo ""
echo "🎵 Để gỡ cài đặt, chạy: $REPO/scripts/uninstall.sh"
echo ""
echo "🚀 Mở launcher và gõ 'Lumen' để khởi chạy ứng dụng!"
