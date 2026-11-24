"""Threading-contract tests for SearchBridge.

Mirrors tests/test_download_bridge.py: a fake `search()` stands in for the
real network call (tests/test_youtube_search.py already covers yt-dlp
parsing), and what's under test here is that results always land on the main
thread, and -- the one bug search boxes are famous for -- that a stale
in-flight search's result can never clobber a newer one.
"""

from __future__ import annotations

import os
import threading

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEventLoop, QTimer  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402

from lumen.bridge import search_bridge as search_bridge_module  # noqa: E402
from lumen.bridge.search_bridge import SearchBridge  # noqa: E402
from lumen.core.errors import NetworkError  # noqa: E402
from lumen.core.youtube_search import SearchResult  # noqa: E402


@pytest.fixture(scope="module")
def qapp() -> QGuiApplication:
    return QGuiApplication.instance() or QGuiApplication([])


class _FakeSearch:
    """Stands in for core.youtube_search.search. Records call order and can
    block a specific query on a threading.Event so tests control exactly
    which worker's result reaches the bridge first.
    """

    def __init__(self) -> None:
        self.calls: list[str] = []
        self.blocking: dict[str, threading.Event] = {}
        self.results: dict[str, list[SearchResult]] = {}
        self.errors: dict[str, Exception] = {}

    def __call__(self, query: str, *, limit: int = 12) -> list[SearchResult]:
        self.calls.append(query)
        event = self.blocking.get(query)
        if event is not None:
            assert event.wait(timeout=5), f"test forgot to release the block on {query!r}"
        if query in self.errors:
            raise self.errors[query]
        return self.results.get(query, [])


def _result(video_id: str = "dQw4w9WgXcQ", title: str = "Never Gonna Give You Up") -> SearchResult:
    return SearchResult(
        video_id=video_id,
        title=title,
        uploader="Rick Astley",
        duration_ms=213_000,
        url=f"https://www.youtube.com/watch?v={video_id}",
        thumbnail="https://i.ytimg.com/vi/dQw4w9WgXcQ/small.jpg",
    )


@pytest.fixture(autouse=True)
def no_network_likes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Chặn PHA HAI gọi mạng thật.

    Sau khi tìm xong, bridge tự chạy fetch_likes() để xếp lại theo tỉ lệ
    like/view. Không chặn thì mỗi bài test lại gọi YouTube thật — bộ test từ
    4 giây vọt lên 25 giây và phụ thuộc mạng. autouse để không ai quên.
    """
    monkeypatch.setattr(search_bridge_module, "fetch_likes", lambda ids, **kw: {})


@pytest.fixture
def fake_search(monkeypatch: pytest.MonkeyPatch) -> _FakeSearch:
    fake = _FakeSearch()
    monkeypatch.setattr(search_bridge_module, "search", fake)
    return fake


def _pump_until(predicate, timeout_ms: int = 5000) -> bool:
    """Run a real event loop until predicate() is true or the timeout expires."""
    loop = QEventLoop()
    ticker = QTimer()
    ticker.setInterval(10)
    ticker.timeout.connect(lambda: loop.quit() if predicate() else None)
    guard = QTimer()
    guard.setSingleShot(True)
    guard.timeout.connect(loop.quit)
    ticker.start()
    guard.start(timeout_ms)
    loop.exec()
    ticker.stop()
    guard.stop()
    return predicate()


def test_run_populates_the_model(qapp, fake_search) -> None:
    fake_search.results["abc"] = [_result()]
    bridge = SearchBridge()

    bridge.run("abc")
    assert _pump_until(lambda: bridge.count == 1)

    index = bridge.index(0, 0)
    assert bridge.data(index, SearchBridge.VideoIdRole) == "dQw4w9WgXcQ"
    assert bridge.data(index, SearchBridge.TitleRole) == "Never Gonna Give You Up"
    assert bridge.data(index, SearchBridge.UploaderRole) == "Rick Astley"
    assert bridge.data(index, SearchBridge.DurationTextRole) == "3:33"
    assert bridge.data(index, SearchBridge.UrlRole) == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    assert bridge.data(index, SearchBridge.ThumbnailRole) == "https://i.ytimg.com/vi/dQw4w9WgXcQ/small.jpg"


def test_busy_is_true_while_running_and_false_after(qapp, fake_search) -> None:
    release = threading.Event()
    fake_search.blocking["abc"] = release
    fake_search.results["abc"] = [_result()]
    bridge = SearchBridge()

    bridge.run("abc")
    assert bridge.busy is True

    release.set()
    assert _pump_until(lambda: bridge.busy is False)
    assert bridge.count == 1


def test_stale_result_from_a_superseded_search_is_dropped(qapp, fake_search) -> None:
    # "a" is slow and will only return once we release it below; "b" is
    # instant. The user retyped before "a" came back -- its result must
    # never overwrite what "b" put on screen.
    release_a = threading.Event()
    fake_search.blocking["a"] = release_a
    fake_search.results["a"] = [_result(video_id="AAAAAAAAAAA", title="Stale A")]
    fake_search.results["b"] = [_result(video_id="BBBBBBBBBBB", title="Fresh B")]
    bridge = SearchBridge()

    bridge.run("a")
    bridge.run("b")
    assert _pump_until(lambda: bridge.count == 1), "search for 'b' never completed"
    assert bridge.data(bridge.index(0, 0), SearchBridge.TitleRole) == "Fresh B"

    # Now let the stale "a" search finish and pump a bit more: it must not
    # be allowed to clobber "b"'s results.
    release_a.set()
    import time

    time.sleep(0.2)
    for _ in range(20):
        qapp.processEvents()
    assert bridge.count == 1
    assert bridge.data(bridge.index(0, 0), SearchBridge.TitleRole) == "Fresh B"


def test_error_reports_and_clears_model(qapp, fake_search) -> None:
    fake_search.errors["boom"] = NetworkError("boom", user_message="Không tìm được trên YouTube.")
    bridge = SearchBridge()
    errors: list[str] = []
    bridge.errorOccurred.connect(errors.append)

    bridge.run("boom")
    assert _pump_until(lambda: bool(errors))

    assert errors == ["Không tìm được trên YouTube."]
    assert bridge.busy is False
    assert bridge.count == 0


def test_clear_empties_model_and_query(qapp, fake_search) -> None:
    fake_search.results["abc"] = [_result()]
    bridge = SearchBridge()
    bridge.run("abc")
    assert _pump_until(lambda: bridge.count == 1)

    bridge.clear()

    assert bridge.count == 0
    assert bridge.query == ""
    assert bridge.hasSearched is False


def test_empty_query_clears_without_calling_search(qapp, fake_search) -> None:
    bridge = SearchBridge()

    bridge.run("   ")

    assert bridge.count == 0
    assert bridge.busy is False
    assert fake_search.calls == []
