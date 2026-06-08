## ADDED Requirements

### Requirement: Generalize plan data model with type discriminator
The system SHALL support two plan types — `event` and `library-import` — distinguished by a `plan_type` field in the persisted JSON. All pipeline commands SHALL accept either plan type via a common `Plan.load()` entry point.

#### Scenario: Save a library-import plan with type discriminator
- **GIVEN** a library-import plan has been created via `crate fetch`
- **WHEN** the plan is saved to JSON
- **THEN** the JSON includes `"plan_type": "library-import"`

#### Scenario: Load a library-import plan
- **GIVEN** a JSON file contains `"plan_type": "library-import"`
- **WHEN** the system loads the plan via `Plan.load()`
- **THEN** the returned object is a `LibraryImportPlan` instance

#### Scenario: Load a legacy plan without plan_type field
- **GIVEN** a JSON file was created before the plan-type feature and has no `plan_type` field
- **WHEN** the system loads the plan via `Plan.load()`
- **THEN** the returned object is an `EventPlan` instance (backward compatible default)

### Requirement: Interactive plan-type selection during fetch
The system SHALL ask the DJ whether a fetched playlist is for an event or a library import when running `crate fetch` interactively.

#### Scenario: DJ selects library import
- **GIVEN** the DJ runs `crate fetch` with a valid Spotify playlist URL
- **AND** stdin is an interactive terminal
- **WHEN** the DJ selects "library import" at the prompt
- **THEN** the system creates a `LibraryImportPlan` and saves it to `data/<playlist-name>.json`

#### Scenario: DJ selects event
- **GIVEN** the DJ runs `crate fetch` with a valid Spotify playlist URL
- **AND** stdin is an interactive terminal
- **WHEN** the DJ selects "event" at the prompt
- **THEN** the system creates an `EventPlan` and saves it as before

#### Scenario: Non-interactive stdin defaults to event
- **GIVEN** the DJ runs `crate fetch` with a valid Spotify playlist URL
- **AND** stdin is not an interactive terminal
- **WHEN** the fetch completes
- **THEN** the system creates an `EventPlan` (no prompt shown)

### Requirement: Event-only commands reject library-import plans
Event-specific commands SHALL refuse to operate on library-import plans with a clear error message.

#### Scenario: build-event rejects library-import plan
- **GIVEN** a plan file with `plan_type` of `library-import`
- **WHEN** the DJ runs `crate build-event` with that plan file
- **THEN** the system prints an error: "build-event is not applicable to library imports. Use build-library instead."
- **AND** exits with a non-zero exit code

#### Scenario: create-playlists rejects library-import plan
- **GIVEN** a plan file with `plan_type` of `library-import`
- **WHEN** the DJ runs `crate create-playlists` with that plan file
- **THEN** the system prints an error: "create-playlists is not applicable to library imports."
- **AND** exits with a non-zero exit code

#### Scenario: sync-to-tidal rejects library-import plan
- **GIVEN** a plan file with `plan_type` of `library-import`
- **WHEN** the DJ runs `crate sync-to-tidal` with that plan file
- **THEN** the system prints an error: "sync-to-tidal is not applicable to library imports."
- **AND** exits with a non-zero exit code

### Requirement: Library-import plans go through the full processing pipeline
A library-import plan SHALL be processable through all pipeline commands: enrich, classify, review, match, analyze-mood, apply-tags, tag, review-library, build-library, and build-masters.

#### Scenario: Enrich a library-import plan
- **GIVEN** a library-import plan with tracks missing genre data
- **WHEN** the DJ runs `crate enrich` on the plan
- **THEN** the system enriches tracks via MusicBrainz identically to event plans

#### Scenario: Classify a library-import plan
- **GIVEN** a library-import plan with enriched tracks
- **WHEN** the DJ runs `crate classify` on the plan
- **THEN** tracks are assigned genre buckets identically to event plans

#### Scenario: Review library candidates from a library-import plan
- **GIVEN** a library-import plan with matched and tagged tracks
- **WHEN** the DJ runs `crate review-library` on the plan
- **THEN** the interactive review works identically to event plans

#### Scenario: Build library from a library-import plan
- **GIVEN** a library-import plan with approved and fully-tagged tracks
- **WHEN** the DJ runs `crate build-library` on the plan
- **THEN** approved tracks are copied to the master library identically to event plans
