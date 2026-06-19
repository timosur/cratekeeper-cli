## 1. Data model and storage foundation

- [x] 1.1 Add `added_at` field to `Track` dataclass in `cratekeeper/models.py`
- [x] 1.2 Add `added_at` field to `LocalTrack` dataclass in `cratekeeper/local/repository.py`
- [x] 1.3 Add `added_at` column to PostgreSQL schema in `cratekeeper/local/pg_repository.py` (with `ALTER TABLE ADD COLUMN IF NOT EXISTS`)
- [x] 1.4 Update `PostgresTrackRepository._row_to_track` and upsert methods to read/write `added_at`
- [x] 1.5 Update `LocalTrack.to_dict()` if it exists, or ensure `added_at` is passed through the dict serialization path

## 2. Config and profile changes

- [x] 2.1 Add `library_structure` field to `Profile` dataclass in `cratekeeper/config.py`
- [x] 2.2 Parse `library_structure` in `_build_profile` with validation (`"genre_artist"` or `"genre_year_month"`)
- [x] 2.3 Update `DEFAULT_CONFIG_TEMPLATE` so `electronic` profile sets `library_structure = "genre_year_month"`
- [x] 2.4 Update `implicit_commercial_profile` to default `library_structure` to `"genre_artist"`
- [x] 2.5 Update `Profile.describe()` to include `library_structure`

## 3. Spotify ingestion changes

- [x] 3.1 Update `fetch_playlist_tracks` in `cratekeeper/spotify/client.py` to include `added_at` in the `fields` API request
- [x] 3.2 Pass `added_at` from each playlist item into the `Track` constructor

## 4. Local scan and import changes

- [x] 4.1 Update `cratekeeper/local/scanner.py` `_extract_metadata` to read filesystem birthtime (or mtime fallback) and include it as `added_at`
- [x] 4.2 Update `cratekeeper/local/bulk_import.py` to extract `added_at` from `LocalTrack` and pass it to `Track` constructor
- [x] 4.3 Update `cratekeeper/local/bulk_import.py` to include `added_at` in the `rows` tuple unpacking

## 5. Library builder changes

- [x] 5.1 Add `library_structure` parameter to `build_library` in `cratekeeper/builder/library_builder.py`
- [x] 5.2 Implement `_build_dest_path` helper that computes `Genre/YYYY/MM/Artist - Title.ext` when `library_structure == "genre_year_month"` and `added_at` is present
- [x] 5.3 Ensure fallback to `Genre/Artist - Title.ext` when `added_at` is missing or `library_structure` is `"genre_artist"`
- [x] 5.4 Update `library_preflight` to report tracks that will use fallback due to missing `added_at`

## 6. CLI and wiring changes

- [x] 6.1 Update `build_library_cmd` in `cratekeeper/cli_builder.py` to pass `profile.library_structure` to `build_library`
- [x] 6.2 Update `_run_build_library` in `cratekeeper/wizard.py` to pass `profile.library_structure` to `build_library`
- [x] 6.3 Update `cratekeeper/wizard.py` review-library display to show `added_at` if available

## 7. Testing and validation

- [x] 7.1 Add tests in `tests/test_build_library.py` for `genre_year_month` layout with valid `added_at`
- [x] 7.2 Add tests in `tests/test_build_library.py` for fallback to `genre_artist` when `added_at` is missing
- [x] 7.3 Add tests in `tests/test_config.py` for `library_structure` parsing and validation
- [x] 7.4 Add tests in `tests/test_bulk_import.py` for `added_at` transfer from `LocalTrack` to `Track`
- [x] 7.5 Run the full test suite (`pytest`) to ensure no regressions
- [x] 7.6 Run `openspec validate electronic-masters-genre-year-month --type change --strict` before archive
