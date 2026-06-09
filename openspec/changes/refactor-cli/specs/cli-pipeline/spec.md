## ADDED Requirements

### Requirement: CLI command handlers contain no inline business logic
Feature: Thin CLI command handlers
Rule: Each `crate` command handler in `cli.py` delegates to a domain module function; file I/O, API calls, and data transformation are not performed inline in the command body.

#### Scenario: Command handler loads plan and delegates to domain function
- **GIVEN** a valid plan file on disk
- **WHEN** any pipeline command (e.g., `crate classify`, `crate tag`) is invoked
- **THEN** the handler loads the plan, calls the corresponding domain function, saves the result, and exits
- **AND** the handler contains no loops, API calls, or file-system operations beyond plan load/save

#### Scenario: Domain function is callable independently of the CLI
- **GIVEN** a domain module function (e.g., `classifier.classify_tracks`)
- **WHEN** it is called directly in a test with a `Plan` object
- **THEN** it returns a result without requiring a Typer context or CLI invocation

### Requirement: Wizard delegates to CLI handlers via context invoke
Feature: Wizard re-uses CLI handlers
Rule: `wizard.py` calls each pipeline step by invoking the corresponding Typer command function via `ctx.invoke`; it does not re-implement pipeline logic.

#### Scenario: Wizard fetch step invokes the fetch command
- **GIVEN** the wizard is running interactively
- **WHEN** the fetch step is reached
- **THEN** `ctx.invoke(fetch, ...)` is called with the user-provided arguments
- **AND** the output produced is identical to running `crate fetch` directly

#### Scenario: Wizard classify step invokes the classify command
- **GIVEN** the wizard has completed the fetch step and a plan file exists
- **WHEN** the classify step is reached
- **THEN** `ctx.invoke(classify, ...)` is called
- **AND** the plan file is updated as if `crate classify` had been run directly

#### Scenario: Wizard error handling mirrors CLI error handling
- **GIVEN** the wizard is running and a step fails (e.g., Spotify rate limit)
- **WHEN** the invoked CLI handler raises an error
- **THEN** the wizard surfaces the same error message as the standalone CLI command would
- **AND** the wizard does not swallow or re-format the error

### Requirement: Public CLI surface is unchanged
Rule: All `crate` command names, arguments, and flags remain identical after the refactor.

#### Scenario: All existing commands are still available
- **GIVEN** the refactored package is installed
- **WHEN** `crate --help` is run
- **THEN** all commands present before the refactor appear in the help output with the same names and signatures

#### Scenario: Existing command invocations produce the same output
- **GIVEN** a valid plan file
- **WHEN** a command is invoked with the same arguments as before the refactor
- **THEN** the observable output (console text, plan file mutations, created directories) is identical to the pre-refactor behaviour
