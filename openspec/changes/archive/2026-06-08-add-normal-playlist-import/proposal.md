## Why

The CLI currently treats every Spotify playlist as an event wishlist. The `EventPlan` data model is hard-wired to event concepts (event name, event date, per-bucket Spotify sub-playlists). There is no way to ingest a personal curated playlist into the master library without pretending it is an event. DJs regularly discover and curate tracks outside of event prep — those tracks should go through the same quality pipeline (classify, match, analyze, tag, review) and land in the master library without event ceremony.

## What Changes

- **BREAKING**: Generalize `EventPlan` into a `Plan` base class. `EventPlan` and `LibraryImportPlan` become subclasses sharing `source_playlist_id`, `source_playlist_name`, and `tracks`, while event-specific fields (`event_name`, `event_date`, `created_playlists`, `tidal_playlists`) live only on `EventPlan`.
- `crate fetch` gains an interactive prompt asking whether the playlist is for an event or a library import. The answer determines which `Plan` subclass is created.
- All pipeline commands (`enrich`, `classify`, `review`, `match`, `analyze-mood`, `apply-tags`, `tag`, `review-library`, `build-library`, `build-masters`) work on both plan types.
- Event-only commands (`build-event`, `create-playlists`) error with a clear message when given a `LibraryImportPlan`.
- `build-masters` includes library-import tracks alongside event tracks when accumulating per-genre Spotify master playlists.
- Existing JSON plan files remain loadable (backward-compatible deserialization).

## Capabilities

### New Capabilities
- `library-import`: Ingesting a personal curated Spotify playlist through the full pipeline (minus event steps) into the master library. Covers the new `LibraryImportPlan` type, the interactive plan-type selection during fetch, and the guard rails on event-only commands.

### Modified Capabilities
- `playlist-ingestion`: `crate fetch` now asks whether the playlist is for an event or library import and creates the corresponding plan type. `crate enrich` works on both.
- `library-build`: `crate build-library` and `crate build-masters` accept both plan types.
- `playlist-management`: `crate create-playlists` rejects `LibraryImportPlan` with a clear error. `crate build-masters` accepts both.

## Impact

- **`models.py`**: Refactor `EventPlan` into `Plan` base + `EventPlan` + `LibraryImportPlan`. Requires careful JSON serialization (plan type discriminator field) and backward-compatible loading of existing plans.
- **`cli.py`**: All commands that accept a plan file need to use `Plan.load()` instead of `EventPlan.load()`. `fetch` gains interactive plan-type prompt. Event-only commands add type guard.
- **`spotify_client.py`**: No changes — playlist fetching is plan-type agnostic.
- **`library_builder.py`**: No logic changes — already operates on tracks, not event metadata.
- **`event_builder.py`**: Add type guard rejecting `LibraryImportPlan`.
- **Existing JSON files**: Need a migration path or auto-detection (missing `plan_type` field → assume `event`).
- **`prepare-event` skill**: No changes — it orchestrates the event path which continues to work.
- **Tests**: All existing tests that create `EventPlan` directly need updating to use the new class hierarchy.
