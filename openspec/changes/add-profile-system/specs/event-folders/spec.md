## MODIFIED Requirements

### Requirement: Tag-completeness gate
The system SHALL copy a track only if it has a usable `local_path` (file exists on disk) AND every field in the active profile's admission criteria (`required_fields`) is non-empty in the plan. The `commercial` profile requires `energy`, `function`, `crowd`, and `mood_tags`; other profiles MAY require fewer fields.

#### Scenario: Fully tagged track copied
- **WHEN** a track has `local_path`, the file exists, and every field required by the active profile is non-empty
- **THEN** the system copies the file into the event folder

#### Scenario: Partially tagged track skipped
- **WHEN** a track has some but not all of the active profile's required fields
- **THEN** the track is not copied and is listed in the `_untagged.txt` report

#### Scenario: Reduced profile field set
- **GIVEN** the active profile's `required_fields` omits `function` and `crowd`
- **WHEN** a track has `local_path`, the file exists, and the profile's required fields are populated
- **THEN** the system copies the file even though `function` and `crowd` are empty

### Requirement: Embedded comment verification
The system SHALL verify the embedded comment tag before copying only when the active profile's tag format is `structured_comment`. For the `id3_only` tag format the system SHALL skip the embedded-comment gate, since such profiles intentionally write no structured comment.

#### Scenario: Embedded comment present under structured-comment profile
- **GIVEN** the active profile uses the `structured_comment` tag format
- **WHEN** the audio file contains a non-empty comment field with the `energy:` marker (MP3 `COMM::eng`, FLAC `comment`, M4A `\xa9cmt`)
- **THEN** the track passes the embedded-comment gate

#### Scenario: Comment not yet embedded under structured-comment profile
- **GIVEN** the active profile uses the `structured_comment` tag format
- **WHEN** plan tags are present but the audio file lacks the embedded comment
- **THEN** the track is added to the untagged list, directing the DJ to re-run `crate tag`

#### Scenario: Comment gate skipped under id3-only profile
- **GIVEN** the active profile uses the `id3_only` tag format
- **WHEN** a track has `local_path`, the file exists, and the profile's required fields are populated
- **THEN** the system copies the file without checking for an embedded comment
