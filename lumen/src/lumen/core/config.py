from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import paths

log = logging.getLogger(__name__)


@dataclass
class Config:
    """Application configuration with default values."""

    music_dir: str | None = None
    audio_bitrate: str = "192"
    volume: int = 80
    playback_speed: float = 1.0
    window_width: int = 1040
    window_height: int = 660
    theme_follow_noctalia: bool = True
    #: Màu chủ đạo khi TỰ CHỈNH (bỏ trống = màu mặc định của Lumen).
    theme_accent: str = ""
    #: Nền riêng của Lumen: rỗng, "gradient:Tên", hoặc đường dẫn ảnh.
    wallpaper: str = ""
    #: Các ảnh đã từng chọn, mới nhất trước — để lần sau bấm lại, khỏi mở thư mục.
    wallpapers: list[str] = field(default_factory=list)
    #: Design R-1: kính / độ nảy / tốc độ hiệu ứng (khoá trong core/look.py).
    look_glass: str = "kinh"
    look_bounce: str = "vua"
    look_speed: str = "vua"
    #: Phím tắt toàn cục (Cài đặt › Phím tắt) và track của ba ô phím (vòng 2 R-1).
    keybinds: dict[str, str] = field(default_factory=dict)
    key_slots: dict[str, int] = field(default_factory=dict)

    def resolved_music_dir(self) -> Path:
        """Return configured music directory or default."""
        if self.music_dir:
            return Path(self.music_dir)
        return paths.music_dir()


def _defaults() -> Config:
    """Giá trị mặc định, đã tính tới hệ điều hành đang chạy.

    Windows không có Noctalia, nên "lấy màu theo hình nền máy" ở đó sẽ ra bảng
    màu dự phòng và người dùng tưởng app hỏng màu. Đặt ở ĐÂY chứ không phải
    trong `load_config`: lần chạy đầu chưa có file cấu hình thì hàm đó thoát sớm,
    và mặc định theo hệ sẽ không bao giờ được áp.
    """
    config = Config()
    if paths.on_windows():
        config.theme_follow_noctalia = False
    return config


def load_config() -> Config:
    """Load configuration from file or return defaults if missing/corrupted.

    Đọc TỪNG trường một cách có chủ đích (thay vì `Config(**data)`) để một file
    cấu hình hỏng hay bị sửa tay không làm app chết. Cái giá: thêm trường mới mà
    quên thêm vào đây thì nó được GHI xuống đĩa nhưng không bao giờ đọc lại —
    đã xảy ra thật với màu và ảnh nền: đang chạy thì nhớ, thoát hẳn rồi mở lại
    là mất sạch. `tests/test_config.py` có test đi vòng cho MỌI trường để chặn.
    """
    config_file = paths.config_path()

    if not config_file.exists():
        return _defaults()

    try:
        with open(config_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError, ValueError) as e:
        log.warning(f"Failed to load config from {config_file}: {e}")
        return _defaults()

    config = _defaults()

    if isinstance(data.get("music_dir"), str):
        config.music_dir = data["music_dir"]
    if isinstance(data.get("audio_bitrate"), str):
        config.audio_bitrate = data["audio_bitrate"]
    if isinstance(data.get("volume"), int):
        config.volume = max(0, min(100, data["volume"]))
    if isinstance(data.get("playback_speed"), (int, float)):
        config.playback_speed = max(0.0, min(3.0, float(data["playback_speed"])))
    if isinstance(data.get("window_width"), int):
        config.window_width = max(720, data["window_width"])
    if isinstance(data.get("window_height"), int):
        config.window_height = max(480, data["window_height"])
    if isinstance(data.get("theme_follow_noctalia"), bool):
        config.theme_follow_noctalia = data["theme_follow_noctalia"]
    if isinstance(data.get("theme_accent"), str):
        config.theme_accent = data["theme_accent"]
    if isinstance(data.get("wallpaper"), str):
        config.wallpaper = data["wallpaper"]
    if isinstance(data.get("wallpapers"), list):
        config.wallpapers = [item for item in data["wallpapers"] if isinstance(item, str)]
    if isinstance(data.get("keybinds"), dict):
        config.keybinds = {k: v for k, v in data["keybinds"].items() if isinstance(v, str)}
    if isinstance(data.get("key_slots"), dict):
        config.key_slots = {k: v for k, v in data["key_slots"].items() if isinstance(v, int)}
    for key in ("look_glass", "look_bounce", "look_speed"):
        if isinstance(data.get(key), str):
            setattr(config, key, data[key])

    return config


def save_config(cfg: Config) -> None:
    """Save configuration to file atomically."""
    config_file = paths.config_path()
    config_dir = config_file.parent

    config_dir.mkdir(parents=True, exist_ok=True)

    temp_file = config_dir / f"{config_file.name}.tmp"

    try:
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(asdict(cfg), f, indent=2)

        temp_file.replace(config_file)
    except (OSError, json.JSONDecodeError) as e:
        log.error(f"Failed to save config: {e}")
        if temp_file.exists():
            temp_file.unlink()
        raise
