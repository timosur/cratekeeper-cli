## Context

Audio analysis via essentia + TensorFlow is the most expensive step in the pipeline (~2-5s/track). Results currently persist only in per-plan JSON files. The same audio file re-analyzed across plans (event + library) or on re-import wastes significant compute. PostgreSQL already runs locally (Docker) for track metadata. The analysis cache adds a content-addressed store alongside it.

ADR-0001 (Plan base class with type discriminator) is in force and unaffected — this change operates below the Plan layer, at the analysis function level.

## Goals / Non-Goals

**Goals:**
- Eliminate redundant audio analysis for the same file content across all plans
- Transparent cache — callers of `analyze_tracks()` need zero changes
- Deterministic: same content hash → same stored results
- Respect existing `--force` flag for cache bypass

**Non-Goals:**
- Acoustic fingerprinting (Chromaprint, etc.) — content hash is sufficient
- Caching derived fields (mood label, energy category) — these depend on genre thresholds that evolve
- Cross-machine cache sharing — local PostgreSQL only
- Migration framework — continue existing `_ensure_schema()` pattern

## Architecture

### Component Diagram (C4 Level 3 — inside `crate` CLI container)

```mermaid
flowchart TD
    subgraph CLI["crate CLI (single Python process)"]
        CMD["Pipeline Commands\n(analyze-mood, wizard)"]
        MA["mood_analyzer.py\nanalyze_tracks()"]
        HASH["content_hasher\n(SHA256)"]
        ACR["AnalysisCacheRepository\n(new)"]
        PTR["PostgresTrackRepository\n(existing)"]
    end

    PG[(PostgreSQL\nlocalhost:5432)]
    FS[/Audio Files\n(local disk)/]

    CMD -->|"calls"| MA
    MA -->|"1. hash file"| HASH
    HASH -->|"reads bytes"| FS
    MA -->|"2. lookup by hash"| ACR
    ACR -->|"SELECT"| PG
    MA -->|"3. on miss: analyze"| FS
    MA -->|"4. on miss: store"| ACR
    ACR -->|"INSERT/UPDATE"| PG
    PTR -->|"tracks table"| PG
```

**Boundaries:**
- `AnalysisCacheRepository` is a new class following the existing Protocol pattern, owning only the `track_analysis` table
- `content_hasher` is a pure function (file path → SHA256 hex string)
- `mood_analyzer.py` orchestrates: hash → lookup → analyze-if-miss → store
- Existing `PostgresTrackRepository` unchanged — separate table, separate concern

## Decisions

### 1. New `track_analysis` table (not extending `tracks`)

**Rationale:** Analysis is keyed by content, not file path. A file in an event plan may never appear in the `tracks` table (only scanned files go there). Separate table = separate concern, no coupling.

**Alternative rejected:** Adding columns to `tracks` — would require path-based key, lose cross-plan dedup, and bloat a table with different update patterns.

### 2. SHA256 of full file bytes as cache key

**Rationale:** Deterministic, survives renames/moves/copies. stdlib `hashlib` — no dependency. ~500MB/s on modern hardware (negligible vs 2-5s analysis).

**Alternative rejected:** Partial hash (first N bytes) — risk of collision on files with same headers but different audio content. Acoustic fingerprint (Chromaprint) — heavy dependency, overkill for local dedup.

### 3. Protocol + class pattern (matches existing codebase)

**Rationale:** Follow `TrackRepository` Protocol pattern. New `AnalysisCacheRepository` Protocol with `PostgresAnalysisCacheRepository` concrete class. Enables `InMemoryAnalysisCacheRepository` for tests.

### 4. Auto-create schema via `_ensure_schema()` (no migrations)

**Rationale:** Existing pattern. `CREATE TABLE IF NOT EXISTS` + `CREATE INDEX IF NOT EXISTS`. No migration framework needed for a single additive table.

### 5. Cache integrated inside `analyze_tracks()` — not at caller level

**Rationale:** Single integration point. All callers (event pipeline, library pipeline, future pipelines) get caching transparently. The existing `_is_analyzed()` check becomes secondary — DB cache is checked first.

### 6. Store raw `AudioFeatures` fields only

**Rationale:** Derived fields (`mood` label, `energy` category) depend on genre-specific thresholds in `mood_config.py` which may change. Storing them would create stale cache entries. Re-derivation from raw values is O(1).

## Table Schema

```sql
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
);
```

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| Hashing large files (500MB+) adds latency on first run | SHA256 at ~500MB/s = 1s max. Still 2-4x faster than re-analysis. Stream in 8KB chunks to avoid memory spikes. |
| DB unavailable (Docker not running) | Graceful fallback: if connection fails, log warning and analyze without cache. Never block the pipeline. |
| Schema drift if AudioFeatures gains new fields | `_ensure_schema()` adds `ALTER TABLE ADD COLUMN IF NOT EXISTS` for new fields. Old rows get NULL for new columns — re-analyze with `--force` to backfill. |
| Disk space for hashes in DB | 64-char hex string × N tracks is negligible (~64 bytes/row for PK). |

## Migration Plan

1. Add `AnalysisCacheRepository` Protocol + Postgres implementation
2. Add `content_hasher` utility function
3. Modify `analyze_tracks()` flow: hash → lookup → analyze-if-miss → store
4. `_ensure_schema()` in new repo class creates table on first use — no manual migration
5. Rollback: drop `track_analysis` table. Pipeline works exactly as before (no cache, re-analyzes everything).

## Open Questions

None — all decisions resolved during proposal grilling. No in-force ADRs conflict with this design.
