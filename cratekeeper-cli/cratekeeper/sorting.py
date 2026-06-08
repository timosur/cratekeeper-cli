"""Profile-driven track sorting within genre buckets."""

from __future__ import annotations

from cratekeeper.config import SortRule  # re-exported companion type
from cratekeeper.models import Track

__all__ = ["SortRule", "sort_tracks"]

# Ordinal rank for the string ``energy`` field so it sorts numerically.
_ENERGY_RANK = {"low": 0, "mid": 1, "high": 2}


def _key_value(track: Track, key: str):
    """Return a (missing_flag, value) tuple so missing values always sort last."""
    if key == "energy":
        rank = _ENERGY_RANK.get(track.energy) if track.energy else None
        return (rank is None, rank if rank is not None else 0)

    value = getattr(track, key, None)
    if value is None or value == [] or value == "":
        return (True, 0)
    if isinstance(value, (list, dict)):
        # Non-scalar fields aren't meaningfully orderable; treat as present-but-equal.
        return (False, 0)
    return (False, value)


def sort_tracks(tracks: list[Track], sort) -> list[Track]:
    """Return a new list ordered by the given ``SortRule``.

    ``sort`` may be ``None`` (returns the list unchanged). Sorting is stable, so
    ties preserve the original order.
    """
    if sort is None or not sort.keys:
        return list(tracks)

    reverse = sort.direction == "desc"

    def sort_key(track: Track):
        return tuple(_key_value(track, key) for key in sort.keys)

    return sorted(tracks, key=sort_key, reverse=reverse)
