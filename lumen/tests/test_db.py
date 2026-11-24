from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from lumen.core import db


def test_migrate_from_empty_db_reaches_latest_version(tmp_path: Path) -> None:
    """A fresh database migrates from 0 to the newest schema version."""
    conn = sqlite3.connect(tmp_path / "fresh.db")
    conn.row_factory = sqlite3.Row
    assert db.schema_version(conn) == 0

    version = db.migrate(conn)

    assert version == len(db.MIGRATIONS)
    assert db.schema_version(conn) == len(db.MIGRATIONS)
    conn.close()


def test_migrate_twice_is_idempotent(tmp_path: Path) -> None:
    """Running migrate() a second time changes nothing."""
    conn = db.connect(tmp_path / "twice.db")
    before_tables = _table_names(conn)
    before_version = db.schema_version(conn)

    version_again = db.migrate(conn)

    assert version_again == before_version
    assert _table_names(conn) == before_tables
    conn.close()


def test_connect_enables_foreign_keys(tmp_path: Path) -> None:
    """connect() turns PRAGMA foreign_keys on."""
    conn = db.connect(tmp_path / "fk.db")
    row = conn.execute("PRAGMA foreign_keys").fetchone()
    assert row[0] == 1
    conn.close()


def test_connect_uses_wal_journal_mode(tmp_path: Path) -> None:
    """connect() sets PRAGMA journal_mode to WAL."""
    conn = db.connect(tmp_path / "wal.db")
    row = conn.execute("PRAGMA journal_mode").fetchone()
    assert row[0].lower() == "wal"
    conn.close()


def test_connect_creates_parent_directories(tmp_path: Path) -> None:
    """connect() creates missing parent directories for the database file."""
    nested = tmp_path / "a" / "b" / "c" / "library.db"
    conn = db.connect(nested)
    assert nested.exists()
    conn.close()


def test_foreign_keys_actually_enforced_on_cascade_delete(tmp_path: Path) -> None:
    """Deleting a playlist cascades to remove its playlist_items rows."""
    conn = db.connect(tmp_path / "cascade.db")
    conn.execute(
        "INSERT INTO tracks (real_name, file_path, added_at) "
        "VALUES ('t', '/f/one.mp3', 1)"
    )
    conn.execute("INSERT INTO playlists (name, created_at) VALUES ('p', 1)")
    conn.commit()
    track_id = conn.execute("SELECT id FROM tracks").fetchone()[0]
    playlist_id = conn.execute("SELECT id FROM playlists").fetchone()[0]

    conn.execute(
        "INSERT INTO playlist_items (playlist_id, track_id, position) VALUES (?, ?, 0)",
        (playlist_id, track_id),
    )
    conn.commit()
    assert conn.execute("SELECT COUNT(*) FROM playlist_items").fetchone()[0] == 1

    conn.execute("DELETE FROM playlists WHERE id = ?", (playlist_id,))
    conn.commit()

    assert conn.execute("SELECT COUNT(*) FROM playlist_items").fetchone()[0] == 0
    conn.close()


def test_foreign_keys_reject_orphan_playlist_item(tmp_path: Path) -> None:
    """Inserting a playlist_items row referencing a missing track fails under FK enforcement."""
    conn = db.connect(tmp_path / "orphan.db")
    conn.execute("INSERT INTO playlists (name, created_at) VALUES ('p', 1)")
    conn.commit()
    playlist_id = conn.execute("SELECT id FROM playlists").fetchone()[0]

    try:
        conn.execute(
            "INSERT INTO playlist_items (playlist_id, track_id, position) VALUES (?, 999, 0)",
            (playlist_id,),
        )
        conn.commit()
        assert False, "expected sqlite3.IntegrityError"
    except sqlite3.IntegrityError:
        conn.rollback()
    conn.close()


