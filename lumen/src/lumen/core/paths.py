from __future__ import annotations

import os
from pathlib import Path

from lumen.core.metadata import sanitize_filename

APP_ID = "com.toast.Lumen"
APP_NAME = "Lumen"
APP_SLUG = "lumen"


def on_windows() -> bool:
    """Report whether Lumen is running on Windows.

    Một hàm chứ không phải hằng số: test cần giả lập cả hai hệ điều hành trên
    cùng một máy, mà hằng số thì chốt cứng lúc nạp module.
    """
    return os.name == "nt"


def _windows_dir(env_var: str, fallback: str) -> Path:
    """Return %APPDATA%/%LOCALAPPDATA% style folder for Lumen.

    Windows dùng TÊN app viết hoa (`Lumen`), không phải slug thường như Linux —
    người dùng Windows mở thư mục đó ra và thấy tên app bên cạnh các app khác.
    """
    root = os.environ.get(env_var)
    return (Path(root) if root else Path.home() / fallback) / APP_NAME


def _config_home() -> Path:
    """Return $XDG_CONFIG_HOME (default: ~/.config)."""
    value = os.environ.get("XDG_CONFIG_HOME")
    return Path(value) if value else Path.home() / ".config"


def _expand_home(value: str) -> Path:
    """Expand a user-dirs.dirs value such as "$HOME/Music" into a real path."""
    value = value.strip().strip('"')
    if value == "$HOME":
        return Path.home()
    if value.startswith("$HOME/"):
        return Path.home() / value[len("$HOME/"):]
    return Path(value).expanduser()


