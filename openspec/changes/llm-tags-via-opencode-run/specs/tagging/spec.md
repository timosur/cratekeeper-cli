## ADDED Requirements

### Requirement: Tag prompt generation available as standalone command

Feature: Standalone CLI command for tag prompt
Rule: `crate tag-prompt` is registered as a pipeline command alongside `apply-tags` and `tag`

#### Scenario: Command registered in CLI
- **GIVEN** the cratekeeper CLI is installed
- **WHEN** the DJ runs `crate tag-prompt --help`
- **THEN** the system shows usage for the tag-prompt command with plan_file argument and --output option

## MODIFIED Requirements

### Requirement: Apply pre-classified tags from JSON
The system SHALL validate and import structured tags (energy, function, crowd, mood) from an externally-produced JSON file into the event plan, enabling agent-layer LLM tagging without an LLM dependency in the CLI.

#### Scenario: Successful tag application
- **GIVEN** a plan file and a tags JSON file with valid entries
- **WHEN** the DJ runs `crate apply-tags` with the plan file and tags JSON file
- **THEN** the system validates the tag structure and writes `energy`, `function` (array), `crowd` (array), `mood_tags` (array), and optionally `genre_suggestion` onto each matching track in the plan

#### Scenario: Invalid tag structure
- **WHEN** the tags JSON contains malformed or missing required fields
- **THEN** the system reports validation errors and does not apply partial tags

#### Scenario: Track not found in plan
- **WHEN** the tags JSON references a track that does not exist in the plan
- **THEN** the system reports the mismatch and continues processing remaining tracks

#### Scenario: Function and crowd accepted as arrays
- **GIVEN** a tags JSON entry with `"function": ["floorfiller", "singalong"]` and `"crowd": ["mixed-age", "younger"]`
- **WHEN** the tags are applied
- **THEN** the track's function and crowd fields are set to the provided arrays (filtered to valid vocabulary)
