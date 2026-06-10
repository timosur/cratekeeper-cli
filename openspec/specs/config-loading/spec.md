# Config Loading

## Purpose

Defines how configuration data (genre buckets, mood parameters) is loaded from bundled YAML files at import time, replacing hardcoded Python literals with external data files.

## Requirements

### Requirement: Genre buckets loaded from YAML
Rule: System MUST satisfy this requirement.
Feature: Genre bucket configuration loaded from YAML data file
Rule: Genre bucket definitions are read from `cratekeeper/data/genre_buckets.yaml` at import time; no genre bucket data is hardcoded in Python source.

#### Scenario: Genre buckets load successfully from the bundled YAML file
- **GIVEN** the `cratekeeper` package is installed
- **WHEN** the classifier module is imported
- **THEN** genre bucket definitions are available in memory
- **AND** no Python dict literal in source code defines the bucket structure

#### Scenario: Missing genre buckets YAML raises a clear error
- **GIVEN** `genre_buckets.yaml` is absent from the package data
- **WHEN** the classifier module is imported
- **THEN** a `FileNotFoundError` or `PackageDataError` is raised with a message identifying the missing file

#### Scenario: Genre bucket YAML is included in the installed package
- **GIVEN** the package is installed via `pip install`
- **WHEN** `importlib.resources.files("cratekeeper.data").joinpath("genre_buckets.yaml")` is called
- **THEN** the file is accessible without referencing a filesystem path

### Requirement: Mood config loaded from YAML
Rule: System MUST satisfy this requirement.
Feature: Mood analysis configuration loaded from YAML data file
Rule: Mood model parameters and thresholds are read from `cratekeeper/data/mood_config.yaml` at import time; no mood config data is hardcoded in Python source.

#### Scenario: Mood config loads successfully from the bundled YAML file
- **GIVEN** the `cratekeeper` package is installed
- **WHEN** the mood analyzer module is imported
- **THEN** mood model configuration is available in memory
- **AND** no Python dict literal in source code defines the mood config structure

#### Scenario: Missing mood config YAML raises a clear error
- **GIVEN** `mood_config.yaml` is absent from the package data
- **WHEN** the mood analyzer module is imported
- **THEN** a `FileNotFoundError` or `PackageDataError` is raised with a message identifying the missing file

### Requirement: Config data is cached after first load
Rule: System MUST satisfy this requirement.
Rule: YAML data files are parsed once per process; repeated imports do not re-read the file.

#### Scenario: Genre buckets parsed only once per process
- **GIVEN** the classifier module has already been imported
- **WHEN** genre bucket data is accessed multiple times in the same process
- **THEN** the YAML file is read from disk exactly once
