# Audio Analysis

## Purpose

Analyzes matched audio files to extract objective audio features (BPM, key, energy, danceability, loudness, mood) using essentia and TensorFlow models, running inside a Docker container on Linux x86_64.

## Requirements

### Requirement: Analyze audio features of matched tracks
The system SHALL analyze each matched audio file to extract BPM, musical key, energy, danceability, loudness, and mood descriptors using essentia and pre-trained TensorFlow models.

#### Scenario: Full audio analysis
- **WHEN** the DJ runs `crate analyze-mood` on a plan with matched tracks
- **THEN** the system extracts BPM, key, energy, danceability, loudness, and mood predictions for each matched track and persists them in the plan JSON

#### Scenario: Docker execution
- **WHEN** the analysis command runs
- **THEN** the system executes inside the provided Docker image (Linux x86_64 with essentia-tensorflow) since the models require that environment

#### Scenario: TensorFlow model auto-download
- **WHEN** the Docker image is built or the analysis runs for the first time
- **THEN** the system downloads the required pre-trained TensorFlow models (~300 MB) automatically

#### Scenario: Mood classification
- **WHEN** audio analysis completes
- **THEN** the system produces mood labels using genre-specific thresholds (BPM/energy/danceability ranges for Chill, Warm-Up, Groovy, Energetic, Peak per genre)

#### Scenario: Voice/instrumental detection
- **WHEN** audio analysis runs
- **THEN** the system detects whether the track is primarily vocal or instrumental and records the result

#### Scenario: Unmatched track skipped
- **WHEN** a track has no `local_path`
- **THEN** the system skips analysis for that track without error
