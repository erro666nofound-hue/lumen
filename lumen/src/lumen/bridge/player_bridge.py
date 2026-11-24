"""Playback state and controls for QML — translation only, no policy.

Threading contract (CLAUDE.md muc 4): the backend calls its listener from
libmpv's own thread. Those calls become private signals connected with
QueuedConnection, so every line below — including every database write — runs
on the Qt main thread. Never shorten that hop: calling back into libmpv from
its own event thread deadlocks, and sqlite from it is undefined behaviour.
Position is polled, not pushed (core/player.py); what plays next lives in
core/playback.py.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from PySide6.QtCore import Property, QObject, QTimer, Qt, Signal, Slot

from lumen.bridge.library_bridge import LibraryBridge
from lumen.bridge.preview_worker import (
    PreviewResolver,
    on_preview_failed,
    on_preview_resolved,
    start_preview,
    stop_preview,
)
from lumen.core.errors import LumenError
from lumen.core.playback import PlaybackController

log = logging.getLogger(__name__)

_TICK_MS = 250              # four seek-bar updates a second: smooth, still cheap
_RESTART_WINDOW_MS = 3_000  # mid-song "previous" restarts; only near the start steps back


class PlayerBridge(QObject):
    """Expose the audio player to QML: what is playing, and how to control it."""

    trackChanged = Signal()
    playingChanged = Signal()
    positionChanged = Signal()
    volumeChanged = Signal()
    speedChanged = Signal()
    modeChanged = Signal()
    scopeChanged = Signal()
    previewChanged = Signal()
    errorOccurred = Signal(str)

    # Private, and only ever emitted from libmpv's thread. See module docstring.
    _backendFinished = Signal()
    _backendFailed = Signal(str)

    def __init__(
        self,
        controller: PlaybackController,
        library: LibraryBridge,
        parent: Any = None,
    ) -> None:
        super().__init__(parent)
        self._controller = controller
        self._library = library
        # Track (playlist) hiện đang phát, KHÔNG phải bài hiện đang phát --
        # -1 nghĩa là không thuộc track nào. Đây là "phạm vi phát": cùng một
        # bài có thể nằm ở nhiều track, nên phải nhớ đang phát TỪ ĐÂU thì mới
        # tô sáng đúng chỗ (xem TrackSongsBridge.set_playing).
        self._scope_id: int = -1

        self._backendFinished.connect(self._onFinished, Qt.ConnectionType.QueuedConnection)
        self._backendFailed.connect(self._onFailed, Qt.ConnectionType.QueuedConnection)
        controller.set_listener(
            finished=self._backendFinished.emit,
            failed=self._backendFailed.emit,
        )
        library.trackRemoved.connect(self._onTrackRemoved)

        # Nghe thử: phát thẳng luồng YouTube, không tải về, không ghi vào thư
        # viện. Bài nghe thử có id = None nên KHÔNG track nào tô sáng theo nó
        # (xem scopePlaylistId) và nó cũng không được tính lượt nghe.
        self._preview = PreviewResolver(self)
        self._preview.resolved.connect(lambda info: on_preview_resolved(self, info))
        self._preview.failed.connect(lambda message: on_preview_failed(self, message))
        self._preview.busyChanged.connect(self.previewChanged)
        self._preview_id = ""

        self._ticker = QTimer(self)
        self._ticker.setInterval(_TICK_MS)
        self._ticker.timeout.connect(self._tick)

    @Slot(int, "QVariantList", int)
    def playPlaylist(self, playlist_id: int, track_ids: list, start_id: int) -> None:
        """Start playing a track (playlist): the ONLY entry point that begins playback.

        Remembers `playlist_id` as the playback scope (see scopePlaylistId) so
        that only the track this queue came FROM highlights a row -- the same
        song sitting in a second track must stay dark there.
        start_id < 0 means "play from the first song".
        """
        self._preview.cancel()
        self._preview_id = ""
        ids = [int(i) for i in track_ids]
        if not ids:
            self.errorOccurred.emit("Track này chưa có bài nào.")
            return
        start = ids[0] if start_id < 0 else int(start_id)
        self._scope_id = int(playlist_id)
        self._controller.set_queue(ids, start_id=start)
        self._start(start)

    @Slot(int, "QVariantList")
    def onSongsReordered(self, playlist_id: int, track_ids: list) -> None:
        """Follow a drag in the open track: same songs, new order, no gap in the music.

        Only for the track this queue came FROM (`scopePlaylistId`). Dragging
        inside a track nobody is listening to must not touch what is playing.
        """
        if int(playlist_id) != self._scope_id:
            return
        self._controller.reorder_queue([int(i) for i in track_ids])

    @Slot(str)
    def preview(self, video_id: str) -> None:
        """Listen to a YouTube video without downloading it (see preview_worker)."""
        start_preview(self, video_id)

    @Slot()
    def stopPreview(self) -> None:
        """Abandon a preview -- either still resolving, or already playing."""
        stop_preview(self)

    @Slot()
    def toggle(self) -> None:
        """Play/pause the currently loaded track. Nothing loaded -> do nothing.

        The library is no longer a place to listen from, so there is no more
        "start the top of the library" fallback here.
        """
        if self._controller.track is None:
            return
        if self._controller.toggle():
            self._ticker.start()
        else:
            self._ticker.stop()
        self.playingChanged.emit()

    @Slot()
    def playNext(self) -> None:
        """Skip forward. Repeat-one does not trap a deliberate skip."""
        self._advance(manual=True)

    @Slot()
    def playPrevious(self) -> None:
        """Restart the song, or step back when already near its start."""
        if self._controller.track is not None and self._controller.position_ms > _RESTART_WINDOW_MS:
            self.seek(0)
            return
        track_id = self._controller.previous_id()
        if track_id is not None:
            self._start(track_id)

    @Slot(int)
    def seek(self, position_ms: int) -> None:
        """Jump to an absolute position in the current track."""
        self._controller.seek(position_ms)
        self.positionChanged.emit()

    @Slot(float)
    def setVolume(self, value: float) -> None:
        """Set volume from a 0..1 ratio."""
        if self._controller.set_volume(round(value * 100)):
            self.volumeChanged.emit()

    @Slot(float)
    def setSpeed(self, rate: float) -> None:
        """Set playback rate, already in 0..3 units — no conversion needed."""
        if self._controller.set_speed(rate):
            self.speedChanged.emit()

    @Slot()
    def cycleRepeat(self) -> None:
        """Step through off -> all -> one."""
        self._controller.cycle_repeat()
        self.modeChanged.emit()

    @Slot(str)
    def setRepeat(self, mode: str) -> None:
        """Set repeat mode directly ("off"/"all"/"one"); unknown values are ignored.

        The sidebar's play button needs to force list-repeat on without
        stepping through cycleRepeat() blind.
        """
        if self._controller.set_repeat(mode):
            self.modeChanged.emit()

    @Slot()
    def toggleShuffle(self) -> None:
        """Shuffle the queue without changing what is playing right now."""
        self._controller.toggle_shuffle()
        self.modeChanged.emit()

    @Slot()
    def stop(self) -> None:
        """Unload the current track, clear the player bar, and leave any scope."""
        self._ticker.stop()
        self._controller.stop()
        self._scope_id = -1
        self._emitAll()

    @Slot(int, result="QVariantList")
    def upNext(self, limit: int) -> list:
        """Return the songs after the current one, in list order, for Now Playing."""
        queue = self._controller.queue
        ids, here = list(queue.ids), queue.current_index
        if here < 0:
            return []
        rows = []
        for track_id in (ids[here + 1:] + ids[:here])[:max(0, limit)]:
            track = self._library.track_for(track_id)
            if track is not None:
                rows.append({"id": track.id, "title": track.title, "artist": track.subtitle,
                             "coverPath": track.cover_path or "", "durationMs": track.duration_ms})
        return rows

    @Slot(int)
    def jumpTo(self, track_id: int) -> None:
        """Play a song that is already in the queue, keeping the queue as it is."""
        if self._controller.queue.jump_to(track_id) is not None:
            self._start(track_id)

    def _start(self, track_id: int) -> None:
        """Load and play one track, reporting anything that stops it."""
        track = self._library.track_for(track_id)
        if track is None:
            self.errorOccurred.emit("Bài này không còn trong thư viện.")
            return
        if not track.file_path or not Path(track.file_path).exists():
            self.errorOccurred.emit(f"Không tìm thấy file của “{track.title}”.")
            return
        try:
            self._controller.start(track)
        except LumenError as exc:
            log.exception("Cannot start track %s", track_id)
            self.errorOccurred.emit(exc.user_message)
            return
        self._ticker.start()
        self._emitAll()

    def _advance(self, *, manual: bool) -> None:
        track_id = self._controller.next_id(manual=manual)
        if track_id is None:
            self._ticker.stop()
            self._controller.pause_at_end()
            self.playingChanged.emit()
            return
        self._start(track_id)

    def _tick(self) -> None:
        if self._controller.poll():
            self.positionChanged.emit()
        self._creditListen()

    def _creditListen(self, *, force: bool = False) -> None:
        track_id = self._controller.take_listen_credit(force=force)
        if track_id is not None:
            self._library.record_play(track_id)

    def _emitAll(self) -> None:
        self.trackChanged.emit()
        self.playingChanged.emit()
        self.positionChanged.emit()
        self.scopeChanged.emit()

    @Slot()
    def _onFinished(self) -> None:
        # Ended on its own: the listen always counts, whatever the threshold says.
        self._creditListen(force=True)
        self._advance(manual=False)

    @Slot(str)
    def _onFailed(self, message: str) -> None:
        log.warning("Playback failed: %s", message)
        if self._preview_id:
            # Nghe thử phát thẳng luồng YouTube, và YouTube CÓ LÚC từ chối phát
            # trực tiếp (trả 403 cho ffmpeg) dù bài vẫn tải về được bình thường.
            # Báo "không phát được file này" ở đây là sai và làm người dùng
            # tưởng bài hỏng — nói rõ đây là phía YouTube, và lối thoát là tải về.
            self._preview_id = ""
            self.previewChanged.emit()
            self._ticker.stop()
            self._controller.fail()
            self.playingChanged.emit()
            self.errorOccurred.emit(
                "YouTube đang không cho nghe trực tiếp bài này. Tải về rồi nghe nhé."
            )
            return
        self._ticker.stop()
        self._controller.fail()
        self.playingChanged.emit()
        self.errorOccurred.emit(message)

    @Slot(int)
    def _onTrackRemoved(self, track_id: int) -> None:
        # Keep the queue in step when a track is deleted from the library.
        current = self._controller.track
        was_current = current is not None and current.id == track_id
        self._controller.drop(track_id)
        if not was_current:
            return
        next_id = self._controller.queue.current_id
        if next_id is None:
            self.stop()
        else:
            self._start(next_id)

    @Slot(int, str)
    def onSongRenamed(self, track_id: int, title: str) -> None:
        """Follow a rename made in a song list, when that song is the one playing.

        `PlaybackController` holds its own copy of the Track, taken when the
        song started, so without this the player bar, Mini Lumen's now-playing
        panel and MPRIS (the Noctalia bar, `playerctl`, the media keys) all
        keep the old name until the next song starts.

        `trackChanged` is the signal every one of those already listens to —
        nothing new has to be wired on their side.
        """
        if self._controller.rename(track_id, title):
            self.trackChanged.emit()

    @Slot()
    def onLibraryChanged(self) -> None:
        """Follow a rename that arrived from the OTHER machine, mid-song.

        A sync writes straight into SQLite behind every open model and then
        emits one payload-free `libraryChanged`. `onSongRenamed` cannot help
        here: nobody typed anything, so no list emits `songRenamed`, and the
        name that changed is not carried by the signal. So this re-reads the
        playing row from the database and compares.

        The image: the rename above is a note passed to us; this one is finding
        the ledger already rewritten and going back to read it again.

        A song the sync deleted reads back as None — leave the controller
        alone. Stopping playback belongs to `trackRemoved`, and guessing at it
        from here would cut the music off under a merge that only reordered.
        """
        playing = self._controller.track
        if playing is None or playing.id is None:
            return
        fresh = self._library.track_for(playing.id)
        if fresh is None or fresh.display_name == playing.display_name:
            return
        if self._controller.rename(playing.id, fresh.display_name):
            self.trackChanged.emit()

    hasTrack = Property(bool, lambda self: self._controller.track is not None, notify=trackChanged)
    isPlaying = Property(bool, lambda self: self._controller.playing, notify=playingChanged)
    trackId = Property(int, lambda self: _field(self._controller, "id", -1), notify=trackChanged)
    title = Property(str, lambda self: _field(self._controller, "title", ""), notify=trackChanged)
    artist = Property(str, lambda self: _field(self._controller, "subtitle", ""), notify=trackChanged)
    coverPath = Property(str, lambda self: _field(self._controller, "cover_path", ""), notify=trackChanged)
    positionMs = Property(int, lambda self: self._controller.position_ms, notify=positionChanged)
    durationMs = Property(int, lambda self: self._controller.duration_ms, notify=positionChanged)
    volume = Property(float, lambda self: self._controller.volume / 100.0, notify=volumeChanged)
    speed = Property(float, lambda self: self._controller.speed, notify=speedChanged)
    repeatMode = Property(str, lambda self: self._controller.repeat, notify=modeChanged)
    shuffle = Property(bool, lambda self: self._controller.shuffle, notify=modeChanged)
    scopePlaylistId = Property(int, lambda self: self._scope_id, notify=scopeChanged)
    previewVideoId = Property(str, lambda self: self._preview_id, notify=previewChanged)
    previewBusy = Property(bool, lambda self: self._preview.busy, notify=previewChanged)

    @property
    def volume_percent(self) -> int:
        """Volume as whole percent, for storing in config on exit."""
        return self._controller.volume

    def shutdown(self) -> None:
        """Stop the timer and tear down the backend. Called once, on app exit."""
        self._ticker.stop()
        self._controller.shutdown()


def _field(controller: PlaybackController, name: str, default: Any) -> Any:
    """Read one attribute off the current track, falling back when nothing plays."""
    track = controller.track
    if track is None:
        return default
    return getattr(track, name) or default
