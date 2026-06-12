"""Profile-based configuration system for Cratekeeper.

Loads a TOML config from ``$XDG_CONFIG_HOME/cratekeeper/config.toml``
(default: ``~/.config/cratekeeper/config.toml``) describing named profiles.
Each profile drives genre buckets, DJ-software target, library output path,
per-profile data directory, library admission criteria, track sort order, and
tag format.

When no config file exists the CLI uses an implicit ``commercial`` profile
that reproduces the historical hardcoded defaults, so existing behaviour is
preserved without any config.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from cratekeeper.pipeline.genre_buckets import GenreBucket, get_preset

_XDG_CONFIG = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
DEFAULT_CONFIG_PATH = _XDG_CONFIG / "cratekeeper" / "config.toml"

TAG_FORMATS = {"structured_comment", "id3_only"}
TAG_FIELD_TYPES = {"single", "list"}
DJ_SOFTWARE = {"djay_pro", "rekordbox"}
SORT_DIRECTIONS = {"asc", "desc"}
DEFAULT_REQUIRED_FIELDS = ["energy", "function", "crowd", "mood_tags"]
DEFAULT_LIBRARY_TARGET = Path.home() / "Music" / "Library"


@dataclass
class TagFieldDef:
    """Definition of a single tag field within a profile's vocabulary."""

    name: str
    type: str  # "single" | "list"
    values: list[str]
    pick: tuple[int, int] | None = None  # (min, max) for list fields


@dataclass
class TagConfig:
    """Per-profile tag vocabulary and classification guidance."""

    fields: dict[str, TagFieldDef] = field(default_factory=dict)
    guidance: str = ""


def default_tag_config() -> TagConfig:
    """Build the default TagConfig matching the legacy hardcoded vocabulary."""
    return TagConfig(
        fields={
            "energy": TagFieldDef(name="energy", type="single", values=["low", "mid", "high"]),
            "function": TagFieldDef(
                name="function", type="list",
                values=["floorfiller", "singalong", "bridge", "reset", "closer", "opener"],
                pick=(1, 3),
            ),
            "crowd": TagFieldDef(
                name="crowd", type="list",
                values=["mixed-age", "older", "younger", "family"],
                pick=(1, 2),
            ),
            "mood_tags": TagFieldDef(
                name="mood_tags", type="list",
                values=[
                    "feelgood", "emotional", "euphoric", "nostalgic",
                    "romantic", "melancholic", "dark", "aggressive",
                    "uplifting", "dreamy", "funky", "groovy",
                ],
                pick=(1, 4),
            ),
        },
        guidance=(
            "Classify tracks for a commercial DJ set (weddings, parties, corporate events). "
            "Consider energy, singability, crowd demographics, and emotional tone."
        ),
    )


class ConfigError(Exception):
    """Raised when the config file is malformed or invalid."""


DEFAULT_CONFIG_TEMPLATE = '''\
# Cratekeeper configuration
# The active profile is used when --profile is not passed on the command line.
active_profile = "commercial"

# Commercial profile: reproduces the default DJ-set behaviour (structured tags,
# djay Pro flat event folders, commercial genre buckets).
[profiles.commercial]
buckets = "commercial"           # preset name, or an inline list of bucket tables
dj_software = "djay_pro"
tag_format = "structured_comment"
library_target = "~/Music/Library"
required_fields = ["energy", "function", "crowd", "mood_tags"]

# Electronic profile: finer EDM buckets, Rekordbox target, ID3-only tags.
[profiles.electronic]
buckets = "electronic"
dj_software = "rekordbox"
tag_format = "structured_comment"
library_target = "~/Music/Library-Electronic"
required_fields = ["energy", "function", "mood_tags", "mix_traits"]

[profiles.electronic.sort]
keys = ["bpm"]
direction = "asc"

[profiles.electronic.tags]
guidance = "Classify for a club/festival DJ set. Think in terms of set position and energy arc."

[profiles.electronic.tags.fields.energy]
type = "single"
values = ["low", "mid", "high"]

[profiles.electronic.tags.fields.function]
type = "list"
pick = [1, 3]
values = ["warm-up", "build", "peak-time", "breakdown", "cooldown", "closer"]

[profiles.electronic.tags.fields.mood_tags]
type = "list"
pick = [1, 4]
values = ["hypnotic", "driving", "atmospheric", "deep", "acidic", "industrial", "melodic", "dark", "euphoric", "groovy"]

[profiles.electronic.tags.fields.mix_traits]
type = "list"
pick = [1, 3]
values = ["loop-friendly", "long-intro", "long-outro", "vocal", "instrumental", "acapella-section"]
'''


