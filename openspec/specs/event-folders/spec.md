# Event Folders

## Purpose

Builds a flat, tag-driven event folder for djay PRO. All eligible files are copied directly into a single directory (no genre subfolders) so the DJ can slice the set using djay PRO quick filters on energy, function, crowd, and mood tags embedded in the files.

## Requirements

### Requirement: Flat folder layout
The system SHALL copy eligible files directly into the output directory with no genre subfolders, using `Artist - Title.ext` as the filename.

#### Scenario: Flat output
- **WHEN** the DJ runs `crate build-event -o <dir> <plan>`
- **THEN** all eligible files are written directly into `<dir>` with no `Genre/` subdirectories

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

### Requirement: Missing-file and untagged reports
The system SHALL write report files in the output directory listing tracks that were skipped.

#### Scenario: Missing local file report
- **WHEN** a track has no `local_path` or the file does not exist on disk
- **THEN** the track is listed in `_missing.txt` in the output directory

#### Scenario: Untagged/collision report
- **WHEN** tracks are skipped for missing tags, missing embedded comment, or filename collision
- **THEN** those tracks are listed in `_untagged.txt` in the output directory

### Requirement: Filename collision handling
The system SHALL handle filename collisions (two tracks resolving to the same `Artist - Title.ext`) using a first-writer-wins strategy.

#### Scenario: Collision detected
- **WHEN** two different source files resolve to the same destination filename
- **THEN** the first track is copied and the second is added to the `_untagged.txt` report

### Requirement: Build summary and exit behaviour
The system SHALL print a Rich summary table and use appropriate exit codes.

#### Scenario: Successful build summary
- **WHEN** `crate build-event` completes with at least one eligible track
- **THEN** the summary reports counts for: copied, already existed, missing local file, and skipped (untagged or collision), and the command exits 0

#### Scenario: Zero eligible tracks
- **WHEN** candidates exist but no track qualifies
- **THEN** the system warns clearly and exits non-zero without creating a misleading output

#### Scenario: Warning for skipped tracks
- **WHEN** any tracks are skipped for missing tags
- **THEN** the summary includes a warning line pointing at `_untagged.txt`

### Requirement: Idempotent re-builds
The system SHALL handle re-runs after additional tagging without duplicating or overwriting files.

#### Scenario: Re-run after more tagging
- **WHEN** `crate build-event` is re-run after more tracks become fully tagged
- **THEN** newly eligible tracks are copied while already-present files are skipped (counted as "already existed")
