# Local Library Scan

## Purpose

Indexes the DJ's local audio file library into a PostgreSQL database, extracting metadata for fast lookup during track matching.

## Requirements

### Requirement: Scan and index local audio files
The system SHALL recursively scan a directory of audio files, extract metadata (title, artist, album, ISRC, duration) via mutagen, and store normalized records in a PostgreSQL database.

#### Scenario: Scan a directory
- **WHEN** the DJ runs `crate scan` with a directory path
- **THEN** the system indexes all supported audio files (MP3, FLAC, M4A) with their metadata into the PostgreSQL database

#### Scenario: Normalized metadata storage
- **WHEN** audio files are indexed
- **THEN** artist names and titles are stored in a normalized form suitable for exact and fuzzy matching

#### Scenario: Re-scan idempotency
- **WHEN** the DJ re-runs `crate scan` on an already-indexed directory
- **THEN** existing records are updated and new files are added without creating duplicates

#### Scenario: Unsupported file format
- **WHEN** the scanner encounters a file that is not a supported audio format
- **THEN** the file is skipped silently and scanning continues