def _legacy_data_dir() -> Path:
    """The historical shared ``data/`` directory used before profiles existed."""
    return Path(__file__).resolve().parent.parent.parent / "data"


@dataclass
class SortRule:
    """Ordering rule for tracks within a genre bucket."""

    keys: list[str] = field(default_factory=list)
    direction: str = "asc"


@dataclass
class Profile:
    """A fully resolved profile that drives the whole pipeline."""

    name: str
    buckets: list[GenreBucket]
    fallback: str
    library_target: Path
    data_dir: Path
    required_fields: list[str] = field(default_factory=lambda: list(DEFAULT_REQUIRED_FIELDS))
    dj_software: str = "djay_pro"
    tag_format: str = "structured_comment"
    sort: SortRule | None = None
    tag_config: TagConfig = field(default_factory=default_tag_config)

    def plan_path(self, name: str) -> Path:
        """Return the default JSON plan path for a playlist or source name.

        Slugifies ``name`` to a safe 50-char filename and ensures the
        profile's ``data_dir`` exists. Used by ``fetch`` and ``import-library``
        to derive a consistent output path without duplicating the logic.
        """
        self.data_dir.mkdir(parents=True, exist_ok=True)
        safe_name = name.lower().replace(" ", "-").replace("/", "-")[:50]
        return self.data_dir / f"{safe_name}.json"

    def describe(self) -> dict:
        """Return a JSON-friendly summary for ``crate profile show``."""
        tag_vocab = {}
        for fname, fdef in self.tag_config.fields.items():
            entry: dict = {"type": fdef.type, "values": fdef.values}
            if fdef.pick:
                entry["pick"] = list(fdef.pick)
            tag_vocab[fname] = entry

        return {
            "name": self.name,
            "buckets": [b.name for b in self.buckets],
            "fallback": self.fallback,
            "library_target": str(self.library_target),
            "data_dir": str(self.data_dir),
            "required_fields": list(self.required_fields),
            "dj_software": self.dj_software,
            "tag_format": self.tag_format,
            "sort": None if self.sort is None else {"keys": list(self.sort.keys), "direction": self.sort.direction},
            "tag_vocabulary": tag_vocab,
            "tag_guidance": self.tag_config.guidance,
        }


@dataclass
class Settings:
    """Parsed config: a set of named profiles plus the active one."""

    profiles: dict[str, Profile] = field(default_factory=dict)
    active_profile: str | None = None


def implicit_commercial_profile() -> Profile:
    """Build the implicit ``commercial`` profile matching pre-profile defaults."""
    preset = get_preset("commercial")
    return Profile(
        name="commercial",
        buckets=list(preset.buckets),
        fallback=preset.fallback,
        library_target=DEFAULT_LIBRARY_TARGET,
        data_dir=_XDG_CONFIG / "cratekeeper" / "commercial" / "data",
        required_fields=list(DEFAULT_REQUIRED_FIELDS),
        dj_software="djay_pro",
        tag_format="structured_comment",
        sort=None,
        tag_config=default_tag_config(),
    )


def _parse_buckets(raw, profile_name: str) -> tuple[list[GenreBucket], str]:
    """Resolve a profile's ``buckets`` value into (buckets, default_fallback)."""
    if isinstance(raw, str):
        try:
            preset = get_preset(raw)
        except ValueError as exc:
            raise ConfigError(f"Profile {profile_name!r}: {exc}") from exc
        return list(preset.buckets), preset.fallback
    if isinstance(raw, list):
        buckets: list[GenreBucket] = []
        for entry in raw:
            if not isinstance(entry, dict) or "name" not in entry or "genre_tags" not in entry:
                raise ConfigError(
                    f"Profile {profile_name!r}: each inline bucket must define 'name' and 'genre_tags'"
                )
            buckets.append(GenreBucket(name=entry["name"], genre_tags=list(entry["genre_tags"])))
        if not buckets:
            raise ConfigError(f"Profile {profile_name!r}: inline buckets list is empty")
        return buckets, "Unclassified"
    raise ConfigError(
        f"Profile {profile_name!r}: 'buckets' must be a preset name or a list of bucket tables"
    )


