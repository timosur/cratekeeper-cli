# Tagging

## Purpose

Manages the structured tagging pipeline: applying LLM-classified tags from an external JSON file into the event plan, embedding metadata (genre, BPM, key, structured comment) into audio file tags, and writing basic metadata into untagged files.

## Requirements

### Requirement: Apply pre-classified tags from JSON
The system SHALL validate and import structured tags (energy, function, crowd, mood) from an externally-produced JSON file into the event plan, enabling agent-layer LLM tagging without an LLM dependency in the CLI.

#### Scenario: Successful tag application
- **WHEN** the DJ runs `crate apply-tags` with a plan file and a tags JSON file
- **THEN** the system validates the tag structure and writes `energy`, `function`, `crowd`, `mood_tags`, and `era` onto each matching track in the plan

#### Scenario: Invalid tag structure
- **WHEN** the tags JSON contains malformed or missing required fields
- **THEN** the system reports validation errors and does not apply partial tags

#### Scenario: Track not found in plan
- **WHEN** the tags JSON references a track that does not exist in the plan
- **THEN** the system reports the mismatch and continues processing remaining tracks

### Requirement: Embed metadata into audio file tags
The system SHALL write genre, BPM, key, and a structured comment containing all DJ-oriented tags into the audio file's metadata using mutagen.

#### Scenario: Write tags to MP3
- **WHEN** the DJ runs `crate tag` and the track's local file is an MP3
- **THEN** the system writes genre, BPM, key into standard ID3 frames and the structured comment into the `COMM::eng` frame

#### Scenario: Write tags to FLAC
- **WHEN** the track's local file is a FLAC
- **THEN** the system writes metadata into Vorbis comment fields including the `comment` tag

#### Scenario: Write tags to M4A/MP4
- **WHEN** the track's local file is an M4A or MP4
- **THEN** the system writes metadata into the appropriate atoms including the `\xa9cmt` comment atom

#### Scenario: Idempotent re-tagging
- **WHEN** `crate tag` is run on a file that already has tags
- **THEN** the system overwrites the existing tags with the current values without duplicating frames

### Requirement: Write basic metadata into untagged files
The system SHALL write basic metadata (artist, title, album) into audio files that lack standard tags, using the information from the event plan.

#### Scenario: Tag untagged files
- **WHEN** the DJ runs `crate tag-untagged` on a plan with matched but untagged local files
- **THEN** the system writes artist, title, and album metadata into those files

#### Scenario: Already-tagged files skipped
- **WHEN** a file already has standard metadata tags
- **THEN** the system skips the file without modification
