#!/bin/bash
set -euo pipefail

# Xác định đường dẫn repo
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "🗑️  Gỡ cài đặt Lumen..."

# Gỡ desktop entry
if [ -f "$HOME/.local/share/applications/com.toast.Lumen.desktop" ]; then
  rm "$HOME/.local/share/applications/com.toast.Lumen.desktop"
  echo "✓ Đã xóa desktop entry"
fi

# Gỡ shim khởi chạy
if [ -f "$HOME/.local/bin/lumen" ]; then
  rm "$HOME/.local/bin/lumen"
  echo "✓ Đã xóa shim $HOME/.local/bin/lumen"
fi

# Gỡ icon
if [ -f "$HOME/.local/share/icons/hicolor/scalable/apps/com.toast.Lumen.svg" ]; then
  rm "$HOME/.local/share/icons/hicolor/scalable/apps/com.toast.Lumen.svg"
  echo "✓ Đã xóa icon"
fi

# Cập nhật cache
if command -v gtk-update-icon-cache &> /dev/null; then
  gtk-update-icon-cache -f "$HOME/.local/share/icons/hicolor" 2>/dev/null || true
fi

if command -v update-desktop-database &> /dev/null; then
  update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
fi

# Xử lý cờ --purge
if [[ "${1:-}" == "--purge" ]]; then
  echo ""
  echo "⚠️  Chế độ purge sẽ xóa dữ liệu người dùng:"
  echo "   - $HOME/.local/share/lumen/"
  echo "   - $HOME/.config/lumen/"
  echo ""
  read -p "Bạn có chắc chắn muốn xóa? (y/N) " -n 1 -r
  echo
  if [[ $REPLY =~ ^[Yy]$ ]]; then
    if [ -d "$HOME/.local/share/lumen" ]; then
      rm -rf "$HOME/.local/share/lumen"
      echo "✓ Đã xóa $HOME/.local/share/lumen/"
    fi
    if [ -d "$HOME/.config/lumen" ]; then
      rm -rf "$HOME/.config/lumen"
      echo "✓ Đã xóa $HOME/.config/lumen/"
    fi
  else
    echo "❌ Hủy bỏ"
    exit 1
  fi
fi

echo ""
echo "✨ Gỡ cài đặt hoàn tất!"
echo ""
echo "📝 Ghi chú:"
echo "   ⚠️  Thư mục nhạc ~/Music/Lumen vẫn được giữ nguyên (nếu muốn xóa, hãy làm thủ công)"
echo "   💾 Để xóa cả dữ liệu, chạy lại với cờ --purge:"
echo "      $0 --purge"