def _parse_sort(raw, profile_name: str) -> SortRule | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ConfigError(f"Profile {profile_name!r}: 'sort' must be a table with 'keys' and 'direction'")
    keys = list(raw.get("keys", []))
    direction = raw.get("direction", "asc")
    if direction not in SORT_DIRECTIONS:
        raise ConfigError(
            f"Profile {profile_name!r}: sort direction {direction!r} must be one of {sorted(SORT_DIRECTIONS)}"
        )
    return SortRule(keys=keys, direction=direction)


def _parse_tag_config(raw: dict | None, profile_name: str) -> TagConfig:
    """Parse a ``[profiles.<name>.tags]`` TOML section into a TagConfig.

    Returns the default TagConfig when *raw* is None (section absent).
    """
    if raw is None:
        return default_tag_config()

    if not isinstance(raw, dict):
        raise ConfigError(f"Profile {profile_name!r}: 'tags' must be a table")

    guidance = raw.get("guidance", "")
    if not isinstance(guidance, str):
        raise ConfigError(f"Profile {profile_name!r}: tags.guidance must be a string")

    fields_raw = raw.get("fields", {})
    if not isinstance(fields_raw, dict):
        raise ConfigError(f"Profile {profile_name!r}: tags.fields must be a table")

    if not fields_raw:
        raise ConfigError(f"Profile {profile_name!r}: tags.fields must define at least one field")

    fields: dict[str, TagFieldDef] = {}
    for fname, fdef in fields_raw.items():
        if not isinstance(fdef, dict):
            raise ConfigError(f"Profile {profile_name!r}: tags.fields.{fname} must be a table")

        ftype = fdef.get("type", "list")
        if ftype not in TAG_FIELD_TYPES:
            raise ConfigError(
                f"Profile {profile_name!r}: tags.fields.{fname}.type {ftype!r} "
                f"must be one of {sorted(TAG_FIELD_TYPES)}"
            )

        values = fdef.get("values", [])
        if not isinstance(values, list) or not values:
            raise ConfigError(
                f"Profile {profile_name!r}: tags.fields.{fname}.values must be a non-empty list"
            )

        pick: tuple[int, int] | None = None
        pick_raw = fdef.get("pick")
        if pick_raw is not None:
            if not isinstance(pick_raw, list) or len(pick_raw) != 2:
                raise ConfigError(
                    f"Profile {profile_name!r}: tags.fields.{fname}.pick must be [min, max]"
                )
            pick = (int(pick_raw[0]), int(pick_raw[1]))
            if pick[0] < 1 or pick[1] < pick[0]:
                raise ConfigError(
                    f"Profile {profile_name!r}: tags.fields.{fname}.pick must satisfy 1 <= min <= max"
                )

        fields[fname] = TagFieldDef(name=fname, type=ftype, values=values, pick=pick)

    return TagConfig(fields=fields, guidance=guidance)


def _build_profile(name: str, raw: dict) -> Profile:
    """Build a Profile from a raw ``[profiles.<name>]`` table."""
    if not isinstance(raw, dict):
        raise ConfigError(f"Profile {name!r} must be a table")

    buckets_raw = raw.get("buckets", "commercial")
    buckets, default_fallback = _parse_buckets(buckets_raw, name)
    fallback = raw.get("fallback", default_fallback)

    dj_software = raw.get("dj_software", "djay_pro")
    if dj_software not in DJ_SOFTWARE:
        raise ConfigError(
            f"Profile {name!r}: dj_software {dj_software!r} must be one of {sorted(DJ_SOFTWARE)}"
        )

    tag_format = raw.get("tag_format", "structured_comment")
    if tag_format not in TAG_FORMATS:
        raise ConfigError(
            f"Profile {name!r}: tag_format {tag_format!r} must be one of {sorted(TAG_FORMATS)}"
        )

    library_target_raw = raw.get("library_target")
    library_target = (
        Path(library_target_raw).expanduser() if library_target_raw else DEFAULT_LIBRARY_TARGET
    )

    data_dir_raw = raw.get("data_dir")
    data_dir = (
        Path(data_dir_raw).expanduser()
        if data_dir_raw
        else _XDG_CONFIG / "cratekeeper" / name / "data"
    )

    required_fields = list(raw.get("required_fields", DEFAULT_REQUIRED_FIELDS))
    sort = _parse_sort(raw.get("sort"), name)
    tag_config = _parse_tag_config(raw.get("tags"), name)

    return Profile(
        name=name,
        buckets=buckets,
        fallback=fallback,
        library_target=library_target,
        data_dir=data_dir,
        required_fields=required_fields,
        dj_software=dj_software,
        tag_format=tag_format,
        sort=sort,
        tag_config=tag_config,
    )


