# 🎵 Lumen

Lumen là một ứng dụng nghe nhạc tối giản cho Arch Linux, được tối ưu hóa cho Hyprland + Noctalia.
Dán link YouTube → tải mp3 → xếp vào các track do bạn tự tạo.

UI được thiết kế với phong cách glass tối giản, ít cài đặt, tập trung vào trải nghiệm nghe nhạc.

## Yêu cầu hệ thống

- **OS:** Arch Linux
- **WM:** Hyprland (tuỳ chọn, nhưng khuyến khích)
- **Python:** 3.14+
- **Công cụ:** ffmpeg, yt-dlp
- **Qt:** PySide6 6.11+

### Cài đặt dependencies (Arch Linux)

```bash
sudo pacman -Syu --needed python pyside6 python-mpv python-mutagen yt-dlp ffmpeg mpv ttf-material-symbols-variable
```

## Cài đặt

Lệnh cài cho máy mới nằm ở **`README.md` ở gốc repo** (một chỗ duy nhất, đừng chép sang đây).

## Chạy ứng dụng

### Chế độ bình thường (sau khi cài)

Mở launcher và tìm kiếm **"Lumen"**.

Hoặc từ terminal:

```bash
python3 /path/to/lumen/run.py
```

### Chế độ phát triển (development)

Chạy từ source với log đầy đủ:

```bash
./scripts/dev.sh
```

Log sẽ in ra terminal, giúp debug nhanh hơn.

Để chạy với thêm tuỳ chọn:

```bash
./scripts/dev.sh --some-flag
```

## Bố cục dữ liệu người dùng

```
~/Music/Lumen/<slug>-<source_id>.mp3     File nhạc (người dùng thấy được)
~/.local/share/lumen/library.db          Cơ sở dữ liệu
~/.local/share/lumen/covers/<id>.jpg     Ảnh bìa
~/.config/lumen/config.json              Cấu hình
~/.local/state/lumen/lumen.log           Log ứng dụng
```

## Gỡ cài đặt

### Xóa launcher entry + icon

```bash
./scripts/uninstall.sh
```

### Xóa luôn cả dữ liệu

```bash
./scripts/uninstall.sh --purge
```

⚠️ **Lưu ý:** Thư mục `~/Music/Lumen` sẽ **không** được xóa tự động.
Nếu muốn xóa, hãy làm thủ công: `rm -rf ~/Music/Lumen`

## Cảnh báo: Đường dẫn đặc biệt

Repo được đặt trong thư mục chứa ký tự `:` và `>`. Vì lý do này:

- ⚠️ **TUYỆT ĐỐI không dùng `PYTHONPATH`** — dấu `:` là ký tự phân tách path của Python, sẽ làm vỡ import.
- ✓ App chỉ vào qua `run.py` ở gốc repo, file này tự định vị đúng đường dẫn.
- ✓ Mọi shell script đều quote đường dẫn: `"$REPO"`, không bao giờ `$REPO` trần.
- ✓ Python code luôn dùng `pathlib.Path`, không nối chuỗi path bằng `+` hay f-string.

## Tại sao không dùng venv?

Dự án **tuyệt đối không dùng virtual environment**:

- ✓ Tất cả dependencies (PySide6, python-mpv, mutagen, yt-dlp) đã cài sẵn ở hệ thống bằng pacman.
- ✗ Venv mặc định có `include-system-site-packages = false` → không nhìn thấy PySide6 → test xanh nhưng app chạy từ launcher sẽ chết.
- ✗ Dùng `pip install` trong venv sẽ ghi đè phiên bản system, dễ dẫn đến bug khó tìm.

**Nếu cần công cụ:** (pytest, linter, etc.)
- Báo cho chủ dự án cài bằng `sudo pacman -S <package>`
- Hoặc dùng `uvx <tool>` để chạy tạm thời (không tạo `.venv/` trong repo)

## License

MIT
