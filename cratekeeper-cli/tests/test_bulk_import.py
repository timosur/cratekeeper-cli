"""Tests for bulk library import (ID3-based, no Spotify)."""

from __future__ import annotations

from pathlib import Path

import pytest

import cratekeeper.bulk_import as bulk_import
from cratekeeper.bulk_import import SourceNotScannedError, import_tracks
from cratekeeper.classifier import classify_tracks


class _FakeCursor:
    def __init__(self, rows):
        self._rows = rows
        self.executed = None

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params=None):
        self.executed = (sql, params)

    def fetchall(self):
        return self._rows


class _FakeConn:
    def __init__(self, rows):
        self._rows = rows
        self.closed = False

    def cursor(self):
        return _FakeCursor(self._rows)

    def close(self):
        self.closed = True


def _patch_db(monkeypatch, rows):
    monkeypatch.setattr(bulk_import, "_get_conn", lambda db_url=None: _FakeConn(rows))


def test_unscanned_source_raises(monkeypatch, tmp_path: Path):
    _patch_db(monkeypatch, [])
    with pytest.raises(SourceNotScannedError):
        import_tracks(tmp_path / "music")


def test_import_builds_tracks_with_genres(monkeypatch, tmp_path: Path):
    rows = [
        ("/music/a.mp3", "Title A", "Artist A", "Album", "ISRC1", 2020, 200000),
        ("/music/b.mp3", None, None, None, None, None, 0),
    ]
    _patch_db(monkeypatch, rows)
    monkeypatch.setattr(
        bulk_import, "_read_genre",
        lambda p: ["tech house"] if p.name == "a.mp3" else [],
    )

    tracks = import_tracks("/music")
    assert len(tracks) == 2
    assert tracks[0].name == "Title A"
    assert tracks[0].artists == ["Artist A"]
    assert tracks[0].local_path == "/music/a.mp3"
    assert tracks[0].artist_genres == ["tech house"]
    # Fallback for missing title -> filename stem; missing artist -> Unknown
    assert tracks[1].name == "b"
    assert tracks[1].artists == ["Unknown"]


def test_imported_tracks_classify_with_profile(monkeypatch, tmp_path: Path):
    rows = [("/music/a.mp3", "A", "DJ", "Al", None, 2021, 1000)]
    _patch_db(monkeypatch, rows)
    monkeypatch.setattr(bulk_import, "_read_genre", lambda p: ["tech house"])

    tracks = import_tracks("/music")
    from cratekeeper.genre_buckets import get_preset
    preset = get_preset("electronic")
    classify_tracks(tracks, buckets=preset.buckets, fallback=preset.fallback)
    assert tracks[0].bucket == "Minimal / Tech House"
