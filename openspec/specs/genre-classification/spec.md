# Genre Classification

## Purpose

Classifies tracks into one of 18 genre buckets using a rule-based, specificity-ordered matching system, and provides a review step for low-confidence classifications.

## Requirements

### Requirement: Classify tracks into genre buckets
The system SHALL assign each track in an event plan to exactly one of 18 genre buckets based on its enriched genre tags, using word-boundary matching with a first-match-wins specificity ordering.

#### Scenario: Successful classification
- **WHEN** the DJ runs `crate classify` on an enriched plan
- **THEN** each track with genre tags is assigned to the most specific matching genre bucket and the result is persisted in the plan JSON

#### Scenario: Genre bucket ordering
- **WHEN** multiple genre buckets could match a track's tags
- **THEN** the system selects the first match in specificity order (electronic sub-genres before general genres, Pop as the fallback bucket)

#### Scenario: No genre match
- **WHEN** a track has no enriched genre tags or none match any bucket keyword
- **THEN** the track is assigned to the Pop fallback bucket

### Requirement: Review low-confidence classifications
The system SHALL allow the DJ to review and override tracks whose classification confidence is low.

#### Scenario: Show low-confidence tracks
- **WHEN** the DJ runs `crate review` on a classified plan
- **THEN** the system displays tracks flagged as low-confidence with their assigned bucket, and the DJ can override the assignment

#### Scenario: Small-bucket consolidation
- **WHEN** a genre bucket contains very few tracks after classification
- **THEN** the system flags those tracks for review as low-confidence candidates
