"""MPRIS2: cho thanh Noctalia, playerctl và phím media điều khiển Lumen.

Dùng QtDBus — đi kèm PySide6, không thêm phụ thuộc, và quan trọng hơn: nó chạy
TRÊN vòng lặp sự kiện Qt. Một thư viện D-Bus có luồng riêng sẽ gọi ngược vào
bridge từ luồng khác, đúng thứ luật luồng của dự án cấm (CLAUDE.md mục 4).

Đây là dịch vụ của Linux. Máy không có D-Bus (Windows) thì `start()` trả về
False và app chạy bình thường, không có nó.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import ClassInfo, Property, QMetaType, QObject, Signal, Slot
from PySide6.QtDBus import (
    QDBusAbstractAdaptor,
    QDBusArgument,
    QDBusConnection,
    QDBusMessage,
    QDBusObjectPath,
)

log = logging.getLogger(__name__)

MPRIS_PATH = "/org/mpris/MediaPlayer2"
SERVICE_NAME = "org.mpris.MediaPlayer2.lumen"
PLAYER_IFACE = "org.mpris.MediaPlayer2.Player"
PROPERTIES_IFACE = "org.freedesktop.DBus.Properties"
TRACK_PATH = "/com/toast/Lumen/track/"

_US_PER_MS = 1000


@ClassInfo({"D-Bus Interface": "org.mpris.MediaPlayer2"})
class _RootAdaptor(QDBusAbstractAdaptor):
    """The org.mpris.MediaPlayer2 interface: what this application is."""

    def __init__(self, service: MprisService) -> None:
        super().__init__(service)
        self._service = service

    @Slot()
    def Raise(self) -> None:  # noqa: N802 (tên do chuẩn MPRIS quy định)
        self._service.raiseRequested.emit()

    @Slot()
    def Quit(self) -> None:  # noqa: N802
        self._service.quitRequested.emit()

    Identity = Property(str, lambda self: "Lumen", constant=True)
    DesktopEntry = Property(str, lambda self: "com.toast.Lumen", constant=True)
    CanQuit = Property(bool, lambda self: True, constant=True)
    CanRaise = Property(bool, lambda self: True, constant=True)
    HasTrackList = Property(bool, lambda self: False, constant=True)
    SupportedUriSchemes = Property("QStringList", lambda self: [], constant=True)
    SupportedMimeTypes = Property("QStringList", lambda self: [], constant=True)


@ClassInfo({"D-Bus Interface": PLAYER_IFACE})
class _PlayerAdaptor(QDBusAbstractAdaptor):
    """The org.mpris.MediaPlayer2.Player interface: what is playing, and control."""

    def __init__(self, service: MprisService) -> None:
        super().__init__(service)
        self._service = service

    @property
    def _player(self):
        return self._service.player

    @Slot()
    def PlayPause(self) -> None:  # noqa: N802
        self._player.toggle()

    @Slot()
    def Play(self) -> None:  # noqa: N802
        if not self._player.isPlaying:
            self._player.toggle()

    @Slot()
    def Pause(self) -> None:  # noqa: N802
        if self._player.isPlaying:
            self._player.toggle()

    @Slot()
    def Stop(self) -> None:  # noqa: N802
        self._player.stop()

    @Slot()
    def Next(self) -> None:  # noqa: N802
        self._player.playNext()

    @Slot()
    def Previous(self) -> None:  # noqa: N802
        self._player.playPrevious()

    @Slot("qlonglong")
    def Seek(self, offset_us: int) -> None:  # noqa: N802
        """Seek relative to the current position; MPRIS speaks microseconds."""
        target = self._player.positionMs + offset_us // _US_PER_MS
        self._player.seek(max(0, min(target, self._player.durationMs)))

    @Slot("QDBusObjectPath", "qlonglong")
    def SetPosition(self, _track: object, position_us: int) -> None:  # noqa: N802
        self._player.seek(max(0, position_us // _US_PER_MS))

    PlaybackStatus = Property(str, lambda self: self._service.playback_status())
    Metadata = Property("QVariantMap", lambda self: self._service.metadata())
    Position = Property("qlonglong", lambda self: self._player.positionMs * _US_PER_MS)
    Rate = Property(float, lambda self: self._player.speed)
    MinimumRate = Property(float, lambda self: 0.25, constant=True)
    MaximumRate = Property(float, lambda self: 2.0, constant=True)
    Volume = Property(float, lambda self: self._player.volume)
    CanGoNext = Property(bool, lambda self: True, constant=True)
    CanGoPrevious = Property(bool, lambda self: True, constant=True)
    CanPlay = Property(bool, lambda self: True, constant=True)
    CanPause = Property(bool, lambda self: True, constant=True)
    CanSeek = Property(bool, lambda self: True, constant=True)
    CanControl = Property(bool, lambda self: True, constant=True)


def no_invalidated_properties() -> QDBusArgument:
    """Return an empty D-Bus string array ('as') for PropertiesChanged.

    Một list Python rỗng bị PySide6 gói thành 'av', nên tín hiệu thành 'sa{sv}av'.
    Quickshell (dynsle, Noctalia) nối theo chữ ký 'sa{sv}as' và LẶNG LẼ vứt tin sai —
    đảo của dynsle tưởng nhạc vẫn phát mãi, chỉ dừng được, không Play được. CB-057.
    """
    arg = QDBusArgument()
    arg.beginArray(QMetaType(QMetaType.Type.QString.value))
    arg.endArray()
    return arg


class MprisService(QObject):
    """Publish the running player on the session bus, and relay its changes."""

    raiseRequested = Signal()
    quitRequested = Signal()

    def __init__(self, player: QObject, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.player = player
        # Giữ tham chiếu: adaptor bị thu hồi là interface biến mất mà không báo
        # gì — cùng họ với bẫy context property ở CLAUDE.md mục 6.
        self._root = _RootAdaptor(self)
        self._player_adaptor = _PlayerAdaptor(self)
        self._registered = False

    def start(self) -> bool:
        """Claim the bus name; return False when there is no session bus."""
        bus = QDBusConnection.sessionBus()
        if not bus.isConnected():
            log.info("No session bus: MPRIS is off")
            return False
        # ExportAdaptors là BẮT BUỘC ở PySide6. Thiếu nó thì registerObject vẫn
        # trả về True nhưng không interface nào được xuất ra — đã đo tận nơi.
        options = (
            QDBusConnection.RegisterOption.ExportAllContents
            | QDBusConnection.RegisterOption.ExportAdaptors
        )
        if not bus.registerObject(MPRIS_PATH, self, options):
            log.error("Could not export %s on the session bus", MPRIS_PATH)
            return False
        if not bus.registerService(SERVICE_NAME):
            log.error("Could not claim %s (another Lumen?)", SERVICE_NAME)
            return False
        self._registered = True
        self.player.trackChanged.connect(self._on_track_changed)
        self.player.playingChanged.connect(self._on_playing_changed)
        log.info("MPRIS ready at %s", SERVICE_NAME)
        return True

    def stop(self) -> None:
        """Release the bus name."""
        if not self._registered:
            return
        bus = QDBusConnection.sessionBus()
        bus.unregisterService(SERVICE_NAME)
        bus.unregisterObject(MPRIS_PATH)
        self._registered = False

    def playback_status(self) -> str:
        """Return Playing / Paused / Stopped, in MPRIS spelling."""
        if not self.player.hasTrack:
            return "Stopped"
        return "Playing" if self.player.isPlaying else "Paused"

    def metadata(self) -> dict:
        """Describe the current track the way MPRIS clients expect."""
        if not self.player.hasTrack:
            return {}
        # PHẢI là object path ('o'), không phải chuỗi. Chuỗi thì playerctl vẫn
        # đọc được (nó dễ tính), nhưng client sinh proxy có kiểu — như Quickshell
        # của Noctalia — sẽ không nhận ra player.
        track = QDBusObjectPath(f"{TRACK_PATH}{max(0, self.player.trackId)}")
        data = {
            "mpris:trackid": track,
            "mpris:length": self.player.durationMs * _US_PER_MS,
            "xesam:title": self.player.title,
            "xesam:artist": [self.player.artist] if self.player.artist else [],
        }
        cover = self.player.coverPath
        if cover:
            data["mpris:artUrl"] = f"file://{cover}"
        return data

    def _on_track_changed(self) -> None:
        self._announce({"Metadata": self.metadata(), "PlaybackStatus": self.playback_status()})

    def _on_playing_changed(self) -> None:
        self._announce({"PlaybackStatus": self.playback_status()})

    def _announce(self, changed: dict) -> None:
        """Tell the bus which properties changed.

        Bắt buộc phải tự gửi: Qt không tự phát PropertiesChanged cho thuộc tính
        đọc bằng hàm Python, nên không có bước này thì thanh trạng thái hiện bài
        đầu tiên rồi đứng im mãi.
        """
        if not self._registered:
            return
        message = QDBusMessage.createSignal(MPRIS_PATH, PROPERTIES_IFACE, "PropertiesChanged")
        message.setArguments([PLAYER_IFACE, changed, no_invalidated_properties()])
        QDBusConnection.sessionBus().send(message)
