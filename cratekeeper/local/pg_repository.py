"""PostgreSQL implementation of TrackRepository."""

from __future__ import annotations

import os
from datetime import datetime, timezone

import psycopg2
import psycopg2.extras

from cratekeeper.local.repository import LocalTrack, TrackRepository


class ConfigurationError(Exception):
    """Raised when required configuration (e.g., DATABASE_URL) is missing."""


class PostgresTrackRepository:
    """TrackRepository backed by PostgreSQL via psycopg2.

    Reads ``DATABASE_URL`` from the environment on construction.
    Raises ``ConfigurationError`` if the variable is absent.
    """

    def __init__(self, db_url: str | None = None) -> None:
        resolved = db_url or os.environ.get("DATABASE_URL")
        if not resolved:
            raise ConfigurationError(
                "DATABASE_URL environment variable is not set. "
                "Set it to a PostgreSQL connection string (e.g., "
                "postgresql://user:pass@localhost:5432/dbname)."
            )
        self._conn = psycopg2.connect(resolved)
        self._conn.autocommit = False
        self._ensure_schema()

    # ── schema ───────────────────────────────────────────────────────────────

    def _ensure_schema(self) -> None:
        with self._conn.cursor() as cur:
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
        self._conn.commit()

    # ── write ────────────────────────────────────────────────────────────────

    def upsert(self, track: LocalTrack) -> None:
        self.upsert_batch([track.to_dict()])

    def upsert_batch(self, records: list[dict]) -> None:
        with_rel = [d for d in records if d.get("rel_path")]
        without_rel = [d for d in records if not d.get("rel_path")]

        with self._conn.cursor() as cur:
            if with_rel:
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
        self._conn.commit()

    def set_scan_meta(self, key: str, value: str) -> None:
        with self._conn.cursor() as cur:
            cur.execute(
                "INSERT INTO scan_meta (key, value) VALUES (%s, %s) "
                "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
                (key, value),
            )
        self._conn.commit()

    # ── read ─────────────────────────────────────────────────────────────────

    def _row_to_track(self, row: tuple) -> LocalTrack:
        return LocalTrack(
            path=row[0], rel_path=row[1], title=row[2], artist=row[3],
            album=row[4], isrc=row[5], year=row[6], duration_ms=row[7] or 0,
            format=row[8], title_norm=row[9], artist_norm=row[10],
        )

    def find_by_isrc(self, isrc: str) -> LocalTrack | None:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT path, rel_path, title, artist, album, isrc, year, duration_ms, format, title_norm, artist_norm "
                "FROM tracks WHERE isrc = %s LIMIT 1",
                (isrc.upper(),),
            )
            row = cur.fetchone()
        return self._row_to_track(row) if row else None

    def find_by_path(self, path: str) -> LocalTrack | None:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT path, rel_path, title, artist, album, isrc, year, duration_ms, format, title_norm, artist_norm "
                "FROM tracks WHERE path = %s",
                (path,),
            )
            row = cur.fetchone()
        return self._row_to_track(row) if row else None

    def find_by_rel_path(self, rel_path: str) -> LocalTrack | None:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT path, rel_path, title, artist, album, isrc, year, duration_ms, format, title_norm, artist_norm "
                "FROM tracks WHERE rel_path = %s",
                (rel_path,),
            )
            row = cur.fetchone()
        return self._row_to_track(row) if row else None

    def find_by_exact(self, artist_norm: str, title_norm: str) -> LocalTrack | None:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT path, rel_path, title, artist, album, isrc, year, duration_ms, format, title_norm, artist_norm "
                "FROM tracks WHERE artist_norm = %s AND title_norm = %s LIMIT 1",
                (artist_norm, title_norm),
            )
            row = cur.fetchone()
        return self._row_to_track(row) if row else None

    def find_candidates(self, artist_prefix: str) -> list[LocalTrack]:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT path, rel_path, title, artist, album, isrc, year, duration_ms, format, title_norm, artist_norm "
                "FROM tracks WHERE artist_norm LIKE %s AND title_norm IS NOT NULL",
                (artist_prefix + "%",),
            )
            rows = cur.fetchall()
        return [self._row_to_track(r) for r in rows]

    def existing_rel_paths(self) -> set[str]:
        with self._conn.cursor() as cur:
            cur.execute("SELECT rel_path FROM tracks WHERE rel_path IS NOT NULL")
            return {row[0] for row in cur}

    def all(self) -> list[LocalTrack]:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT path, rel_path, title, artist, album, isrc, year, duration_ms, format, title_norm, artist_norm "
                "FROM tracks"
            )
            rows = cur.fetchall()
        return [self._row_to_track(r) for r in rows]

    def get_stats(self) -> dict:
        with self._conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM tracks")
            total = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM tracks WHERE title IS NOT NULL AND artist IS NOT NULL")
            with_tags = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM tracks WHERE isrc IS NOT NULL")
            with_isrc = cur.fetchone()[0]
            formats: dict[str, int] = {}
            cur.execute("SELECT format, COUNT(*) FROM tracks GROUP BY format ORDER BY COUNT(*) DESC")
            for row in cur:
                formats[row[0]] = row[1]
            cur.execute("SELECT value FROM scan_meta WHERE key='last_scan'")
            row = cur.fetchone()
            last_scan = row[0] if row else None
        return {
            "total": total, "with_tags": with_tags, "with_isrc": with_isrc,
            "formats": formats, "last_scan": last_scan,
        }

    # ── lifecycle ────────────────────────────────────────────────────────────

    def close(self) -> None:
        if self._conn and not self._conn.closed:
            self._conn.close()
