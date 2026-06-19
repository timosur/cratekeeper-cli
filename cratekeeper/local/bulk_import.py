"""Import scanned local audio files into a profile's library pipeline.

Unlike the Spotify-based ``fetch`` path, this reads files already indexed in the
shared PostgreSQL scan database, builds :class:`Track` records from their ID3
metadata (including the genre tag, read directly from the file), and produces a
:class:`LibraryImportPlan`. No Spotify access is required.
"""

from __future__ import annotations

from pathlib import Path

import mutagen
from mutagen.mp4 import MP4

from cratekeeper.local.repository import TrackRepository
from cratekeeper.models import Track


class SourceNotScannedError(Exception):
    """Raised when no scanned files exist under the requested source path."""


def _read_genre(path: Path) -> list[str]:
    """Read the genre tag(s) from an audio file. Returns [] when absent."""
    try:
        suffix = path.suffix.lower()
        if suffix in (".m4a", ".mp4"):
            audio = MP4(str(path))
            vals = audio.tags.get("\xa9gen") if audio.tags else None
            return [str(v) for v in vals] if vals else []
        audio = mutagen.File(str(path), easy=True)
        if audio is None:
            return []
        vals = audio.get("genre")
        if not vals:
            return []
        return [str(v) for v in (vals if isinstance(vals, list) else [vals])]
    except Exception:
        return []


def import_tracks(source_path: Path, repo: TrackRepository | None = None, db_url: str | None = None) -> list[Track]:
    """Build Track records for all scanned files under ``source_path``.

    Raises :class:`SourceNotScannedError` when the source has no indexed files.
    """
    source = Path(source_path).expanduser().resolve()
    prefix = str(source)

    _owns_repo = False
    if repo is None:
        from cratekeeper.local.pg_repository import PostgresTrackRepository
        repo = PostgresTrackRepository(db_url)
        _owns_repo = True

    all_tracks = repo.all()
    rows = [
        (t.path, t.title, t.artist, t.album, t.isrc, t.year, t.duration_ms, t.added_at)
        for t in all_tracks
        if t.path == prefix or t.path.startswith(prefix + "/")
    ]

    if _owns_repo:
        repo.close()

    if not rows:
        raise SourceNotScannedError(
            f"No scanned files found under {source}. Run 'crate scan {source}' first."
        )

    tracks: list[Track] = []
    for path, title, artist, album, isrc, year, duration_ms, added_at in rows:
        file_path = Path(path)
        name = title or file_path.stem
        artists = [artist] if artist else ["Unknown"]
        track = Track(
            id=isrc or path,
            name=name,
            artists=artists,
            artist_ids=[],
            album=album or "",
            duration_ms=duration_ms or 0,
            isrc=isrc,
            release_year=year,
            artist_genres=_read_genre(file_path),
            local_path=path,
            added_at=added_at,
        )
        tracks.append(track)

    return tracks
