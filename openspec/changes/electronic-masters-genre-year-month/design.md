## Context

Cratekeeper's master library builder currently uses a single hardcoded path structure: `Genre/Artist - Title.ext`. DJs who purchase electronic music over time want a chronological view (`Genre/YYYY/MM/`) that reflects when tracks entered their collection.

The change is cross-cutting: it requires capturing an `added_at` timestamp from two different sources (Spotify API and local filesystem), storing it in two different persistence layers (JSON plans and PostgreSQL), threading it through the import pipeline, and finally using it in the library builder.

Current in-force ADR:
- ADR-0001: Plan base class with type discriminator — unaffected, `added_at` is a new scalar field on `Track`.

## Goals / Non-Goals

**Goals:**
- Provide a `Genre/YYYY/MM/Artist - Title.ext` folder layout for profiles that opt into it.
- Capture the acquisition timestamp for Spotify-fetched tracks (`added_at` from playlist items).
- Capture the acquisition timestamp for local files (filesystem birthtime, falling back to mtime).
- Make the folder structure configurable per profile via `library_structure`.
- Ensure backward compatibility: default remains `genre_artist`.

**Non-Goals:**
- No manual purchase date entry UI.
- No retroactive backfill for existing plans without `added_at`.
- No support for additional custom folder structures beyond `genre_artist` and `genre_year_month`.
- No changes to event folder building (`build-event` remains flat).

## Decisions

### 1. Use `added_at` as the universal acquisition timestamp field
**Rationale:** One field on `Track` and `LocalTrack` keeps the model simple. For Spotify it means the playlist item's `added_at`; for local files it means filesystem birthtime/mtime.

**Alternative rejected:** A separate `purchase_date` field — would require a second source of truth and complicate the UI. `added_at` is already available from Spotify and is a reasonable proxy.

### 2. `library_structure` as a profile-level TOML config option
**Rationale:** The library builder is already profile-driven (target path, sort order, required fields). Adding `library_structure` there is consistent. The electronic profile defaults to `genre_year_month`; all others default to `genre_artist`.

**Alternative rejected:** A command-line flag on `build-library` — would require the DJ to remember it every time. Profile-level config is set-and-forget.

### 3. Fallback to `genre_artist` when `added_at` is missing
**Rationale:** Prevents build failures for legacy plans or tracks where the filesystem timestamp is unavailable. The track still gets copied, just into the flat `Genre/` folder.

**Alternative rejected:** Skip the track entirely — too aggressive; the DJ might still want the file in the library.

### 4. Use filesystem birthtime with mtime fallback for local files
**Rationale:** Birthtime is the closest proxy to "when this file first appeared on this machine". On macOS `st_birthtime` is reliable; on Linux it depends on filesystem (ext4 supports it, but not all tools populate it). mtime is a safe fallback.

**Alternative rejected:** Use `TDRC` (ID3 recording date) or custom tags — mutagen doesn't reliably expose purchase date, and users don't populate it.

## Risks / Trade-offs

- **[Risk]** Filesystem birthtime is unreliable on Linux or after file copies — `added_at` may reflect copy time, not purchase time. -> **Mitigation:** Document the limitation; DJ can accept the approximation or re-tag files.
- **[Risk]** Adding a column to PostgreSQL requires a migration for existing installations. -> **Mitigation:** The column is added via the schema-ensure code in `pg_repository.py` which already handles `ALTER TABLE ADD COLUMN IF NOT EXISTS` gracefully.
- **[Risk]** `library_structure` affects every track in a profile. A DJ switching from `genre_artist` to `genre_year_month` on an existing library will create duplicate files. -> **Mitigation:** Document this in the config template; re-building into a clean target directory is the recommended migration path.

## Migration Plan

1. Update code to support `added_at` and `library_structure`.
2. Re-scan local library to populate `added_at` in PostgreSQL.
3. Re-fetch any Spotify playlists to populate `added_at` in plan JSON.
4. For electronic masters: set `library_structure = "genre_year_month"` in config, then run `build-library` on a fresh target directory.

## Open Questions

- None. No in-force ADRs are contradicted by this design.

## Architecture Overview

```
+-----------------+        +------------------+
|   Spotify API   |        |   Local Files    |
|  (playlist items|        |  (filesystem)    |
|   with added_at)|        |  (birthtime/mtime) |
+--------+--------+        +--------+---------+
         |                          |
         v                          v
+--------+--------+        +--------+---------+
|  fetch_playlist |        |   scan_directory |
|   (client.py)   |        |   (scanner.py)   |
+--------+--------+        +--------+---------+
         |                          |
         v                          v
+--------+--------+        +--------+---------+
|   Track.added_at|        |  LocalTrack.added|
|   (plan JSON)   |        |   _at (PostgreSQL)|
+--------+--------+        +--------+---------+
         |                          |
         |    +------------------+  |
         +--->|  import_library  |<--+
              | (bulk_import.py) |
              +--------+---------+
                       |
                       v
              +--------+---------+
              |   Track.added_at |
              |   (plan JSON)    |
              +--------+---------+
                       |
                       v
              +--------+---------+
              |   build_library   |
              | (library_builder) |
              +--------+---------+
                       |
                       v
              +--------+---------+
              |  Profile config   |
              | library_structure  |
              +--------+---------+
                       |
                       v
              +--------+---------+
              |  Genre/YYYY/MM/   |
              |  Artist - Title   |
              +------------------+
```

**Data flow:**
- **Spotify path:** `added_at` is fetched from `playlist_items` API, stored in the plan JSON `Track` model, and later read by `build_library`.
- **Local path:** `added_at` is extracted from `os.stat()` during scan, stored in PostgreSQL via `LocalTrack`, transferred to the plan JSON `Track` during `import_library`, and later read by `build_library`.
- **Config path:** `library_structure` is parsed from TOML config into the `Profile` dataclass and passed to `build_library`.
- **Builder:** If `library_structure == "genre_year_month"` and `added_at` is present, the destination path includes `YYYY/MM/`. Otherwise, it falls back to the flat `Genre/` structure.
