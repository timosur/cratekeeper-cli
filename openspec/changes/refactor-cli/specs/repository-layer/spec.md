## ADDED Requirements

### Requirement: TrackRepository protocol
Feature: TrackRepository protocol
Rule: All local track persistence operations go through a TrackRepository implementation; no domain code calls psycopg2 directly.

#### Scenario: Upsert a new track
- **GIVEN** a `TrackRepository` instance
- **AND** a `LocalTrack` with a file path not yet in the repository
- **WHEN** `upsert(track)` is called
- **THEN** the track is persisted and retrievable by path

#### Scenario: Upsert updates an existing track
- **GIVEN** a `TrackRepository` instance
- **AND** a `LocalTrack` already stored for a given file path
- **WHEN** `upsert(track)` is called with updated metadata for that path
- **THEN** the stored record reflects the updated metadata

#### Scenario: Find track by ISRC
- **GIVEN** a `TrackRepository` instance with a track that has a known ISRC
- **WHEN** `find_by_isrc(isrc)` is called with that ISRC
- **THEN** the matching `LocalTrack` is returned

#### Scenario: Find track by ISRC returns None when not found
- **GIVEN** a `TrackRepository` instance
- **WHEN** `find_by_isrc(isrc)` is called with an ISRC that does not exist
- **THEN** `None` is returned

#### Scenario: Find track by path
- **GIVEN** a `TrackRepository` instance with a track at a known path
- **WHEN** `find_by_path(path)` is called
- **THEN** the matching `LocalTrack` is returned

#### Scenario: List all tracks
- **GIVEN** a `TrackRepository` instance with N tracks stored
- **WHEN** `all()` is called
- **THEN** a list of all N `LocalTrack` objects is returned

### Requirement: PostgreSQL repository implementation
Rule: `PostgresTrackRepository` satisfies the `TrackRepository` protocol using psycopg2.

#### Scenario: PostgresTrackRepository connects via environment variable
- **GIVEN** `DATABASE_URL` is set in the environment
- **WHEN** `PostgresTrackRepository` is instantiated
- **THEN** it connects to the specified PostgreSQL database without error

#### Scenario: PostgresTrackRepository raises on missing connection string
- **GIVEN** `DATABASE_URL` is not set
- **WHEN** `PostgresTrackRepository` is instantiated
- **THEN** a clear `ConfigurationError` is raised identifying the missing variable

### Requirement: In-memory repository for testing
Rule: `InMemoryTrackRepository` satisfies the `TrackRepository` protocol using a dict; no database connection required.

#### Scenario: InMemoryTrackRepository persists and retrieves tracks without a database
- **GIVEN** an `InMemoryTrackRepository` instance
- **WHEN** a track is upserted and then retrieved by path
- **THEN** the stored track matches the upserted track
- **AND** no database connection was made

### Requirement: CLI injects repository into domain functions
Rule: `cli.py` constructs the repository and passes it to scanner and matcher functions; scanner and matcher do not instantiate repositories themselves.

#### Scenario: scan command uses PostgresTrackRepository by default
- **GIVEN** `DATABASE_URL` is set
- **WHEN** `crate scan <dir>` is run
- **THEN** the scanner receives a `PostgresTrackRepository` instance
- **AND** scanned tracks are persisted through that instance

#### Scenario: match command uses the injected repository
- **GIVEN** a populated repository and a loaded plan
- **WHEN** `crate match <plan>` is run
- **THEN** the matcher queries the injected repository for ISRC and path lookups
