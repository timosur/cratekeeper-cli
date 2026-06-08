# Playlist Management

## Purpose

Creates and syncs streaming playlists from the classified event plan: Spotify sub-playlists per genre bucket, cross-event DJ master playlists, and Tidal playlist sync via ISRC.

## Requirements

### Requirement: Create Spotify sub-playlists per genre bucket
The system SHALL create one Spotify playlist per genre bucket from the classified plan, containing the tracks assigned to that bucket.

#### Scenario: Create genre playlists
- **WHEN** the DJ runs `crate create-playlists` on a classified plan
- **THEN** the system creates (or updates) a Spotify playlist for each non-empty genre bucket, named with the event and bucket name

### Requirement: Build cross-event master playlists
The system SHALL maintain persistent `[DJ] Genre` master playlists on Spotify that accumulate tracks across multiple events.

#### Scenario: Add to master playlists
- **WHEN** the DJ runs `crate build-masters` on a classified plan
- **THEN** the system adds each track to the corresponding `[DJ] <Genre>` master playlist, creating the playlist if it does not exist

#### Scenario: Deduplication
- **WHEN** a track already exists in the target master playlist
- **THEN** the system skips it without adding a duplicate

### Requirement: Sync classified playlists to Tidal
The system SHALL sync Spotify-based genre playlists to Tidal by looking up each track via ISRC.

#### Scenario: Successful ISRC sync
- **WHEN** the DJ runs `crate sync-to-tidal` and a track's ISRC is found on Tidal
- **THEN** the system adds the Tidal track to the corresponding Tidal playlist

#### Scenario: ISRC not found on Tidal
- **WHEN** a track's ISRC has no Tidal match
- **THEN** the track is reported as missing and the sync continues
