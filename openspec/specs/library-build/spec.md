# Library Build

## Purpose

Copies approved and fully tagged tracks into the master library using a `Genre/Artist - Title.ext` folder structure. Enforces dual admission gates: the track must be approved via `review-library` and carry all required structured tags.

## Requirements

### Requirement: Copy only approved and fully tagged tracks to master library
The system SHALL copy a track into the master library only when it is `library_approval == "approved"` AND fully tagged AND has a `local_path` and `bucket`. "Fully tagged" SHALL mean every field listed in the active profile's admission criteria (`required_fields`) is non-empty; the `commercial` profile requires `energy`, `function`, `crowd`, and `mood_tags`, while other profiles MAY require fewer fields. The library SHALL be written under the active profile's configured target path. This applies to both event and library-import plans.

#### Scenario: Successful library copy from event plan
- **GIVEN** an event plan with tracks meeting all admission criteria for the active profile
- **WHEN** the DJ runs `crate build-library`
- **THEN** the system copies qualifying files to `<profile-target>/Genre/Artist - Title.ext`

#### Scenario: Successful library copy from library-import plan
- **GIVEN** a library-import plan with tracks meeting all admission criteria for the active profile
- **WHEN** the DJ runs `crate build-library`
- **THEN** the system copies qualifying files to `<profile-target>/Genre/Artist - Title.ext` identically to event plans

#### Scenario: Rejected track excluded
- **WHEN** a track has `library_approval == "rejected"`
- **THEN** the track is not copied and is counted as "rejected" in the summary

#### Scenario: Undecided track excluded
- **WHEN** a track has `library_approval == "undecided"` (not yet reviewed)
- **THEN** the track is not copied and is counted as "undecided" in the summary

#### Scenario: Approved but missing a profile-required field
- **GIVEN** the active profile requires `energy`, `function`, `crowd`, and `mood_tags`
- **WHEN** a track is approved but lacks one or more of those required fields
- **THEN** the track is not copied and is reported as "missing tags" in the summary

#### Scenario: Admission honours a reduced profile field set
- **GIVEN** the active profile's `required_fields` omits `function` and `crowd`
- **WHEN** a track is approved and has every field the profile requires
- **THEN** the track qualifies and is copied even though `function` and `crowd` are empty

### Requirement: Empty-approval safety guard
The system SHALL warn and exit non-zero without copying any files when candidates exist but zero tracks qualify.

#### Scenario: No qualifying tracks
- **WHEN** `crate build-library` is run and candidates exist but none are approved and fully tagged
- **THEN** the system prints a warning explaining what to fix (run `crate review-library` and/or finish tagging) and exits non-zero without copying

### Requirement: Comprehensive build summary
The system SHALL report a detailed summary after building the library.

#### Scenario: Full count breakdown
- **WHEN** `crate build-library` completes
- **THEN** the summary table reports counts for: copied, already existed, missing (local file gone), rejected, undecided/un-reviewed, and excluded for missing tags

### Requirement: Idempotent re-builds
The system SHALL handle re-runs after additional approvals without duplicating files.

#### Scenario: Re-run after new approvals
- **WHEN** `crate build-library` is re-run after the DJ approves more tracks
- **THEN** newly qualified tracks are copied while already-copied files are skipped (counted as "already existed")

### Requirement: Profile-driven sorting within buckets
The system SHALL order tracks within each genre bucket according to the active profile's sort configuration (sort keys and direction), affecting the order in which tracks are processed and laid out during the build.

#### Scenario: Sort by BPM descending
- **GIVEN** the active profile defines a sort over BPM in descending direction
- **WHEN** the DJ runs `crate build-library`
- **THEN** within each bucket the tracks are processed in descending BPM order

#### Scenario: Default sort preserves insertion order
- **GIVEN** the active profile defines no sort configuration
- **WHEN** the DJ runs `crate build-library`
- **THEN** tracks within each bucket retain their existing plan order
