"""Tests for the profile config system: loading, validation, resolution."""

from __future__ import annotations

from pathlib import Path

import pytest

from cratekeeper.config import (
    ConfigError,
    Profile,
    implicit_commercial_profile,
    load_settings,
    resolve_profile,
    set_active_profile,
    write_default_config,
)


def _write(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "config.toml"
    p.write_text(body)
    return p


# --- No config => implicit commercial profile ---

def test_no_config_returns_implicit_commercial(tmp_path: Path):
    missing = tmp_path / "nope.toml"
    assert load_settings(missing) is None
    prof = resolve_profile(None, config_path=missing)
    assert prof.name == "commercial"
    assert prof.tag_format == "structured_comment"
    assert prof.required_fields == ["energy", "function", "crowd", "mood_tags"]
    assert prof.fallback == "Unclassified"


def test_no_config_unknown_profile_errors(tmp_path: Path):
    missing = tmp_path / "nope.toml"
    with pytest.raises(ConfigError):
        resolve_profile("electronic", config_path=missing)


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


def test_implicit_commercial_matches_defaults():
    prof = implicit_commercial_profile()
    assert isinstance(prof, Profile)
    assert prof.dj_software == "djay_pro"
    assert prof.buckets  # non-empty
