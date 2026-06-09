## ADDED Requirements

### Requirement: TOML config file with named profiles
The system SHALL load configuration from `~/.cratekeeper/config.toml` containing an `active_profile` key and one or more named `[profiles.<name>]` tables. Each profile defines its genre buckets (preset name or inline list), DJ software target, library output path, `data_dir`, admission criteria, sort rules, and tag format.

#### Scenario: Load an existing config file
- **GIVEN** a `~/.cratekeeper/config.toml` exists with `active_profile = "electronic"` and profiles `commercial` and `electronic`
- **WHEN** the DJ runs any `crate` command
- **THEN** the system loads the config and resolves the `electronic` profile as the active profile

#### Scenario: Invalid TOML syntax
- **GIVEN** `~/.cratekeeper/config.toml` contains malformed TOML
- **WHEN** the DJ runs any `crate` command
- **THEN** the system prints a clear error identifying the parse failure and exits non-zero without running the command

#### Scenario: Reference to an unknown preset
- **GIVEN** a profile sets `buckets = "trance"` and no such preset exists
- **WHEN** the system validates the config on load
- **THEN** the system reports that `trance` is not a known preset and exits non-zero

### Requirement: Backward-compatible implicit profile
The system SHALL behave exactly as the pre-profile CLI when no config file exists, using an implicit `commercial` profile whose buckets, library target, tag format, and admission criteria match the historical hardcoded defaults.

#### Scenario: No config file present
- **GIVEN** no `~/.cratekeeper/config.toml` exists
- **WHEN** the DJ runs a pipeline command such as `crate classify`
- **THEN** the system uses the implicit `commercial` profile and produces the same result as before profiles existed

#### Scenario: Existing plans still load without a config
- **GIVEN** no config file exists and a legacy `data/*.json` plan is present
- **WHEN** the DJ runs a command against that plan path
- **THEN** the plan loads and processes without requiring a profile to be configured

### Requirement: Active profile resolution and override
The system SHALL resolve the active profile using the precedence: `--profile` flag, then config `active_profile`, then the first defined profile, then the implicit `commercial` profile. The `--profile` flag SHALL be available as a global option on all commands.

#### Scenario: Per-invocation override
- **GIVEN** the config `active_profile` is `commercial`
- **WHEN** the DJ runs `crate classify --profile electronic <plan>`
- **THEN** the system uses the `electronic` profile for that invocation only, leaving `active_profile` unchanged

#### Scenario: Override names an unknown profile
- **GIVEN** the config defines `commercial` and `electronic`
- **WHEN** the DJ runs a command with `--profile studio`
- **THEN** the system reports that `studio` is not a defined profile and exits non-zero

### Requirement: Profile management subcommands
The system SHALL provide a `crate profile` command group with `list`, `show`, `use`, and `init` subcommands to inspect and manage profiles.

#### Scenario: List profiles
- **WHEN** the DJ runs `crate profile list`
- **THEN** the system prints every defined profile name and marks which one is currently active

#### Scenario: Show the effective resolved config
- **WHEN** the DJ runs `crate profile show electronic`
- **THEN** the system prints the fully resolved profile settings, including buckets resolved from any referenced preset, target path, `data_dir`, tag format, DJ software target, admission criteria, and sort rules

#### Scenario: Switch the active profile
- **GIVEN** the config defines `commercial` and `electronic`
- **WHEN** the DJ runs `crate profile use electronic`
- **THEN** the system writes `active_profile = "electronic"` to the config file and confirms the change

#### Scenario: Initialise a config file
- **GIVEN** no `~/.cratekeeper/config.toml` exists
- **WHEN** the DJ runs `crate profile init`
- **THEN** the system scaffolds a config file with `commercial` and `electronic` example profiles and reports the path it created

#### Scenario: Init does not clobber an existing config
- **GIVEN** a `~/.cratekeeper/config.toml` already exists
- **WHEN** the DJ runs `crate profile init`
- **THEN** the system refuses to overwrite it, reports that a config already exists, and exits non-zero
