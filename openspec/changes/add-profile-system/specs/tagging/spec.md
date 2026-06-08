## MODIFIED Requirements

### Requirement: Embed metadata into audio file tags
The system SHALL write audio file metadata according to the active profile's tag format. For the `structured_comment` format the system SHALL write genre, BPM, and key into standard fields AND a structured comment containing all DJ-oriented tags. For the `id3_only` format the system SHALL write only genre, BPM, and key into standard fields and SHALL NOT write the structured comment. Tag writing SHALL use mutagen across MP3, FLAC, and M4A/MP4.

#### Scenario: Structured-comment profile writes the comment
- **GIVEN** the active profile uses the `structured_comment` tag format
- **WHEN** the DJ runs `crate tag` on an MP3 track
- **THEN** the system writes genre, BPM, and key into standard ID3 frames and the structured comment into the `COMM::eng` frame

#### Scenario: ID3-only profile omits the comment
- **GIVEN** the active profile uses the `id3_only` tag format
- **WHEN** the DJ runs `crate tag` on a track
- **THEN** the system writes only genre, BPM, and key into the standard fields and writes no structured comment

#### Scenario: Write tags to FLAC
- **GIVEN** the active profile uses the `structured_comment` tag format
- **WHEN** the track's local file is a FLAC
- **THEN** the system writes metadata into Vorbis comment fields including the `comment` tag

#### Scenario: Write tags to M4A/MP4
- **GIVEN** the active profile uses the `structured_comment` tag format
- **WHEN** the track's local file is an M4A or MP4
- **THEN** the system writes metadata into the appropriate atoms including the `\xa9cmt` comment atom

#### Scenario: Idempotent re-tagging
- **WHEN** `crate tag` is run on a file that already has tags
- **THEN** the system overwrites the existing tags with the current values for the active profile's tag format without duplicating frames
