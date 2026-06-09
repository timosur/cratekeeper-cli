"""Tests for rekordbox XML export."""

from __future__ import annotations

from pathlib import Path

import pytest

from cratekeeper.models import Track
from cratekeeper.export.rekordbox import EmptyLibraryError, export_rekordbox
from cratekeeper.pipeline.tag_writer import tag_track


def _tagged_file(folder: Path, name: str, bucket: str, bpm: float, key: str) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    p = folder / name
    p.write_bytes(b"")
    t = Track(
        id=name, name="", artists=[], artist_ids=[], album="", duration_ms=0,
        bucket=bucket, local_path=str(p), bpm=bpm, key=key,
    )
    tag_track(t, "id3_only")


def test_export_full_library(tmp_path: Path):
    lib = tmp_path / "Library"
    _tagged_file(lib / "House", "DJ X - Track.mp3", "House", 128.0, "8A")
    _tagged_file(lib / "Techno", "DJ Y - Boom.mp3", "Techno", 130.0, "9A")

    out = tmp_path / "rekordbox.xml"
    track_count, bucket_count = export_rekordbox(lib, out)
    assert track_count == 2
    assert bucket_count == 2

    xml = out.read_text()
    assert "file://localhost" in xml
    assert 'AverageBpm="128.00"' in xml
    assert 'Name="House"' in xml
    assert 'Name="Techno"' in xml
    # Track names recovered from "Artist - Title" filename
    assert 'Name="Track"' in xml
    assert 'Artist="DJ X"' in xml


def test_export_bucket_filter(tmp_path: Path):
    lib = tmp_path / "Lib"
    _tagged_file(lib / "House", "A - B.mp3", "House", 124.0, "5A")
    _tagged_file(lib / "Techno", "C - D.mp3", "Techno", 132.0, "10A")

    out = tmp_path / "rb.xml"
    track_count, bucket_count = export_rekordbox(lib, out, buckets_filter=["House"])
    assert track_count == 1
    assert bucket_count == 1
    xml = out.read_text()
    assert 'Name="House"' in xml
    assert 'Name="Techno"' not in xml


def test_export_empty_library_raises(tmp_path: Path):
    lib = tmp_path / "Empty"
    lib.mkdir()
    out = tmp_path / "out.xml"
    with pytest.raises(EmptyLibraryError):
        export_rekordbox(lib, out)
    assert not out.exists()
