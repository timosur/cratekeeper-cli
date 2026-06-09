"""Genre-specific mood thresholds for DJ classification.

Data is loaded from ``cratekeeper/data/mood_config.yaml`` at import time.
Moods are determined by audio features (BPM, energy, danceability, etc.)
with thresholds that vary by genre.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from cratekeeper.data import load_mood_config


@dataclass
class MoodThresholds:
    """Thresholds for a single mood level within a genre."""

    name: str
    min_bpm: float = 0
    max_bpm: float = 999
    min_energy: float = 0
    max_energy: float = 1.0
    min_danceability: float = 0
    max_danceability: float = 1.0


def _build_threshold(d: dict) -> MoodThresholds:
    return MoodThresholds(
        name=d["name"],
        min_bpm=d.get("min_bpm", 0),
        max_bpm=d.get("max_bpm", 999),
        min_energy=d.get("min_energy", 0),
        max_energy=d.get("max_energy", 1.0),
        min_danceability=d.get("min_danceability", 0),
        max_danceability=d.get("max_danceability", 1.0),
    )


@lru_cache(maxsize=None)
def _config():
    raw = load_mood_config()
    rt_raw = raw.get("romantic_threshold", {})
    romantic = MoodThresholds(
        name="Romantic",
        max_bpm=rt_raw.get("max_bpm", 110),
        max_energy=rt_raw.get("max_energy", 0.3),
        max_danceability=rt_raw.get("max_danceability", 0.4),
    )
    default_moods = [_build_threshold(d) for d in raw.get("default_moods", [])]
    mood_profiles: dict[str, list[MoodThresholds]] = {
        genre: [_build_threshold(t) for t in thresholds]
        for genre, thresholds in raw.get("mood_profiles", {}).items()
    }
    return romantic, default_moods, mood_profiles


def _romantic_threshold() -> MoodThresholds:
    return _config()[0]


def _default_moods() -> list[MoodThresholds]:
    return _config()[1]


def _mood_profiles() -> dict[str, list[MoodThresholds]]:
    return _config()[2]


# ---------------------------------------------------------------------------
# Module-level constants (lazy, populated on first import)
# ---------------------------------------------------------------------------

def _init_constants() -> None:
    global ROMANTIC_THRESHOLD, DEFAULT_MOODS, MOOD_PROFILES
    ROMANTIC_THRESHOLD, DEFAULT_MOODS, MOOD_PROFILES = _config()


ROMANTIC_THRESHOLD: MoodThresholds = None  # type: ignore[assignment]
DEFAULT_MOODS: list[MoodThresholds] = None  # type: ignore[assignment]
MOOD_PROFILES: dict[str, list[MoodThresholds]] = None  # type: ignore[assignment]

_init_constants()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def classify_mood(bpm: float, energy: float, danceability: float, genre: str | None = None) -> str:
    """Classify a track's mood based on audio features and genre context."""
    rt = _romantic_threshold()
    if bpm <= rt.max_bpm and energy <= rt.max_energy and danceability <= rt.max_danceability:
        return "Romantic"

    thresholds = _mood_profiles().get(genre or "", _default_moods())

    for mood in reversed(thresholds):
        if (mood.min_bpm <= bpm <= mood.max_bpm
                and mood.min_energy <= energy <= mood.max_energy
                and mood.min_danceability <= danceability <= mood.max_danceability):
            return mood.name

    if energy >= 0.7:
        return "Energetic"
    elif energy >= 0.45:
        return "Groovy"
    elif energy >= 0.25:
        return "Warm-Up"
    return "Chill"


def classify_energy(energy_value: float) -> str:
    """Map raw 0-1 energy to low/mid/high."""
    if energy_value < 0.33:
        return "low"
    elif energy_value < 0.66:
        return "mid"
    return "high"
