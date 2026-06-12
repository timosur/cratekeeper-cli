"""Tests for analysis cache: content hashing, in-memory repo, and analyze_tracks integration."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cratekeeper.analysis.content_hasher import compute_content_hash
from cratekeeper.analysis.mood_analyzer import AudioFeatures
from cratekeeper.local.repository import InMemoryAnalysisCacheRepository


# ─── 5.1 content_hasher tests ────────────────────────────────────────────────


class TestComputeContentHash:
    def test_deterministic_output(self, tmp_path: Path):
        """Same content → same hash."""
        f = tmp_path / "track.mp3"
        f.write_bytes(b"fake audio content for hashing test")
        h1 = compute_content_hash(str(f))
        h2 = compute_content_hash(str(f))
        assert h1 == h2
        assert len(h1) == 64  # SHA256 hex digest

    def test_different_content_different_hash(self, tmp_path: Path):
        """Different content → different hash."""
        f1 = tmp_path / "a.mp3"
        f2 = tmp_path / "b.mp3"
        f1.write_bytes(b"content A")
        f2.write_bytes(b"content B")
        assert compute_content_hash(str(f1)) != compute_content_hash(str(f2))

    def test_missing_file_returns_none(self):
        """Non-existent file → None."""
        result = compute_content_hash("/nonexistent/path/track.mp3")
        assert result is None

    def test_same_content_different_paths(self, tmp_path: Path):
        """Same bytes at different paths → same hash."""
        content = b"identical audio bytes"
        f1 = tmp_path / "dir1" / "track.mp3"
        f2 = tmp_path / "dir2" / "track.mp3"
        f1.parent.mkdir()
        f2.parent.mkdir()
        f1.write_bytes(content)
        f2.write_bytes(content)
        assert compute_content_hash(str(f1)) == compute_content_hash(str(f2))


# ─── 5.2 InMemoryAnalysisCacheRepository tests ──────────────────────────────


class TestInMemoryAnalysisCacheRepository:
    def test_get_miss_returns_none(self):
        repo = InMemoryAnalysisCacheRepository()
        assert repo.get("nonexistent_hash") is None

    def test_store_and_get_roundtrip(self):
        repo = InMemoryAnalysisCacheRepository()
        features = AudioFeatures(
            bpm=128.0,
            energy=0.7,
            danceability=0.85,
            loudness=-8.5,
            key="A minor",
            mood_happy=0.6,
            mood_party=0.8,
            mood_relaxed=0.2,
            mood_sad=0.1,
            mood_aggressive=0.3,
            arousal=6.5,
            valence=7.0,
            voice_instrumental="voice",
            danceability_ml=0.9,
        )
        repo.store("abc123hash", features)
        result = repo.get("abc123hash")
        assert result is not None
        assert result.bpm == 128.0
        assert result.key == "A minor"
        assert result.mood_party == 0.8
        assert result.voice_instrumental == "voice"

    def test_store_overwrites(self):
        repo = InMemoryAnalysisCacheRepository()
        f1 = AudioFeatures(bpm=120.0)
        f2 = AudioFeatures(bpm=130.0)
        repo.store("hash1", f1)
        repo.store("hash1", f2)
        assert repo.get("hash1").bpm == 130.0


# ─── 5.3 analyze_tracks with cache integration ──────────────────────────────


class _FakeTrack:
    """Minimal track mock for analyze_tracks tests."""

    def __init__(self, local_path: str | None, bucket: str = "house"):
        self.local_path = local_path
        self.bucket = bucket
        self.bpm = None
        self.key = None
        self.danceability = None
        self.audio_energy = None
        self.energy = None
        self.audio_mood = None
        self.arousal = None
        self.valence = None
        self.mood = None

    def display_name(self):
        return "FakeTrack"


_FAKE_FEATURES = AudioFeatures(
    bpm=126.0,
    energy=0.65,
    danceability=0.8,
    loudness=-9.0,
    key="C minor",
    mood_happy=0.4,
    mood_party=0.7,
    mood_relaxed=0.3,
    mood_sad=0.1,
    mood_aggressive=0.2,
    arousal=5.5,
    valence=6.0,
    voice_instrumental="instrumental",
    danceability_ml=0.85,
)


class TestAnalyzeTracksWithCache:
    @patch("cratekeeper.analysis.mood_analyzer.analyze_track")
    @patch("cratekeeper.analysis.mood_analyzer.Path")
    def test_cache_hit_skips_essentia(self, mock_path_cls, mock_analyze_track, tmp_path: Path):
        """Cache hit → no essentia call, track populated from cache."""
        from cratekeeper.analysis.mood_analyzer import analyze_tracks

        # Setup: file exists
        audio_file = tmp_path / "track.mp3"
        audio_file.write_bytes(b"test audio")
        mock_path_cls.return_value.exists.return_value = True

        track = _FakeTrack(str(audio_file))

        # Pre-populate cache
        cache = InMemoryAnalysisCacheRepository()
        content_hash = compute_content_hash(str(audio_file))
        cache.store(content_hash, _FAKE_FEATURES)

        with patch("cratekeeper.analysis.mood_config.classify_mood", return_value="Groovy"):
            result = analyze_tracks([track], cache_repo=cache)

        assert result == 1
        assert track.bpm == 126.0
        assert track.key == "C minor"
        # essentia should NOT have been called
        mock_analyze_track.assert_not_called()

    @patch("cratekeeper.analysis.mood_analyzer.analyze_track", return_value=_FAKE_FEATURES)
    @patch("cratekeeper.analysis.mood_analyzer.Path")
    def test_cache_miss_runs_analysis_and_stores(self, mock_path_cls, mock_analyze_track, tmp_path: Path):
        """Cache miss → runs essentia, stores result."""
        from cratekeeper.analysis.mood_analyzer import analyze_tracks

        audio_file = tmp_path / "track.mp3"
        audio_file.write_bytes(b"test audio")
        mock_path_cls.return_value.exists.return_value = True

        track = _FakeTrack(str(audio_file))
        cache = InMemoryAnalysisCacheRepository()

        with patch("cratekeeper.analysis.mood_config.classify_mood", return_value="Groovy"):
            result = analyze_tracks([track], cache_repo=cache)

        assert result == 1
        mock_analyze_track.assert_called_once()

        # Verify stored in cache
        content_hash = compute_content_hash(str(audio_file))
        cached = cache.get(content_hash)
        assert cached is not None
        assert cached.bpm == 126.0

    # ─── 5.4 force flag bypasses cache ───────────────────────────────────────

    @patch("cratekeeper.analysis.mood_analyzer.analyze_track", return_value=_FAKE_FEATURES)
    @patch("cratekeeper.analysis.mood_analyzer.Path")
    def test_force_bypasses_cache(self, mock_path_cls, mock_analyze_track, tmp_path: Path):
        """--force → skips cache lookup, re-analyzes, stores fresh."""
        from cratekeeper.analysis.mood_analyzer import analyze_tracks

        audio_file = tmp_path / "track.mp3"
        audio_file.write_bytes(b"test audio")
        mock_path_cls.return_value.exists.return_value = True

        track = _FakeTrack(str(audio_file))

        # Pre-populate cache with stale data
        cache = InMemoryAnalysisCacheRepository()
        content_hash = compute_content_hash(str(audio_file))
        stale = AudioFeatures(bpm=100.0)
        cache.store(content_hash, stale)

        with patch("cratekeeper.analysis.mood_config.classify_mood", return_value="Groovy"):
            result = analyze_tracks([track], force=True, cache_repo=cache)

        assert result == 1
        # Should have called essentia despite cache hit
        mock_analyze_track.assert_called_once()
        # Cache should be updated with fresh result
        assert cache.get(content_hash).bpm == 126.0

    # ─── 5.5 graceful fallback without cache ─────────────────────────────────

    @patch("cratekeeper.analysis.mood_analyzer.analyze_track", return_value=_FAKE_FEATURES)
    @patch("cratekeeper.analysis.mood_analyzer.Path")
    def test_no_cache_repo_works_normally(self, mock_path_cls, mock_analyze_track, tmp_path: Path):
        """cache_repo=None → normal analysis, no errors."""
        from cratekeeper.analysis.mood_analyzer import analyze_tracks

        audio_file = tmp_path / "track.mp3"
        audio_file.write_bytes(b"test audio")
        mock_path_cls.return_value.exists.return_value = True

        track = _FakeTrack(str(audio_file))

        with patch("cratekeeper.analysis.mood_config.classify_mood", return_value="Groovy"):
            result = analyze_tracks([track], cache_repo=None)

        assert result == 1
        assert track.bpm == 126.0
        mock_analyze_track.assert_called_once()
