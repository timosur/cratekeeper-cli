"""Tests for genre presets, classification with profiles, sorting, and admission."""

from __future__ import annotations

from cratekeeper.pipeline.classifier import classify_track, classify_tracks
from cratekeeper.config import resolve_profile
from cratekeeper.pipeline.genre_buckets import get_preset
from cratekeeper.builder.library_builder import is_fully_tagged
from cratekeeper.models import Track
from cratekeeper.pipeline.sorting import SortRule, sort_tracks


def _track(**kw) -> Track:
    base = dict(id="1", name="N", artists=["A"], artist_ids=[], album="Al", duration_ms=1000)
    base.update(kw)
    return Track(**base)


# --- Electronic preset ---

def test_electronic_preset_exists_with_house_fallback():
    preset = get_preset("electronic")
    names = {b.name for b in preset.buckets}
    assert preset.fallback == "House"
    # No commercial-only buckets
    assert "Schlager" not in names
    assert "Pop" not in names
    assert "Rock" not in names
    assert "Latin / Global" not in names


def test_commercial_preset_pop_fallback():
    assert get_preset("commercial").fallback == "Pop"


def test_classify_with_electronic_buckets():
    preset = get_preset("electronic")
    t = _track(artist_genres=["tech house"])
    bucket, conf = classify_track(t, preset.buckets, preset.fallback)
    assert conf == "high"
    assert bucket == "Minimal / Tech House"


def test_classify_fallback_uses_profile_fallback():
    preset = get_preset("electronic")
    t = _track(artist_genres=["polka"])
    bucket, conf = classify_track(t, preset.buckets, preset.fallback)
    assert conf == "low"
    assert bucket == "House"


def test_classify_tracks_threads_fallback():
    preset = get_preset("electronic")
    tracks = [_track(artist_genres=["nothing matches here"])]
    classify_tracks(tracks, buckets=preset.buckets, fallback=preset.fallback)
    assert tracks[0].bucket == "House"


# --- Admission via required_fields ---

def test_is_fully_tagged_default_commercial_fields():
    t = _track(energy="high", function=["floorfiller"], crowd=["mixed-age"], mood_tags=["euphoric"])
    assert is_fully_tagged(t) is True
    t2 = _track(energy="high")  # missing the rest
    assert is_fully_tagged(t2) is False


def test_is_fully_tagged_reduced_field_set():
    t = _track(energy="high")  # only energy
    assert is_fully_tagged(t, ["energy"]) is True
    assert is_fully_tagged(t, ["energy", "function"]) is False


# --- Sorting ---

def test_sort_by_bpm_desc():
    tracks = [_track(id="a", bpm=120.0), _track(id="b", bpm=128.0), _track(id="c", bpm=124.0)]
    out = sort_tracks(tracks, SortRule(keys=["bpm"], direction="desc"))
    assert [t.id for t in out] == ["b", "c", "a"]


def test_sort_none_preserves_order():
    tracks = [_track(id="a", bpm=120.0), _track(id="b", bpm=128.0)]
    out = sort_tracks(tracks, None)
    assert [t.id for t in out] == ["a", "b"]


def test_sort_energy_rank():
    tracks = [_track(id="a", energy="high"), _track(id="b", energy="low"), _track(id="c", energy="mid")]
    out = sort_tracks(tracks, SortRule(keys=["energy"], direction="asc"))
    assert [t.id for t in out] == ["b", "c", "a"]


def test_sort_missing_values_last():
    tracks = [_track(id="a", bpm=None), _track(id="b", bpm=128.0)]
    out = sort_tracks(tracks, SortRule(keys=["bpm"], direction="asc"))
    assert [t.id for t in out] == ["b", "a"]
