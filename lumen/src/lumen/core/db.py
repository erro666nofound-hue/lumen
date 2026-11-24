from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from . import paths

log = logging.getLogger(__name__)

# Each entry is one migration step, applied in order. To add a migration
# later, just append a new SQL string to this list — never edit an existing
# entry, since already-migrated databases must stay compatible.
MIGRATIONS: list[str] = [
    """
    CREATE TABLE meta (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );

    CREATE TABLE tracks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source_id TEXT UNIQUE,
        source_url TEXT,
        title TEXT NOT NULL,
        artist TEXT NOT NULL DEFAULT '',
        duration_ms INTEGER NOT NULL DEFAULT 0,
        file_path TEXT NOT NULL UNIQUE,
        cover_path TEXT,
        added_at INTEGER NOT NULL,
        play_count INTEGER NOT NULL DEFAULT 0,
        last_played_at INTEGER
    );

    CREATE TABLE playlists (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        icon TEXT NOT NULL DEFAULT '',
        position INTEGER NOT NULL DEFAULT 0,
        created_at INTEGER NOT NULL
    );

    CREATE TABLE playlist_items (
        playlist_id INTEGER NOT NULL REFERENCES playlists(id) ON DELETE CASCADE,
        track_id INTEGER NOT NULL REFERENCES tracks(id) ON DELETE CASCADE,
        position INTEGER NOT NULL,
        PRIMARY KEY (playlist_id, track_id)
    );

    CREATE INDEX idx_tracks_added ON tracks(added_at DESC);
    CREATE INDEX idx_items_playlist ON playlist_items(playlist_id, position);
    """,
    # v2: mỗi track có thư mục riêng, nên CÙNG một bài YouTube có thể tồn tại
    # nhiều lần — mỗi track một bản sao, mỗi bản một dòng. Vì vậy phải bỏ ràng
    # buộc UNIQUE trên source_id. file_path VẪN unique: hai bản nằm ở hai thư
    # mục khác nhau nên đường dẫn vẫn khác nhau.
    #
    # SQLite không sửa được ràng buộc tại chỗ, phải dựng lại bảng. Xem hàm
    # migrate() bên dưới về việc BẮT BUỘC tắt foreign_keys quanh bước này.
    """
    CREATE TABLE tracks_v2 (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source_id TEXT,
        source_url TEXT,
        title TEXT NOT NULL,
        artist TEXT NOT NULL DEFAULT '',
        duration_ms INTEGER NOT NULL DEFAULT 0,
        file_path TEXT NOT NULL UNIQUE,
        cover_path TEXT,
        added_at INTEGER NOT NULL,
        play_count INTEGER NOT NULL DEFAULT 0,
        last_played_at INTEGER
    );

    INSERT INTO tracks_v2 (id, source_id, source_url, title, artist, duration_ms,
                           file_path, cover_path, added_at, play_count, last_played_at)
        SELECT id, source_id, source_url, title, artist, duration_ms,
               file_path, cover_path, added_at, play_count, last_played_at
        FROM tracks;

    DROP TABLE tracks;
    ALTER TABLE tracks_v2 RENAME TO tracks;

    CREATE INDEX idx_tracks_added ON tracks(added_at DESC);
    CREATE INDEX idx_tracks_source ON tracks(source_id);
    """,
    # v3: "Nhạc của tôi" phải liệt kê MỌI bài từng tải, KỂ CẢ bài đã xoá khỏi
    # máy. Bảng tracks không làm được việc đó — xoá bài là mất dấu vết. Nên tách
    # riêng một cuốn sổ chỉ ghi thêm, khoá theo URL.
    #
    # Nạp ngược từ tracks để nhạc tải từ các bản cũ vẫn hiện ra. GROUP BY để một
    # bài nằm trong nhiều track (mỗi track một bản sao) chỉ thành MỘT dòng sổ,
    # và lấy lần tải sớm nhất làm mốc thời gian.
    #
    # `uploader` (kênh đăng) trống với nhạc tải từ bản cũ — bảng tracks không
    # giữ nó. Nó đáng tin hơn cột artist để suy ra nghệ sĩ: artist do phép tách
    # "A - B" đoán ra, và phép đoán đó lật ngược khi kênh viết "Tên bài - Nghệ
    # sĩ" (dữ liệu thật của chủ dự án đang có đúng lỗi đó).
    """
    CREATE TABLE download_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source_id TEXT,
        url TEXT NOT NULL UNIQUE,
        title TEXT NOT NULL DEFAULT '',
        artist TEXT NOT NULL DEFAULT '',
        uploader TEXT NOT NULL DEFAULT '',
        downloaded_at INTEGER NOT NULL
    );

    INSERT OR IGNORE INTO download_history (source_id, url, title, artist, downloaded_at)
        SELECT source_id, source_url, title, artist, MIN(added_at)
        FROM tracks
        WHERE source_url IS NOT NULL AND source_url <> ''
        GROUP BY source_url;

    CREATE INDEX idx_history_time ON download_history(downloaded_at DESC);
    """,
    # v4: đệm kết quả khám phá. Xếp hạng theo tỉ lệ like/view bắt buộc phải bóc
    # đầy đủ từng video (~1.6s mỗi bài), nên dựng lại trang mỗi lần mở app là
    # không chấp nhận được. Đệm theo TỪNG nghệ sĩ chứ không phải cả trang: thêm
    # một nghệ sĩ mới thì chỉ phải đi lấy đúng nghệ sĩ đó.
    """
    CREATE TABLE discovery_cache (
        artist TEXT PRIMARY KEY,
        payload TEXT NOT NULL,
        fetched_at INTEGER NOT NULL
    );
    """,
    # v5: đệm phải biết nó được dựng theo LUẬT NÀO. Khi luật lọc/xếp hạng đổi
    # (ví dụ thêm bộ lọc "chỉ lấy nhạc"), các dòng đệm cũ vẫn còn hạn 24 giờ
    # nhưng nội dung đã sai luật mới — người dùng sẽ thấy trang cũ nguyên si và
    # tưởng bản vá không chạy. Số phiên bản lệch = coi như chưa có đệm.
    """
    ALTER TABLE discovery_cache ADD COLUMN rules_version INTEGER NOT NULL DEFAULT 0;
    """,
    # v6: đánh giá nghệ sĩ do NGƯỜI DÙNG tự đặt. Trước đây app chỉ suy từ số bài
    # đã tải — mà tải 5 bài của một kênh remix không có nghĩa là thích kênh đó.
    # Đánh giá tay đè lên phép đoán; không đánh thì vẫn suy như cũ.
    #
    # `name` lưu dạng ĐÃ CHUẨN HOÁ (xem core/tiers.normalise_artist) để khớp
    # được với tên nghệ sĩ suy ra từ nhạc, vốn cũng đã chuẩn hoá.
    """
    CREATE TABLE artist_prefs (
        name TEXT PRIMARY KEY,
        rating INTEGER NOT NULL,
        added_at INTEGER NOT NULL
    );
    """,
    # v7: đệm ảnh đại diện kênh. Lấy được nó tốn HAI lần gọi mạng (video -> link
    # kênh -> trang kênh), khoảng 3s mỗi nghệ sĩ — không thể làm lại mỗi lần mở
    # trang. `url` rỗng nghĩa là đã hỏi và không có, để khỏi hỏi lại mãi.
    """
    CREATE TABLE artist_avatars (
        name TEXT PRIMARY KEY,
        url TEXT NOT NULL DEFAULT '',
        fetched_at INTEGER NOT NULL
    );
    """,
    # v8: nền cho F-5 (đồng bộ giữa các máy). Ba thứ còn thiếu, và không thứ
    # nào thêm được sau khi đã có dữ liệu của hai máy — nên phải có TRƯỚC.
    #
    # 1. DANH TÍNH BỀN cho track. `playlists.id` là AUTOINCREMENT của RIÊNG một
    #    máy: track #3 của máy A và track #3 của máy B là hai thứ khác nhau.
    #    Hoà theo `id` là trộn bừa hai thư viện vào nhau. Tên thì vừa đổi được
    #    vừa trùng được, nên cũng không dùng làm khoá được.
    #
    #    `DEFAULT (lower(hex(randomblob(16))))` sinh uuid ngay trong SQL, mỗi
    #    dòng một giá trị — kể cả cho dữ liệu cũ đang chép sang. Phải DỰNG LẠI
    #    BẢNG chứ không ALTER được: SQLite từ chối thẳng "Cannot add a column
    #    with non-constant default" (đã đo).
    #
    # 2. ĐỒNG HỒ để biết bên nào mới hơn. Tách `updated_at` (đổi tên/icon) khỏi
    #    `order_updated_at` (sắp lại thứ tự bài) vì luật hoà của hai thứ này
    #    khác nhau: đổi tên hoà theo từng track, còn thứ tự là ý định về CẢ danh
    #    sách nên phải lấy trọn của một máy. Nhập chung một cột thì mỗi lần đổi
    #    tên là nuốt mất thứ tự của máy kia.
    #
    #    Dữ liệu cũ lấy `created_at` làm mốc: nó là thứ thật duy nhất đang có,
    #    và nó luôn cũ hơn mọi thay đổi sắp tới nên không cướp của máy nào.
    #
    # 3. BIA MỘ. Không có nó thì xoá không đồng bộ được: máy A xoá một bài, máy
    #    B chưa biết, hoà xong bài đó MỌC LẠI và người dùng không có cách nào
    #    diệt. Phải ghi lại rằng "món này từng tồn tại và đã bị xoá lúc T".
    """
    CREATE TABLE playlists_v2 (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        uuid TEXT NOT NULL UNIQUE DEFAULT (lower(hex(randomblob(16)))),
        name TEXT NOT NULL,
        icon TEXT NOT NULL DEFAULT '',
        position INTEGER NOT NULL DEFAULT 0,
        created_at INTEGER NOT NULL,
        updated_at INTEGER NOT NULL DEFAULT 0,
        order_updated_at INTEGER NOT NULL DEFAULT 0
    );

    INSERT INTO playlists_v2 (id, name, icon, position, created_at, updated_at, order_updated_at)
        SELECT id, name, icon, position, created_at, created_at, created_at
        FROM playlists;

    DROP TABLE playlists;
    ALTER TABLE playlists_v2 RENAME TO playlists;

    ALTER TABLE playlist_items ADD COLUMN added_at INTEGER NOT NULL DEFAULT 0;

    CREATE TABLE sync_tombstones (
        kind TEXT NOT NULL,
        key TEXT NOT NULL,
        removed_at INTEGER NOT NULL,
        PRIMARY KEY (kind, key)
    );

    CREATE INDEX idx_tombstones_time ON sync_tombstones(removed_at DESC);
    """,
    # v9: `file_path` được phép TRỐNG — chỗ ngồi cho bài đồng bộ về mà máy này
    # chưa tải.
    #
    # Đồng bộ mang danh sách đi, không mang mp3 đi. Máy nhận phải dựng được một
    # dòng `tracks` cho bài lạ (có tên, có link, chưa có file) thì bài mới hiện
    # ra để bấm "tải lại". Trước v9 việc đó bất khả: `file_path` là
    # `NOT NULL UNIQUE`, mà SQLite coi `''` là một GIÁ TRỊ THẬT — nên dòng chỗ
    # trống thứ HAI đụng ràng buộc và nổ. NULL thì khác: SQLite coi mọi NULL là
    # khác nhau, nên bao nhiêu bài chưa tải cũng nằm được, mà UNIQUE vẫn canh
    # đúng những file có thật (hai dòng cùng trỏ một file vẫn bị chặn).
    #
    # Tầng Python KHÔNG thấy NULL: `track_from_row` đổi về `""`, nên luật cũ
    # "`not track.file_path` = chưa có file" đứng nguyên ở mọi nơi.
    #
    # `NULLIF(file_path, '')` để dòng cũ nào lỡ mang chuỗi rỗng cũng về đúng một
    # cách hiểu. Phải DỰNG LẠI BẢNG: SQLite không có `ALTER COLUMN`.
    """
    CREATE TABLE tracks_v3 (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source_id TEXT,
        source_url TEXT,
        title TEXT NOT NULL,
        artist TEXT NOT NULL DEFAULT '',
        duration_ms INTEGER NOT NULL DEFAULT 0,
        file_path TEXT UNIQUE,
        cover_path TEXT,
        added_at INTEGER NOT NULL,
        play_count INTEGER NOT NULL DEFAULT 0,
        last_played_at INTEGER
    );

    INSERT INTO tracks_v3 (id, source_id, source_url, title, artist, duration_ms,
                           file_path, cover_path, added_at, play_count, last_played_at)
        SELECT id, source_id, source_url, title, artist, duration_ms,
               NULLIF(file_path, ''), cover_path, added_at, play_count, last_played_at
        FROM tracks;

    DROP TABLE tracks;
    ALTER TABLE tracks_v3 RENAME TO tracks;

    CREATE INDEX idx_tracks_added ON tracks(added_at DESC);
    CREATE INDEX idx_tracks_source ON tracks(source_id);
    """,
    # v10: một bài mang HAI cái tên, không phải một (QĐ-019).
    #
    # `real_name` là tên YouTube nói, `display_name` là tên chủ dự án đặt cho
    # RIÊNG dòng này. Cùng một bài nằm ở hai track là hai dòng, nên đổi tên ở
    # track A không đụng tới track B — hai cuốn băng chép ra từ một bản thu, ai
    # dán nhãn nấy.
    #
    # `display_name` để TRỐNG cho mọi dòng cũ, KHÔNG chép `title` sang. Trống
    # nghĩa là "chưa ai đặt tên riêng", và chỗ hiển thị rơi về `real_name`. Chép
    # sang thì vĩnh viễn không phân biệt được "chủ dự án đặt trùng tên thật" với
    # "chưa đặt bao giờ" — và luật "tải lại thì tên thật cập nhật, tên hiển thị
    # không ai đụng" gãy ngay lần tải lại đầu tiên. Mất rồi không dựng lại được.
    #
    # `display_name_updated_at` là mốc riêng của lần đổi tên, so THEO TỪNG DÒNG
    # lúc hoà (mới nhất thắng). 0 = chưa từng đổi, nên mọi lần đổi tên thật sau
    # này đều thắng nó.
    #
    # Phải DỰNG LẠI BẢNG: đổi tên một cột thì SQLite cũ có `ALTER ... RENAME
    # COLUMN`, nhưng ở đây còn thêm hai cột và phải giữ đúng thứ tự đọc được, và
    # nếp của v2/v8/v9 trong file này là dựng lại. Nhớ: `migrate()` đã tắt khoá
    # ngoại quanh bước này — nếu không, `DROP TABLE tracks` sẽ cuốn sạch
    # `playlist_items`.
    """
    CREATE TABLE tracks_v4 (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source_id TEXT,
        source_url TEXT,
        real_name TEXT NOT NULL,
        display_name TEXT NOT NULL DEFAULT '',
        display_name_updated_at INTEGER NOT NULL DEFAULT 0,
        artist TEXT NOT NULL DEFAULT '',
        duration_ms INTEGER NOT NULL DEFAULT 0,
        file_path TEXT UNIQUE,
        cover_path TEXT,
        added_at INTEGER NOT NULL,
        play_count INTEGER NOT NULL DEFAULT 0,
        last_played_at INTEGER
    );

    INSERT INTO tracks_v4 (id, source_id, source_url, real_name, artist, duration_ms,
                           file_path, cover_path, added_at, play_count, last_played_at)
        SELECT id, source_id, source_url, title, artist, duration_ms,
               file_path, cover_path, added_at, play_count, last_played_at
        FROM tracks;

    DROP TABLE tracks;
    ALTER TABLE tracks_v4 RENAME TO tracks;

    CREATE INDEX idx_tracks_added ON tracks(added_at DESC);
    CREATE INDEX idx_tracks_source ON tracks(source_id);
    """,
    # v11: chỗ cho DANH TÍNH của bài nhập từ đĩa (QĐ-027).
    #
    # Tới v10, "có `source_id`" trả lời một lúc HAI câu hỏi khác nhau: *bản kê
    # gọi tên được dòng này không* và *tải lại được từ link không*. Bài YouTube
    # trả lời CÓ cho cả hai nên không ai thấy đó là hai câu. Bài nhập từ đĩa
    # tách chúng ra: nó có thể được gọi tên (khoá kho R2 = sha256 của chính
    # file) mà vẫn không có link nào để tải lại.
    #
    # `content_hash` là sha256 của BYTE trong file, chữ thường, 64 ký tự — thứ
    # `files/<sub>/<sha256>` trên R2 dùng làm địa chỉ. Không phải id của bài
    # hát, không bao giờ hiện ra cho chủ dự án thấy.
    #
    # KHÔNG `UNIQUE`: từ v2 cùng một bài nằm ở hai track là hai dòng, mỗi track
    # một bản sao trên đĩa — hai dòng đó mang cùng một hash. `UNIQUE` ở đây là
    # cấm chính cái nếp mà cả app đang chạy trên đó.
    #
    # Cột để TRỐNG cho mọi dòng cũ. Không có bước nào lấp nó ở đây: băm cả thư
    # viện lúc mở app là treo giao diện, và bài YouTube không cần hash (nó đã
    # có link). Cửa nhập mp3 sẽ lấp cột này cho bài mới; bài nhập từ đĩa trước
    # bản này ở lại ngoài bản kê cho tới khi có một lượt băm bù chạy nền.
    """
    ALTER TABLE tracks ADD COLUMN content_hash TEXT;

    CREATE INDEX idx_tracks_hash ON tracks(content_hash);
    """,
]


