"""Bundled data files and loaders for cratekeeper.

YAML data lives alongside this package and is loaded via ``importlib.resources``
so it works whether running from a source checkout or an installed wheel.
"""

from __future__ import annotations

from functools import lru_cache
from importlib.resources import files
from typing import Any

import yaml


def _load_yaml(name: str) -> dict[str, Any]:
    """Load a YAML file bundled in this package by file name."""
    resource = files(__name__).joinpath(name)
    with resource.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    return data or {}


@lru_cache(maxsize=None)
def load_genre_buckets() -> dict[str, Any]:
    """Return the parsed ``genre_buckets.yaml`` contents."""
    return _load_yaml("genre_buckets.yaml")


@lru_cache(maxsize=None)
def load_mood_config() -> dict[str, Any]:
    """Return the parsed ``mood_config.yaml`` contents."""
    return _load_yaml("mood_config.yaml")


__all__ = ["load_genre_buckets", "load_mood_config"]
