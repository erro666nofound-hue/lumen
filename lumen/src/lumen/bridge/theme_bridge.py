"""Qt-facing theme bridge: exposes Noctalia colors and design tokens to QML.

Colors come from :mod:`lumen.core.theme_source`, which is pure Python and
knows nothing about Qt. When ``follow_noctalia`` is on, this bridge keeps the
palette live in sync with ``~/.config/noctalia/colors.json`` using a
``QFileSystemWatcher`` -- all watching/debouncing/retry logic lives here,
``theme_source.load_palette`` stays a plain, testable file reader.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

from PySide6.QtCore import Property, QFileSystemWatcher, QObject, QTimer, Signal, Slot
from PySide6.QtGui import QColor, QFontDatabase

from lumen.core import backgrounds, look, palettes, paths
from lumen.core.theme_source import (
    FALLBACK,
    TOKENS,
    is_valid_color,
    load_palette,
    load_palette_result,
    normalize_color,
)

log = logging.getLogger(__name__)

# dynsle chạy Google Sans Flex (QĐ-041: Lumen theo vibe dynsle).
_FONT_PRIORITY: list[str] = ["Google Sans Flex", "Adwaita Sans", "Inter", "Noto Sans", "DejaVu Sans"]

# Coalesce bursts of filesystem events (an editor or generator script can
# fire several in a row) into a single reload once things settle.
_RELOAD_DEBOUNCE_MS = 150
# If a reload lands mid-write and reads back FALLBACK, retry a few times
# before accepting it, instead of flashing the whole UI to fallback colors.
_FALLBACK_RETRY_MS = 300
_MAX_FALLBACK_RETRIES = 3


class ThemeBridge(QObject):
    """Expose theme colors and design tokens as QML properties."""

    changed = Signal()

    def __init__(
        self,
        follow_noctalia: bool = True,
        accent: str = "",
        wallpaper: str = "",
        wallpapers: list[str] | None = None,
        on_changed: Callable[[ThemeBridge], None] | None = None,
        feel: dict[str, str] | None = None,
        gate: Any | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._follow_noctalia = follow_noctalia
        self._accent = accent if is_valid_color(accent) else palettes.DEFAULT_ACCENT
        self._wallpaper = wallpaper
        # Ảnh đã bị xoá khỏi máy mà vẫn hiện trong bảng chọn thì bấm vào là nền
        # trống trơn — lọc ngay lúc nạp.
        self._wallpapers = backgrounds.surviving(list(wallpapers or []))
        # Ai muốn ghi lựa chọn xuống đĩa thì nối vào đây. Bridge không tự biết
        # cấu hình nằm ở đâu — đó là việc của app.py.
        self._on_changed = on_changed
        # Kính / độ nảy / tốc độ (design R-1) — khoá đã kiểm bằng core/look.
        given = feel or {}
        self._feel = {kind: look.clean(kind, given.get(kind, "")) for kind in ("glass", "bounce", "speed")}
        # F-4f: quyền cá nhân hoá. Optional như mọi bridge khác — dựng
        # ThemeBridge trần thì KHÔNG ai khoá, nên toàn bộ test màu cũ vẫn đúng.
        # Phải gán TRƯỚC `_palette()` ngay dưới: nguồn màu phụ thuộc vào nó.
        self._gate = gate
        if gate is not None:
            gate.changed.connect(self._on_plan_changed)
        self._colors: dict[str, str] = self._palette()
        self._font_family = self._detect_font_family()

        self._watcher: QFileSystemWatcher | None = None
        self._fallback_retries = 0

        self._reload_timer = QTimer(self)
        self._reload_timer.setSingleShot(True)
        self._reload_timer.timeout.connect(self._reload)

        self._fallback_retry_timer = QTimer(self)
        self._fallback_retry_timer.setSingleShot(True)
        self._fallback_retry_timer.timeout.connect(self._reload)

        if self._effective_follow():
            self._start_watching()

    # -- gói nào thì áp dụng được gì (F-4f) ----------------------------------

    def _may_personalise(self) -> bool:
        """Say whether the plan in force lets these choices actually apply."""
        return self._gate is None or self._gate.personalise

    def _effective_follow(self) -> bool:
        """Return the colour source in force — not necessarily the one chosen.

        Free thì LUÔN theo hệ điều hành (Noctalia). Chủ dự án chốt 2026-08-25:
        gói Free không chỉ mất nút đổi, nó ngưng ÁP DỤNG màu và ảnh nền riêng —
        khác với hướng F-4d đã đoán và ghi ở QĐ-010 mục "Còn treo".

        Lựa chọn cũ vẫn nằm nguyên trong file cấu hình (`self._accent`,
        `self._wallpaper` không bị xoá): lên Pro là thấy lại đúng thứ mình đã
        chọn, không phải dựng lại từ đầu. Đó là phần "không lấy mất" của luật 1.
        """
        if not self._may_personalise():
            return True
        return self._follow_noctalia

    def _effective_wallpaper(self) -> str:
        """Return the wallpaper actually painted right now — Free paints none."""
        return self._wallpaper if self._may_personalise() else ""

    def _on_plan_changed(self) -> None:
        """Đổi gói là đổi thứ ĐANG áp dụng, ngay giữa phiên — không đợi mở lại app.

        Đúng cái CB-019 cảnh báo, chỉ khác tầng: ở đây không phải binding QML
        đóng băng mà là bảng màu đóng băng. Người vừa trả tiền phải thấy nền của
        mình quay lại NGAY.
        """
        if self._effective_follow():
            # `_start_watching` ghi đè `self._watcher` nên gọi hai lần là rò một
            # watcher; ở đây tín hiệu đổi gói bắn nhiều lần được nên phải chốt.
            if self._watcher is None:
                self._start_watching()
        else:
            self.stop_watching()
        self._apply_colors(self._palette())
        # `_apply_colors` im lặng khi bảng màu không đổi, nhưng ẢNH NỀN thì vừa
        # đổi — vẫn phải báo cho QML, không thì nền cũ nằm lại trên màn hình.
        self.changed.emit()

    def _palette(self) -> dict[str, str]:
        """Return the palette from whichever source is currently in force."""
        if self._effective_follow():
            return load_palette()
        return palettes.palette_from_accent(self._accent)

    @Slot(bool)
    def setFollowNoctalia(self, follow: bool) -> None:
        """Switch between following the wallpaper theme and a hand-picked colour."""
        if not self._may_personalise():
            return
        if follow == self._follow_noctalia:
            return
        self._follow_noctalia = follow
        if follow:
            self._start_watching()
        else:
            self.stop_watching()
        self._apply_colors(self._palette())
        self.changed.emit()
        self._remember()

    @Slot(str)
    def setAccent(self, accent: str) -> None:
        """Pick the colour the whole application is built from."""
        # Khoá DUY NHẤT còn lại (QML không còn khoá, QĐ-041); personal_use luôn mở.
        if not self._may_personalise():
            return
        if not is_valid_color(accent):
            return
        cleaned = normalize_color(accent)
        if cleaned == self._accent:
            return
        self._accent = cleaned
        if not self._follow_noctalia:
            self._apply_colors(self._palette())
        self.changed.emit()
        self._remember()

    @Slot(str)
    def setWallpaper(self, value: str) -> None:
        """Set the background image, or "" for none."""
        if not self._may_personalise():
            return
        cleaned = backgrounds.clean_path(value)
        # Chép vào kho riêng: nhớ đường dẫn gốc thôi thì người dùng dọn thư mục
        # Tải về là ảnh biến mất khỏi bảng chọn.
        if cleaned:
            cleaned = backgrounds.store(cleaned) or cleaned
        if cleaned == self._wallpaper:
            return
        self._wallpaper = cleaned
        self._wallpapers = backgrounds.remember(self._wallpapers, cleaned)
        self.changed.emit()
        self._remember()

    @Slot(str)
    def forgetWallpaper(self, path: str) -> None:
        """Drop one image from the remembered list (the file itself is untouched)."""
        # Cửa thứ TƯ, và là cửa duy nhất từng quên hỏi quyền. Ba setter trên đều
        # chặn, cái này thì không — mà nó là cửa DUY NHẤT xoá được lựa chọn cũ.
        # Đo được bằng cách chạy app thật: gọi lúc Free thì `wallpaper` trong
        # config.json về "" và không lên Pro nào lấy lại được.
        if not self._may_personalise():
            return
        cleaned = backgrounds.clean_path(path)
        if cleaned not in self._wallpapers:
            return
        self._wallpapers = [item for item in self._wallpapers if item != cleaned]
        if self._wallpaper == cleaned:
            self._wallpaper = ""
        # Quên nghĩa là bỏ hẳn: bản sao trong kho của Lumen không còn ai dùng.
        # Ảnh GỐC của người dùng không bị đụng tới.
        kept = Path(cleaned)
        if kept.parent == backgrounds.store_dir():
            try:
                kept.unlink(missing_ok=True)
            except OSError:
                log.exception("Cannot remove stored wallpaper %s", kept)
        self.changed.emit()
        self._remember()

    @Slot(str, str)
    def setFeel(self, kind: str, value: str) -> None:
        """Change one of glass / bounce / speed and remember it."""
        if kind not in self._feel or look.clean(kind, value) != value or self._feel[kind] == value:
            return
        self._feel[kind] = value
        self.changed.emit()
        self._remember()

    def feel(self) -> dict[str, str]:
        """Return the three feel choices, for saving."""
        return dict(self._feel)

    def _remember(self) -> None:
        if self._on_changed is not None:
            self._on_changed(self)

    @staticmethod
    def _detect_font_family() -> str:
        """Return the first available font from the priority list, or empty string."""
        available = QFontDatabase.families()
        for name in _FONT_PRIORITY:
            if name in available:
                return name
        return ""

    # -- Live reload: filesystem watching ------------------------------------

    def _start_watching(self) -> None:
        """Start watching the Noctalia palette file and its parent directory."""
        self._watcher = QFileSystemWatcher(self)
        palette_path = paths.desktop_colors_path()
        parent_dir = palette_path.parent
        if parent_dir.exists():
            self._watcher.addPath(str(parent_dir))
        else:
            log.warning("Noctalia config dir %s missing -- live theme reload inactive until it appears", parent_dir)
        if palette_path.exists():
            self._watcher.addPath(str(palette_path))
        self._watcher.fileChanged.connect(self._on_file_changed)
        self._watcher.directoryChanged.connect(self._on_dir_changed)

    def _on_file_changed(self, path: str) -> None:
        """Handle the palette file itself changing (edit or atomic replace)."""
        self._resync_watch_target()
        self._schedule_reload()

    def _on_dir_changed(self, path: str) -> None:
        """Handle the palette's parent directory changing (create/replace/remove)."""
        self._resync_watch_target()
        self._schedule_reload()

    def _resync_watch_target(self) -> None:
        """Re-add the palette path if the watcher silently dropped it.

        Palette generators typically write a temp file and rename it over the
        original. The rename retires the old inode and QFileSystemWatcher
        quietly stops watching it -- re-adding after every event is what
        keeps that from becoming a permanent, silent loss of live reload.
        """
        if self._watcher is None:
            return
        palette_path = paths.desktop_colors_path()
        target = str(palette_path)
        if target not in self._watcher.files() and palette_path.exists():
            self._watcher.addPath(target)

    def _schedule_reload(self) -> None:
        """Debounce bursts of filesystem events into a single reload later."""
        self._reload_timer.start(_RELOAD_DEBOUNCE_MS)

    def _reload(self) -> None:
        """Re-read the palette and apply it, guarding against mid-write reads."""
        result = load_palette_result()
        palette_path = paths.desktop_colors_path()

        # Ask the reader whether it succeeded instead of guessing from the
        # values: a real palette identical to FALLBACK is legitimate and must
        # still be applied.
        looks_like_failed_read = not result.ok and palette_path.exists()
        if looks_like_failed_read:
            if self._fallback_retries < _MAX_FALLBACK_RETRIES:
                self._fallback_retries += 1
                log.debug(
                    "Palette read as fallback while %s still exists -- retry %d/%d",
                    palette_path, self._fallback_retries, _MAX_FALLBACK_RETRIES,
                )
                self._fallback_retry_timer.start(_FALLBACK_RETRY_MS)
            else:
                log.debug("Giving up on fallback retries for %s -- keeping previous palette", palette_path)
                self._fallback_retries = 0
            return

        self._fallback_retries = 0
        self._apply_colors(result.colors)

    def _apply_colors(self, new_colors: dict[str, str]) -> None:
        """Swap in a new palette and notify QML, only if it actually changed."""
        if new_colors == self._colors:
            return
        changed_tokens = sum(1 for token in TOKENS if self._colors.get(token) != new_colors.get(token))
        self._colors = new_colors
        log.info("Noctalia palette changed (%d/%d tokens updated)", changed_tokens, len(TOKENS))
        self.changed.emit()

    def stop_watching(self) -> None:
        """Detach the filesystem watcher and cancel pending timers."""
        self._reload_timer.stop()
        self._fallback_retry_timer.stop()
        if self._watcher is not None:
            watched_paths = self._watcher.files() + self._watcher.directories()
            if watched_paths:
                self._watcher.removePaths(watched_paths)
            self._watcher.deleteLater()
            self._watcher = None

    # -- Color properties -----------------------------------------------------

    def _get_color(self, key: str) -> str:
        return self._colors[key]

    background = Property(str, lambda self: self._get_color("background"), notify=changed)
    surface = Property(str, lambda self: self._get_color("surface"), notify=changed)
    surfaceVariant = Property(str, lambda self: self._get_color("surfaceVariant"), notify=changed)
    primary = Property(str, lambda self: self._get_color("primary"), notify=changed)
    onPrimary = Property(str, lambda self: self._get_color("onPrimary"), notify=changed)
    secondary = Property(str, lambda self: self._get_color("secondary"), notify=changed)
    onSecondary = Property(str, lambda self: self._get_color("onSecondary"), notify=changed)
    tertiary = Property(str, lambda self: self._get_color("tertiary"), notify=changed)
    onTertiary = Property(str, lambda self: self._get_color("onTertiary"), notify=changed)
    error = Property(str, lambda self: self._get_color("error"), notify=changed)
    onError = Property(str, lambda self: self._get_color("onError"), notify=changed)
    onSurface = Property(str, lambda self: self._get_color("onSurface"), notify=changed)
    onSurfaceVariant = Property(str, lambda self: self._get_color("onSurfaceVariant"), notify=changed)
    outline = Property(str, lambda self: self._get_color("outline"), notify=changed)
    shadow = Property(str, lambda self: self._get_color("shadow"), notify=changed)
    hover = Property(str, lambda self: self._get_color("hover"), notify=changed)
    onHover = Property(str, lambda self: self._get_color("onHover"), notify=changed)

    # -- Numeric / layout tokens ------------------------------------------------

    spacingXs = Property(int, lambda self: 4, constant=True)
    spacingSm = Property(int, lambda self: 8, constant=True)
    spacingMd = Property(int, lambda self: 12, constant=True)
    spacingLg = Property(int, lambda self: 16, constant=True)
    spacingXl = Property(int, lambda self: 24, constant=True)
    spacingXxl = Property(int, lambda self: 32, constant=True)

    radiusSm = Property(int, lambda self: 10, constant=True)
    radiusMd = Property(int, lambda self: 14, constant=True)
    radiusLg = Property(int, lambda self: 22, constant=True)

    rowHeight = Property(int, lambda self: 52, constant=True)
    headerHeight = Property(int, lambda self: 44, constant=True)
    playerBarHeight = Property(int, lambda self: 76, constant=True)
    sidebarWidth = Property(int, lambda self: 236, constant=True)

    navItemHeight = Property(int, lambda self: 40, constant=True)
    searchFieldHeight = Property(int, lambda self: 38, constant=True)
    coverSize = Property(int, lambda self: 40, constant=True)
    seekBarHeight = Property(int, lambda self: 4, constant=True)
    contentMaxWidth = Property(int, lambda self: 1160, constant=True)
    dividerAlpha = Property(float, lambda self: 0.10, constant=True)

    fontSizeSm = Property(int, lambda self: 11, constant=True)
    fontSizeMd = Property(int, lambda self: 13, constant=True)
    fontSizeLg = Property(int, lambda self: 16, constant=True)
    fontSizeXl = Property(int, lambda self: 22, constant=True)

    # Hyprland nhân thêm active_opacity của người dùng lên trên giá trị này.
    surfaceAlpha = Property(float, lambda self: look.number("glass", self._feel["glass"]), notify=changed)
    glass = Property(str, lambda self: self._feel["glass"], notify=changed)
    bounce = Property(str, lambda self: self._feel["bounce"], notify=changed)
    speed = Property(str, lambda self: self._feel["speed"], notify=changed)
    # Số cho QML: overshoot của OutBack và hệ số nhân mọi thời lượng hiệu ứng.
    overshoot = Property(float, lambda self: look.number("bounce", self._feel["bounce"]), notify=changed)
    motionScale = Property(float, lambda self: look.number("speed", self._feel["speed"]), notify=changed)
    #: Lớp kính mỏng hơn hẳn khi người dùng đã chọn nền riêng — 0.78 thì nền đó
    #: gần như không thấy (đo được: đổi nền mà pixel chỉ nhích 3/255).
    wallpaperSurfaceAlpha = Property(
        float, lambda self: look.WALL_GLASS.get(self._feel["glass"], 0.45), notify=changed)
    panelAlpha = Property(float, lambda self: 0.10, constant=True)

    fontFamily = Property(str, lambda self: self._font_family, constant=True)
    # Bộ icon của dynsle (Icon.qml): Material Symbols Rounded, tô đặc. QĐ-041.
    iconFont = Property(str, lambda self: "Material Symbols Rounded", constant=True)
    iconSize = Property(int, lambda self: 20, constant=True)
    # Khoảng view phải chừa ở đáy cho hòn đảo phát nhạc (cao 64 + lề 18 hai bên).
    islandReserve = Property(int, lambda self: 100, constant=True)
    #: Nguồn màu ĐANG áp dụng. Free luôn là "theo hệ điều hành" dù người dùng
    #: từng chọn màu tay — thẻ trong Cài đặt phải nói thật thứ đang chạy.
    followNoctalia = Property(bool, lambda self: self._effective_follow(), notify=changed)
    accent = Property(str, lambda self: self._accent, notify=changed)
    #: Thứ người dùng ĐÃ CHỌN, không phải thứ đang được áp. Ai GHI XUỐNG ĐĨA thì
    #: phải đọc hai cái này: `followNoctalia`/`wallpaper` là giá trị đã bị gói
    #: Free che đi, ghi chúng vào cấu hình là xoá vĩnh viễn lựa chọn của người
    #: dùng — đúng thứ F-4f hứa không làm.
    chosenFollowNoctalia = Property(bool, lambda self: self._follow_noctalia, notify=changed)
    chosenWallpaper = Property(str, lambda self: self._wallpaper, notify=changed)
    #: Ảnh nền ĐANG áp dụng — Free là rỗng. `self._wallpaper` vẫn giữ nguyên
    #: lựa chọn cũ: nó là của người dùng, chỉ tạm không được áp lên màn hình.
    wallpaper = Property(str, lambda self: self._effective_wallpaper(), notify=changed)
    wallpapers = Property("QStringList", lambda self: list(self._wallpapers), notify=changed)
    wallpaperIsImage = Property(
        bool, lambda self: backgrounds.is_image(self._effective_wallpaper()), notify=changed
    )
    #: Các màu dựng sẵn (tên + mã + các sắc độ), để giao diện khỏi tự bịa một
    #: danh sách riêng rồi lệch với phần lõi.
    presets = Property(
        "QVariantList",
        lambda self: [{"name": n, "color": c, "shades": palettes.shades(c)}
                      for n, c in palettes.PRESETS.items()],
        constant=True,
    )

    @Slot(str, float, result=QColor)
    def alpha(self, color_hex: str, a: float) -> QColor:
        """Return color_hex as a QColor with alpha channel a (0.0-1.0) applied."""
        color = QColor(color_hex)
        color.setAlphaF(max(0.0, min(1.0, a)))
        return color
