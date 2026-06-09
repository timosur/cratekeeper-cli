"""Parity tests: with the implicit commercial profile (no config), behaviour
must match the historical pre-profile defaults."""

from __future__ import annotations

from pathlib import Path

from mutagen.id3 import ID3

from cratekeeper.pipeline.classifier import classify_tracks
from cratekeeper.config import implicit_commercial_profile
from cratekeeper.pipeline.genre_buckets import DEFAULT_BUCKETS, FALLBACK_BUCKET, get_buckets
from cratekeeper.builder.library_builder import is_fully_tagged
from cratekeeper.models import Track
from cratekeeper.pipeline.tag_writer import tag_track


def _track(**kw) -> Track:
    base = dict(id="1", name="N", artists=["A"], artist_ids=[], album="Al", duration_ms=1000)
    base.update(kw)
    return Track(**base)


def test_commercial_profile_buckets_match_defaults():
    prof = implicit_commercial_profile()
    assert [b.name for b in prof.buckets] == [b.name for b in DEFAULT_BUCKETS]
    assert prof.fallback == FALLBACK_BUCKET


def test_get_buckets_default_matches_commercial():
    prof = implicit_commercial_profile()
    assert [b.name for b in get_buckets()] == [b.name for b in prof.buckets]


def test_classification_parity():
    genres = [["deep house"], ["rap"], ["nothing here"], ["schlager"]]
    legacy = [_track(artist_genres=g) for g in genres]
    profiled = [_track(artist_genres=g) for g in genres]

    classify_tracks(legacy)  # legacy default path
    prof = implicit_commercial_profile()
    classify_tracks(profiled, buckets=prof.buckets, fallback=prof.fallback)

    assert [t.bucket for t in legacy] == [t.bucket for t in profiled]


def test_admission_parity():
    full = _track(energy="high", function=["floorfiller"], crowd=["mixed-age"], mood_tags=["euphoric"])
    partial = _track(energy="high")
    prof = implicit_commercial_profile()
    # Default and commercial-profile required_fields agree.
    assert is_fully_tagged(full) == is_fully_tagged(full, prof.required_fields) is True
    assert is_fully_tagged(partial) == is_fully_tagged(partial, prof.required_fields) is False


def test_tagging_parity_writes_comment(tmp_path: Path):
    p = tmp_path / "a.mp3"
    p.write_bytes(b"")
    t = _track(
        bucket="House", energy="high", function=["floorfiller"], crowd=["mixed-age"],
        mood_tags=["euphoric"], local_path=str(p), bpm=128.0, key="8A", era="90s",
    )
    prof = implicit_commercial_profile()
    assert tag_track(t, prof.tag_format) is True
    tags = ID3(str(p))
    assert any(k.startswith("COMM") for k in tags.keys())
