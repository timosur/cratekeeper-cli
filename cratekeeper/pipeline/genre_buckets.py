"""Genre bucket definitions for DJ playlist classification.

Data is loaded from ``cratekeeper/data/genre_buckets.yaml`` at import time.
Each bucket has:
- name: display name used in playlists and folder structure
- genre_tags: partial matches against Spotify artist genre strings

Buckets are checked in list order (first match wins).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache

from cratekeeper.data import load_genre_buckets


@dataclass
class GenreBucket:
    name: str
    genre_tags: list[str]


@dataclass
class BucketPreset:
    """A named, ordered set of genre buckets with its own fallback bucket."""

    name: str
    buckets: list[GenreBucket] = field(default_factory=list)
    fallback: str = "Pop"


def _build_presets() -> dict[str, BucketPreset]:
    """Build the PRESETS dict from YAML data."""
    raw = load_genre_buckets()
    result: dict[str, BucketPreset] = {}
    for preset_name, preset_data in raw.get("presets", {}).items():
        buckets = [
            GenreBucket(name=b["name"], genre_tags=b["genre_tags"])
            for b in preset_data.get("buckets", [])
        ]
        result[preset_name] = BucketPreset(
            name=preset_name,
            buckets=buckets,
            fallback=preset_data.get("fallback", "Pop"),
        )
    return result


@lru_cache(maxsize=None)
def _presets() -> dict[str, BucketPreset]:
    return _build_presets()


# ---------------------------------------------------------------------------
# Public constants (computed from YAML on first access)
# ---------------------------------------------------------------------------

@property  # type: ignore[misc]
def DEFAULT_BUCKETS() -> list[GenreBucket]:  # noqa: N802
    return _presets()["commercial"].buckets


@property  # type: ignore[misc]
def FALLBACK_BUCKET() -> str:  # noqa: N802
    return _presets()["commercial"].fallback


# Module-level constants for backward compat (lazy, evaluated on first import of the module)
def _get_default_buckets() -> list[GenreBucket]:
    return _presets()["commercial"].buckets


DEFAULT_BUCKETS: list[GenreBucket] = None  # type: ignore[assignment]  # populated below
FALLBACK_BUCKET: str = None  # type: ignore[assignment]


def _init_module_constants() -> None:
    global DEFAULT_BUCKETS, FALLBACK_BUCKET
    p = _presets()
    DEFAULT_BUCKETS = p["commercial"].buckets
    FALLBACK_BUCKET = p["commercial"].fallback


_init_module_constants()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_preset(name: str) -> BucketPreset:
    """Return the named preset, raising a clear error if it is unknown."""
    presets = _presets()
    try:
        return presets[name]
    except KeyError:
        known = ", ".join(sorted(presets))
        raise ValueError(f"Unknown genre bucket preset {name!r}. Known presets: {known}")


def get_buckets(profile=None) -> list[GenreBucket]:
    """Return buckets in check order for the given profile.

    If ``profile`` is None, returns the default ``commercial`` buckets.
    """
    if profile is None:
        return list(DEFAULT_BUCKETS)
    return list(profile.buckets)


def get_fallback(profile=None) -> str:
    """Return the fallback bucket name for the given profile."""
    if profile is None:
        return FALLBACK_BUCKET
    return profile.fallback
