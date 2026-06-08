"""Genre bucket definitions for DJ playlist classification.

Each bucket has:
- name: display name used in playlists and folder structure
- genre_tags: partial matches against Spotify artist genre strings

Buckets are checked in list order (first match wins).
Most specific genres are listed first, broadest/fallback last.
Era (80s, 90s, etc.) is NOT a genre — it's derived from release_year
and stored as a comment tag.
"""

from __future__ import annotations

from dataclasses import dataclass, field


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


# Ordered: most specific first, broadest/fallback last.
# The classifier iterates top-to-bottom; first tag match wins.
DEFAULT_BUCKETS: list[GenreBucket] = [
    # --- Specific genres (checked first) ---
    GenreBucket(
        name="Schlager",
        genre_tags=["schlager", "german schlager", "discofox", "volksmusik"],
    ),
    # --- Electronic sub-genres (specific → broad) ---
    GenreBucket(
        name="Drum & Bass",
        genre_tags=["drum and bass", "jungle", "liquid dnb", "liquid funk", "dnb"],
    ),
    GenreBucket(
        name="Hardstyle",
        genre_tags=["hardstyle", "hardcore", "gabber"],
    ),
    GenreBucket(
        name="Melodic Techno",
        genre_tags=["melodic techno", "indie dance"],
    ),
    GenreBucket(
        name="Techno",
        genre_tags=["techno", "hard techno", "industrial techno"],
    ),
    GenreBucket(
        name="Minimal / Tech House",
        genre_tags=["minimal techno", "tech house", "minimal"],
    ),
    GenreBucket(
        name="Deep House",
        genre_tags=["deep house", "organic house", "tropical house"],
    ),
    GenreBucket(
        name="Progressive House",
        genre_tags=["progressive house", "progressive trance"],
    ),
    GenreBucket(
        name="Trance",
        genre_tags=["trance", "psytrance", "uplifting trance"],
    ),
    GenreBucket(
        name="House",
        genre_tags=["house", "electro house", "funky house", "uk garage"],
    ),
    GenreBucket(
        name="EDM / Big Room",
        genre_tags=["edm", "big room", "electro"],
    ),
    GenreBucket(
        name="Dance / Hands Up",
        genre_tags=["dance", "hands up", "eurodance"],
    ),
    # --- General genres ---
    GenreBucket(
        name="Hip-Hop / R&B",
        genre_tags=[
            "hip hop", "rap", "r&b", "trap", "urban contemporary",
            "german hip hop", "gangster rap", "g-funk", "west coast hip hop",
        ],
    ),
    GenreBucket(
        name="Latin / Global",
        genre_tags=["reggaeton", "latin", "salsa", "bachata", "latin pop"],
    ),
    GenreBucket(
        name="Disco / Funk / Soul",
        genre_tags=[
            "disco", "funk", "soul", "motown", "boogie",
            "classic soul", "nu disco", "italo disco",
        ],
    ),
    GenreBucket(
        name="Rock",
        genre_tags=[
            "rock", "classic rock", "indie", "alternative", "punk",
            "indie rock", "indie pop", "new wave", "post-punk",
        ],
    ),
    GenreBucket(
        name="Ballads / Slow",
        genre_tags=["ballad", "slow", "acoustic", "singer-songwriter"],
    ),
    # --- Catch-all (checked last) ---
    GenreBucket(
        name="Pop",
        genre_tags=[
            "pop", "dance pop", "europop", "german pop",
            "soft pop", "viral pop", "party",
        ],
    ),
]

FALLBACK_BUCKET = "Pop"


# Electronic-focused preset: finer EDM sub-genre granularity, House fallback,
# and no commercial genres (Schlager, Pop, Rock, Latin, Ballads, Disco).
ELECTRONIC_BUCKETS: list[GenreBucket] = [
    GenreBucket(
        name="Drum & Bass",
        genre_tags=["drum and bass", "jungle", "liquid dnb", "liquid funk", "dnb", "neurofunk"],
    ),
    GenreBucket(
        name="Hardstyle / Hardcore",
        genre_tags=["hardstyle", "hardcore", "gabber", "rawstyle", "hard dance"],
    ),
    GenreBucket(
        name="Dubstep / Bass",
        genre_tags=["dubstep", "bass music", "future bass", "riddim", "trap"],
    ),
    GenreBucket(
        name="Melodic Techno",
        genre_tags=["melodic techno", "melodic house", "indie dance"],
    ),
    GenreBucket(
        name="Techno",
        genre_tags=["techno", "hard techno", "industrial techno", "peak time techno"],
    ),
    GenreBucket(
        name="Minimal / Tech House",
        genre_tags=["minimal techno", "tech house", "minimal"],
    ),
    GenreBucket(
        name="Deep House",
        genre_tags=["deep house", "organic house", "tropical house", "afro house"],
    ),
    GenreBucket(
        name="Progressive House",
        genre_tags=["progressive house", "progressive trance"],
    ),
    GenreBucket(
        name="Trance",
        genre_tags=["trance", "psytrance", "uplifting trance", "goa"],
    ),
    GenreBucket(
        name="EDM / Big Room",
        genre_tags=["edm", "big room", "electro", "future house", "bigroom"],
    ),
    GenreBucket(
        name="Disco / Nu Disco",
        genre_tags=["nu disco", "disco", "italo disco", "funk", "boogie"],
    ),
    # --- Catch-all (checked last) ---
    GenreBucket(
        name="House",
        genre_tags=["house", "electro house", "funky house", "uk garage", "garage", "dance"],
    ),
]


# Registry of named presets. Profiles reference a preset by name or define
# their own inline bucket list.
PRESETS: dict[str, BucketPreset] = {
    "commercial": BucketPreset(name="commercial", buckets=DEFAULT_BUCKETS, fallback=FALLBACK_BUCKET),
    "electronic": BucketPreset(name="electronic", buckets=ELECTRONIC_BUCKETS, fallback="House"),
}


def get_preset(name: str) -> BucketPreset:
    """Return the named preset, raising a clear error if it is unknown."""
    try:
        return PRESETS[name]
    except KeyError:
        known = ", ".join(sorted(PRESETS))
        raise ValueError(f"Unknown genre bucket preset {name!r}. Known presets: {known}")


def get_buckets(profile=None) -> list[GenreBucket]:
    """Return buckets in check order (first match wins) for the given profile.

    If ``profile`` is None, returns the default ``commercial`` buckets, preserving
    the historical behaviour for callers that do not supply a profile.
    """
    if profile is None:
        return list(DEFAULT_BUCKETS)
    return list(profile.buckets)


def get_fallback(profile=None) -> str:
    """Return the fallback bucket name for the given profile."""
    if profile is None:
        return FALLBACK_BUCKET
    return profile.fallback
