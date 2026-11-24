"""Application bootstrap: Qt setup, theme bridge, QML engine load."""

from __future__ import annotations

import logging
from pathlib import Path
import sys

from PySide6.QtCore import QCoreApplication, QObject, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickWindow

import lumen
from lumen.bridge.app_bridge import AppBridge
from lumen.bridge.artists_bridge import ArtistsBridge
from lumen.bridge.clipboard_bridge import ClipboardBridge
from lumen.bridge.discovery_bridge import DiscoveryBridge
from lumen.bridge.download_bridge import DownloadBridge
from lumen.bridge.import_bridge import ImportBridge
from lumen.bridge.history_bridge import HistoryBridge
from lumen.bridge.listen_history_bridge import ListenHistoryBridge
from lumen.bridge.keybinds_bridge import KeybindsBridge
from lumen.bridge.library_bridge import LibraryBridge
from lumen.bridge.player_bridge import PlayerBridge
from lumen.bridge.playlist_bridge import PlaylistsBridge
from lumen.bridge.remote_commands import RemoteCommands
from lumen.bridge.search_bridge import SearchBridge
from lumen.bridge.theme_bridge import ThemeBridge
from lumen.bridge.track_songs_bridge import TrackSongsBridge
from lumen.core import cli, db, ipc, paths, tools
from lumen.core.config import load_config, save_config
from lumen.core.downloader import Downloader
from lumen.core.artist_prefs import ArtistAvatarCache, ArtistPrefsRepository
from lumen.core.discovery_store import DiscoveryCache
from lumen.core.history import DownloadHistoryRepository
from lumen.core.playback import PlaybackController
from lumen.core.player import MpvPlayer
from lumen.core.logging_setup import setup_logging
from lumen.core.repository import PlaylistRepository, TrackRepository
from lumen.services.control import ControlServer
from lumen.services.mpris import MprisService

log = logging.getLogger(__name__)


def _handle_control(command: str, window: QObject) -> None:
    """React to a command sent by another `lumen` invocation."""
    if command == ipc.CMD_QUIT:
        log.info("Quit requested over the control socket")
        # exit() chứ không quit(): xem AppBridge.quit.
        QCoreApplication.exit(0)
    elif command == ipc.CMD_MINI:
        # Bấm phím tắt lần nữa là đóng — nên lật, không phải mở.
        window.setProperty("miniOpen", not window.property("miniOpen"))
    elif command == ipc.CMD_SHOW:
        # Mở cửa sổ lớn là dẹp Mini — cùng luật với nút "Mở Lumen" trong Mini.
        window.setProperty("miniOpen", False)
        window.show()
        window.raise_()
        # Wayland có thể từ chối tự đưa mình lên trước; show() thì luôn có tác
        # dụng, còn requestActivate() là xin thêm, không phải chỗ dựa.
        window.requestActivate()


