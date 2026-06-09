## 1. Flatten Repo Layout

- [ ] 1.1 Move `pyproject.toml`, `cratekeeper/`, `tests/`, and `Dockerfile` from `cratekeeper-cli/cratekeeper-cli/` up to repo root
- [ ] 1.2 Remove now-empty inner `cratekeeper-cli/` directory
- [ ] 1.3 Update `pyproject.toml` package paths if any referenced the old nested location
- [ ] 1.4 Update `Dockerfile` `COPY` paths to reflect new layout
- [ ] 1.5 Update `release.sh` paths if referencing the old layout
- [ ] 1.6 Verify `pip install -e .` succeeds from repo root and `crate --help` runs

## 2. Create Domain Sub-package Structure

- [ ] 2.1 Create `cratekeeper/spotify/__init__.py` and move `spotify_client.py` → `cratekeeper/spotify/client.py`
- [ ] 2.2 Move `tidal_client.py` → `cratekeeper/spotify/tidal.py`
- [ ] 2.3 Move `musicbrainz_client.py` → `cratekeeper/spotify/musicbrainz.py`
- [ ] 2.4 Create `cratekeeper/local/__init__.py` and move `local_scanner.py` → `cratekeeper/local/scanner.py`
- [ ] 2.5 Move `matcher.py` → `cratekeeper/local/matcher.py`
- [ ] 2.6 Move `bulk_import.py` → `cratekeeper/local/bulk_import.py`
- [ ] 2.7 Create `cratekeeper/pipeline/__init__.py` and move `classifier.py` → `cratekeeper/pipeline/classifier.py`
- [ ] 2.8 Move `tag_writer.py` → `cratekeeper/pipeline/tag_writer.py`
- [ ] 2.9 Move `sorting.py` → `cratekeeper/pipeline/sorting.py`
- [ ] 2.10 Create `cratekeeper/builder/__init__.py` and move `event_builder.py`, `library_builder.py`, `review_library.py` → `cratekeeper/builder/`
- [ ] 2.11 Create `cratekeeper/analysis/__init__.py` and move `mood_analyzer.py` → `cratekeeper/analysis/mood_analyzer.py`
- [ ] 2.12 Create `cratekeeper/export/__init__.py` and move `rekordbox_export.py` → `cratekeeper/export/rekordbox.py`
- [ ] 2.13 Update all import statements in `cli.py`, `wizard.py`, and cross-module imports to use new paths
- [ ] 2.14 Update all test imports in `tests/` to use new module paths
- [ ] 2.15 Run full test suite; confirm all 9 test files pass

## 3. TrackRepository Protocol and PostgreSQL Implementation

- [ ] 3.1 Create `cratekeeper/local/repository.py` with `TrackRepository` protocol defining `upsert`, `find_by_isrc`, `find_by_path`, `all`
- [ ] 3.2 Add `InMemoryTrackRepository` (dict-backed) in `repository.py`
- [ ] 3.3 Create `cratekeeper/local/pg_repository.py` with `PostgresTrackRepository` implementing the protocol via psycopg2
- [ ] 3.4 `PostgresTrackRepository.__init__` reads `DATABASE_URL` from env; raises `ConfigurationError` if missing
- [ ] 3.5 Refactor `cratekeeper/local/scanner.py` to accept a `TrackRepository` argument instead of creating a DB connection internally
- [ ] 3.6 Refactor `cratekeeper/local/matcher.py` to accept a `TrackRepository` argument
- [ ] 3.7 Update `cli.py` `scan` command to construct `PostgresTrackRepository` and inject it into `scanner`
- [ ] 3.8 Update `cli.py` `match` command to construct `PostgresTrackRepository` and inject it into `matcher`
- [ ] 3.9 Replace any existing DB-mocking test fixtures with `InMemoryTrackRepository` injection
- [ ] 3.10 Run test suite; confirm scanner and matcher tests pass without a live database

## 4. Config-as-Code → YAML Data Files

- [ ] 4.1 Create `cratekeeper/data/` directory with `__init__.py`
- [ ] 4.2 Extract genre bucket data from `genre_buckets.py` into `cratekeeper/data/genre_buckets.yaml`
- [ ] 4.3 Extract mood config data from `mood_config.py` into `cratekeeper/data/mood_config.yaml`
- [ ] 4.4 Add a loader in `cratekeeper/data/__init__.py` using `importlib.resources.files("cratekeeper.data")` with `functools.lru_cache`
- [ ] 4.5 Add `pyyaml` to `pyproject.toml` runtime dependencies
- [ ] 4.6 Add `cratekeeper/data/*.yaml` to `pyproject.toml` package data includes (Hatchling `include` or `tool.hatch.build.targets.wheel`)
- [ ] 4.7 Update `cratekeeper/pipeline/classifier.py` to load genre buckets via the new data loader
- [ ] 4.8 Update `cratekeeper/analysis/mood_analyzer.py` to load mood config via the new data loader
- [ ] 4.9 Delete `genre_buckets.py` and `mood_config.py`
- [ ] 4.10 Verify `python -c "from cratekeeper.data import load_genre_buckets; print(load_genre_buckets())"` succeeds

## 5. Thin CLI Handlers

- [ ] 5.1 Extract inline logic from `cli.py` `fetch` command into `cratekeeper/spotify/client.py` (genre enrichment loop, plan-type selection)
- [ ] 5.2 Extract inline logic from `cli.py` `tag-untagged` command into `cratekeeper/pipeline/tag_writer.py` (file matching, Unicode normalization, mutagen writes)
- [ ] 5.3 Extract inline logic from `cli.py` `apply-tags` command into an appropriate domain module (validation logic)
- [ ] 5.4 Extract any remaining business logic from `cli.py` command handlers (>20 lines of non-orchestration code) into their domain modules
- [ ] 5.5 Confirm each CLI handler body is: load plan → call domain function → save plan → output to console
- [ ] 5.6 Standardise `is_fully_tagged` — make it public in `cratekeeper/pipeline/tag_writer.py`; update all callers in `event_builder.py`, `library_builder.py`, and `cli.py` to import from the canonical location
- [ ] 5.7 Run `crate --help` and spot-check 5 commands to confirm all names and flags are unchanged

## 6. Wizard Delegation

- [ ] 6.1 Refactor `wizard.py` to call each pipeline step via `ctx.invoke(command_fn, ...)` using the Typer context
- [ ] 6.2 Remove duplicated display logic and pipeline step implementations from `wizard.py`
- [ ] 6.3 Verify `crate wizard` runs end-to-end using the CLI runner and produces the same output as direct command invocations

## 7. Final Verification

- [ ] 7.1 Run full test suite (`pytest`) and confirm all tests pass
- [ ] 7.2 Run `openspec validate refactor-cli --type change --strict`
- [ ] 7.3 Install package from repo root (`pip install -e .`) and run `crate --help` confirming all 20 commands are present
- [ ] 7.4 Confirm no source file imports from the old flat paths (e.g., `from cratekeeper.spotify_client import ...`)
