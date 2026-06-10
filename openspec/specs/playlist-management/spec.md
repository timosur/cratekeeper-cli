# Playlist Management

## Purpose

Creates and syncs streaming playlists from classified plans: Spotify sub-playlists per genre bucket (event-only), cross-event/cross-import DJ master playlists, and Tidal playlist sync via ISRC (event-only).

## Requirements

### Requirement: Create Spotify sub-playlists per genre bucket
The system SHALL create one Spotify playlist per genre bucket from the classified plan, containing the tracks assigned to that bucket. This command is event-only and SHALL reject library-import plans.

#### Scenario: Create genre playlists from event plan
- **GIVEN** a classified event plan
- **WHEN** the DJ runs `crate create-playlists`
- **THEN** the system creates (or updates) a Spotify playlist for each non-empty genre bucket, named with the event and bucket name

#### Scenario: Reject library-import plan
- **GIVEN** a classified library-import plan
- **WHEN** the DJ runs `crate create-playlists`
- **THEN** the system prints an error indicating this command is not applicable to library imports
- **AND** exits with a non-zero exit code

### Requirement: Build cross-event master playlists
The system SHALL maintain persistent `[DJ] Genre` master playlists on Spotify that accumulate tracks across multiple plans, including both event and library-import plans.

#### Scenario: Add event plan tracks to master playlists
- **GIVEN** a classified event plan
- **WHEN** the DJ runs `crate build-masters`
- **THEN** the system adds each track to the corresponding `[DJ] <Genre>` master playlist, creating the playlist if it does not exist

#### Scenario: Add library-import plan tracks to master playlists
- **GIVEN** a classified library-import plan
- **WHEN** the DJ runs `crate build-masters`
- **THEN** the system adds each track to the corresponding `[DJ] <Genre>` master playlist identically to event plans

#### Scenario: Deduplication
- **WHEN** a track already exists in the target master playlist
- **THEN** the system skips it without adding a duplicate

### Requirement: Sync classified playlists to Tidal
The system SHALL sync Spotify-based genre playlists to Tidal by looking up each track via ISRC. This command is event-only and SHALL reject library-import plans. The command is registered in `cli_tidal.py` and imports from `cratekeeper.tidal.client`. Authentication uses the native session at `~/.config/cratekeeper/tidal-session.json`.

#### Scenario: Successful ISRC sync from event plan
- **GIVEN** a classified event plan
- **AND** a valid Tidal session exists
- **WHEN** the DJ runs `crate sync-to-tidal`
- **THEN** the system creates a Tidal playlist per non-empty genre bucket
- **AND** adds tracks by ISRC to each playlist
- **AND** stores Tidal playlist IDs in the plan JSON

#### Scenario: ISRC not found on Tidal
- **WHEN** a track's ISRC has no Tidal match
- **THEN** the track is reported as missing and the sync continues

#### Scenario: Reject library-import plan
- **GIVEN** a library-import plan
- **WHEN** the DJ runs `crate sync-to-tidal`
- **THEN** the system prints an error indicating this command is not applicable to library imports
- **AND** exits with a non-zero exit code

#### Scenario: No Tidal session
- **GIVEN** no Tidal session file exists
- **WHEN** the DJ runs `crate sync-to-tidal`
- **THEN** the system displays an error directing the user to run `crate tidal-auth`
