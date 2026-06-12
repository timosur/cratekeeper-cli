"""PostgreSQL implementation of AnalysisCacheRepository."""

from __future__ import annotations

import os

import psycopg2
import psycopg2.extras

from cratekeeper.analysis.mood_analyzer import AudioFeatures


class PostgresAnalysisCacheRepository:
    """AnalysisCacheRepository backed by PostgreSQL via psycopg2.

    Stores audio analysis results keyed by SHA256 content hash.
    Reads ``DATABASE_URL`` from the environment on construction.
    """

    def __init__(self, db_url: str | None = None) -> None:
        resolved = db_url or os.environ.get("DATABASE_URL")
        if not resolved:
            raise RuntimeError(
                "DATABASE_URL environment variable is not set. "
                "Cannot initialize analysis cache."
            )
        self._conn = psycopg2.connect(resolved)
        self._conn.autocommit = False
        self._ensure_schema()

    # ── schema ───────────────────────────────────────────────────────────────

    def _ensure_schema(self) -> None:
        with self._conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS track_analysis (
                    content_hash TEXT PRIMARY KEY,
                    bpm REAL,
                    energy REAL,
                    danceability REAL,
                    loudness REAL,
                    key TEXT,
                    mood_happy REAL,
                    mood_party REAL,
                    mood_relaxed REAL,
                    mood_sad REAL,
                    mood_aggressive REAL,
                    arousal REAL,
                    valence REAL,
                    voice_instrumental TEXT,
                    danceability_ml REAL,
                    analyzed_at TIMESTAMP DEFAULT NOW()
                )
            """)
            # Schema evolution: add any missing columns for future fields
            _columns = [
                ("bpm", "REAL"),
                ("energy", "REAL"),
                ("danceability", "REAL"),
                ("loudness", "REAL"),
                ("key", "TEXT"),
                ("mood_happy", "REAL"),
                ("mood_party", "REAL"),
                ("mood_relaxed", "REAL"),
                ("mood_sad", "REAL"),
                ("mood_aggressive", "REAL"),
                ("arousal", "REAL"),
                ("valence", "REAL"),
                ("voice_instrumental", "TEXT"),
                ("danceability_ml", "REAL"),
                ("analyzed_at", "TIMESTAMP DEFAULT NOW()"),
            ]
            for col_name, col_type in _columns:
                cur.execute(f"""
                    DO $$ BEGIN
                        ALTER TABLE track_analysis ADD COLUMN {col_name} {col_type};
                    EXCEPTION WHEN duplicate_column THEN NULL;
                    END $$
                """)
            self._conn.commit()

    # ── read ─────────────────────────────────────────────────────────────────

    def get(self, content_hash: str) -> AudioFeatures | None:
        """Retrieve cached analysis results by content hash."""
        with self._conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """
                SELECT bpm, energy, danceability, loudness, key,
                       mood_happy, mood_party, mood_relaxed, mood_sad, mood_aggressive,
                       arousal, valence, voice_instrumental, danceability_ml
                FROM track_analysis
                WHERE content_hash = %s
                """,
                (content_hash,),
            )
            row = cur.fetchone()
            if row is None:
                return None
            return AudioFeatures(
                bpm=row["bpm"] or 0.0,
                energy=row["energy"] or 0.0,
                danceability=row["danceability"] or 0.0,
                loudness=row["loudness"] or 0.0,
                key=row["key"] or "",
                mood_happy=row["mood_happy"] or 0.0,
                mood_party=row["mood_party"] or 0.0,
                mood_relaxed=row["mood_relaxed"] or 0.0,
                mood_sad=row["mood_sad"] or 0.0,
                mood_aggressive=row["mood_aggressive"] or 0.0,
                arousal=row["arousal"] or 0.0,
                valence=row["valence"] or 0.0,
                voice_instrumental=row["voice_instrumental"] or "",
                danceability_ml=row["danceability_ml"] or 0.0,
            )

    # ── write ────────────────────────────────────────────────────────────────

    def store(self, content_hash: str, features: AudioFeatures) -> None:
        """Store analysis results (upsert by content hash)."""
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO track_analysis (
                    content_hash, bpm, energy, danceability, loudness, key,
                    mood_happy, mood_party, mood_relaxed, mood_sad, mood_aggressive,
                    arousal, valence, voice_instrumental, danceability_ml, analyzed_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW()
                )
                ON CONFLICT (content_hash) DO UPDATE SET
                    bpm = EXCLUDED.bpm,
                    energy = EXCLUDED.energy,
                    danceability = EXCLUDED.danceability,
                    loudness = EXCLUDED.loudness,
                    key = EXCLUDED.key,
                    mood_happy = EXCLUDED.mood_happy,
                    mood_party = EXCLUDED.mood_party,
                    mood_relaxed = EXCLUDED.mood_relaxed,
                    mood_sad = EXCLUDED.mood_sad,
                    mood_aggressive = EXCLUDED.mood_aggressive,
                    arousal = EXCLUDED.arousal,
                    valence = EXCLUDED.valence,
                    voice_instrumental = EXCLUDED.voice_instrumental,
                    danceability_ml = EXCLUDED.danceability_ml,
                    analyzed_at = NOW()
                """,
                (
                    content_hash,
                    features.bpm,
                    features.energy,
                    features.danceability,
                    features.loudness,
                    features.key,
                    features.mood_happy,
                    features.mood_party,
                    features.mood_relaxed,
                    features.mood_sad,
                    features.mood_aggressive,
                    features.arousal,
                    features.valence,
                    features.voice_instrumental,
                    features.danceability_ml,
                ),
            )
            self._conn.commit()

    # ── lifecycle ────────────────────────────────────────────────────────────

    def close(self) -> None:
        """Close the database connection."""
        if self._conn and not self._conn.closed:
            self._conn.close()
