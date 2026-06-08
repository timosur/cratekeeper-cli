# Track Matching

## Purpose

Matches Spotify tracks in the event plan to local audio files in the PostgreSQL index using a cascading strategy: ISRC lookup, then exact artist+title match, then fuzzy matching.

## Requirements

### Requirement: Match tracks to local files via cascading strategy
The system SHALL attempt to match each track in the event plan to a local audio file using three strategies in order: ISRC match, exact normalized artist+title match, and fuzzy artist+title match.

#### Scenario: ISRC match (highest priority)
- **WHEN** the DJ runs `crate match` and a track's ISRC matches a local file's ISRC in the database
- **THEN** the system records the local file path on the track in the plan JSON

#### Scenario: Exact artist+title match
- **WHEN** no ISRC match is found but a local file's normalized artist and title match exactly
- **THEN** the system records the local file path on the track

#### Scenario: Fuzzy match
- **WHEN** neither ISRC nor exact match succeeds but a local file scores above the fuzzy matching threshold (via thefuzz)
- **THEN** the system records the local file path on the track

#### Scenario: No match found
- **WHEN** no matching local file is found for a track
- **THEN** the track's `local_path` remains empty and the pipeline continues without error

#### Scenario: Match result persistence
- **WHEN** matching completes
- **THEN** all match results are persisted back to the event-plan JSON so downstream commands can use them
