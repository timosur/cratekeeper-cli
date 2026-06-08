"""Tests for per-profile tag format and event-folder comment gating."""

from __future__ import annotations

from pathlib import Path

from mutagen.id3 import ID3

from cratekeeper.event_builder import _has_embedded_comment, build_event_folder
from cratekeeper.models import EventPlan, Track
from cratekeeper.tag_writer import (
    COMMENT_MARKER,
    VALID_CROWD,
    VALID_ENERGY,
    VALID_FUNCTION,
    VALID_MOOD,
    _build_comment,
    tag_track,
)


def _full_track(path: Path) -> Track:
    return Track(
        id="1", name="Song", artists=["Artist"], artist_ids=[], album="Al", duration_ms=1000,
        bucket="House", energy="high", function=["floorfiller"], crowd=["mixed-age"],
        mood_tags=["euphoric"], local_path=str(path), bpm=128.0, key="8A", era="90s",
    )


def _empty_mp3(tmp_path: Path, name: str) -> Path:
    p = tmp_path / name
    p.write_bytes(b"")
    return p


def test_vocab_consolidated():
    assert VALID_ENERGY == {"low", "mid", "high"}
    assert "floorfiller" in VALID_FUNCTION
    assert "mixed-age" in VALID_CROWD
    assert "euphoric" in VALID_MOOD


def test_build_comment_format():
    t = _full_track(Path("/x.mp3"))
    comment = _build_comment(t)
    assert comment.startswith("era:90s")
    assert "energy:high" in comment
    assert "function:floorfiller" in comment


def test_structured_comment_writes_comm(tmp_path: Path):
    p = _empty_mp3(tmp_path, "a.mp3")
    assert tag_track(_full_track(p), "structured_comment") is True
    tags = ID3(str(p))
    assert any(k.startswith("COMM") for k in tags.keys())
    assert _has_embedded_comment(p) is True


def test_id3_only_skips_comm(tmp_path: Path):
    p = _empty_mp3(tmp_path, "b.mp3")
    assert tag_track(_full_track(p), "id3_only") is True
    tags = ID3(str(p))
    assert not any(k.startswith("COMM") for k in tags.keys())
    # Genre / BPM / key still written
    assert str(tags.get("TCON")) == "House"
    assert _has_embedded_comment(p) is False


def test_comment_marker_value():
    assert COMMENT_MARKER == "energy:"


def test_event_id3_only_skips_comment_gate(tmp_path: Path):
    """An id3_only-tagged file (no comment) should still be copied for an id3_only profile."""
    src = _empty_mp3(tmp_path, "src.mp3")
    tag_track(_full_track(src), "id3_only")  # writes genre/bpm/key, no comment
    track = _full_track(src)

    out = tmp_path / "event"
    result = build_event_folder(
        [track], out, required_fields=["energy"], tag_format="id3_only"
    )
    assert result.copied == 1
    assert (out / "Artist - Song.mp3").exists()


def test_event_structured_requires_comment(tmp_path: Path):
    """A file lacking the embedded comment is skipped for a structured_comment profile."""
    src = _empty_mp3(tmp_path, "src2.mp3")
    tag_track(_full_track(src), "id3_only")  # deliberately no comment
    track = _full_track(src)

    out = tmp_path / "event2"
    result = build_event_folder(
        [track], out, required_fields=["energy", "function", "crowd", "mood_tags"],
        tag_format="structured_comment",
    )
    assert result.copied == 0
    assert len(result.untagged_tracks) == 1
