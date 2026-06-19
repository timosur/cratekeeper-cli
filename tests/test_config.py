"""Tests for the profile config system: loading, validation, resolution."""

from __future__ import annotations

from pathlib import Path

import pytest

from cratekeeper.config import (
    ConfigError,
    Profile,
    TagConfig,
    TagFieldDef,
    _parse_tag_config,
    default_tag_config,
    load_settings,
    resolve_profile,
    set_active_profile,
    write_default_config,
)


def _write(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "config.toml"
    p.write_text(body)
    return p


# --- No config => auto-write default config ---

def test_no_config_auto_writes_default_and_uses_commercial(tmp_path: Path):
    missing = tmp_path / "config.toml"
    assert not missing.exists()
    prof = resolve_profile(None, config_path=missing)
    # Config was written automatically
    assert missing.exists()
    assert prof.name == "commercial"
    assert prof.tag_format == "structured_comment"
    assert prof.required_fields == ["energy", "function", "crowd", "mood_tags"]
    assert prof.fallback == "Unclassified"


def test_no_config_unknown_profile_errors(tmp_path: Path):
    missing = tmp_path / "config.toml"
    # auto-init writes commercial + electronic; requesting an unknown name still errors
    with pytest.raises(ConfigError):
        resolve_profile("nonexistent", config_path=missing)


# --- Loading + validation ---

def test_invalid_toml_raises(tmp_path: Path):
    path = _write(tmp_path, "this is = = not valid toml [[[")
    with pytest.raises(ConfigError):
        load_settings(path)


def test_unknown_preset_raises(tmp_path: Path):
    path = _write(tmp_path, '[profiles.x]\nbuckets = "trance"\n')
    with pytest.raises(ConfigError):
        load_settings(path)


def test_bad_dj_software_raises(tmp_path: Path):
    path = _write(tmp_path, '[profiles.x]\nbuckets = "commercial"\ndj_software = "serato"\n')
    with pytest.raises(ConfigError):
        load_settings(path)


def test_bad_tag_format_raises(tmp_path: Path):
    path = _write(tmp_path, '[profiles.x]\nbuckets = "commercial"\ntag_format = "weird"\n')
    with pytest.raises(ConfigError):
        load_settings(path)


def test_active_profile_unknown_raises(tmp_path: Path):
    path = _write(tmp_path, 'active_profile = "ghost"\n[profiles.x]\nbuckets = "commercial"\n')
    with pytest.raises(ConfigError):
        load_settings(path)


# --- Resolution precedence ---

def test_override_takes_precedence(tmp_path: Path):
    path = _write(
        tmp_path,
        'active_profile = "commercial"\n'
        '[profiles.commercial]\nbuckets = "commercial"\n'
        '[profiles.electronic]\nbuckets = "electronic"\n',
    )
    assert resolve_profile("electronic", config_path=path).name == "electronic"
    assert resolve_profile(None, config_path=path).name == "commercial"


def test_override_unknown_profile_errors(tmp_path: Path):
    path = _write(
        tmp_path,
        '[profiles.commercial]\nbuckets = "commercial"\n[profiles.electronic]\nbuckets = "electronic"\n',
    )
    with pytest.raises(ConfigError):
        resolve_profile("studio", config_path=path)


def test_first_profile_when_no_active(tmp_path: Path):
    path = _write(
        tmp_path,
        '[profiles.alpha]\nbuckets = "commercial"\n[profiles.beta]\nbuckets = "electronic"\n',
    )
    assert resolve_profile(None, config_path=path).name == "alpha"


# --- Inline buckets + sort + required_fields ---

def test_inline_buckets_and_sort(tmp_path: Path):
    path = _write(
        tmp_path,
        '[profiles.x]\n'
        'required_fields = ["energy"]\n'
        'buckets = [{ name = "Bass", genre_tags = ["dubstep", "dnb"] }]\n'
        '[profiles.x.sort]\nkeys = ["bpm"]\ndirection = "desc"\n',
    )
    prof = resolve_profile("x", config_path=path)
    assert [b.name for b in prof.buckets] == ["Bass"]
    assert prof.required_fields == ["energy"]
    assert prof.sort.keys == ["bpm"]
    assert prof.sort.direction == "desc"


def test_bad_sort_direction_raises(tmp_path: Path):
    path = _write(
        tmp_path,
        '[profiles.x]\nbuckets = "commercial"\n[profiles.x.sort]\nkeys = ["bpm"]\ndirection = "sideways"\n',
    )
    with pytest.raises(ConfigError):
        load_settings(path)


# --- init + use ---

def test_write_default_config_and_use(tmp_path: Path):
    path = tmp_path / "config.toml"
    write_default_config(path)
    assert path.exists()
    # Refuses to overwrite
    with pytest.raises(ConfigError):
        write_default_config(path)

    settings = load_settings(path)
    assert set(settings.profiles) == {"commercial", "electronic"}
    assert settings.active_profile == "commercial"

    set_active_profile("electronic", config_path=path)
    assert load_settings(path).active_profile == "electronic"


def test_set_active_unknown_profile_raises(tmp_path: Path):
    path = tmp_path / "config.toml"
    write_default_config(path)
    with pytest.raises(ConfigError):
        set_active_profile("ghost", config_path=path)


def test_default_config_commercial_matches_expected(tmp_path: Path):
    missing = tmp_path / "config.toml"
    prof = resolve_profile(None, config_path=missing)
    assert isinstance(prof, Profile)
    assert prof.dj_software == "djay_pro"
    assert prof.buckets  # non-empty


# --- TagConfig parsing ---

def test_parse_tag_config_electronic(tmp_path: Path):
    """7.1: _parse_tag_config with valid electronic config."""
    raw = {
        "guidance": "Classify for a club DJ set.",
        "fields": {
            "energy": {"type": "single", "values": ["low", "mid", "high"]},
            "function": {"type": "list", "pick": [1, 3], "values": ["warm-up", "build", "peak-time"]},
            "mood_tags": {"type": "list", "pick": [1, 4], "values": ["hypnotic", "driving", "dark"]},
            "mix_traits": {"type": "list", "pick": [1, 3], "values": ["loop-friendly", "long-intro"]},
        },
    }
    tc = _parse_tag_config(raw, "electronic")
    assert tc.guidance == "Classify for a club DJ set."
    assert len(tc.fields) == 4
    assert tc.fields["energy"].type == "single"
    assert tc.fields["function"].pick == (1, 3)
    assert "loop-friendly" in tc.fields["mix_traits"].values


def test_parse_tag_config_missing_section_returns_defaults():
    """7.2: _parse_tag_config with None returns defaults."""
    tc = _parse_tag_config(None, "commercial")
    default = default_tag_config()
    assert tc.fields.keys() == default.fields.keys()
    assert tc.fields["energy"].values == default.fields["energy"].values


def test_parse_tag_config_invalid_type_raises():
    """7.3: config validation rejects invalid type."""
    raw = {"fields": {"x": {"type": "number", "values": ["a", "b"]}}}
    with pytest.raises(ConfigError, match="must be one of"):
        _parse_tag_config(raw, "test")


def test_parse_tag_config_empty_values_raises():
    """7.3: config validation rejects empty values."""
    raw = {"fields": {"x": {"type": "single", "values": []}}}
    with pytest.raises(ConfigError, match="non-empty list"):
        _parse_tag_config(raw, "test")


def test_parse_tag_config_bad_pick_raises():
    """7.3: config validation rejects bad pick ranges."""
    raw = {"fields": {"x": {"type": "list", "values": ["a"], "pick": [3, 1]}}}
    with pytest.raises(ConfigError, match="1 <= min <= max"):
        _parse_tag_config(raw, "test")


def test_parse_tag_config_no_fields_raises():
    """7.3: config validation rejects tags section with no fields."""
    raw = {"fields": {}}
    with pytest.raises(ConfigError, match="at least one field"):
        _parse_tag_config(raw, "test")


def test_electronic_profile_has_tag_config(tmp_path: Path):
    """Default config template electronic profile parses tag config."""
    path = tmp_path / "config.toml"
    write_default_config(path)
    prof = resolve_profile("electronic", config_path=path)
    assert "function" in prof.tag_config.fields
    assert "warm-up" in prof.tag_config.fields["function"].values
    assert "mix_traits" in prof.tag_config.fields
    assert prof.tag_config.guidance != ""


def test_commercial_profile_uses_defaults(tmp_path: Path):
    """Commercial profile without tags section gets default vocabulary."""
    path = tmp_path / "config.toml"
    write_default_config(path)
    prof = resolve_profile("commercial", config_path=path)
    assert "crowd" in prof.tag_config.fields
    assert "floorfiller" in prof.tag_config.fields["function"].values


def test_profile_describe_includes_tag_vocab(tmp_path: Path):
    """Profile.describe() includes tag vocabulary and guidance."""
    path = tmp_path / "config.toml"
    write_default_config(path)
    prof = resolve_profile("electronic", config_path=path)
    desc = prof.describe()
    assert "tag_vocabulary" in desc
    assert "mix_traits" in desc["tag_vocabulary"]
    assert "tag_guidance" in desc


# --- library_structure ---

def test_library_structure_defaults_to_genre_artist(tmp_path: Path):
    path = _write(tmp_path, '[profiles.x]\nbuckets = "commercial"\n')
    prof = resolve_profile("x", config_path=path)
    assert prof.library_structure == "genre_artist"


def test_library_structure_parsed_from_config(tmp_path: Path):
    path = _write(
        tmp_path,
        '[profiles.x]\nbuckets = "commercial"\nlibrary_structure = "genre_year_month"\n',
    )
    prof = resolve_profile("x", config_path=path)
    assert prof.library_structure == "genre_year_month"


def test_bad_library_structure_raises(tmp_path: Path):
    path = _write(
        tmp_path,
        '[profiles.x]\nbuckets = "commercial"\nlibrary_structure = "invalid"\n',
    )
    with pytest.raises(ConfigError, match="library_structure"):
        load_settings(path)


def test_default_config_electronic_has_genre_year_month(tmp_path: Path):
    path = tmp_path / "config.toml"
    write_default_config(path)
    prof = resolve_profile("electronic", config_path=path)
    assert prof.library_structure == "genre_year_month"


def test_default_config_commercial_has_genre_artist(tmp_path: Path):
    path = tmp_path / "config.toml"
    write_default_config(path)
    prof = resolve_profile("commercial", config_path=path)
    assert prof.library_structure == "genre_artist"
