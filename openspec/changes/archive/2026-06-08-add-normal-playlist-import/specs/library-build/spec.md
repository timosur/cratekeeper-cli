## MODIFIED Requirements

### Requirement: Copy only approved and fully tagged tracks to master library
The system SHALL copy a track into the master library only when it is `library_approval == "approved"` AND fully tagged (`energy`, `function`, `crowd`, `mood_tags` all non-empty) AND has a `local_path` and `bucket`. This applies to both event and library-import plans.

#### Scenario: Successful library copy from event plan
- **GIVEN** an event plan with tracks meeting all admission criteria
- **WHEN** the DJ runs `crate build-library`
- **THEN** the system copies qualifying files to `<target>/Genre/Artist - Title.ext`

#### Scenario: Successful library copy from library-import plan
- **GIVEN** a library-import plan with tracks meeting all admission criteria
- **WHEN** the DJ runs `crate build-library`
- **THEN** the system copies qualifying files to `<target>/Genre/Artist - Title.ext` identically to event plans

#### Scenario: Rejected track excluded
- **WHEN** a track has `library_approval == "rejected"`
- **THEN** the track is not copied and is counted as "rejected" in the summary

#### Scenario: Undecided track excluded
- **WHEN** a track has `library_approval == "undecided"` (not yet reviewed)
- **THEN** the track is not copied and is counted as "undecided" in the summary

#### Scenario: Approved but not fully tagged
- **WHEN** a track is approved but lacks one or more required tags (`energy`, `function`, `crowd`, `mood_tags`)
- **THEN** the track is not copied and is reported as "missing tags" in the summary

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
