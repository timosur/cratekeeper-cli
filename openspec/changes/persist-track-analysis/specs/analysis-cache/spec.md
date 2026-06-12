## ADDED Requirements

### Requirement: Persist audio analysis results in database
The system SHALL store raw audio analysis results in PostgreSQL keyed by the SHA256 content hash of the audio file, enabling cross-plan reuse without re-analysis.

#### Scenario: Cache store on first analysis
- **GIVEN** an audio file has not been analyzed before
- **WHEN** audio analysis completes for that file
- **THEN** the system computes the SHA256 hash of the file content
- **AND** stores all raw analysis fields (BPM, key, energy, danceability, loudness, mood scores, arousal, valence, voice/instrumental, ML danceability) in the database keyed by that hash

#### Scenario: Cache hit on subsequent analysis
- **GIVEN** an audio file has been analyzed before and its content hash exists in the database
- **WHEN** the system is asked to analyze that file
- **THEN** the system retrieves the stored analysis results from the database
- **AND** populates the track fields without running essentia or TensorFlow models

#### Scenario: Same content at different paths shares cache
- **GIVEN** two files at different paths contain identical audio bytes
- **WHEN** both files are analyzed
- **THEN** only the first file triggers essentia analysis
- **AND** the second file retrieves results from the cache via matching content hash

#### Scenario: Force flag bypasses cache
- **GIVEN** a file's analysis results exist in the cache
- **WHEN** the DJ runs analysis with the `--force` flag
- **THEN** the system re-runs essentia analysis regardless of cache state
- **AND** overwrites the stored results with fresh values

#### Scenario: Modified file gets re-analyzed
- **GIVEN** a file was previously analyzed and cached
- **WHEN** the file content changes (re-encoded, trimmed, different bytes)
- **THEN** the new content produces a different SHA256 hash
- **AND** the system treats it as a cache miss and runs fresh analysis

### Requirement: Graceful fallback when database unavailable
The system SHALL continue analysis without caching if the PostgreSQL database is unreachable.

#### Scenario: Database connection failure
- **GIVEN** PostgreSQL is not running or unreachable
- **WHEN** the system attempts to check the analysis cache
- **THEN** the system logs a warning about cache unavailability
- **AND** proceeds with full essentia analysis without storing results
- **BUT** does not raise an error or halt the pipeline

### Requirement: Analysis cache schema auto-creation
The system SHALL create the analysis cache table automatically on first use.

#### Scenario: Table does not exist
- **GIVEN** the `track_analysis` table does not exist in the database
- **WHEN** the analysis cache repository is initialized
- **THEN** the system creates the table with appropriate columns and indexes
- **AND** subsequent operations use the table normally

#### Scenario: Schema evolution adds new columns
- **GIVEN** a new analysis field is added in a future version
- **WHEN** the analysis cache repository is initialized
- **THEN** the system adds any missing columns to the existing table
- **AND** existing rows retain their values with NULL for new columns
