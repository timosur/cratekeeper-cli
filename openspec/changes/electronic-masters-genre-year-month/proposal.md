## Why

The electronic profile's master library currently stores tracks in a flat `Genre/Artist - Title.ext` structure. For DJs who purchase electronic music over time, a chronological organization by acquisition date is more useful for browsing and set preparation. Grouping by `Genre/Year/Month` makes it easy to find recently purchased tracks and track crate growth over time.

## What Changes

- Add `added_at` field to the `Track` model to store the ISO-8601 timestamp when a track was acquired.
- Capture `added_at` from Spotify playlist items during `crate fetch` (this timestamp is the closest available proxy for when the track entered the DJ's collection).
- Capture `added_at` from local file filesystem birthtime (or modification time as fallback) during `crate scan` and store it in the PostgreSQL repository alongside the `LocalTrack`.
- When local tracks are imported into a plan via `crate import-library`, transfer their `added_at` into the `Track` model.
- Add `library_structure` config option to profile definitions. Supported values:
  - `genre_artist` (default): current behaviour — `Genre/Artist - Title.ext`
  - `genre_year_month`: new behaviour — `Genre/YYYY/MM/Artist - Title.ext`
- Update `build_library` to read the active profile's `library_structure` and lay out files accordingly.
- Update the default config template so the `electronic` profile uses `library_structure = "genre_year_month"`.
- Update `crate build-library` CLI and wizard to pass `library_structure` through to the builder.
- Tracks without a usable `added_at` fall back to the `genre_artist` structure regardless of profile setting.

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `playlist-ingestion`: Spotify fetch now persists `added_at` on each track in the plan JSON.
- `local-library-scan`: File scan extracts filesystem birthtime (or mtime fallback) as `added_at` and stores it in the PostgreSQL repository.
- `bulk-library-import`: Imported local tracks transfer `added_at` into the plan's `Track` model.
- `config-loading`: Profile definitions support an optional `library_structure` field with `"genre_artist"` or `"genre_year_month"`.
- `library-build`: The build step respects the active profile's `library_structure` and writes tracks into `Genre/YYYY/MM/Artist - Title.ext` when `genre_year_month` is selected.

## Impact

- `cratekeeper/models.py` — new `added_at` field on `Track` and `LocalTrack`.
- `cratekeeper/spotify/client.py` — include `added_at` in playlist API fields and pass it to `Track`.
- `cratekeeper/local/scanner.py` — extract filesystem birthtime (or mtime fallback) and include it in metadata.
- `cratekeeper/local/repository.py` — add `added_at` to `LocalTrack`.
- `cratekeeper/local/pg_repository.py` — add `added_at` column to PostgreSQL schema, read/write it.
- `cratekeeper/local/bulk_import.py` — transfer `added_at` from `LocalTrack` to `Track` during import.
- `cratekeeper/config.py` — parse `library_structure`, add to `Profile` dataclass, update default template.
- `cratekeeper/builder/library_builder.py` — accept `library_structure` parameter and compute destination path.
- `cratekeeper/cli_builder.py` — pass `profile.library_structure` to `build_library`.
- `cratekeeper/wizard.py` — pass `profile.library_structure` to `build_library`.
- `tests/test_build_library.py` — add tests for `genre_year_month` layout.
- `openspec/specs/library-build/spec.md` — delta update to reflect the new path structure.
- `openspec/specs/config-loading/spec.md` — delta update to document `library_structure`.
- `openspec/specs/playlist-ingestion/spec.md` — delta update to document `added_at` capture.
- `openspec/specs/local-library-scan/spec.md` — delta update to document `added_at` extraction from filesystem.
