## ADDED Requirements

### Requirement: Generate LLM tag classification prompt from plan

Feature: Tag prompt generation
Rule: The CLI generates a self-contained prompt suitable for any LLM harness that produces JSON compatible with `crate apply-tags`

#### Scenario: Generate prompt to stdout
- **GIVEN** a plan file with tracks that have analysis data (bpm, key, audio_energy, audio_mood, arousal, valence, bucket, era)
- **WHEN** the DJ runs `crate tag-prompt <plan.json>`
- **THEN** the system prints a self-contained LLM prompt to stdout containing all track context, vocabulary constraints, and the expected JSON output schema

#### Scenario: Generate prompt to file
- **GIVEN** a plan file with analyzed tracks
- **WHEN** the DJ runs `crate tag-prompt <plan.json> --output prompt.txt`
- **THEN** the system writes the prompt to the specified file instead of stdout

#### Scenario: Prompt includes vocabulary constraints
- **GIVEN** any plan with tracks
- **WHEN** the prompt is generated
- **THEN** the prompt text includes the valid values for energy (low, mid, high), function (floorfiller, singalong, bridge, reset, closer, opener), crowd (mixed-age, older, younger, family), and mood_tags (feelgood, emotional, euphoric, nostalgic, romantic, melancholic, dark, aggressive, uplifting, dreamy, funky, groovy)

#### Scenario: Prompt includes per-track context
- **GIVEN** a plan with tracks that have been analyzed
- **WHEN** the prompt is generated
- **THEN** each track appears as a context line with id, name, artists, bucket, era, bpm, key, audio energy score, audio mood, arousal, and valence

#### Scenario: Prompt specifies output JSON schema
- **GIVEN** any plan
- **WHEN** the prompt is generated
- **THEN** the prompt instructs the LLM to return a JSON array where each element has: id (string), energy (string), function (array of strings), crowd (array of strings), mood_tags (array of strings), and optionally genre_suggestion (string)

#### Scenario: Plan with no analyzed tracks
- **GIVEN** a plan where no tracks have analysis data (no bpm, no audio_mood)
- **WHEN** the DJ runs `crate tag-prompt <plan.json>`
- **THEN** the system warns that tracks lack analysis data and generates the prompt with available fields only

#### Scenario: Works with any plan type
- **GIVEN** a LibraryImportPlan or EventPlan loaded via `Plan.load()`
- **WHEN** the DJ runs `crate tag-prompt`
- **THEN** the system generates the prompt regardless of plan type

### Requirement: Wizard generates tag prompt before requesting tags file

Feature: Tag prompt generation in wizard
Rule: The wizard automatically generates and saves the LLM prompt when entering the apply-tags step, reducing manual effort

#### Scenario: Wizard generates prompt file automatically
- **GIVEN** the wizard reaches the "Apply LLM-classified tags" step
- **AND** the step is not yet complete
- **WHEN** the wizard prepares the step
- **THEN** the system generates the tag prompt and saves it to a file in the plan's data directory
- **AND** displays the path to the saved prompt file
- **AND** instructs the DJ to feed the prompt to an LLM and provide the resulting tags JSON path

#### Scenario: Wizard skips prompt generation when tags already applied
- **GIVEN** the wizard reaches the "Apply LLM-classified tags" step
- **AND** all tracks already have energy and function tags
- **WHEN** the wizard checks step completion
- **THEN** the step is marked complete and no prompt is generated
