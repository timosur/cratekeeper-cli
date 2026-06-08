## MODIFIED Requirements

### Requirement: Fetch Spotify playlist to JSON plan
The system SHALL fetch all tracks from a Spotify playlist URL and persist them as a structured JSON plan under the active profile's `data_dir` (e.g. `<profile-data_dir>/<plan>.json`) instead of the shared `data/` directory. The plan type (event or library-import) is determined by an interactive prompt or defaults to event for non-interactive sessions.

#### Scenario: Fetch a valid playlist as event
- **GIVEN** stdin is an interactive terminal
- **WHEN** the DJ runs `crate fetch` with a valid Spotify playlist URL
- **AND** selects "event" at the plan-type prompt
- **THEN** the system creates a JSON file under the active profile's `data_dir` with `plan_type` of `event` containing every track from the playlist with name, artists, album, ISRC, Spotify URI, and duration

#### Scenario: Fetch a valid playlist as library import
- **GIVEN** stdin is an interactive terminal
- **WHEN** the DJ runs `crate fetch` with a valid Spotify playlist URL
- **AND** selects "library import" at the plan-type prompt
- **THEN** the system creates a JSON file under the active profile's `data_dir` with `plan_type` of `library-import` containing every track from the playlist

#### Scenario: Reuse cached Spotify token
- **WHEN** a valid Spotify token exists in `spotify-config.json`
- **THEN** the system reuses the token without re-authenticating

#### Scenario: Invalid or empty playlist
- **WHEN** the playlist URL is invalid or the playlist contains zero tracks
- **THEN** the system exits with a clear error message and non-zero exit code

#### Scenario: Non-interactive fetch defaults to event
- **GIVEN** stdin is not an interactive terminal
- **WHEN** the DJ runs `crate fetch` with a valid Spotify playlist URL
- **THEN** the system creates an event plan under the active profile's `data_dir` without prompting
