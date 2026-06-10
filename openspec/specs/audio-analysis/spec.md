# Audio Analysis

## Purpose

Analyzes matched audio files to extract objective audio features (BPM, key, energy, danceability, loudness, mood) using essentia and TensorFlow models, running natively via pip-installed essentia-tensorflow on macOS Apple Silicon or Linux x86_64.

## Requirements

### Requirement: Analyze audio features of matched tracks
The system SHALL analyze each matched audio file to extract BPM, musical key, energy, danceability, loudness, and mood descriptors using essentia and pre-trained TensorFlow models, running natively via pip-installed essentia-tensorflow on macOS Apple Silicon or Linux x86_64.

#### Scenario: Full audio analysis
- **WHEN** the DJ runs `crate analyze-mood` on a plan with matched tracks
- **THEN** the system extracts BPM, key, energy, danceability, loudness, and mood predictions for each matched track and persists them in the plan JSON

#### Scenario: Native execution
- **WHEN** the analysis command runs
- **THEN** the system executes natively using pip-installed essentia-tensorflow without requiring Docker or container emulation

#### Scenario: TensorFlow model auto-download
- **WHEN** the analysis runs for the first time and models are not cached locally
- **THEN** the system downloads the required pre-trained TensorFlow models (~300 MB) to `~/.cache/cratekeeper/models` automatically
- **AND** subsequent runs reuse the cached models without network access

#### Scenario: Mood classification
- **WHEN** audio analysis completes
- **THEN** the system produces mood labels using genre-specific thresholds (BPM/energy/danceability ranges for Chill, Warm-Up, Groovy, Energetic, Peak per genre)

#### Scenario: Voice/instrumental detection
- **WHEN** audio analysis runs
- **THEN** the system detects whether the track is primarily vocal or instrumental and records the result

#### Scenario: Unmatched track skipped
- **WHEN** a track has no `local_path`
- **THEN** the system skips analysis for that track without error

#### Scenario: essentia-tensorflow not installed
- **GIVEN** essentia-tensorflow is not installed in the Python environment
- **WHEN** the DJ runs `crate analyze-mood`
- **THEN** the system raises an ImportError with a message directing the user to run `pip install essentia-tensorflow`
