## MODIFIED Requirements

### Requirement: Fetch Spotify playlist to JSON plan
The system SHALL fetch all tracks from a Spotify playlist URL and persist them as a structured JSON plan at `data/<plan>.json`. The plan type (event or library-import) is determined by an interactive prompt or defaults to event for non-interactive sessions.

#### Scenario: Fetch a valid playlist as event
- **GIVEN** stdin is an interactive terminal
- **WHEN** the DJ runs `crate fetch` with a valid Spotify playlist URL
- **AND** selects "event" at the plan-type prompt
- **THEN** the system creates a JSON file with `plan_type` of `event` containing every track from the playlist with name, artists, album, ISRC, Spotify URI, and duration

#### Scenario: Fetch a valid playlist as library import
- **GIVEN** stdin is an interactive terminal
- **WHEN** the DJ runs `crate fetch` with a valid Spotify playlist URL
- **AND** selects "library import" at the plan-type prompt
- **THEN** the system creates a JSON file with `plan_type` of `library-import` containing every track from the playlist

#### Scenario: Reuse cached Spotify token
- **WHEN** a valid Spotify token exists in `spotify-config.json`
- **THEN** the system reuses the token without re-authenticating

#### Scenario: Invalid or empty playlist
- **WHEN** the playlist URL is invalid or the playlist contains zero tracks
- **THEN** the system exits with a clear error message and non-zero exit code

#### Scenario: Non-interactive fetch defaults to event
- **GIVEN** stdin is not an interactive terminal
- **WHEN** the DJ runs `crate fetch` with a valid Spotify playlist URL
- **THEN** the system creates an event plan without prompting

### Requirement: Enrich genres and release years via MusicBrainz
The system SHALL enrich each track in a plan with genre tags and release years by looking up ISRCs on MusicBrainz. This works identically for both event and library-import plans.

#### Scenario: Successful ISRC lookup
- **WHEN** the DJ runs `crate enrich` on a fetched plan and MusicBrainz returns genre/year data for a track's ISRC
- **THEN** the system writes the genre tags and release year onto the track in the plan JSON

#### Scenario: Rate limiting
- **WHEN** the system makes MusicBrainz API requests
- **THEN** the system respects a minimum 1.1-second interval between requests to comply with rate limits

#### Scenario: ISRC not found
- **WHEN** a track's ISRC has no MusicBrainz match
- **THEN** the track is left without enriched genre/year data and the pipeline continues without error