def _table_names(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    return {row["name"] for row in rows}


# --- v8: nền cho F-5 đồng bộ ------------------------------------------------
#
# Migration này KHÔNG thêm được sau khi hai máy đã có dữ liệu: uuid sinh muộn thì
# mỗi máy tự đặt một cái khác nhau cho cùng một track, và hoà sẽ nhân đôi mọi thứ.
# Nên nó phải đúng ngay từ bây giờ, lúc chưa ai đồng bộ lần nào.

def _v7_db(path: Path) -> sqlite3.Connection:
    """Một database dừng ở v7 — tức là dữ liệu của bản app trước F-5."""
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = OFF")
    for version in range(7):
        conn.executescript(db.MIGRATIONS[version])
    conn.execute(
        "INSERT INTO meta (key, value) VALUES ('schema_version', '7') "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value"
    )
    conn.commit()
    return conn


def test_v8_moi_track_cu_deu_duoc_mot_uuid_rieng(tmp_path: Path) -> None:
    """Dữ liệu cũ phải được đặt tên, không chỉ dữ liệu mới."""
    conn = _v7_db(tmp_path / "cu.db")
    for name in ("Cozy", "Gym", "Chill"):
        conn.execute(
            "INSERT INTO playlists (name, created_at) VALUES (?, 100)", (name,)
        )
    conn.commit()

    db.migrate(conn)

    rows = conn.execute("SELECT name, uuid FROM playlists ORDER BY name").fetchall()
    uuids = [r["uuid"] for r in rows]
    assert [r["name"] for r in rows] == ["Chill", "Cozy", "Gym"], "tên phải giữ nguyên"
    assert len(set(uuids)) == 3, "trùng uuid là hai máy hoà vào nhau thành một mớ"
    assert all(len(u) == 32 for u in uuids)
    conn.close()


def test_v8_track_moi_tu_co_uuid_khong_ai_phai_nho(tmp_path: Path) -> None:
    """DEFAULT nằm trong lược đồ, nên quên gán ở tầng Python cũng không thủng."""
    conn = db.connect(tmp_path / "moi.db")

    conn.execute("INSERT INTO playlists (name, created_at) VALUES ('Mới', 1)")
    conn.commit()

    uuid = conn.execute("SELECT uuid FROM playlists").fetchone()["uuid"]
    assert len(uuid) == 32 and uuid.strip() != ""
    conn.close()


def test_v8_dong_ho_nap_tu_created_at(tmp_path: Path) -> None:
    """Mốc thời gian của dữ liệu cũ phải CŨ, không được là 0 lẫn "bây giờ".

    0 thì mọi máy hoà nhau đều thấy "chưa ai sửa"; "bây giờ" thì máy nào chạy
    migration sau cùng sẽ nuốt hết thay đổi của máy kia.
    """
    conn = _v7_db(tmp_path / "dongho.db")
    conn.execute("INSERT INTO playlists (name, created_at) VALUES ('Cũ', 12345)")
    conn.commit()

    db.migrate(conn)

    row = conn.execute(
        "SELECT created_at, updated_at, order_updated_at FROM playlists"
    ).fetchone()
    assert row["updated_at"] == 12345
    assert row["order_updated_at"] == 12345
    conn.close()


def test_v8_giu_nguyen_thanh_vien_track(tmp_path: Path) -> None:
    """Dựng lại bảng playlists mà làm rơi playlist_items là mất sạch track của
    người dùng — không có bản sao nào để khôi phục."""
    conn = _v7_db(tmp_path / "thanhvien.db")
    conn.execute("INSERT INTO playlists (id, name, created_at) VALUES (1, 'Cozy', 100)")
    conn.execute(
        "INSERT INTO tracks (id, title, file_path, added_at) VALUES (7, 'Bài', '/a.mp3', 100)"
    )
    conn.execute(
        "INSERT INTO playlist_items (playlist_id, track_id, position) VALUES (1, 7, 0)"
    )
    conn.commit()

    db.migrate(conn)

    rows = conn.execute("SELECT playlist_id, track_id, added_at FROM playlist_items").fetchall()
    assert [(r["playlist_id"], r["track_id"]) for r in rows] == [(1, 7)]
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    conn.close()


def test_v8_co_ban_bia_mo(tmp_path: Path) -> None:
    """Không có bia mộ thì bài đã xoá MỌC LẠI sau mỗi lần hoà."""
    conn = db.connect(tmp_path / "biamo.db")

    conn.execute(
        "INSERT INTO sync_tombstones (kind, key, removed_at) VALUES ('playlist', 'abc', 9)"
    )
    conn.commit()

    row = conn.execute("SELECT kind, key, removed_at FROM sync_tombstones").fetchone()
    assert (row["kind"], row["key"], row["removed_at"]) == ("playlist", "abc", 9)
    conn.close()


# --- v9: chỗ ngồi cho bài chưa tải ------------------------------------------
#
# Đồng bộ mang danh sách đi, không mang mp3 đi. Máy nhận phải dựng được dòng
# `tracks` cho bài lạ, và trước v9 việc đó bất khả: `file_path NOT NULL UNIQUE`
# chỉ cho ĐÚNG MỘT dòng mang chuỗi rỗng.

def _v8_db(path: Path) -> sqlite3.Connection:
    """Một database dừng ở v8 — tức là dữ liệu của bản app trước khi đồng bộ chạy thật."""
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = OFF")
    for version in range(8):
        conn.executescript(db.MIGRATIONS[version])
    conn.execute(
        "INSERT INTO meta (key, value) VALUES ('schema_version', '8') "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value"
    )
    conn.commit()
    return conn


def _add_track(
    conn: sqlite3.Connection, title: str, file_path: str, *, column: str = "real_name"
) -> None:
    """Thêm một dòng tracks. `column` vì cột tên ĐỔI ở v10: database dựng dở
    (chưa migrate) vẫn còn `title`, database đã migrate thì là `real_name`."""
    conn.execute(
        f"INSERT INTO tracks ({column}, file_path, added_at) VALUES (?, ?, 1)",
        (title, file_path),
    )
    conn.commit()


def test_v9_nhac_da_tai_khong_mat_duong_dan(tmp_path: Path) -> None:
    """Dựng lại bảng là lúc dễ đánh rơi dữ liệu nhất — và rơi đây là mất nhạc."""
    conn = _v8_db(tmp_path / "cu.db")
    _add_track(conn, "Cũ", "/music/cu.mp3", column="title")

    db.migrate(conn)

    row = conn.execute("SELECT id, real_name, file_path FROM tracks").fetchone()
    assert (row["id"], row["real_name"], row["file_path"]) == (1, "Cũ", "/music/cu.mp3")
    conn.close()


def test_v9_duong_dan_rong_cu_thanh_TRONG(tmp_path: Path) -> None:
    """Một cách nói 'chưa có file' thôi: NULL. Hai cách là hai nhánh if ở mọi nơi."""
    conn = _v8_db(tmp_path / "rong.db")
    _add_track(conn, "Không file", "", column="title")

    db.migrate(conn)

    assert conn.execute("SELECT file_path FROM tracks").fetchone()["file_path"] is None
    conn.close()


def test_v9_nhieu_bai_chua_tai_cung_nam_duoc(tmp_path: Path) -> None:
    """Đúng thứ v9 sinh ra để làm: một track đồng bộ về có thể có mười bài chưa tải."""
    conn = db.connect(tmp_path / "moi.db")

    for i in range(3):
        conn.execute(
            "INSERT INTO tracks (source_id, real_name, file_path, added_at) "
            "VALUES (?, ?, NULL, 1)",
            (f"id{i}", f"Bài {i}"),
        )
    conn.commit()

    assert conn.execute("SELECT COUNT(*) AS n FROM tracks").fetchone()["n"] == 3
    conn.close()


def test_v9_hai_dong_van_khong_duoc_tro_cung_mot_file(tmp_path: Path) -> None:
    """Nới cho NULL, KHÔNG nới cho file thật: hai dòng cùng file là xoá một cái mất cả hai."""
    conn = db.connect(tmp_path / "dung.db")
    _add_track(conn, "Một", "/music/mot.mp3")

    with pytest.raises(sqlite3.IntegrityError):
        _add_track(conn, "Hai", "/music/mot.mp3")
    conn.close()


def test_v9_index_cua_tracks_van_con(tmp_path: Path) -> None:
    """DROP TABLE kéo theo index của bảng đó — quên dựng lại là mọi câu truy vấn chậm dần."""
    conn = db.connect(tmp_path / "index.db")

    names = {
        row["name"]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'index' AND tbl_name = 'tracks'"
        ).fetchall()
    }
    assert {"idx_tracks_added", "idx_tracks_source"} <= names
    conn.close()


