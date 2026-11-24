# Đóng gói Lumen cho Windows. PHẢI chạy TRÊN máy Windows.
#
# Nuitka biên dịch cho chính hệ đang chạy, không thể biên dịch chéo từ Linux —
# đây là lý do bước này phải làm trên máy Windows chứ không làm sẵn được.
#
# Cần cài trước trên Windows:
#   1. Python 3.12+ (đánh dấu "Add python.exe to PATH" lúc cài)
#   2. pip install nuitka PySide6 python-mpv yt-dlp mutagen requests
#   3. mpv-2.dll và ffmpeg.exe (tải rời, đặt vào thư mục runtime bên dưới)

$ErrorActionPreference = "Stop"
$Repo = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$Out = Join-Path $Repo "dist\windows"
$Runtime = Join-Path $Out "run.dist\runtime"

Write-Host "==> Dọn bản cũ"
if (Test-Path $Out) { Remove-Item -Recurse -Force $Out }
New-Item -ItemType Directory -Force -Path $Out | Out-Null

Write-Host "==> Biên dịch"
Set-Location $Repo
python -m nuitka `
  --standalone `
  --enable-plugin=pyside6 `
  --include-package=lumen `
  --include-package=yt_dlp `
  --include-package=mutagen `
  --include-module=mpv `
  --include-data-dir=src/lumen/ui=lumen/ui `
  --output-dir=$Out `
  --output-filename=Lumen.exe `
  --company-name=Lumen `
  --product-name=Lumen `
  --windows-console-mode=disable `
  --assume-yes-for-downloads `
  run.py

Write-Host "==> Chuẩn bị thư mục runtime"
# App tìm mpv-2.dll và ffmpeg.exe ở đây — xem core/tools.py.
New-Item -ItemType Directory -Force -Path $Runtime | Out-Null
Write-Host "    Chép mpv-2.dll và ffmpeg.exe vào: $Runtime"

Write-Host "==> Xong. Chạy thử: $Out\run.dist\Lumen.exe"
