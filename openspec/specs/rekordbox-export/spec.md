# Rekordbox Export

## Purpose

Generates Rekordbox-compatible XML from a built master library, allowing the DJ to import their curated collection into Rekordbox with genre-based playlist nodes.

## Requirements

### Requirement: Generate Rekordbox XML from built library buckets
The system SHALL provide a `crate export-rekordbox` command that reads the active profile's built master library and produces a `rekordbox.xml` containing a collection of track entries and playlist nodes mirroring the selected genre buckets.

#### Scenario: Export the full library
- **GIVEN** the active profile's library target directory contains genre-bucket subfolders of tagged audio files
- **WHEN** the DJ runs `crate export-rekordbox`
- **THEN** the system writes a `rekordbox.xml` whose collection lists every library track with its file location, BPM, key, and genre, and whose playlist nodes mirror the genre buckets

#### Scenario: Export selected buckets only
- **GIVEN** a built library with multiple genre buckets
- **WHEN** the DJ runs `crate export-rekordbox --buckets House,Techno`
- **THEN** the generated XML contains only tracks from the `House` and `Techno` buckets and only playlist nodes for those buckets

#### Scenario: Empty library
- **GIVEN** the active profile's library target directory contains no eligible audio files
- **WHEN** the DJ runs `crate export-rekordbox`
- **THEN** the system reports that there is nothing to export and exits non-zero without writing an XML file

### Requirement: Rekordbox-compatible track locations and metadata
The system SHALL encode each track's file location and metadata in the format Rekordbox expects when importing an XML collection.

#### Scenario: Track entry encoding
- **GIVEN** a library track at an absolute file path with known BPM, key, and genre
- **WHEN** the track is written into the Rekordbox XML collection
- **THEN** its location is a URL-encoded `file://` path and its BPM, key, and genre are written into the corresponding Rekordbox track attributes

#### Scenario: Playlist node ordering follows profile sort
- **GIVEN** the active profile defines a sort rule over BPM descending
- **WHEN** the system builds a bucket's playlist node
- **THEN** the playlist entries are ordered by BPM descending, matching the profile's sort configuration

### Requirement: Rekordbox profiles do not auto-generate XML during build
The system SHALL NOT generate Rekordbox XML automatically during `crate build-library`; XML generation SHALL occur only when `crate export-rekordbox` is run.

#### Scenario: Build does not emit XML
- **GIVEN** the active profile targets Rekordbox
- **WHEN** the DJ runs `crate build-library`
- **THEN** the system copies tracks into the library but does not write a `rekordbox.xml`

#### Scenario: Regenerate XML without rebuilding
- **GIVEN** a library was already built
- **WHEN** the DJ runs `crate export-rekordbox` again after adding more tracks
- **THEN** the system regenerates the XML from the current library contents without re-copying audio files
