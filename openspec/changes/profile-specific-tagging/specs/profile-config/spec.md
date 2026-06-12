## ADDED Requirements

### Requirement: Per-profile tag vocabulary configuration

Feature: Profile tag configuration
Rule: Each profile MAY define a `[profiles.<name>.tags]` section with field definitions and classification guidance that drives prompt generation and validation

#### Scenario: Profile with custom tag fields
- **GIVEN** a config file where the `electronic` profile defines `[profiles.electronic.tags]` with fields `energy`, `function`, `mood_tags`, and `mix_traits`
- **WHEN** the system loads the profile
- **THEN** the profile's tag config contains exactly those four fields with their configured valid values, type, and pick ranges

#### Scenario: Profile without tags section uses defaults
- **GIVEN** a config file where the `commercial` profile has no `[profiles.commercial.tags]` section
- **WHEN** the system loads the profile
- **THEN** the profile's tag config defaults to energy (low, mid, high), function (floorfiller, singalong, bridge, reset, closer, opener), crowd (mixed-age, older, younger, family), and mood_tags (feelgood, emotional, euphoric, nostalgic, romantic, melancholic, dark, aggressive, uplifting, dreamy, funky, groovy)

#### Scenario: Tag field defines type and valid values
- **GIVEN** a profile tags section with a field defined as `type = "list"`, `pick = [1, 3]`, `values = ["warm-up", "build", "peak-time"]`
- **WHEN** the system loads the profile
- **THEN** the field is parsed as a list-type field allowing 1 to 3 selections from the given values

#### Scenario: Tag field with single type
- **GIVEN** a profile tags section with a field defined as `type = "single"`, `values = ["low", "mid", "high"]`
- **WHEN** the system loads the profile
- **THEN** the field is parsed as a single-value field accepting exactly one of the given values

#### Scenario: Invalid tag field type
- **GIVEN** a profile tags section with a field defined as `type = "number"`
- **WHEN** the system validates the config on load
- **THEN** the system reports that the field type must be "single" or "list" and exits non-zero

#### Scenario: Empty values list
- **GIVEN** a profile tags section with a field defined as `values = []`
- **WHEN** the system validates the config on load
- **THEN** the system reports that a tag field must have at least one valid value and exits non-zero

#### Scenario: Classification guidance text
- **GIVEN** a profile tags section with `guidance = "Classify for a club DJ set."`
- **WHEN** the system loads the profile
- **THEN** the profile's tag config stores the guidance text for use in prompt generation

## MODIFIED Requirements

### Requirement: TOML config file with named profiles
The system SHALL load configuration from `~/.cratekeeper/config.toml` containing an `active_profile` key and one or more named `[profiles.<name>]` tables. Each profile defines its genre buckets (preset name or inline list), DJ software target, library output path, `data_dir`, admission criteria, sort rules, tag format, and optionally a `[profiles.<name>.tags]` section with per-profile tag field definitions and classification guidance.

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

#### Scenario: Profile with tags section loaded alongside other settings
- **GIVEN** a profile defines both standard settings (buckets, tag_format) and a `[profiles.<name>.tags]` section
- **WHEN** the system loads the profile
- **THEN** both the standard Profile fields and the TagConfig are resolved and available

### Requirement: Profile management subcommands
The system SHALL provide a `crate profile` command group with `list`, `show`, `use`, and `init` subcommands to inspect and manage profiles.

#### Scenario: List profiles
- **WHEN** the DJ runs `crate profile list`
- **THEN** the system prints every defined profile name and marks which one is currently active

#### Scenario: Show the effective resolved config
- **WHEN** the DJ runs `crate profile show electronic`
- **THEN** the system prints the fully resolved profile settings, including buckets resolved from any referenced preset, target path, `data_dir`, tag format, DJ software target, admission criteria, sort rules, and tag vocabulary with field names and valid values

#### Scenario: Switch the active profile
- **GIVEN** the config defines `commercial` and `electronic`
- **WHEN** the DJ runs `crate profile use electronic`
- **THEN** the system writes `active_profile = "electronic"` to the config file and confirms the change

#### Scenario: Initialise a config file
- **GIVEN** no `~/.cratekeeper/config.toml` exists
- **WHEN** the DJ runs `crate profile init`
- **THEN** the system scaffolds a config file with `commercial` and `electronic` example profiles including example tag vocabulary for each and reports the path it created

#### Scenario: Init does not clobber an existing config
- **GIVEN** a `~/.cratekeeper/config.toml` already exists
- **WHEN** the DJ runs `crate profile init`
- **THEN** the system refuses to overwrite it, reports that a config already exists, and exits non-zero
