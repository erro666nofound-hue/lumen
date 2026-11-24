from __future__ import annotations

import sqlite3
from dataclasses import dataclass


#: Cột tác giả của bài nhập từ đĩa. Một hằng số vì cả sắp xếp, ô tìm và giao
#: diện đều phải nói CÙNG một chữ — xem QĐ-025.
CUSTOM_ARTIST = "Custom mp3"


@dataclass(slots=True)
class Track:
    """Plain data holder for a single library track. No I/O, no SQL, no Qt."""

    id: int | None = None
    source_id: str | None = None
    # QĐ-027: sha256 của chính byte trong file, và cũng là địa chỉ của nó trong
    # kho R2. KHÔNG phải id của bài hát và không bao giờ hiện ra — nó chỉ trả
    # lời đúng một câu: bản kê có gọi tên được dòng này không.
    content_hash: str | None = None
    source_url: str | None = None
    # QĐ-019: hai cái tên, không phải một. `real_name` do YouTube nói và mỗi lần
    # tải lại là cập nhật; `display_name` do chủ dự án đặt cho RIÊNG dòng này và
    # không ai được đè. Trống = chưa đặt bao giờ.
    real_name: str = ""
    display_name: str = ""
    display_name_updated_at: int = 0
    artist: str = ""
    duration_ms: int = 0
    file_path: str = ""
    cover_path: str | None = None
    added_at: int = 0
    play_count: int = 0
    last_played_at: int | None = None

    @property
    def title(self) -> str:
        """Tên để HIỆN RA: tên chủ dự án đặt, không đặt thì tên thật.

        Chỉ đọc, cố ý. Gán `track.title = ...` phải nổ ngay tại chỗ gán, vì từ
        v10 câu hỏi "ghi vào ô nào" đã có hai câu trả lời khác nhau — ghi nhầm
        vào `real_name` là lần tải lại sau sẽ xoá mất tên người dùng đặt.
        """
        return self.display_name or self.real_name

    @property
    def subtitle(self) -> str:
        """Return the artist name, or 'Unknown' when not set."""
        return self.artist if self.artist else "Unknown"

    @property
    def artist_label(self) -> str:
        """Artist as the interface shows it. An imported song NEVER borrows the file's tag.

        QĐ-025: the TPE1 frame in a stray mp3 is unreliable — plenty of files carry
        the song's own name there, so trusting it invents an artist called
        "dreamscape". A row with no `source_id` came off the owner's disk, so it
        reports what it actually is and claims no artist at all.

        Chỗ này hỏi "CÓ LINK KHÔNG", và sau QĐ-027 nó vẫn hỏi đúng câu đó —
        không đổi sang danh tính. Một bài nhập từ đĩa đã băm và đã sao lưu VẪN
        là bài nhập từ đĩa: nhãn `Custom mp3` đúng trước và sau khi sao lưu, và
        đó chính là lý do QĐ-027 xoá hẳn huy hiệu "máy này" thay vì đổi tên nó.
        """
        if not self.source_id:
            return CUSTOM_ARTIST
        return self.artist


@dataclass(slots=True)
class Playlist:
    """Plain data holder for a mood playlist. No I/O, no SQL, no Qt."""

    id: int | None = None
    name: str = ""
    icon: str = ""
    position: int = 0
    created_at: int = 0
    track_count: int = 0


def track_from_row(row: sqlite3.Row) -> Track:
    """Build a Track from a sqlite3.Row of the tracks table."""
    return Track(
        id=row["id"],
        source_id=row["source_id"],
        content_hash=row["content_hash"],
        source_url=row["source_url"],
        real_name=row["real_name"],
        display_name=row["display_name"],
        display_name_updated_at=row["display_name_updated_at"],
        artist=row["artist"],
        duration_ms=row["duration_ms"],
        # v9 cho phép cột này TRỐNG (bài đồng bộ về, chưa tải). Tầng Python
        # chỉ biết một cách nói "chưa có file": chuỗi rỗng.
        file_path=row["file_path"] or "",
        cover_path=row["cover_path"],
        added_at=row["added_at"],
        play_count=row["play_count"],
        last_played_at=row["last_played_at"],
    )


def playlist_from_row(row: sqlite3.Row) -> Playlist:
    """Build a Playlist from a sqlite3.Row of the playlists table (track_count optional)."""
    keys = row.keys()
    return Playlist(
        id=row["id"],
        name=row["name"],
        icon=row["icon"],
        position=row["position"],
        created_at=row["created_at"],
        track_count=row["track_count"] if "track_count" in keys else 0,
    )


def one_row_per_song(tracks: list[Track]) -> list[Track]:
    """Collapse the per-track file copies of one song into a single entry.

    Each track owns a folder, so adding a song to a track makes another
    copy on disk and another row. The library lists SONGS, not files -- without
    this the same song shows up once per track it is in. Reported as a bug.
    Keeps the lowest id (the library-root copy); rows with no identity at all are
    never merged, since nothing identifies them.

    Gộp theo KHOÁ DANH TÍNH, không theo link (QĐ-027): thêm một bài nhập từ đĩa
    vào hai track cũng đẻ ra hai dòng y hệt bài YouTube, nên nó cũng phải gộp
    lại làm một. Hỏi `source_id` ở đây là thư viện hiện bài custom trùng lặp.
    """
    seen: set[str] = set()
    unique: list[Track] = []
    for track in sorted(tracks, key=lambda t: t.id or 0):
        key = track.source_id or track.content_hash
        if key:
            if key in seen:
                continue
            seen.add(key)
        unique.append(track)
    return unique
