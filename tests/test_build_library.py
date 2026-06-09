"""Integration tests for build_library admission, profile target, and sorting."""

from __future__ import annotations

from pathlib import Path

from cratekeeper.builder.library_builder import build_library
from cratekeeper.models import Track
from cratekeeper.pipeline.sorting import SortRule


def _approved(tmp_path: Path, name: str, bucket: str, title: str = "Song", **kw) -> Track:
    src = tmp_path / name
    src.write_bytes(b"data")
    base = dict(
        id=name, name=title, artists=["Artist"], artist_ids=[], album="Al", duration_ms=1000,
        bucket=bucket, local_path=str(src), library_approval="approved",
        energy="high", function=["floorfiller"], crowd=["mixed-age"], mood_tags=["euphoric"],
    )
    base.update(kw)
    return Track(**base)


def test_build_copies_to_profile_target(tmp_path: Path):
    target = tmp_path / "Library"
    t = _approved(tmp_path, "song.mp3", "House", title="Song")
    result = build_library([t], target)
    assert result.copied == 1
    assert (target / "House" / "Artist - Song.mp3").exists()


def test_build_reduced_required_fields_admits(tmp_path: Path):
    """A track with only energy qualifies when required_fields == ['energy']."""
    target = tmp_path / "Lib"
    t = _approved(
        tmp_path, "e.mp3", "Techno", title="Energy",
        function=[], crowd=[], mood_tags=[],  # only energy populated
    )
    # Default fields => excluded as missing tags
    res_default = build_library([t], tmp_path / "d")
    assert res_default.copied == 0
    assert res_default.missing_tags == 1

    # Reduced required fields => copied
    res = build_library([t], target, required_fields=["energy"])
    assert res.copied == 1
    assert (target / "Techno" / "Artist - Energy.mp3").exists()


def test_build_sorts_within_bucket(tmp_path: Path):
    target = tmp_path / "Sorted"
    order = []

    def cb(i, total, track, dest):
        order.append(track.id)

    t1 = _approved(tmp_path, "a.mp3", "House", bpm=120.0)
    t2 = _approved(tmp_path, "b.mp3", "House", bpm=128.0)
    t3 = _approved(tmp_path, "c.mp3", "House", bpm=124.0)
    build_library([t1, t2, t3], target, progress_callback=cb, sort=SortRule(keys=["bpm"], direction="desc"))
    assert order == ["b.mp3", "c.mp3", "a.mp3"]
