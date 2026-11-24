"""Asking YouTube who uploaded a video, without letting the test touch YouTube."""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from lumen.core import channel  # noqa: E402


def _fake_response(payload: dict):
    class _Response(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    return _Response(json.dumps(payload).encode())


class TestFetchChannel:
    def test_reads_the_author_name(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            channel.urllib.request,
            "urlopen",
            lambda url, timeout=0: _fake_response({"author_name": "Zachz Winner"}),
        )

        assert channel.fetch_channel("worB0RjpbDg") == "Zachz Winner"

    def test_blank_id_never_hits_the_network(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def explode(*args, **kwargs):
            raise AssertionError("should not have been called")

        monkeypatch.setattr(channel.urllib.request, "urlopen", explode)

        assert channel.fetch_channel("") == ""

    def test_a_deleted_video_is_a_blank_not_a_crash(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Deleted or private videos are a normal outcome, not an error to raise.
        def fail(*args, **kwargs):
            raise channel.urllib.error.URLError("404")

        monkeypatch.setattr(channel.urllib.request, "urlopen", fail)

        assert channel.fetch_channel("gone") == ""

    def test_junk_payload_is_a_blank(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            channel.urllib.request, "urlopen", lambda url, timeout=0: _fake_response({})
        )

        assert channel.fetch_channel("x") == ""


class TestFetchChannels:
    def test_maps_ids_to_names_and_drops_the_failures(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        names = {"a": "Alpha", "b": "", "c": "Gamma"}
        monkeypatch.setattr(channel, "fetch_channel", lambda video_id: names[video_id])

        assert channel.fetch_channels(["a", "b", "c"]) == {"a": "Alpha", "c": "Gamma"}

    def test_empty_list_short_circuits(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def explode(*args, **kwargs):
            raise AssertionError("should not have been called")

        monkeypatch.setattr(channel, "fetch_channel", explode)

        assert channel.fetch_channels([]) == {}
