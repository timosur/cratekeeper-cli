"""Helpers for master-library candidate selection and approval tracking."""

from __future__ import annotations

from cratekeeper.models import Track


def candidate_tracks(tracks: list[Track]) -> list[Track]:
    """Return tracks that are master-library candidates: both local_path and bucket are set."""
    return [t for t in tracks if t.local_path and t.bucket]


def undecided_candidates(tracks: list[Track]) -> list[Track]:
    """Return candidate tracks whose library_approval is still 'undecided'."""
    return [t for t in candidate_tracks(tracks) if t.library_approval == "undecided"]
