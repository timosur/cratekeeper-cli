# Playlist Ingestion

## Purpose

Fetches tracks from a Spotify playlist and enriches them with genre and release-year metadata from MusicBrainz, producing the initial event-plan JSON that drives the rest of the pipeline.

## Requirements

### Requirement: Fetch Spotify playlist to JSON plan
The system SHALL fetch all tracks from a Spotify playlist URL and persist them as a structured JSON event plan at `data/<plan>.json`.

#### Scenario: Fetch a valid playlist
- **WHEN** the DJ runs `crate fetch` with a valid Spotify playlist URL and an output path
- **THEN** the system creates a JSON file containing every track from the playlist with name, artists, album, ISRC, Spotify URI, and duration

#### Scenario: Reuse cached Spotify token
- **WHEN** a valid Spotify token exists in `spotify-config.json`
- **THEN** the system reuses the token without re-authenticating

#### Scenario: Invalid or empty playlist
- **WHEN** the playlist URL is invalid or the playlist contains zero tracks
- **THEN** the system exits with a clear error message and non-zero exit code

### Requirement: Enrich genres and release years via MusicBrainz
The system SHALL enrich each track in an event plan with genre tags and release years by looking up ISRCs on MusicBrainz.

#### Scenario: Successful ISRC lookup
- **WHEN** the DJ runs `crate enrich` on a fetched plan and MusicBrainz returns genre/year data for a track's ISRC
- **THEN** the system writes the genre tags and release year onto the track in the plan JSON

#### Scenario: Rate limiting
- **WHEN** the system makes MusicBrainz API requests
- **THEN** the system respects a minimum 1.1-second interval between requests to comply with rate limits

#### Scenario: ISRC not found
- **WHEN** a track's ISRC has no MusicBrainz match
- **THEN** the track is left without enriched genre/year data and the pipeline continues without error
