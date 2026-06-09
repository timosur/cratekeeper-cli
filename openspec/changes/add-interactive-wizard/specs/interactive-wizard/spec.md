## ADDED Requirements

### Requirement: Pipeline selection

Feature: Pipeline selection
  The wizard asks the user which pipeline to run before proceeding.

#### Scenario: User selects the event pipeline

- **GIVEN** the user runs `crate wizard`
- **WHEN** the wizard asks which pipeline to use
- **AND** the user selects "event"
- **THEN** the wizard presents the event pipeline steps (fetch, classify, enrich, match, analyze-mood, apply-tags, tag, build-event)

#### Scenario: User selects the library-import pipeline

- **GIVEN** the user runs `crate wizard`
- **WHEN** the wizard asks which pipeline to use
- **AND** the user selects "library-import"
- **THEN** the wizard presents the library-import pipeline steps (scan, import-library, classify, enrich, match, analyze-mood, apply-tags, tag, review-library, build-library)

#### Scenario: User provides a profile override

- **GIVEN** the user runs `crate wizard --profile electronic`
- **WHEN** the wizard resolves the profile
- **THEN** all subsequent steps use the "electronic" profile settings

### Requirement: Step-by-step guided execution

Feature: Step-by-step guided execution
  The wizard executes each pipeline step in order, showing output and prompting between steps.

#### Scenario: Wizard executes a required step

- **GIVEN** the wizard is on a required step (e.g. "classify")
- **WHEN** the wizard presents the step
- **THEN** the step label and description are shown
- **AND** the step executes automatically
- **AND** a summary of the result is displayed (e.g. track count, bucket distribution)

#### Scenario: Wizard prompts before advancing

- **GIVEN** a step has completed successfully
- **WHEN** the wizard shows the result
- **THEN** the wizard asks "Continue to next step?" before advancing

#### Scenario: User aborts mid-pipeline

- **GIVEN** the wizard asks "Continue to next step?"
- **WHEN** the user declines
- **THEN** the wizard saves progress and exits
- **AND** the plan JSON reflects all completed steps

### Requirement: Just-in-time input collection

Feature: Just-in-time input collection
  The wizard collects step-specific inputs immediately before each step runs.

#### Scenario: Wizard collects playlist URL before fetch

- **GIVEN** the wizard is about to run the "fetch" step
- **WHEN** the wizard prompts for input
- **THEN** the user is asked for a Spotify playlist URL
- **AND** the wizard uses the provided URL to execute fetch

#### Scenario: Wizard collects music directory before scan

- **GIVEN** the wizard is about to run the "scan" step
- **WHEN** the wizard prompts for input
- **THEN** the user is asked for the local music directory path
- **AND** the wizard uses the provided path to execute scan

#### Scenario: Wizard collects output path before build-event

- **GIVEN** the wizard is about to run the "build-event" step
- **WHEN** the wizard prompts for input
- **THEN** the user is asked for the event output directory
- **AND** the wizard uses the provided path to execute build-event

#### Scenario: Wizard collects tags file before apply-tags

- **GIVEN** the wizard is about to run the "apply-tags" step
- **WHEN** the wizard prompts for input
- **THEN** the user is asked for the path to the tags JSON file
- **AND** the wizard uses the provided path to apply tags to the plan

### Requirement: Optional step skipping

Feature: Optional step skipping
  Optional steps can be skipped; required steps cannot.

#### Scenario: User skips an optional step

- **GIVEN** the wizard is on an optional step (e.g. "enrich")
- **WHEN** the wizard asks "Run this step or skip?"
- **THEN** the user can choose "skip"
- **AND** the wizard advances to the next step without executing

#### Scenario: Required steps cannot be skipped

- **GIVEN** the wizard is on a required step (e.g. "classify")
- **WHEN** the wizard presents the step
- **THEN** no skip option is offered
- **AND** the step executes

#### Scenario: Optional terminal steps can be skipped

- **GIVEN** the wizard is on an optional terminal step (e.g. "create-playlists")
- **WHEN** the wizard asks "Run this step or skip?"
- **AND** the user chooses "skip"
- **THEN** the wizard advances (or finishes if no more steps remain)

### Requirement: Progress detection and resume

Feature: Progress detection and resume
  The wizard detects completed steps from the plan JSON and resumes from the next incomplete step.

#### Scenario: Resume from a partially completed pipeline

- **GIVEN** a plan JSON exists with tracks that have `bucket` set (classify done) but no `local_path` (match not done)
- **WHEN** the user runs `crate wizard` and provides the existing plan file
- **THEN** the wizard detects that fetch and classify are complete
- **AND** the wizard offers to resume from the "match" step

#### Scenario: Fresh start with no existing plan

- **GIVEN** no plan file exists for this pipeline run
- **WHEN** the user runs `crate wizard`
- **THEN** the wizard starts from the first step (fetch or scan)

#### Scenario: All steps already complete

- **GIVEN** a plan JSON exists where all pipeline steps are complete
- **WHEN** the user runs `crate wizard` and provides the plan file
- **THEN** the wizard reports that the pipeline is complete
- **AND** no steps are executed

### Requirement: Docker step failure handling

Feature: Docker step failure handling
  The analyze-mood step attempts execution and fails loudly if Docker or essentia is unavailable.

#### Scenario: Analyze-mood succeeds with Docker available

- **GIVEN** Docker is running and the essentia image is built
- **AND** the wizard is on the "analyze-mood" step
- **WHEN** the step executes
- **THEN** audio analysis results are written to the plan
- **AND** the wizard advances to the next step

#### Scenario: Analyze-mood fails without Docker

- **GIVEN** Docker is not available or the essentia image is not built
- **AND** the wizard is on the "analyze-mood" step
- **WHEN** the step attempts execution
- **THEN** the error from essentia/Docker is displayed to the user
- **AND** the wizard does not silently skip the step

### Requirement: Wizard completion summary

Feature: Wizard completion summary
  When all steps finish, the wizard shows a summary of what was accomplished.

#### Scenario: Pipeline completes successfully

- **GIVEN** the wizard has executed all steps in the pipeline
- **WHEN** the final step completes
- **THEN** the wizard displays a summary showing each step and its outcome
- **AND** the wizard displays the path to the final output (event folder or library directory)

## MODIFIED Requirements

_(none)_

## REMOVED Requirements

_(none)_
