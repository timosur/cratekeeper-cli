## 1. Analysis Cache Repository

- [x] 1.1 Create `AnalysisCacheRepository` Protocol in `cratekeeper/local/repository.py` with methods: `get(content_hash: str) -> AudioFeatures | None`, `store(content_hash: str, features: AudioFeatures) -> None`, `close() -> None`
- [x] 1.2 Create `PostgresAnalysisCacheRepository` class in `cratekeeper/local/pg_analysis_cache.py` implementing the protocol with psycopg2
- [x] 1.3 Implement `_ensure_schema()` in `PostgresAnalysisCacheRepository` — `CREATE TABLE IF NOT EXISTS track_analysis (...)` with all 14 columns + `analyzed_at` timestamp
- [x] 1.4 Implement `get()` — `SELECT` by content_hash, return `AudioFeatures` or None
- [x] 1.5 Implement `store()` — `INSERT ... ON CONFLICT (content_hash) DO UPDATE SET ...` (upsert pattern)
- [x] 1.6 Create `InMemoryAnalysisCacheRepository` for testing (dict-backed)

## 2. Content Hashing

- [x] 2.1 Create `content_hasher.py` in `cratekeeper/analysis/` with function `compute_content_hash(file_path: str) -> str` — streams file in 8KB chunks through SHA256, returns hex digest
- [x] 2.2 Add error handling for missing/unreadable files (return None or raise with clear message)

## 3. Integration into mood_analyzer.py

- [x] 3.1 Add `cache_repo` parameter to `analyze_tracks()` (optional, defaults to None for backward compat)
- [x] 3.2 Modify per-track loop: compute hash → check cache → on hit, populate Track fields from cached AudioFeatures → on miss, run existing analysis then store
- [x] 3.3 Respect `--force` flag: skip cache lookup, re-analyze, overwrite stored results
- [x] 3.4 Graceful fallback: wrap cache operations in try/except, log warning on DB failure, continue without cache

## 4. Pipeline Wiring

- [x] 4.1 Instantiate `PostgresAnalysisCacheRepository` in pipeline commands that call `analyze_tracks()` (wizard, analyze-mood)
- [x] 4.2 Pass cache_repo to `analyze_tracks()` calls
- [x] 4.3 Handle case where PostgreSQL is unavailable — pass None as cache_repo, log warning

## 5. Testing

- [x] 5.1 Unit tests for `compute_content_hash()` — deterministic output, handles missing file
- [x] 5.2 Unit tests for `InMemoryAnalysisCacheRepository` — get/store round-trip
- [x] 5.3 Integration test: `analyze_tracks()` with in-memory cache — verify cache hit skips essentia, cache miss runs analysis and stores
- [x] 5.4 Integration test: `--force` flag bypasses cache and overwrites
- [x] 5.5 Integration test: DB unavailable graceful fallback (cache_repo=None)

## 6. Validation

- [x] 6.1 Run `openspec validate persist-track-analysis --type change --strict` to verify specs match implementation
