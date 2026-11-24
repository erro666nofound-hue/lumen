"""Playback commands that arrive over the control socket: `lumen --play`, `--seek +10`, `--status`…

Phím tắt Hyprland và trợ lý (script) đều đi qua đây. Mỗi lệnh làm đúng cái
người bấm nút trên giao diện làm — không có đường tắt riêng vào mpv.
"""

from __future__ import annotations

import json
import logging

from lumen.bridge.player_bridge import PlayerBridge
from lumen.bridge.playlist_bridge import PlaylistsBridge
from lumen.core import ipc

log = logging.getLogger(__name__)

#: Bỏ tắt tiếng mà không biết âm lượng trước đó (vd. app vừa mở lại) thì về mức này.
_UNMUTE_FALLBACK = 1.0


class RemoteCommands:
    """Turn control-socket commands into Player calls, and describe the player for `--status`."""

    HANDLED = frozenset({ipc.CMD_TOGGLE, ipc.CMD_PLAY, ipc.CMD_PAUSE, ipc.CMD_NEXT, ipc.CMD_PREV,
                         ipc.CMD_SEEK, ipc.CMD_VOLUME, ipc.CMD_MUTE})

    def __init__(self, player: PlayerBridge, playlists: PlaylistsBridge) -> None:
        self._player = player
        self._playlists = playlists
        self._volume_before_mute: float | None = None

    def handles(self, command: str) -> bool:
        """True when this command is about playback (window commands go elsewhere)."""
        return ipc.split(command)[0] in self.HANDLED

    def run(self, command: str) -> None:
        """Carry out one playback command; the IPC layer has already validated it."""
        word, argument = ipc.split(command)
        player = self._player
        if word == ipc.CMD_TOGGLE:
            self.toggle()
        elif word == ipc.CMD_PLAY:
            if not player.isPlaying:
                self.toggle()
        elif word == ipc.CMD_PAUSE:
            if player.isPlaying:
                player.toggle()
        elif word == ipc.CMD_NEXT:
            player.playNext()
        elif word == ipc.CMD_PREV:
            player.playPrevious()
        elif word == ipc.CMD_SEEK:
            self._seek(argument)
        elif word == ipc.CMD_VOLUME:
            self._volume_before_mute = None
            player.setVolume(int(argument) / 100)
        elif word == ipc.CMD_MUTE:
            self._toggle_mute()

    def toggle(self) -> None:
        """Play/pause; with nothing loaded, start the first track that has songs (like Space)."""
        if self._player.hasTrack:
            self._player.toggle()
            return
        first = self._playlists.firstPlayable()
        if first < 0:
            log.info("Nothing to play: no track has songs")
            return
        self._player.setRepeat("all")
        self._player.playPlaylist(first, self._playlists.orderedIds(first), -1)

    def status(self) -> str:
        """One line of JSON: what is playing, where, and whether it is paused."""
        player = self._player
        loaded = bool(player.hasTrack)
        volume = round(player.volume * 100)
        return json.dumps({
            "running": True,
            "loaded": loaded,
            "playing": bool(player.isPlaying),
            "paused": loaded and not player.isPlaying,
            "title": player.title if loaded else "",
            "artist": player.artist if loaded else "",
            "song_id": player.trackId if loaded else None,
            "track_id": player.scopePlaylistId if loaded else None,
            "position_s": round(player.positionMs / 1000, 1) if loaded else 0,
            "duration_s": round(player.durationMs / 1000, 1) if loaded else 0,
            "volume": volume,
            "muted": volume == 0,
        }, ensure_ascii=False)

    def _seek(self, argument: str) -> None:
        """"+10"/"-10" = jump by seconds, "30" = go to second 30; clamped to the song."""
        player = self._player
        if not player.hasTrack:
            return
        seconds = int(argument)
        target = player.positionMs + seconds * 1000 if argument[0] in "+-" else seconds * 1000
        if player.durationMs > 0:
            target = min(target, player.durationMs)
        player.seek(max(0, target))

    def _toggle_mute(self) -> None:
        """Mute remembers the volume it silenced; muting again brings it back."""
        player = self._player
        if player.volume > 0:
            self._volume_before_mute = player.volume
            player.setVolume(0.0)
        else:
            player.setVolume(self._volume_before_mute or _UNMUTE_FALLBACK)
            self._volume_before_mute = None
