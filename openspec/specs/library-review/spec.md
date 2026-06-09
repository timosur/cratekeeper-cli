# Library Review

## Purpose

Provides an interactive approval gate before tracks enter the master library. The DJ approves or rejects each candidate track individually, ensuring the permanent collection stays curated and free of one-off wish-list tracks.

## Requirements

### Requirement: Interactive per-track approval for master library
The system SHALL present an interactive review of each candidate track (those with both `local_path` and `bucket`) and record an approve, reject, or skip decision that persists in the plan JSON stored under the active profile's `data_dir`.

#### Scenario: Review candidates
- **WHEN** the DJ runs `crate review-library` on a classified plan
- **THEN** the system presents only tracks that have both a `local_path` and a `bucket`, showing track name, artists, bucket, year, and BPM/key if available

#### Scenario: Approve a track
- **WHEN** the DJ presses `a` during review
- **THEN** the track's `library_approval` is set to `"approved"` and persisted in the plan JSON under the active profile's `data_dir`

#### Scenario: Reject a track
- **WHEN** the DJ presses `r` during review
- **THEN** the track's `library_approval` is set to `"rejected"` and persisted in the plan JSON under the active profile's `data_dir`

#### Scenario: Skip a track
- **WHEN** the DJ presses `s` during review
- **THEN** the track remains `"undecided"` and will reappear on the next review run

#### Scenario: Quit and save progress
- **WHEN** the DJ presses `q` during review
- **THEN** all decisions made so far are saved to the plan JSON and the command exits 0 without showing remaining tracks

#### Scenario: Resume interrupted review
- **WHEN** `crate review-library` is re-run on a plan with existing decisions
- **THEN** only tracks that are still `"undecided"` are presented; previously approved or rejected tracks are skipped

#### Scenario: Final summary
- **WHEN** the review completes or the DJ quits
- **THEN** the system prints a summary showing counts of approved, rejected, and remaining undecided tracks

### Requirement: Backwards-compatible approval field
The system SHALL use a `library_approval` field on `Track` with a default of `"undecided"`, so older plan JSON files work without migration.

#### Scenario: Load legacy plan
- **WHEN** the system loads a `data/*.json` plan that has no `library_approval` field on its tracks
- **THEN** every track defaults to `"undecided"` without error, meaning nothing is copied to the library until explicitly reviewed

### Requirement: Edge case handling for review
The system SHALL handle edge cases gracefully during the review process.

#### Scenario: No candidates to review
- **WHEN** no track in the plan has both `local_path` and `bucket`
- **THEN** the system prints "nothing to review; run match/classify first" and exits 0

#### Scenario: All candidates already decided
- **WHEN** every candidate track has already been approved or rejected
- **THEN** the system prints "all candidates already reviewed" and exits 0

#### Scenario: Invalid keypress
- **WHEN** the DJ presses a key other than `a`, `r`, `s`, or `q`
- **THEN** the system re-prompts for the same track instead of advancing or crashing

#### Scenario: Non-interactive stdin
- **WHEN** stdin is not a TTY (piped or non-interactive)
- **THEN** the system exits with a clear message instead of hanging

### Requirement: Profile-configurable admission fields surfaced in review
The system SHALL determine tagging completeness during review using the active profile's admission criteria (`required_fields`), so the review reflects what the active profile actually requires before a track can enter the library.

#### Scenario: Completeness reflects a reduced profile field set
- **GIVEN** the active profile's `required_fields` omits `function` and `crowd`
- **WHEN** the DJ reviews a track that has the profile's required fields populated but lacks `function` and `crowd`
- **THEN** the track is treated as fully tagged for admission purposes under that profile

#### Scenario: Completeness reflects the commercial field set
- **GIVEN** the active profile requires `energy`, `function`, `crowd`, and `mood_tags`
- **WHEN** the DJ reviews a track missing one of those fields
- **THEN** the track is treated as not yet fully tagged for admission purposes