def main(argv: list[str] | None = None) -> int:
    """Parse args, boot Qt, load the QML engine, and run the event loop."""
    try:
        # One convention everywhere: argv always includes the program name at [0],
        # exactly like sys.argv. argparse gets the tail, Qt gets the whole list.
        # Lệnh không cần giao diện đã được trả lời từ trước ở core/cli.py.
        argv_list = list(sys.argv if argv is None else argv)
        args = cli.parse(argv_list[1:])

        setup_logging(args.verbose)
        paths.ensure_dirs()
        # Phải gọi TRƯỚC khi dựng trình phát: python-mpv tra đường dẫn thư viện
        # ngay lúc nạp, gọi sau là muộn.
        tools.prepare_runtime()

        # Required for transparent QML windows to actually be transparent.
        QQuickWindow.setDefaultAlphaBuffer(True)

        app = QGuiApplication(argv_list)
        app.setApplicationName("Lumen")
        app.setApplicationDisplayName("Lumen")
        app.setOrganizationName("Lumen")
        app.setApplicationVersion(lumen.__version__)
        app.setDesktopFileName("com.toast.Lumen")
        # Ẩn cửa sổ cuối cùng KHÔNG được làm app thoát: Lumen sống nền để nhạc
        # chạy tiếp và để phím tắt còn ai mà gọi.
        app.setQuitOnLastWindowClosed(False)

        # Giành socket điều khiển TRƯỚC khi dựng database, mpv hay cửa sổ.
        # Không giành được nghĩa là đã có một Lumen sống: nhường nó rồi thoát
        # NGAY, chứ chạy tiếp là thành hai tiến trình phát chồng nhau mà chỉ
        # một cái gọi tới được.
        control = ControlServer()
        if not control.start():
            if ipc.send(ipc.CMD_SHOW):
                log.info("Handed over to the Lumen that is already running")
                return 0
            log.warning("No control socket: hotkeys and single-instance are off")

        cfg = load_config()
        log.info("Config loaded: %s", cfg)

        # The database connection is created here and never handed to a worker:
        # sqlite3 connections are bound to their creating thread, which is
        # exactly the guard we want for the "main thread only" rule.
        connection = db.connect()
        music_dir = cfg.resolved_music_dir()
        music_dir.mkdir(parents=True, exist_ok=True)

        app_bridge = AppBridge()
        def _remember_theme(bridge: ThemeBridge) -> None:
            """Ghi lựa chọn màu xuống đĩa NGAY, không đợi lúc thoát: người dùng
            có thể tắt máy bất cứ lúc nào và mất hết lựa chọn vừa làm."""
            # `chosen*` chứ không phải `followNoctalia`/`wallpaper`: hai cái
            # sau là thứ ĐANG ÁP DỤNG, mà gói Free thì che chúng đi. Ghi giá
            # trị bị che xuống đĩa là xoá hẳn lựa chọn của người dùng.
            cfg.theme_follow_noctalia = bridge.chosenFollowNoctalia
            cfg.theme_accent = bridge.accent
            cfg.wallpaper = bridge.chosenWallpaper
            cfg.wallpapers = list(bridge.wallpapers)
            feel = bridge.feel()
            cfg.look_glass, cfg.look_bounce, cfg.look_speed = feel["glass"], feel["bounce"], feel["speed"]
            save_config(cfg)

        theme = ThemeBridge(
            follow_noctalia=cfg.theme_follow_noctalia,
            accent=cfg.theme_accent,
            wallpaper=cfg.wallpaper,
            wallpapers=cfg.wallpapers,
            on_changed=_remember_theme,
            feel={"glass": cfg.look_glass, "bounce": cfg.look_bounce, "speed": cfg.look_speed},
        )
        # Một TrackRepository dùng chung: thư viện đọc, và mục đổi tên bài ghi.
        track_repository = TrackRepository(connection)
        library = LibraryBridge(track_repository)
        # Shared by both playlist bridges: one connection, one repository, two
        # views over it (the sidebar list and the currently open playlist).
        playlist_repository = PlaylistRepository(connection)
        playlists = PlaylistsBridge(playlist_repository)
        track_songs = TrackSongsBridge(playlist_repository, track_repository)
        # Mini Lumen có danh sách RIÊNG: xem trong Mini không được làm đổi track
        # đang mở ở cửa sổ lớn.
        mini_songs = TrackSongsBridge(playlist_repository, track_repository)
        # Removing a song from the open playlist must update the sidebar's
        # track count; adding a song to the open playlist must show up in it.
        track_songs.contentsChanged.connect(lambda _pid: playlists.refresh())
        playlists.contentsChanged.connect(track_songs.onPlaylistContentsChanged)
        playlists.contentsChanged.connect(mini_songs.onPlaylistContentsChanged)
        # Hai danh sách là hai bản sao của CÙNG mấy dòng trong database. Đổi tên
        # ở bên này mà không báo bên kia thì Mini Lumen giữ tên cũ cho tới lần
        # nạp lại vì một lý do khác — đúng hình dạng của CB-029. Nối cả hai
        # chiều vì đổi tên được ở cả hai nơi; `onSongRenamed` cố ý không bắn
        # lại `songRenamed`, nếu không hai bên chuyền cho nhau không dứt.
        track_songs.songRenamed.connect(mini_songs.onSongRenamed)
        mini_songs.songRenamed.connect(track_songs.onSongRenamed)
        downloader = Downloader(
            music_dir=music_dir,
            covers_dir=paths.covers_dir(),
            bitrate=cfg.audio_bitrate,
        )
        # Sổ "đã từng tải": sống lâu hơn cả file trên đĩa, nên "Nhạc của tôi"
        # vẫn kể được những bài người dùng đã xoá.
        history_repository = DownloadHistoryRepository(connection)
        history = HistoryBridge(history_repository)
        # Bản public: không tài khoản, không gói, không hạn mức tải.
        downloads = DownloadBridge(downloader, library, playlist_repository, history_repository)
        downloads.historyChanged.connect(history.refresh)
        # Trang khám phá đọc sổ để biết nghe ai, và đệm kết quả 24 giờ.
        artist_prefs = ArtistPrefsRepository(connection)
        artists = ArtistsBridge(
            history_repository, artist_prefs, ArtistAvatarCache(connection)
        )
        # Đánh giá đổi -> trang khám phá phải dựng lại theo mức mới.
        artists.countChanged.connect(lambda: discovery.refresh(False))
        discovery = DiscoveryBridge(
            history_repository, DiscoveryCache(connection), artist_prefs
        )
        downloads.historyChanged.connect(lambda: discovery.refresh(False))
        search = SearchBridge()
        # Ô "Thêm bài" trong trang track tìm bằng bộ RIÊNG: dùng chung `search` thì
        # gõ ở đó làm trang Thư viện nhảy sang kết quả tìm.
        track_search = SearchBridge()
        # Tải/chép nhạc vào một track cũng đổi thành viên track đó — không nối
        # thì dòng đã vào database mà lưới đang mở vẫn hiện số cũ.
        downloads.playlistContentsChanged.connect(track_songs.onPlaylistContentsChanged)
        downloads.playlistContentsChanged.connect(mini_songs.onPlaylistContentsChanged)
        downloads.playlistContentsChanged.connect(lambda _pid: playlists.refresh())
        # Cửa thứ hai vào một track: mp3 có sẵn trên máy.
        imports = ImportBridge(library, playlist_repository)
        for on_contents in (track_songs.onPlaylistContentsChanged,
                            mini_songs.onPlaylistContentsChanged,
                            lambda _pid: playlists.refresh()):
            imports.playlistContentsChanged.connect(on_contents)
        # Đếm một lần lúc mở app: số bài trong thư viện chưa có file trên đĩa.
        downloads.refreshMissing()
        # The backend is built here and handed down: nothing below the bridge
        # layer is allowed to know how audio actually gets out of the machine.
        controller = PlaybackController(
            MpvPlayer(volume=cfg.volume, speed=cfg.playback_speed),
            volume=cfg.volume,
            speed=cfg.playback_speed,
        )
        player = PlayerBridge(controller, library)
        # Xoá bài NGAY TRONG TRACK cũng phải dừng nhạc và bỏ nó khỏi hàng đợi.
        # PlayerBridge chỉ nghe LibraryBridge, nên thiếu dây này thì bài vừa xoá
        # vẫn phát tiếp cho tới khi người dùng bấm sang bài khác — file đã bị
        # xoá mà tiếng vẫn chạy.
        track_songs.trackRemoved.connect(player._onTrackRemoved)
        # Đổi tên ĐÚNG bài đang phát thì thanh phát, panel trong Mini và MPRIS
        # (thanh Noctalia, `playerctl`, phím media) cũng phải đổi theo — chúng
        # đọc bản sao Track mà PlaybackController giữ từ lúc bài bắt đầu, nên
        # thiếu dây này là tên cũ nằm đó tới khi sang bài khác.
        track_songs.songRenamed.connect(player.onSongRenamed)
        mini_songs.songRenamed.connect(player.onSongRenamed)
        # Kéo đổi thứ tự bài thì hàng đợi đang phát cũng phải đổi theo. Hàng đợi
        # là bản chép ids lúc bấm play, nên thiếu dây này người dùng kéo xong,
        # màn hình đúng, mà hết bài nhạc vẫn nhảy theo thứ tự cũ — không có gì
        # trên màn hình nói ra chuyện đó.
        track_songs.songsReordered.connect(player.onSongsReordered)
        mini_songs.songsReordered.connect(player.onSongsReordered)
        # Phải truyền CẢ phạm vi phát, không chỉ id bài: cùng một bài có thể là
        # hai dòng khác nhau ở hai track, và thư viện thì hiện tất cả. Chỉ so id
        # bài thì phát ở đâu cũng làm track khác bốc lửa theo.
        player.trackChanged.connect(
            lambda: track_songs.set_playing(player.scopePlaylistId, player.trackId)
        )
        # Danh sách trong Mini cũng phải biết bài nào đang phát để tô sáng nó.
        player.trackChanged.connect(
            lambda: mini_songs.set_playing(player.scopePlaylistId, player.trackId)
        )
        log.info("Library ready: %d track(s) in %s", library.count, music_dir)

        engine = QQmlApplicationEngine()
        engine.addImportPath(str(paths.ui_dir()))
        context = engine.rootContext()
        context.setContextProperty("Theme", theme)
        context.setContextProperty("Library", library)
        context.setContextProperty("Downloads", downloads)
        context.setContextProperty("Imports", imports)
        context.setContextProperty("Search", search)
        context.setContextProperty("TrackSearch", track_search)
        context.setContextProperty("Player", player)
        context.setContextProperty("Playlists", playlists)
        context.setContextProperty("History", history)
        # Lịch sử NGHE theo ngày (design R-1) — khác History là lịch sử TẢI.
        listened = ListenHistoryBridge(connection, engine)
        listened.refresh()
        player.trackChanged.connect(listened.refresh)
        context.setContextProperty("Listened", listened)
        # Phím tắt toàn cục (vòng 2 R-1): ghi vào cấu hình Hyprland. `live` chỉ
        # khi đó là cấu hình THẬT — sandbox đổi XDG_CONFIG_HOME nên ghi chỗ giả.
        def _remember_keys(bridge: KeybindsBridge) -> None:
            cfg.keybinds, cfg.key_slots = bridge.snapshot()
            save_config(cfg)

        custom_dir = paths.hypr_custom_dir()
        keys = KeybindsBridge(cfg.keybinds, cfg.key_slots, custom_dir, paths.lumen_shim(),
                              live=custom_dir == Path.home() / ".config" / "hypr" / "custom",
                              on_changed=_remember_keys, parent=engine)
        context.setContextProperty("HotKeys", keys)
        context.setContextProperty("Discovery", discovery)
        context.setContextProperty("Artists", artists)
        context.setContextProperty("Clipboard", ClipboardBridge(engine))
        context.setContextProperty("TrackSongs", track_songs)
        context.setContextProperty("MiniSongs", mini_songs)
        context.setContextProperty("App", app_bridge)

        # Applies to the root Window before it is shown, so the saved size is
        # honoured without QML needing to know the config layer exists.
        engine.setInitialProperties({"width": cfg.window_width, "height": cfg.window_height})
        engine.load(QUrl.fromLocalFile(str(paths.ui_dir() / "Main.qml")))

        if not engine.rootObjects():
            log.error("Failed to load QML engine: no root objects created")
            return 1

        window = engine.rootObjects()[0]
        remote = RemoteCommands(player, playlists)
        control.status_provider = remote.status

        def _on_command(command: str) -> None:
            """Playback commands first (shortcuts, `lumen --play/--seek…`), window commands after."""
            if remote.handles(command):
                remote.run(command)
            elif command in ipc.CMD_SLOTS:
                playlist_id = keys.slot_playlist(ipc.CMD_SLOTS.index(command) + 1)
                if playlist_id >= 0:
                    player.setRepeat("all")
                    player.playPlaylist(playlist_id, playlists.orderedIds(playlist_id), -1)
            else:
                _handle_control(command, window)

        control.commandReceived.connect(_on_command)

        # `lumen --mini` lúc chưa có bản nào chạy: mở thẳng vào Mini, cửa sổ
        # đầy đủ để dành cho khi người dùng thật sự cần quản lý nhạc.
        #
        if args.mini:
            window.setProperty("miniOpen", True)

        # Thanh Noctalia / playerctl / phím media. Không có D-Bus thì thôi,
        # app vẫn chạy — đây là dịch vụ của Linux.
        mpris = MprisService(player)
        if mpris.start():
            mpris.raiseRequested.connect(lambda: _handle_control(ipc.CMD_SHOW, window))
            mpris.quitRequested.connect(lambda: QCoreApplication.exit(0))

        exit_code = app.exec()
        mpris.stop()
        control.stop()
        player.shutdown()
        theme.stop_watching()
        cfg.volume = player.volume_percent
        cfg.playback_speed = player.speed
        save_config(cfg)
        connection.close()
        log.info("Lumen exited with code %d", exit_code)
        return exit_code
    except Exception:
        log.exception("Fatal error during application startup")
        return 1
