#!/usr/bin/env bash
# Đóng gói Lumen cho Linux thành một thư mục chạy được, không cần cài Python.
#
# Nuitka biên dịch Python thành mã máy thật (khác PyInstaller chỉ đóng gói
# bytecode, gỡ ra bằng công cụ có sẵn). Đó là lý do dự án chọn Nuitka.
#
# Cần: python-nuitka, patchelf, gcc  (pacman -S python-nuitka patchelf)
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT="$REPO/dist/linux"
RUNTIME="$OUT/Lumen.dist/runtime"

echo "==> Dọn bản cũ"
rm -rf "$OUT"
mkdir -p "$OUT"

echo "==> Biên dịch"
cd "$REPO"
python3 -m nuitka \
  --standalone \
  --enable-plugin=pyside6 \
  --include-package=lumen \
  --include-package=yt_dlp \
  --include-package=mutagen \
  --include-module=mpv \
  --include-data-dir=src/lumen/ui=lumen/ui \
  --output-dir="$OUT" \
  --output-filename=Lumen \
  --company-name=Lumen \
  --product-name=Lumen \
  --assume-yes-for-downloads \
  run.py

echo "==> Gói kèm libmpv và ffmpeg"
# App tìm hai thứ này trong thư mục `runtime/` cạnh file chạy — xem core/tools.py.
mkdir -p "$RUNTIME"
cp -L /usr/lib/libmpv.so.2 "$RUNTIME/" 2>/dev/null || echo "   !! không thấy libmpv.so.2"
cp -L "$(command -v ffmpeg)" "$RUNTIME/" 2>/dev/null || echo "   !! không thấy ffmpeg"

echo "==> Xong: $OUT/Lumen.dist/Lumen"
