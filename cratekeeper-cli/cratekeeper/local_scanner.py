"""Scan a local directory for audio files and index metadata into PostgreSQL."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

import psycopg2
import psycopg2.extras
import mutagen
from mutagen.easyid3 import EasyID3
from mutagen.flac import FLAC
from mutagen.mp3 import MP3
from mutagen.mp4 import MP4

AUDIO_EXTENSIONS = {".mp3", ".flac", ".wav", ".aiff", ".aif", ".m4a", ".ogg", ".opus"}

DEFAULT_DB_URL = os.environ.get("DATABASE_URL", "postgresql://dj:dj@localhost:5432/djlib")


def _get_conn(db_url: str | None = None) -> psycopg2.extensions.connection:
    """Create a PostgreSQL connection and ensure schema exists."""
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
        # Migration: add rel_path column if missing (existing DBs)
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

    if audio is None:
        return {
            "path": str(file_path),
            "rel_path": None,
            "title": None, "artist": None, "album": None,
            "isrc": None, "year": None, "duration_ms": 0,
            "format": file_path.suffix.lstrip(".").lower(),
            "title_norm": None, "artist_norm": None,
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
    db_url: str | None = None,
    incremental: bool = True,
    progress_callback=None,
) -> tuple[psycopg2.extensions.connection, int, int, int]:
    """Recursively scan a directory for audio files and index into PostgreSQL.

    Args:
        root: Directory to scan.
        db_url: PostgreSQL connection URL.
        incremental: If True, skip files already in the DB.
        progress_callback: Called with (new_count, skipped, file_path).

    Returns (connection, new_count, skipped_count, updated_count).
    """
    root = root.resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"Directory not found: {root}")

    conn = _get_conn(db_url)

    # Load existing rel_paths for dedup across different mount points
    with conn.cursor() as cur:
        cur.execute("SELECT rel_path FROM tracks WHERE rel_path IS NOT NULL")
        existing_rel_paths = {row[0] for row in cur}

    new_count = 0
    updated_count = 0
    skipped = 0
    batch: list[dict] = []
    batch_size = 500
    interrupted = False

    # Use os.walk — much faster than rglob over NAS/SMB (avoids per-file stat)
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
                    _insert_batch(conn, batch)
                    batch.clear()

                if progress_callback and (new_count + updated_count + skipped) % 50 == 0:
                    progress_callback(new_count, skipped, file_path)
    except KeyboardInterrupt:
        interrupted = True

    # Flush remaining batch (safe even on interrupt)
    if batch:
        _insert_batch(conn, batch)
        batch.clear()

    # Final progress
    if progress_callback:
        progress_callback(new_count, skipped, None)

    # Update scan metadata
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO scan_meta (key, value) VALUES (%s, %s) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
            ("last_scan", datetime.now(timezone.utc).isoformat()),
        )
        cur.execute(
            "INSERT INTO scan_meta (key, value) VALUES (%s, %s) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
            ("root_path", str(root)),
        )
        cur.execute(
            "INSERT INTO scan_meta (key, value) VALUES (%s, %s) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
            ("status", "interrupted" if interrupted else "complete"),
        )
    conn.commit()

    return conn, new_count, skipped, updated_count


def _insert_batch(conn: psycopg2.extensions.connection, batch: list[dict]) -> None:
    """Insert a batch of track records into the database.

    Uses rel_path as the dedup key when available, falling back to path.
    If a track with the same rel_path already exists (from a different mount),
    the row is updated including the new absolute path.
    """
    with_rel = [d for d in batch if d.get("rel_path")]
    without_rel = [d for d in batch if not d.get("rel_path")]

    with conn.cursor() as cur:
        if with_rel:
            # Delete old rows that would conflict on rel_path but have a different path PK.
            # This avoids a PK violation when the mount point changed.
            for d in with_rel:
                cur.execute(
                    "DELETE FROM tracks WHERE rel_path = %s AND path != %s",
                    (d["rel_path"], d["path"]),
                )
            psycopg2.extras.execute_values(
                cur,
                """INSERT INTO tracks (path, rel_path, title, artist, album, isrc, year, duration_ms, format, title_norm, artist_norm)
                   VALUES %s
                   ON CONFLICT (path) DO UPDATE SET
                       rel_path = EXCLUDED.rel_path,
                       title = EXCLUDED.title, artist = EXCLUDED.artist, album = EXCLUDED.album,
                       isrc = EXCLUDED.isrc, year = EXCLUDED.year, duration_ms = EXCLUDED.duration_ms,
                       format = EXCLUDED.format, title_norm = EXCLUDED.title_norm, artist_norm = EXCLUDED.artist_norm""",
                [(d["path"], d["rel_path"], d["title"], d["artist"], d["album"], d["isrc"], d["year"],
                  d["duration_ms"], d["format"], d["title_norm"], d["artist_norm"]) for d in with_rel],
            )
        if without_rel:
            psycopg2.extras.execute_values(
                cur,
                """INSERT INTO tracks (path, title, artist, album, isrc, year, duration_ms, format, title_norm, artist_norm)
                   VALUES %s
                   ON CONFLICT (path) DO UPDATE SET
                       title = EXCLUDED.title, artist = EXCLUDED.artist, album = EXCLUDED.album,
                       isrc = EXCLUDED.isrc, year = EXCLUDED.year, duration_ms = EXCLUDED.duration_ms,
                       format = EXCLUDED.format, title_norm = EXCLUDED.title_norm, artist_norm = EXCLUDED.artist_norm""",
                [(d["path"], d["title"], d["artist"], d["album"], d["isrc"], d["year"],
                  d["duration_ms"], d["format"], d["title_norm"], d["artist_norm"]) for d in without_rel],
            )
    conn.commit()


def get_db_stats(db_url: str | None = None) -> dict:
    """Get summary stats from the library database."""
    try:
        conn = _get_conn(db_url)
    except Exception:
        return {"total": 0}
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM tracks")
        total = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM tracks WHERE title IS NOT NULL AND artist IS NOT NULL")
        with_tags = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM tracks WHERE isrc IS NOT NULL")
        with_isrc = cur.fetchone()[0]

        formats = {}
        cur.execute("SELECT format, COUNT(*) FROM tracks GROUP BY format ORDER BY COUNT(*) DESC")
        for row in cur:
            formats[row[0]] = row[1]

        last_scan = None
        cur.execute("SELECT value FROM scan_meta WHERE key='last_scan'")
        row = cur.fetchone()
        if row:
            last_scan = row[0]

    conn.close()
    return {
        "total": total, "with_tags": with_tags, "with_isrc": with_isrc,
        "formats": formats, "last_scan": last_scan,
    }
