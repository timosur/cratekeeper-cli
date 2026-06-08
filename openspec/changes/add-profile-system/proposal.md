## Why

The CLI currently has one hardcoded pipeline configuration: one set of genre buckets, one library target, one tag format, one output mode (djay Pro flat folders). A DJ who plays both commercial gigs and electronic sets needs two separate libraries with different classification rules, different folder structures, different target DJ software (djay Pro vs Rekordbox), and different tagging strategies. There is no way to do this today without manually editing code between runs.

## What Changes

- **New config system**: TOML config file (`~/.cratekeeper/config.toml`) with named profiles. Each profile defines genre buckets, DJ software target, library output path, admission criteria, sorting rules, and tag format.
- **Profile switching**: Config sets an `active_profile`. New `crate profile` subcommand group (`list`, `show`, `use`) to manage profiles. Optional `--profile` global flag overrides the active profile per invocation.
- **Genre bucket presets**: Current `DEFAULT_BUCKETS` becomes the `"commercial"` preset. New `"electronic"` preset with finer electronic sub-genre granularity, no commercial genres (Schlager, Pop, Rock, Latin), fallback to House instead of Pop. Profiles reference a preset or define custom buckets inline.
- **Rekordbox XML export**: New `crate export-rekordbox` command generates a `rekordbox.xml` for selected genre buckets from the library. Tracks include file location, BPM, key, and genre metadata. Playlist nodes mirror the genre bucket structure.
- **Per-profile tag format**: Commercial profile writes structured comment tags (`era:...; energy:...; function:...; crowd:...; mood:...`). Electronic/Rekordbox profile writes only standard ID3 fields (genre, BPM, key) -- no comment tags, relying on Rekordbox's own metadata system.
- **Per-profile admission criteria**: Configurable which fields must be populated before a track enters the library (e.g., electronic profile may skip function/crowd requirements).
- **Per-profile sorting**: Configurable sort keys (BPM, energy, danceability, etc.) and direction for track ordering within genre buckets. Affects library build order and Rekordbox playlist order.
- **Bulk library import**: New `crate import-library` command imports all scanned local files into the active profile. Uses ID3 genre tags for classification (no Spotify). Goes through classify → optional review → build-library. Run per-profile with a source path each time.
- **Per-profile data isolation**: Each profile stores plan JSON files in its own `data_dir`. Scan database (PostgreSQL) remains shared.
- **Backward compatibility**: If no config file exists, CLI behaves exactly as today (implicit commercial profile with current defaults). **BREAKING**: Existing `data/` plans are not auto-migrated to a profile's data_dir; users must move them manually or re-import.

## Capabilities

### New Capabilities
- `profile-config`: TOML-based config system with named profiles. Config loading, validation, active profile resolution, `--profile` override, and `crate profile` subcommands (`list`, `show`, `use`, `init`).
- `rekordbox-export`: Generate Rekordbox-compatible XML from selected genre buckets in the built library. Includes collection entries and playlist structure.
- `bulk-library-import`: Import all scanned local audio files into a profile's library pipeline using ID3 tag metadata for classification instead of Spotify.

### Modified Capabilities
- `genre-classification`: Genre buckets become profile-configurable via presets or custom definitions. Classifier reads buckets from active profile config instead of hardcoded `DEFAULT_BUCKETS`. New `"electronic"` preset.
- `library-build`: Output path, folder structure, and track sorting within buckets driven by active profile. Rekordbox profiles no longer auto-generate XML (separate command).
- `tagging`: Tag format is profile-dependent. Commercial profiles write structured comment tags. Electronic/Rekordbox profiles write only standard ID3 fields (genre, BPM, key).
- `library-review`: Admission criteria (which fields must be non-empty) configurable per profile.
- `event-folders`: Event folder output respects active profile's DJ software setting and tag format.
- `playlist-ingestion`: Plan files stored in profile-specific `data_dir` instead of shared `data/`.

## Impact

- **New files**: `cratekeeper/config.py` (config loading/validation), `cratekeeper/rekordbox_export.py` (XML generation), `cratekeeper/bulk_import.py` (library import logic)
- **Modified files**: `cli.py` (profile flag, new commands), `genre_buckets.py` (presets instead of single list), `classifier.py` (reads profile buckets), `library_builder.py` (profile output path + sorting), `tag_writer.py` (profile tag format), `library_review.py` (profile admission criteria), `event_builder.py` (profile DJ software mode), `models.py` (possible Plan updates for profile association)
- **New dependency**: `tomli` (TOML parsing, stdlib in 3.11+ as `tomllib`) -- no new external deps needed
- **Config file**: `~/.cratekeeper/config.toml` -- new file, user-managed
- **Database**: No schema changes. PostgreSQL scan index remains shared across profiles.
- **Breaking**: Plans in `data/` not auto-migrated. Users moving to profiles must relocate existing plan files.
