"""Tests for bulk library import (ID3-based, no Spotify)."""

from __future__ import annotations

from pathlib import Path

import pytest

import cratekeeper.local.bulk_import as bulk_import
from cratekeeper.local.bulk_import import SourceNotScannedError, import_tracks
from cratekeeper.local.repository import InMemoryTrackRepository, LocalTrack
from cratekeeper.pipeline.classifier import classify_tracks


def _make_repo(*rows) -> InMemoryTrackRepository:
    """Build an InMemoryTrackRepository from (path, title, artist, album, isrc, year, duration_ms) tuples."""
    repo = InMemoryTrackRepository()
    for path, title, artist, album, isrc, year, duration_ms in rows:
        repo.upsert(LocalTrack(
            path=path, title=title, artist=artist, album=album,
            isrc=isrc, year=year, duration_ms=duration_ms or 0,
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
    assert tracks[0].bucket == "Minimal / Tech House"
