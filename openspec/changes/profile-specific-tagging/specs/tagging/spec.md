## MODIFIED Requirements

### Requirement: Apply pre-classified tags from JSON
The system SHALL validate and import structured tags from an externally-produced JSON file into the event plan, using the active profile's tag field definitions for validation. Tag fields, valid values, and pick ranges are determined by the profile's tag config. Values not in the profile's vocabulary are rejected.

#### Scenario: Successful tag application with profile vocabulary
- **GIVEN** a plan file and a tags JSON file with valid entries matching the active profile's tag fields
- **WHEN** the DJ runs `crate apply-tags` with the plan file and tags JSON file
- **THEN** the system validates each tag value against the active profile's vocabulary and writes the validated tags onto each matching track in the plan

#### Scenario: Strict validation rejects unknown values
- **GIVEN** the active profile defines function values as ["warm-up", "build", "peak-time", "breakdown", "cooldown", "closer"]
- **AND** a tags JSON entry contains `"function": ["floorfiller"]`
- **WHEN** the tags are applied
- **THEN** the system rejects the entry, reports that "floorfiller" is not a valid value for function in the active profile, and lists the valid alternatives

#### Scenario: Invalid tag structure
- **WHEN** the tags JSON contains malformed or missing required fields as defined by the profile's tag config
- **THEN** the system reports validation errors and does not apply partial tags

#### Scenario: Track not found in plan
- **WHEN** the tags JSON references a track that does not exist in the plan
- **THEN** the system reports the mismatch and continues processing remaining tracks

#### Scenario: List fields accepted as arrays with pick range validation
- **GIVEN** the active profile defines function as a list field with pick range [1, 3]
- **AND** a tags JSON entry contains `"function": ["warm-up", "build", "peak-time", "breakdown"]`
- **WHEN** the tags are applied
- **THEN** the system rejects the entry because 4 values exceeds the maximum pick count of 3

#### Scenario: Single fields reject multiple values
- **GIVEN** the active profile defines energy as a single-type field
- **AND** a tags JSON entry contains `"energy": ["low", "mid"]`
- **WHEN** the tags are applied
- **THEN** the system rejects the entry because energy expects a single value, not an array

#### Scenario: Tags stored in generic tags dict
- **GIVEN** a plan file and valid tags JSON
- **WHEN** tags are successfully applied
- **THEN** each track's `tags` dict is populated with the field names and values from the JSON, and legacy fields (energy, function, crowd, mood_tags) are also populated when the corresponding field name matches

### Requirement: Embed metadata into audio file tags
The system SHALL write audio file metadata according to the active profile's tag format. For the `structured_comment` format the system SHALL write genre, BPM, and key into standard fields AND a structured comment containing the profile's tag fields in definition order. For the `id3_only` format the system SHALL write only genre, BPM, and key into standard fields and SHALL NOT write the structured comment. Tag writing SHALL use mutagen across MP3, FLAC, and M4A/MP4.

#### Scenario: Structured comment uses profile field layout
- **GIVEN** the active profile uses the `structured_comment` tag format and defines tag fields: energy, function, mood_tags, mix_traits
- **WHEN** the DJ runs `crate tag` on an MP3 track with applied tags
- **THEN** the system writes genre, BPM, and key into standard ID3 frames and the structured comment into the `COMM::eng` frame with format `era:<value>; energy:<value>; function:<values>; mood:<values>; mix:<values>`

#### Scenario: Commercial profile structured comment includes crowd
- **GIVEN** the active profile uses the `structured_comment` tag format and defines tag fields: energy, function, crowd, mood_tags
- **WHEN** the DJ runs `crate tag` on an MP3 track with applied tags
- **THEN** the structured comment follows format `era:<value>; energy:<value>; function:<values>; crowd:<values>; mood:<values>`

#### Scenario: ID3-only profile omits the comment
- **GIVEN** the active profile uses the `id3_only` tag format
- **WHEN** the DJ runs `crate tag` on a track
- **THEN** the system writes only genre, BPM, and key into the standard fields and writes no structured comment

#### Scenario: Write tags to FLAC
- **GIVEN** the active profile uses the `structured_comment` tag format
- **WHEN** the track's local file is a FLAC
- **THEN** the system writes metadata into Vorbis comment fields including the `comment` tag with the profile-specific structured comment

#### Scenario: Write tags to M4A/MP4
- **GIVEN** the active profile uses the `structured_comment` tag format
- **WHEN** the track's local file is an M4A or MP4
- **THEN** the system writes metadata into the appropriate atoms including the `\xa9cmt` comment atom with the profile-specific structured comment

#### Scenario: Idempotent re-tagging
- **WHEN** `crate tag` is run on a file that already has tags
- **THEN** the system overwrites the existing tags with the current values for the active profile's tag format without duplicating frames

### Requirement: Write basic metadata into untagged files
The system SHALL write basic metadata (artist, title, album) into audio files that lack standard tags, using the information from the event plan.

#### Scenario: Tag untagged files
- **WHEN** the DJ runs `crate tag-untagged` on a plan with matched but untagged local files
- **THEN** the system writes artist, title, and album metadata into those files

#### Scenario: Already-tagged files skipped
- **WHEN** a file already has standard metadata tags
- **THEN** the system skips the file without modification
