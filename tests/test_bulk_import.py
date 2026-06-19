"""Tests for bulk library import (ID3-based, no Spotify)."""

from __future__ import annotations

from pathlib import Path

import pytest

import cratekeeper.local.bulk_import as bulk_import
from cratekeeper.local.bulk_import import SourceNotScannedError, import_tracks
from cratekeeper.local.repository import InMemoryTrackRepository, LocalTrack
from cratekeeper.pipeline.classifier import classify_tracks


def _make_repo(*rows) -> InMemoryTrackRepository:
    """Build an InMemoryTrackRepository from (path, title, artist, album, isrc, year, duration_ms, added_at) tuples."""
    repo = InMemoryTrackRepository()
    for row in rows:
        added_at = row[7] if len(row) > 7 else None
        repo.upsert(LocalTrack(
            path=row[0], title=row[1], artist=row[2], album=row[3],
            isrc=row[4], year=row[5], duration_ms=row[6] or 0,
            added_at=added_at,
        ))
    return repo


def test_unscanned_source_raises(tmp_path: Path):
    repo = InMemoryTrackRepository()
    with pytest.raises(SourceNotScannedError):
        import_tracks(tmp_path / "music", repo=repo)


def test_import_builds_tracks_with_genres(monkeypatch, tmp_path: Path):
    repo = _make_repo(
        ("/music/a.mp3", "Title A", "Artist A", "Album", "ISRC1", 2020, 200000),
        ("/music/b.mp3", None, None, None, None, None, 0),
    )
    monkeypatch.setattr(
        bulk_import, "_read_genre",
        lambda p: ["tech house"] if p.name == "a.mp3" else [],
    )

    tracks = import_tracks("/music", repo=repo)
    assert len(tracks) == 2
    assert tracks[0].name == "Title A"
    assert tracks[0].artists == ["Artist A"]
    assert tracks[0].local_path == "/music/a.mp3"
    assert tracks[0].artist_genres == ["tech house"]
    # Fallback for missing title -> filename stem; missing artist -> Unknown
    assert tracks[1].name == "b"
    assert tracks[1].artists == ["Unknown"]


def test_imported_tracks_classify_with_profile(monkeypatch, tmp_path: Path):
    repo = _make_repo(("/music/a.mp3", "A", "DJ", "Al", None, 2021, 1000))
    monkeypatch.setattr(bulk_import, "_read_genre", lambda p: ["tech house"])

    tracks = import_tracks("/music", repo=repo)
    from cratekeeper.pipeline.genre_buckets import get_preset
    preset = get_preset("electronic")
    classify_tracks(tracks, buckets=preset.buckets, fallback=preset.fallback)
    assert tracks[0].bucket == "Tech House"


def test_import_transfers_added_at(monkeypatch, tmp_path: Path):
    repo = _make_repo(("/music/a.mp3", "A", "DJ", "Al", None, 2021, 1000, "2024-07-20T12:00:00Z"))
    monkeypatch.setattr(bulk_import, "_read_genre", lambda p: ["tech house"])

    tracks = import_tracks("/music", repo=repo)
    assert len(tracks) == 1
    assert tracks[0].added_at == "2024-07-20T12:00:00Z"


def test_import_without_added_at(monkeypatch, tmp_path: Path):
    repo = _make_repo(("/music/a.mp3", "A", "DJ", "Al", None, 2021, 1000))
    monkeypatch.setattr(bulk_import, "_read_genre", lambda p: ["tech house"])

    tracks = import_tracks("/music", repo=repo)
    assert len(tracks) == 1
    assert tracks[0].added_at is None
