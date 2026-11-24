#!/usr/bin/env python3
"""Đo ĐỘ NHÁM vân nền của từng hộp nổi — mắt người cãi nhau được, số thì không.

    python3 scripts/sandbox_drive.py A surfaces      # chụp + ghi surfaces.json
    python3 scripts/measure_glass.py                 # rồi đọc số

Kính để ảnh nền lọt qua ⇒ nền LỐM ĐỐM ⇒ độ lệch chuẩn cao.
Tấm đục tự đắp ⇒ phẳng lì ⇒ gần 0. Đo NHÁM, KHÔNG đo SÁNG: một tấm đục màu
xám nhạt vẫn sáng, vẫn là tấm đục, và trên ảnh nền của bro nó vẫn lạc lõng.

Cách lấy mẫu, và đây là chỗ đã tốn một vòng (CB-056): chia lòng hộp thành ô
nhỏ, đo từng ô, rồi lấy PHÂN VỊ 25 của các ô. Chữ và ảnh bìa làm vài ô nhám
vọt lên; phân vị dưới bỏ qua chúng và nói đúng cái NỀN. Lấy trung bình cả hộp,
hay lấy một dải sát viền, là đo trúng chữ rồi kết luận tấm gỗ cũng là kính.
"""
import json
import statistics
import sys
from pathlib import Path

from PIL import Image

SHOTS = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/lumen-sandbox/A/shots")

INSET = 6      # bỏ viền + góc bo
TILE = 10      # cạnh ô mẫu
CALM = 0.50    # trung vị các ô — chữ nằm ở đuôi trên, bị bỏ qua
# Ngưỡng CĂN theo hai mốc thật, không bốc ra: thanh bên (kính cửa sổ) ra
# 0.016, bảng tài khoản (tấm đục cố ý) ra 0.002. Mọi mặt kính trong app nằm
# trong 0.010-0.029, tấm đục thấp hơn một bậc mười lần.
GLASS = 0.006  # dưới ngưỡng này là phẳng lì: một tấm đục


def luma(px, i, j):
    r, g, b = px[i, j][:3]
    return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255.0


def roughness(img, x, y, w, h):
    px = img.load()
    x0, y0 = max(0, x + INSET), max(0, y + INSET)
    x1, y1 = min(img.width, x + w - INSET), min(img.height, y + h - INSET)
    tiles = []
    for j in range(y0, y1 - TILE, TILE):
        for i in range(x0, x1 - TILE, TILE):
            vals = [luma(px, a, b) for b in range(j, j + TILE) for a in range(i, i + TILE)]
            tiles.append((statistics.pstdev(vals), statistics.fmean(vals)))
    if not tiles:
        return None
    tiles.sort()
    return tiles[min(len(tiles) - 1, int(len(tiles) * CALM))]


def main() -> int:
    manifest = json.loads(SHOTS.joinpath("surfaces.json").read_text(encoding="utf-8"))
    print(f"{'hộp':<38} {'nhám':>7} {'sáng':>7}  kết luận")
    print("-" * 68)
    flat = []
    for entry in manifest:
        if "x" not in entry:
            continue
        img = Image.open(SHOTS / entry["shot"]).convert("RGB")
        got = roughness(img, entry["x"], entry["y"], entry["w"], entry["h"])
        if got is None:
            continue
        rough, mean = got
        verdict = "kính" if rough >= GLASS else "TẤM ĐỤC"
        if rough < GLASS:
            flat.append(entry["label"])
        print(f"{entry['label']:<38} {rough:7.4f} {mean:7.4f}  {verdict}")
    print()
    print("Tấm đục CỐ Ý (menu, toast, hộp xác nhận — QĐ-039/QĐ-040): bảng tài khoản.")
    print("Tấm đục nào KHÁC hiện ra ở trên là một hộp bị bỏ sót, không phải chủ ý.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
