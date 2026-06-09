"""Helpers for master-library candidate selection and approval tracking."""

from __future__ import annotations

from cratekeeper.pipeline.tag_writer import is_fully_tagged
from cratekeeper.models import Track


def candidate_tracks(tracks: list[Track]) -> list[Track]:
    """Return tracks that are master-library candidates: both local_path and bucket are set."""
    return [t for t in tracks if t.local_path and t.bucket]


def undecided_candidates(tracks: list[Track]) -> list[Track]:
    """Return candidate tracks whose library_approval is still 'undecided'."""
    return [t for t in candidate_tracks(tracks) if t.library_approval == "undecided"]


def is_admission_complete(track: Track, required_fields: list[str] | None = None) -> bool:
    """Return True when the track satisfies the active profile's admission fields.

    Delegates to the shared library admission gate so review and build agree on
    what "fully tagged" means for the active profile.
    """
    return is_fully_tagged(track, required_fields)
