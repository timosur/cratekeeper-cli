# Bulk Library Import

## Purpose

Imports scanned local audio files into a profile's library pipeline using their existing ID3 genre tags, bypassing Spotify entirely.

## Requirements

### Requirement: Import scanned local files into a profile using ID3 tags
The system SHALL provide a `crate import-library <source_path>` command that imports all scanned local audio files under `source_path` into the active profile by reading their existing ID3 genre tags, without contacting Spotify.

#### Scenario: Import a local source directory
- **GIVEN** local audio files under `source_path` have been scanned into the shared index and carry ID3 genre tags
- **WHEN** the DJ runs `crate import-library <source_path>`
- **THEN** the system creates a library-import plan containing those tracks, classified into the active profile's genre buckets from their ID3 genres

#### Scenario: Source not yet scanned
- **GIVEN** `source_path` has no entries in the shared scan index
- **WHEN** the DJ runs `crate import-library <source_path>`
- **THEN** the system reports that the path must be scanned first and exits non-zero

#### Scenario: File missing an ID3 genre tag
- **GIVEN** some files under `source_path` have no genre tag
- **WHEN** the DJ runs `crate import-library <source_path>`
- **THEN** those tracks are assigned the active profile's fallback bucket and the import continues without error

### Requirement: Imported plans use the active profile and its data directory
The system SHALL persist the generated library-import plan in the active profile's `data_dir` and classify tracks using the active profile's buckets, so a source can be imported separately per profile.

#### Scenario: Plan stored in the profile data directory
- **GIVEN** the active profile defines a `data_dir`
- **WHEN** the DJ runs `crate import-library <source_path>`
- **THEN** the resulting plan JSON is written under that profile's `data_dir`

#### Scenario: Same source imported under two profiles
- **GIVEN** the `commercial` and `electronic` profiles both exist
- **WHEN** the DJ runs `crate import-library <source_path> --profile commercial` and again with `--profile electronic`
- **THEN** each profile gets its own plan in its own `data_dir`, classified with that profile's buckets

### Requirement: Imported plans flow through the standard library pipeline
The system SHALL produce a `library-import` plan from `import-library` that is processable through the normal `classify`, `review-library`, and `build-library` steps.

#### Scenario: Continue with review and build
- **GIVEN** a plan produced by `crate import-library`
- **WHEN** the DJ runs `crate review-library` and then `crate build-library` against that plan
- **THEN** the review and build steps operate on the imported tracks identically to any other library-import plan
