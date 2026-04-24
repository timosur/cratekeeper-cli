"""Rule-based genre classification for tracks."""

from __future__ import annotations

import re

from cratekeeper.genre_buckets import FALLBACK_BUCKET, GenreBucket, get_buckets
from cratekeeper.models import Track


def _word_match(tag: str, genre: str) -> bool:
    """Check if the bucket tag matches the track genre.

    The tag must appear as a whole word/phrase within the genre string.
    We do NOT match in reverse (a short genre like "dance" should not match
    a compound tag like "indie dance").
    """
    if tag == genre:
        return True
    # tag appears as a whole word in the genre
    if re.search(rf'\b{re.escape(tag)}\b', genre):
        return True
    return False


def classify_track(track: Track, buckets: list[GenreBucket] | None = None) -> tuple[str, str]:
    """Classify a single track into a genre bucket.

    Returns (bucket_name, confidence).
    Confidence: "high" if genre tags match, "low" if fallback.
    Buckets are checked in list order (first match wins).
    """
    if buckets is None:
        buckets = get_buckets()

    genres_lower = [g.lower() for g in track.artist_genres]

    # Match genre tags (list order = specificity order)
    for bucket in buckets:
        for tag in bucket.genre_tags:
            for genre in genres_lower:
                if _word_match(tag, genre):
                    return bucket.name, "high"

    # Fallback
    return FALLBACK_BUCKET, "low"


def classify_tracks(tracks: list[Track], buckets: list[GenreBucket] | None = None) -> list[Track]:
    """Classify all tracks and set their bucket + confidence fields.

    Returns the same tracks list (mutated).
    """
    if buckets is None:
        buckets = get_buckets()

    for track in tracks:
        bucket_name, confidence = classify_track(track, buckets)
        track.bucket = bucket_name
        track.confidence = confidence
        track.era = track.compute_era()

    return tracks


def consolidate_small_buckets(tracks: list[Track], min_size: int = 3) -> list[Track]:
    """Merge buckets with fewer than min_size tracks into the fallback bucket.

    Returns the same tracks list (mutated).
    """
    # Count tracks per bucket
    counts: dict[str, int] = {}
    for track in tracks:
        bucket = track.bucket or FALLBACK_BUCKET
        counts[bucket] = counts.get(bucket, 0) + 1

    # Find small buckets
    small_buckets = {b for b, count in counts.items() if count < min_size and b != FALLBACK_BUCKET}

    # Merge into fallback
    for track in tracks:
        if track.bucket in small_buckets:
            track.bucket = FALLBACK_BUCKET
            track.confidence = "low"

    return tracks
