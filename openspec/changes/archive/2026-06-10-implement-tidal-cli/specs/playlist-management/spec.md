## MODIFIED Requirements

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
