"""Scan a local directory for audio files and index metadata via TrackRepository."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

import mutagen
from mutagen.easyid3 import EasyID3
from mutagen.flac import FLAC
from mutagen.mp3 import MP3
from mutagen.mp4 import MP4

from cratekeeper.local.repository import TrackRepository

AUDIO_EXTENSIONS = {".mp3", ".flac", ".wav", ".aiff", ".aif", ".m4a", ".ogg", ".opus"}

DEFAULT_DB_URL = os.environ.get("DATABASE_URL", "postgresql://dj:dj@localhost:5432/djlib")


def _get_conn(db_url: str | None = None):  # type: ignore[return]
    """Compatibility shim — used internally only. Prefer injecting TrackRepository."""
    import psycopg2
    import psycopg2.extras
    conn = psycopg2.connect(db_url or DEFAULT_DB_URL)
    conn.autocommit = False
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS tracks (
                path TEXT PRIMARY KEY,
                rel_path TEXT,
                title TEXT,
                artist TEXT,
                album TEXT,
                isrc TEXT,
                year INTEGER,
                duration_ms INTEGER,
                format TEXT,
                title_norm TEXT,
                artist_norm TEXT
            )
        """)
        cur.execute("""
            DO $$ BEGIN
                ALTER TABLE tracks ADD COLUMN rel_path TEXT;
            EXCEPTION WHEN duplicate_column THEN NULL;
            END $$
        """)
        cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_rel_path ON tracks(rel_path) WHERE rel_path IS NOT NULL")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_isrc ON tracks(isrc) WHERE isrc IS NOT NULL")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_artist_title ON tracks(artist_norm, title_norm)")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS scan_meta (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
    conn.commit()
    return conn


def _normalize_for_index(text: str | None) -> str | None:
    """Simple normalization for index lookups."""
    if not text:
        return None
    import re
    import unicodedata
    text = text.lower().strip()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _file_added_at(file_path: Path) -> str | None:
    """Return filesystem birthtime as ISO-8601, falling back to mtime."""
    try:
        stat = file_path.stat()
        # st_birthtime is macOS/BSD; Linux may not have it
        ts = getattr(stat, "st_birthtime", None) or stat.st_mtime
        return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
    except Exception:
        return None


def _extract_metadata(file_path: Path) -> dict | None:
    """Extract metadata from a single audio file using mutagen.

    Returns a dict suitable for SQLite insertion, or None on failure.
    """
    try:
        audio = mutagen.File(str(file_path), easy=True)
    except Exception:
        return None

    title = None
    artist = None
    album = None
    isrc = None
    year = None
    duration_ms = 0

    added_at = _file_added_at(file_path)

    if audio is None:
        return {
            "path": str(file_path),
            "rel_path": None,
            "title": None, "artist": None, "album": None,
            "isrc": None, "year": None, "duration_ms": 0,
            "format": file_path.suffix.lstrip(".").lower(),
            "title_norm": None, "artist_norm": None,
            "added_at": added_at,
        }

    # Duration
    if audio.info and hasattr(audio.info, "length"):
        duration_ms = int(audio.info.length * 1000)

    if isinstance(audio, (MP3, FLAC)) or hasattr(audio, "tags"):
        tags = audio
        if isinstance(audio, MP3):
            try:
                tags = EasyID3(str(file_path))
            except Exception:
                tags = audio

        title = _first_tag(tags, "title")
        artist = _first_tag(tags, "artist")
        album = _first_tag(tags, "album")
        isrc = _first_tag(tags, "isrc")

        date_str = _first_tag(tags, "date") or _first_tag(tags, "year")
        if date_str:
            try:
                year = int(date_str[:4])
            except (ValueError, IndexError):
                pass

    # For MP4/M4A files opened without easy=True, read native atoms.
    # Also fill in any fields the easy interface missed (e.g. ISRC).
    if isinstance(audio, MP4):
        raw = mutagen.File(str(file_path))
        mp4_tags = raw.tags or {} if raw else {}
        title = title or _first_mp4_tag(mp4_tags, "\xa9nam")
        artist = artist or _first_mp4_tag(mp4_tags, "\xa9ART")
        album = album or _first_mp4_tag(mp4_tags, "\xa9alb")
        date_str = _first_mp4_tag(mp4_tags, "\xa9day")
        if date_str and not year:
            try:
                year = int(date_str[:4])
            except (ValueError, IndexError):
                pass
        # ISRC from freeform atom
        if not isrc:
            isrc_raw = mp4_tags.get("----:com.apple.iTunes:ISRC")
            if isrc_raw:
                val = isrc_raw[0]
                isrc = val.decode("utf-8") if isinstance(val, bytes) else str(val)

    return {
        "path": str(file_path),
        "rel_path": None,
        "title": title, "artist": artist, "album": album,
        "isrc": isrc.upper() if isrc else None,
        "year": year, "duration_ms": duration_ms,
        "format": file_path.suffix.lstrip(".").lower(),
        "title_norm": _normalize_for_index(title),
        "artist_norm": _normalize_for_index(artist),
        "added_at": added_at,
    }