# --- v10: một bài mang hai tên (QĐ-019) --------------------------------------


def _v9_db(path: Path) -> sqlite3.Connection:
    """Một database dừng ở v9 — bản app ngay trước khi tên tách làm hai."""
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = OFF")
    for version in range(9):
        conn.executescript(db.MIGRATIONS[version])
    conn.execute(
        "INSERT INTO meta (key, value) VALUES ('schema_version', '9') "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value"
    )
    conn.commit()
    return conn


def test_v10_ten_cu_thanh_ten_that(tmp_path: Path) -> None:
    """Tên đang có là tên YouTube nói — nó phải rơi vào `real_name`, không mất."""
    conn = _v9_db(tmp_path / "ten.db")
    _add_track(conn, "Bài cũ", "/music/cu.mp3", column="title")

    db.migrate(conn)

    row = conn.execute("SELECT real_name, display_name FROM tracks").fetchone()
    assert row["real_name"] == "Bài cũ"
    conn.close()


def test_v10_KHONG_chep_ten_that_sang_ten_hien_thi(tmp_path: Path) -> None:
    """Chép là mất vĩnh viễn ranh giới 'chủ dự án đã đặt tên' / 'chưa đặt bao giờ'.

    Và mất nó là luật 'tải lại làm mới tên thật, không đụng tên hiển thị' gãy
    ngay lần tải lại đầu tiên — QĐ-019.
    """
    conn = _v9_db(tmp_path / "khongchep.db")
    _add_track(conn, "Bài cũ", "/music/cu.mp3", column="title")

    db.migrate(conn)

    row = conn.execute("SELECT display_name, display_name_updated_at FROM tracks").fetchone()
    assert row["display_name"] == "", "dòng cũ = chưa ai đặt tên riêng"
    assert row["display_name_updated_at"] == 0, "chưa từng đổi thì mọi lần đổi sau đều thắng"
    conn.close()


