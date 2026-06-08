## MODIFIED Requirements

### Requirement: Classify tracks into genre buckets
The system SHALL assign each track in a plan to exactly one genre bucket drawn from the active profile's bucket set, using word-boundary matching with a first-match-wins specificity ordering. The bucket set SHALL come from the active profile — either a named preset (`commercial` or `electronic`) or an inline custom list — instead of a single hardcoded default, and the fallback bucket SHALL be the one defined by that profile.

#### Scenario: Successful classification with active profile buckets
- **GIVEN** the active profile resolves to a specific bucket set and fallback
- **WHEN** the DJ runs `crate classify` on an enriched plan
- **THEN** each track with genre tags is assigned to the most specific matching bucket from the active profile's set and the result is persisted in the plan JSON

#### Scenario: Genre bucket ordering
- **WHEN** multiple buckets in the active profile's set could match a track's tags
- **THEN** the system selects the first match in the profile's specificity order

#### Scenario: Commercial preset fallback
- **GIVEN** the active profile uses the `commercial` preset
- **WHEN** a track has no enriched genre tags or none match any bucket keyword
- **THEN** the track is assigned the `Pop` fallback bucket

#### Scenario: Electronic preset fallback
- **GIVEN** the active profile uses the `electronic` preset
- **WHEN** a track has no enriched genre tags or none match any bucket keyword
- **THEN** the track is assigned the `House` fallback bucket, and commercial-only buckets such as Schlager, Pop, Rock, and Latin are not present in the bucket set

## ADDED Requirements

### Requirement: Electronic genre bucket preset
The system SHALL provide an `electronic` bucket preset offering finer electronic sub-genre granularity than the commercial preset, excluding commercial genres and using House as its fallback bucket.

#### Scenario: Select the electronic preset
- **GIVEN** a profile sets `buckets = "electronic"`
- **WHEN** the system resolves that profile's buckets
- **THEN** the resolved set contains electronic sub-genre buckets with `House` as the fallback and contains no Schlager, Pop, Rock, or Latin buckets
