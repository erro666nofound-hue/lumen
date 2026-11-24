# Lumen

Máy nghe nhạc cá nhân cho **Arch Linux + Hyprland**, giao diện kính bo góc.
Dán link YouTube (hoặc tìm theo tên) → tải mp3 → xếp vào các track do bạn tự tạo.

Đây là **bản công khai**: chạy hoàn toàn trên máy bạn — **không tài khoản, không đăng nhập,
không máy chủ, không đồng bộ**. Thư viện, cấu hình và file nhạc nằm trên máy bạn.

## Có gì

- Tải nhạc từ link YouTube, hoặc tìm bài theo tên ngay trong app (yt-dlp).
- Nhập file mp3 có sẵn trên máy vào một track.
- Track tự tạo: đổi tên, kéo đổi thứ tự bài, chọn nhiều bài để xoá, sắp xếp.
- Thanh phát: phát/dừng, tua, tốc độ, âm lượng, lặp, xáo bài; cửa sổ **Mini Lumen** nổi.
- Trang nhạc sĩ + gợi ý dựa trên lịch sử nghe; lịch sử tải và lịch sử nghe.
- Màu theo hình nền/hệ thống hoặc tự chọn, ảnh nền riêng, độ kính và chuyển động chỉnh được.
- Phím tắt toàn hệ thống cho Hyprland (tự đặt trong **Cài đặt → Phím tắt**).
- MPRIS: điều khiển bằng `playerctl`, phím media, thanh trạng thái.
- Lệnh terminal: `lumen --toggle | --next | --prev | --play | --pause | --seek ±10 |
  --volume N | --mute | --slot 1-3 | --mini | --status | --quit` (xem `lumen --help`).

## Cài

**1. Cập nhật máy và cài các gói cần thiết** (tự gõ, sẽ hỏi mật khẩu). Phải là `-Syu`,
không phải `-S`: cài lẻ một gói mới lên một máy chưa cập nhật là các gói lệch nhau và Lumen không mở được.

```bash
sudo pacman -Syu --needed git python pyside6 python-mpv python-mutagen yt-dlp ffmpeg mpv ttf-material-symbols-variable
```

**2. Lấy mã nguồn** (repo công khai, không cần đăng nhập GitHub):

```bash
git clone https://github.com/erro666nofound-hue/lumen.git ~/Projects/lumen
```

**3. Cài:**

```bash
cd ~/Projects/lumen
./install.sh
```

Script tự kiểm tra từng gói. Thiếu gói nào thì nó in đúng lệnh `sudo pacman -Syu --needed …`, chạy lệnh đó rồi
chạy lại `./install.sh`. Cài xong, mở launcher và gõ **Lumen**, hoặc gõ `lumen` trong terminal.

## Cập nhật

```bash
cd ~/Projects/lumen
git pull
```

Rồi tắt và mở lại Lumen. Không cần chạy lại `./install.sh`, trừ khi nó báo cần gói mới.

## Lumen không mở được

Lỗi được ghi vào `~/.local/state/lumen/crash.log`. Thấy `undefined symbol` trong đó = gói hệ thống
lệch phiên bản (cập nhật dở): chạy `sudo pacman -Syu` rồi mở lại.

## Gỡ

```bash
cd ~/Projects/lumen
./uninstall.sh
```

## Trong repo có gì

| Thư mục | Là gì |
|---|---|
| `lumen/src/lumen/` | mã nguồn app: `core/` (Python thuần), `bridge/` (nối Qt), `ui/` (QML) |
| `lumen/tests/` | test (`cd lumen && python3 -m pytest`) |
| `lumen/scripts/`, `install.sh`, `uninstall.sh` | cài / gỡ / chạy thử |
