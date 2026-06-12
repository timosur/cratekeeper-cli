"""TrackRepository protocol and in-memory implementation for local track persistence."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from cratekeeper.analysis.mood_analyzer import AudioFeatures


@dataclass
class LocalTrack:
    """Row in the tracks table."""

    path: str
    rel_path: str | None = None
    title: str | None = None
    artist: str | None = None
    album: str | None = None
    isrc: str | None = None
    year: int | None = None
    duration_ms: int = 0
    format: str | None = None
    title_norm: str | None = None
    artist_norm: str | None = None

    @classmethod
    def from_dict(cls, d: dict) -> "LocalTrack":
        return cls(
            path=d["path"],
            rel_path=d.get("rel_path"),
            title=d.get("title"),
            artist=d.get("artist"),
            album=d.get("album"),
            isrc=d.get("isrc"),
            year=d.get("year"),
            duration_ms=d.get("duration_ms", 0),
            format=d.get("format"),
            title_norm=d.get("title_norm"),
            artist_norm=d.get("artist_norm"),
        )

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "rel_path": self.rel_path,
            "title": self.title,
            "artist": self.artist,
            "album": self.album,
            "isrc": self.isrc,
            "year": self.year,
            "duration_ms": self.duration_ms,
            "format": self.format,
            "title_norm": self.title_norm,
            "artist_norm": self.artist_norm,
        }


@runtime_checkable
class TrackRepository(Protocol):
    """Protocol for local track persistence.

    All domain code interacts with this interface; psycopg2 is an implementation detail.
    """

    # ── write ────────────────────────────────────────────────────────────────

    def upsert(self, track: LocalTrack) -> None:
        """Insert or update a single track record."""
        ...

    def upsert_batch(self, tracks: list[dict]) -> None:
        """Insert or update a batch of track records (dict format from scanner)."""
        ...

    def set_scan_meta(self, key: str, value: str) -> None:
        """Store a scan metadata key/value (e.g., last_scan timestamp)."""
        ...

    # ── read ─────────────────────────────────────────────────────────────────

    def find_by_isrc(self, isrc: str) -> LocalTrack | None:
        """Return the track with the given ISRC, or None."""
        ...

    def find_by_path(self, path: str) -> LocalTrack | None:
        """Return the track with the given absolute path, or None."""
        ...

    def find_by_rel_path(self, rel_path: str) -> LocalTrack | None:
        """Return the track with the given relative path, or None."""
        ...

    def find_by_exact(self, artist_norm: str, title_norm: str) -> LocalTrack | None:
        """Return a track matching the normalized artist + title exactly, or None."""
        ...

    def find_candidates(self, artist_prefix: str) -> list[LocalTrack]:
        """Return tracks whose artist_norm starts with the given prefix (for fuzzy matching)."""
        ...

    def existing_rel_paths(self) -> set[str]:
        """Return all known relative paths (used by scanner for incremental mode)."""
        ...

    def all(self) -> list[LocalTrack]:
        """Return all stored tracks."""
        ...

    def get_stats(self) -> dict:
        """Return summary stats: total, with_tags, with_isrc, formats, last_scan."""
        ...

    # ── lifecycle ────────────────────────────────────────────────────────────

    def close(self) -> None:
        """Release underlying resources (e.g., close DB connection)."""
        ...


@runtime_checkable
class AnalysisCacheRepository(Protocol):
    """Protocol for persistent audio analysis cache.

    Stores and retrieves AudioFeatures keyed by content hash (SHA256).
    """

    def get(self, content_hash: str) -> "AudioFeatures | None":
        """Retrieve cached analysis results for the given content hash, or None."""
        ...

    def store(self, content_hash: str, features: "AudioFeatures") -> None:
        """Store analysis results for the given content hash (upsert)."""
        ...

    def close(self) -> None:
        """Release underlying resources."""
        ...


# ---------------------------------------------------------------------------
# In-memory implementation (for tests and local dev without a DB)
# ---------------------------------------------------------------------------

class InMemoryTrackRepository:
    """TrackRepository backed by plain Python dicts. No database required."""

    def __init__(self) -> None:
        self._by_path: dict[str, LocalTrack] = {}
        self._by_rel_path: dict[str, LocalTrack] = {}
        self._by_isrc: dict[str, LocalTrack] = {}
        self._scan_meta: dict[str, str] = {}

    # ── write ────────────────────────────────────────────────────────────────

    def upsert(self, track: LocalTrack) -> None:
        self._by_path[track.path] = track
        if track.rel_path:
            self._by_rel_path[track.rel_path] = track
        if track.isrc:
            self._by_isrc[track.isrc.upper()] = track

    def upsert_batch(self, records: list[dict]) -> None:
        for d in records:
            self.upsert(LocalTrack.from_dict(d))

    def set_scan_meta(self, key: str, value: str) -> None:
        self._scan_meta[key] = value

    # ── read ─────────────────────────────────────────────────────────────────

    def find_by_isrc(self, isrc: str) -> LocalTrack | None:
        return self._by_isrc.get(isrc.upper())

    def find_by_path(self, path: str) -> LocalTrack | None:
        return self._by_path.get(path)

    def find_by_rel_path(self, rel_path: str) -> LocalTrack | None:
        return self._by_rel_path.get(rel_path)

    def find_by_exact(self, artist_norm: str, title_norm: str) -> LocalTrack | None:
        for t in self._by_path.values():
            if t.artist_norm == artist_norm and t.title_norm == title_norm:
                return t
        return None

    def find_candidates(self, artist_prefix: str) -> list[LocalTrack]:
        return [
            t for t in self._by_path.values()
            if t.artist_norm and t.artist_norm.startswith(artist_prefix)
        ]

    def existing_rel_paths(self) -> set[str]:
        return set(self._by_rel_path.keys())

    def all(self) -> list[LocalTrack]:
        return list(self._by_path.values())

    def get_stats(self) -> dict:
        tracks = list(self._by_path.values())
        formats: dict[str, int] = {}
        for t in tracks:
            if t.format:
                formats[t.format] = formats.get(t.format, 0) + 1
        return {
            "total": len(tracks),
            "with_tags": sum(1 for t in tracks if t.title and t.artist),
            "with_isrc": sum(1 for t in tracks if t.isrc),
            "formats": formats,
            "last_scan": self._scan_meta.get("last_scan"),
        }

    # ── lifecycle ────────────────────────────────────────────────────────────

    def close(self) -> None:
        pass  # nothing to release


# ---------------------------------------------------------------------------
# In-memory analysis cache (for tests and local dev without a DB)
# ---------------------------------------------------------------------------

class InMemoryAnalysisCacheRepository:
    """AnalysisCacheRepository backed by a plain dict. No database required."""

    def __init__(self) -> None:
        self._cache: dict[str, "AudioFeatures"] = {}

    def get(self, content_hash: str) -> "AudioFeatures | None":
        return self._cache.get(content_hash)

    def store(self, content_hash: str, features: "AudioFeatures") -> None:
        self._cache[content_hash] = features

    def close(self) -> None:
        pass
