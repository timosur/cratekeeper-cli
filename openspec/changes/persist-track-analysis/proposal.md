## Why

Audio analysis (essentia + TF models) is the most expensive pipeline step (~2-5s per track). Currently, results live only in per-plan JSON files. When the same audio file appears in multiple plans (event plan + library plan) or a directory is re-imported, analysis runs from scratch each time. Persisting results in PostgreSQL keyed by content hash eliminates redundant computation and makes analysis a one-time cost per unique audio file.

## What Changes

- Introduce SHA256 content hashing for audio files as a stable identity key independent of file path
- Add a `track_analysis` table in PostgreSQL storing all 14 raw `AudioFeatures` fields, keyed by content hash
- Modify `analyze_tracks()` to check DB cache before running essentia; on miss, analyze then store; on hit, populate Track fields from cache
- Existing `--force` flag bypasses cache (re-analyzes and overwrites stored results)
- No derived fields (mood label, energy category) stored — these remain computed at read time from raw values + genre-specific thresholds

## Capabilities

### New Capabilities
- `analysis-cache`: Persistent caching of audio analysis results in PostgreSQL, keyed by SHA256 content hash. Covers cache lookup, store, invalidation via hash mismatch, and force-bypass.

### Modified Capabilities
- `audio-analysis`: Behavior change — analysis now checks DB cache before running essentia. Cache hit populates Track fields without re-analysis. Cache miss triggers analysis then stores results. `--force` flag now also means "ignore cache".

## Impact

- **Code**: `cratekeeper/analysis/mood_analyzer.py` (`analyze_tracks`, `analyze_track`) — add hash computation, DB lookup/store logic
- **Code**: `cratekeeper/db/` or new module — repository functions for `track_analysis` table
- **Schema**: New `track_analysis` table in PostgreSQL (migration or auto-create on first use)
- **Dependencies**: None new (hashlib is stdlib, psycopg2 already used)
- **Performance**: First-run adds ~0.5s/file for hashing; subsequent runs skip entire analysis (~2-5s/file saved)
- **Breaking**: None — all existing behavior preserved, cache is additive