def test_v10_giu_nguyen_thanh_vien_track(tmp_path: Path) -> None:
    """Lại một lần dựng lại bảng tracks — khoá ngoại tắt sai là sạch playlist_items."""
    conn = _v9_db(tmp_path / "thanhvien.db")
    conn.execute("INSERT INTO playlists (id, name, created_at) VALUES (1, 'Cozy', 100)")
    conn.execute(
        "INSERT INTO tracks (id, title, file_path, added_at) VALUES (7, 'Bài', '/a.mp3', 100)"
    )
    conn.execute(
        "INSERT INTO playlist_items (playlist_id, track_id, position) VALUES (1, 7, 0)"
    )
    conn.commit()

    db.migrate(conn)

    assert conn.execute("SELECT COUNT(*) AS n FROM playlist_items").fetchone()["n"] == 1
    conn.close()


def test_v10_van_khong_duoc_hai_dong_tro_cung_mot_file(tmp_path: Path) -> None:
    """Dựng lại bảng lần nữa là cơ hội đánh rơi UNIQUE của v9."""
    conn = db.connect(tmp_path / "unique.db")
    _add_track(conn, "Một", "/music/mot.mp3")

    with pytest.raises(sqlite3.IntegrityError):
        _add_track(conn, "Hai", "/music/mot.mp3")
    conn.close()


def test_v10_bai_chua_tai_van_nam_duoc_nhieu_dong(tmp_path: Path) -> None:
    """v9 nới `file_path` cho NULL; v10 dựng lại bảng, nới đó phải còn."""
    conn = db.connect(tmp_path / "chotrong.db")

    for i in range(3):
        conn.execute(
            "INSERT INTO tracks (source_id, real_name, file_path, added_at) "
            "VALUES (?, ?, NULL, 1)",
            (f"id{i}", f"Bài {i}"),
        )
    conn.commit()

    assert conn.execute("SELECT COUNT(*) AS n FROM tracks").fetchone()["n"] == 3
    conn.close()