def load_settings(config_path: Path | None = None) -> Settings | None:
    """Load and validate settings from the config file.

    Returns ``None`` when no config file exists. Raises :class:`ConfigError`
    on malformed TOML or invalid values.
    """
    path = config_path or DEFAULT_CONFIG_PATH
    if not path.exists():
        return None

    try:
        raw = tomllib.loads(path.read_text())
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"Failed to parse {path}: {exc}") from exc

    profiles_raw = raw.get("profiles", {})
    if not isinstance(profiles_raw, dict) or not profiles_raw:
        raise ConfigError(f"{path}: at least one [profiles.<name>] table is required")

    profiles = {name: _build_profile(name, body) for name, body in profiles_raw.items()}

    active = raw.get("active_profile")
    if active is not None and active not in profiles:
        raise ConfigError(
            f"active_profile {active!r} is not a defined profile (have: {', '.join(sorted(profiles))})"
        )

    return Settings(profiles=profiles, active_profile=active)


def resolve_profile(name: str | None = None, config_path: Path | None = None) -> Profile:
    """Resolve the active profile.

    Precedence: ``name`` (e.g. ``--profile``) -> config ``active_profile`` ->
    first defined profile.

    When no config file exists, writes the default config automatically and
    uses its first profile (commercial).
    """
    path = config_path or DEFAULT_CONFIG_PATH
    settings = load_settings(path)

    if settings is None:
        # No config exists — write defaults and load them
        write_default_config(path)
        settings = load_settings(path)
        if settings is None:
            raise ConfigError("Failed to create default config. Check permissions.")

    if name is not None:
        if name not in settings.profiles:
            raise ConfigError(
                f"Profile {name!r} is not defined (have: {', '.join(sorted(settings.profiles))})"
            )
        return settings.profiles[name]

    if settings.active_profile is not None:
        return settings.profiles[settings.active_profile]

    # First defined profile (insertion order preserved by dict).
    return next(iter(settings.profiles.values()))


def active_profile_name(settings: Settings) -> str:
    """Return the effectively active profile name (active_profile or first defined)."""
    if settings.active_profile is not None:
        return settings.active_profile
    return next(iter(settings.profiles))


def write_default_config(config_path: Path | None = None) -> Path:
    """Scaffold a config file with commercial + electronic profiles.

    Refuses to overwrite an existing file.
    """
    path = config_path or DEFAULT_CONFIG_PATH
    if path.exists():
        raise ConfigError(f"Config already exists at {path}; refusing to overwrite.")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(DEFAULT_CONFIG_TEMPLATE)
    return path


def set_active_profile(name: str, config_path: Path | None = None) -> Path:
    """Update ``active_profile`` in the config file. Validates the name exists."""
    import re

    path = config_path or DEFAULT_CONFIG_PATH
    settings = load_settings(path)
    if settings is None:
        raise ConfigError("No config file exists. Run 'crate profile init' first.")
    if name not in settings.profiles:
        raise ConfigError(
            f"Profile {name!r} is not defined (have: {', '.join(sorted(settings.profiles))})"
        )

    text = path.read_text()
    new_line = f'active_profile = "{name}"'
    if re.search(r"(?m)^\s*active_profile\s*=.*$", text):
        text = re.sub(r"(?m)^\s*active_profile\s*=.*$", new_line, text, count=1)
    else:
        text = new_line + "\n" + text
    path.write_text(text)
    return path