def _xdg_user_dir(key: str, fallback: Path) -> Path:
    """Resolve an XDG user directory from the environment or ~/.config/user-dirs.dirs.

    The file stores fully qualified keys (XDG_MUSIC_DIR="$HOME/Music"), so the
    lookup must match that exact prefix -- matching on the bare key silently
    never fires and every caller quietly falls back.
    """
    env_var = f"XDG_{key}_DIR"
    raw = os.environ.get(env_var)
    if raw:
        return _expand_home(raw)

    user_dirs_file = _config_home() / "user-dirs.dirs"
    try:
        with open(user_dirs_file, "r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if line.startswith("export "):
                    line = line[len("export "):].lstrip()
                if line.startswith(f"{env_var}="):
                    return _expand_home(line.split("=", 1)[1])
    except OSError:
        pass

    return fallback


def data_dir() -> Path:
    """Return the folder holding the database and covers.

    Windows: %LOCALAPPDATA%/Lumen — dữ liệu này gắn với MỘT máy (database, ảnh
    bìa, có thể vài trăm MB), không nên đồng bộ theo hồ sơ người dùng.
    """
    if on_windows():
        return _windows_dir("LOCALAPPDATA", "AppData/Local")
    xdg_data_home = os.environ.get("XDG_DATA_HOME")
    if xdg_data_home:
        return Path(xdg_data_home) / APP_SLUG
    return Path.home() / ".local" / "share" / APP_SLUG


def config_dir() -> Path:
    """Return the folder holding config.json.

    Windows: %APPDATA%/Lumen — cấu hình thì NÊN đi theo người dùng sang máy
    khác, khác với data_dir().
    """
    if on_windows():
        return _windows_dir("APPDATA", "AppData/Roaming")
    return _config_home() / APP_SLUG


def state_dir() -> Path:
    """Return the folder holding the log file."""
    if on_windows():
        return _windows_dir("LOCALAPPDATA", "AppData/Local") / "state"
    xdg_state_home = os.environ.get("XDG_STATE_HOME")
    if xdg_state_home:
        return Path(xdg_state_home) / APP_SLUG
    return Path.home() / ".local" / "state" / APP_SLUG


def control_address() -> str:
    """Return the address of the control channel, in the form this OS uses.

    Hai hệ điều hành nói hai thứ tiếng khác nhau ở đây:

    * Linux/macOS — một ĐƯỜNG DẪN tới file socket. Đặt trong $XDG_RUNTIME_DIR
      vì thư mục đó vốn riêng tư (0700) và tự xoá khi đăng xuất, đúng bằng vòng
      đời một socket cần. Không có nó thì dùng state dir.
    * Windows — một CÁI TÊN. Windows không có socket kiểu file; Qt sẽ dựng một
      named pipe từ cái tên này.
    """
    if on_windows():
        return f"{APP_SLUG}-control"
    runtime = os.environ.get("XDG_RUNTIME_DIR")
    if runtime:
        return str(Path(runtime) / f"{APP_SLUG}-control.sock")
    return str(state_dir() / "control.sock")


def cache_dir() -> Path:
    """Return the folder holding throwaway files."""
    if on_windows():
        return _windows_dir("LOCALAPPDATA", "AppData/Local") / "cache"
    xdg_cache_home = os.environ.get("XDG_CACHE_HOME")
    if xdg_cache_home:
        return Path(xdg_cache_home) / APP_SLUG
    return Path.home() / ".cache" / APP_SLUG


def music_dir() -> Path:
    """Return music directory: <thư mục Nhạc của người dùng>/Lumen."""
    if on_windows():
        # Windows không có XDG; thư mục Nhạc luôn nằm ngay trong hồ sơ người dùng.
        return Path.home() / "Music" / APP_NAME
    music_base = _xdg_user_dir("MUSIC", Path.home() / "Music")
    return music_base / APP_NAME


def track_dir(playlist_name: str) -> Path:
    """Return the folder holding one track's mp3 files: <music_dir>/<safe name>."""
    return music_dir() / sanitize_filename(playlist_name)


def db_path() -> Path:
    """Return path to SQLite library database."""
    return data_dir() / "library.db"


def covers_dir() -> Path:
    """Return path to directory storing cover images."""
    return data_dir() / "covers"


def log_path() -> Path:
    """Return path to application log file."""
    return state_dir() / f"{APP_SLUG}.log"


def config_path() -> Path:
    """Return path to main config file (JSON)."""
    return config_dir() / "config.json"


def noctalia_colors_path() -> Path:
    """Return path to the Noctalia palette that the theme engine follows."""
    return _config_home() / "noctalia" / "colors.json"


def hypr_custom_dir() -> Path:
    """Return the Hyprland folder where Lumen writes its shortcut file."""
    return _config_home() / "hypr" / "custom"


def lumen_shim() -> str:
    """Return the command a Hyprland shortcut runs to reach Lumen."""
    shim = Path.home() / ".local" / "bin" / "lumen"
    return str(shim) if shim.exists() else "lumen"


def dynsle_colors_path() -> Path:
    """Return path to the matugen palette that the dynsle shell writes."""
    state = os.environ.get("XDG_STATE_HOME")
    base = Path(state) if state else Path.home() / ".local" / "state"
    return base / "quickshell" / "user" / "generated" / "colors.json"


def desktop_colors_path() -> Path:
    """Return the desktop palette to follow: dynsle's when present, else Noctalia's.

    QĐ-041: bro đã thay Noctalia bằng dynsle (shell tự làm). File của Noctalia
    vẫn nằm trên đĩa nhưng đã đứng im — đọc nó là theo một desktop đã chết.
    """
    dynsle = dynsle_colors_path()
    return dynsle if dynsle.exists() else noctalia_colors_path()


def package_dir() -> Path:
    """Return directory containing lumen package."""
    return Path(__file__).resolve().parent.parent


def ui_dir() -> Path:
    """Return directory containing QML UI files."""
    return package_dir() / "ui"


def ensure_dirs() -> None:
    """Create all necessary application directories."""
    for directory in [data_dir(), config_dir(), state_dir(), cache_dir(), covers_dir(), music_dir()]:
        directory.mkdir(parents=True, exist_ok=True)