def _first_tag(tags, key: str) -> str | None:
    """Get first value for a tag key, or None."""
    try:
        val = tags.get(key)
        if val:
            return val[0] if isinstance(val, list) else str(val)
    except Exception:
        pass
    return None


def _first_mp4_tag(tags: dict, key: str) -> str | None:
    """Get first value for an MP4 tag key, or None."""
    val = tags.get(key)
    if val:
        return str(val[0]) if isinstance(val, list) else str(val)
    return None


def scan_directory(
    root: Path,
    repo: TrackRepository | None = None,
    db_url: str | None = None,
    incremental: bool = True,
    progress_callback=None,
) -> tuple[int, int, int]:
    """Recursively scan a directory for audio files and index via TrackRepository.

    Args:
        root: Directory to scan.
        repo: TrackRepository to persist scanned tracks into.
              If None, a PostgresTrackRepository is constructed from ``db_url``
              or ``DATABASE_URL`` env var (backward-compat shim).
        db_url: PostgreSQL URL used only when ``repo`` is None.
        incremental: If True, skip files already in the repository.
        progress_callback: Called with (new_count, skipped, file_path).

    Returns (new_count, skipped_count, updated_count).
    """
    from datetime import datetime, timezone

    root = root.resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"Directory not found: {root}")

    if repo is None:
        from cratekeeper.local.pg_repository import PostgresTrackRepository
        repo = PostgresTrackRepository(db_url)
        _owns_repo = True
    else:
        _owns_repo = False

    existing_rel_paths = repo.existing_rel_paths()

    new_count = 0
    updated_count = 0
    skipped = 0
    batch: list[dict] = []
    batch_size = 500
    interrupted = False

    try:
        for dirpath, _dirnames, filenames in os.walk(root):
            for fname in filenames:
                ext = os.path.splitext(fname)[1].lower()
                if ext not in AUDIO_EXTENSIONS:
                    continue

                file_path = Path(dirpath) / fname
                rel = str(file_path.relative_to(root))

                if incremental and rel in existing_rel_paths:
                    skipped += 1
                    if progress_callback and skipped % 500 == 0:
                        progress_callback(new_count, skipped, file_path)
                    continue

                meta = _extract_metadata(file_path)
                if meta:
                    meta["rel_path"] = rel
                    batch.append(meta)
                    if rel in existing_rel_paths:
                        updated_count += 1
                    else:
                        new_count += 1

                if len(batch) >= batch_size:
                    repo.upsert_batch(batch)
                    batch.clear()

                if progress_callback and (new_count + updated_count + skipped) % 50 == 0:
                    progress_callback(new_count, skipped, file_path)
    except KeyboardInterrupt:
        interrupted = True

    if batch:
        repo.upsert_batch(batch)
        batch.clear()

    if progress_callback:
        progress_callback(new_count, skipped, None)

    now = datetime.now(timezone.utc).isoformat()
    repo.set_scan_meta("last_scan", now)
    repo.set_scan_meta("root_path", str(root))
    repo.set_scan_meta("status", "interrupted" if interrupted else "complete")

    return new_count, skipped, updated_count


def get_db_stats(repo: TrackRepository | None = None, db_url: str | None = None) -> dict:
    """Get summary stats from the repository.

    If ``repo`` is None, constructs a PostgresTrackRepository from ``db_url`` / env.
    """
    try:
        if repo is None:
            from cratekeeper.local.pg_repository import PostgresTrackRepository
            repo = PostgresTrackRepository(db_url)
            stats = repo.get_stats()
            repo.close()
            return stats
        return repo.get_stats()
    except Exception:
        return {"total": 0}