def schema_version(conn: sqlite3.Connection) -> int:
    """Return the current schema version stored in meta, or 0 if unset."""
    try:
        row = conn.execute(
            "SELECT value FROM meta WHERE key = 'schema_version'"
        ).fetchone()
    except sqlite3.OperationalError:
        # meta table does not exist yet -> no migrations applied.
        return 0
    if row is None:
        return 0
    return int(row["value"])


def migrate(conn: sqlite3.Connection) -> int:
    """Apply all pending migrations in order, one transaction per step; return final version."""
    current = schema_version(conn)
    target = len(MIGRATIONS)
    if current >= target:
        return current

    # Foreign keys MUST be off while a migration rebuilds a table, and the
    # pragma is a no-op inside a transaction so it has to happen out here.
    # Without this, `DROP TABLE tracks` cascades through
    # playlist_items.track_id and silently empties every playlist the user
    # has ever built. Restoring that is impossible -- there is no copy.
    conn.execute("PRAGMA foreign_keys = OFF")
    try:
        _apply(conn, current, target)
    finally:
        # Đo được: `autocommit = False` mở một transaction và việc trả về
        # LEGACY_TRANSACTION_CONTROL KHÔNG đóng nó. Mà PRAGMA thì bị nuốt im
        # lặng khi đang trong transaction — nên nếu không đóng ở đây, khoá
        # ngoại sẽ ở trạng thái TẮT suốt phần đời còn lại của kết nối.
        if conn.in_transaction:
            conn.commit()
        conn.execute("PRAGMA foreign_keys = ON")

    broken = conn.execute("PRAGMA foreign_key_check").fetchall()
    if broken:
        raise sqlite3.IntegrityError(f"Migration left dangling references: {broken[:5]}")

    return schema_version(conn)


def _apply(conn: sqlite3.Connection, current: int, target: int) -> None:
    """Run each pending migration step in its own transaction."""
    for version in range(current, target):
        script = MIGRATIONS[version]
        log.info("Applying migration %d -> %d", version, version + 1)
        # Python's default (legacy) transaction control does not open an
        # implicit transaction for DDL statements, so executescript() would
        # otherwise commit each statement separately. Switch to PEP 249
        # manual control for the duration of this step to make the whole
        # migration (DDL + version bump) a single atomic transaction.
        conn.autocommit = False
        try:
            conn.executescript(script)
            conn.execute(
                "INSERT INTO meta (key, value) VALUES ('schema_version', ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (str(version + 1),),
            )
            conn.commit()
        except sqlite3.Error:
            conn.rollback()
            raise
        finally:
            conn.autocommit = sqlite3.LEGACY_TRANSACTION_CONTROL


def connect(path: Path | None = None) -> sqlite3.Connection:
    """Open (creating and migrating if needed) the Lumen SQLite database."""
    db_file = path if path is not None else paths.db_path()
    db_file.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")

    migrate(conn)

    return conn
