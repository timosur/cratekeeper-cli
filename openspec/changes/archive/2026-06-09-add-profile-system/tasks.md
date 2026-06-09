## 1. Config foundation (config.py + presets)

- [x] 1.1 Add `cratekeeper/config.py` with immutable `Profile` and `Settings` dataclasses covering: `buckets` (preset name or inline list), `dj_software` (`djay_pro`|`rekordbox`), `library_target`, `data_dir`, `required_fields`, `sort` (keys + direction), and `tag_format` (`structured_comment`|`id3_only`).
- [x] 1.2 Implement `load_settings()` reading `~/.cratekeeper/config.toml` via stdlib `tomllib`, with validation (unknown preset, bad enum, missing/invalid paths) that raises a clear error.
- [x] 1.3 Implement `resolve_profile(name | None) -> Profile` with precedence: `--profile` flag → config `active_profile` → first defined profile → implicit built-in `commercial` profile when no config file exists.
- [x] 1.4 Define the implicit `commercial` profile so a missing config reproduces the historical hardcoded defaults (commercial buckets, `~/Music/Library` target, `structured_comment`, required fields `energy/function/crowd/mood_tags`, shared `data/` equivalent).
- [x] 1.5 Refactor `genre_buckets.py`: move `DEFAULT_BUCKETS` into a `PRESETS` registry under key `"commercial"` (each preset carries ordered buckets + its own fallback), and update `get_buckets()` to resolve buckets for a given profile.

## 2. Wire active profile through the CLI

- [x] 2.1 Add an `@app.callback()` in `cli.py` that adds a global `--profile` option, resolves the active `Profile`, and stores it on the Typer `Context` (`ctx.obj`).
- [x] 2.2 Replace the module-level `DATA_DIR` constant with per-invocation resolution of the active profile's `data_dir` for all plan load/save paths (`fetch` default output and any command that writes plan JSON).
- [x] 2.3 Update every pipeline command to read `ctx.obj.profile` and pass profile-derived values (buckets, target, required fields, sort, tag format, dj_software) instead of hardcoded constants.

## 3. Genre classification (profile buckets + electronic preset)

- [x] 3.1 Thread the active profile's resolved buckets into `classifier.classify_tracks`/`classify_track` (use the existing optional `buckets=` params) from the `classify` command.
- [x] 3.2 Add the `electronic` preset to `PRESETS`: finer EDM sub-genre buckets, `House` fallback, and no Schlager/Pop/Rock/Latin buckets.
- [x] 3.3 Verify fallback selection uses the active profile's preset fallback (Pop for commercial, House for electronic).

## 4. Per-profile tag format

- [x] 4.1 Consolidate the scattered structured-tag vocab (`VALID_ENERGY/FUNCTION/CROWD/MOOD` from `cli.py`), the comment builder (`tag_writer._build_comment`), and the embedded-comment marker (`event_builder`) into one tag-format module/source of truth.
- [x] 4.2 Add a `tag_format` parameter to `tag_writer.tag_track`/`tag_tracks`: `structured_comment` writes ID3 fields + comment (current behavior); `id3_only` writes only genre/BPM/key and no comment. Preserve MP3/FLAC/M4A/MP4 handling.
- [x] 4.3 Pass the active profile's `tag_format` from the `tag` command.

## 5. Admission criteria & sorting

- [x] 5.1 Generalize `library_builder.is_fully_tagged` to check a profile-supplied `required_fields` list (default commercial set); reuse the same helper from `event_builder` and `review_library`.
- [x] 5.2 Make `build_library` write under the active profile's `library_target` and order tracks within each bucket per the profile's `sort` config (default = current insertion order).
- [x] 5.3 Update `event_builder` so the tag-completeness gate uses profile `required_fields` and the embedded-comment gate is skipped for `id3_only` profiles.
- [x] 5.4 Ensure `build-library` does not auto-emit Rekordbox XML for `rekordbox` profiles (XML is a separate command).

## 6. Profile management subcommands

- [x] 6.1 Add a `crate profile` Typer sub-app with `list` (show profiles, mark active), `show <name>` (print fully resolved settings incl. preset-expanded buckets), `use <name>` (write `active_profile` to config), and `init` (scaffold config with `commercial` + `electronic` examples, refuse to overwrite existing).

## 7. Bulk library import

- [x] 7.1 Add `cratekeeper/bulk_import.py` that selects scanned local files under a source path from the shared PostgreSQL index and builds `Track`s from their ID3 metadata (no Spotify).
- [x] 7.2 Add `crate import-library <source_path>` that classifies imported tracks into the active profile's buckets (fallback bucket when genre missing), writes a `LibraryImportPlan` (per ADR-0001) into the profile's `data_dir`, and errors clearly if the source is unscanned.
- [x] 7.3 Verify the imported plan flows through `classify` → `review-library` → `build-library` like any other library-import plan.

## 8. Rekordbox export

- [x] 8.1 Add `cratekeeper/rekordbox_export.py` that walks the active profile's built library, reads BPM/key/genre from tags (mutagen), and emits a `rekordbox.xml` with a `<COLLECTION>` (URL-encoded `file://` locations, BPM/key/genre attributes) and `<PLAYLISTS>` nodes mirroring the genre buckets, ordered by the profile's sort.
- [x] 8.2 Add `crate export-rekordbox` with a `--buckets` filter (default all) and a non-zero exit + clear message when the library is empty.

## 9. Tests, docs & validation

- [x] 9.1 Add parity tests proving that with no config file, classification, tagging, library-build, and event-folder behavior is identical to pre-profile output (commercial defaults).
- [x] 9.2 Add tests for config loading/validation, profile resolution precedence + `--profile` override, the `electronic` preset, `id3_only` tag format, profile `required_fields` admission, and profile sorting.
- [x] 9.3 Add focused tests for `import-library` (ID3 classification, profile `data_dir`, unscanned-source error) and `export-rekordbox` (location encoding, key/BPM/genre attributes, bucket filter, empty-library exit).
- [x] 9.4 Update README with the profile/config system, `crate profile` commands, `import-library`, `export-rekordbox`, and the breaking note that existing `data/` plans are not auto-migrated.
- [x] 9.5 Run `openspec validate add-profile-system --type change --strict` and ensure it passes before archive.
