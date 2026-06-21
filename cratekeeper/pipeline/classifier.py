"""Rule-based genre classification for tracks."""

from __future__ import annotations

import re

from cratekeeper.pipeline.genre_buckets import FALLBACK_BUCKET, GenreBucket, get_buckets
from cratekeeper.models import Track


def _word_match(tag: str, genre: str) -> bool:
    """Check if the bucket tag matches the track genre (case-insensitive).

    Exact match preferred. Partial matches only if tag is longer/more specific.
    We do NOT want "house" to match "progressive house" - that's too broad.
    But "progressive house" SHOULD match "progressive house".
    """
    tag_lower = tag.lower()
    genre_lower = genre.lower()
    
    # Exact match - always wins
    if tag_lower == genre_lower:
        return True
    
    # For partial matches: only match if the tag is MORE specific than the genre
    # e.g., tag="melodic techno" should NOT match genre="techno"
    # but tag="techno" COULD match genre="techno" (exact, already handled above)
    # We want to AVOID: tag="house" matching genre="progressive house"
    # 
    # Simple rule: if tag has fewer words than genre, it's too generic - don't match
    tag_words = tag_lower.split()
    genre_words = genre_lower.split()
    
    if len(tag_words) < len(genre_words):
        # Tag is shorter/more generic - don't match compounds
        return False
    
    # Tag is same length or longer - allow word boundary match
    # This handles cases like tag="progressive house techno" matching genre="progressive house"
    if re.search(rf'\b{re.escape(tag_lower)}\b', genre_lower):
        return True
    
    return False


def classify_track(
    track: Track,
    buckets: list[GenreBucket] | None = None,
    fallback: str = FALLBACK_BUCKET,
) -> tuple[str, str]:
    """Classify a single track into a genre bucket.

    Returns (bucket_name, confidence).
    Confidence: 
    - "high" if exactly one bucket matches
    - "low" if multiple buckets match (ambiguous, needs review) or no match (fallback)
    
    Checks all track genres against all bucket tags. If multiple buckets match,
    uses the first matching bucket but marks confidence as low to flag for review.
    """
    if buckets is None:
        buckets = get_buckets()

    genres_lower = [g.lower() for g in track.artist_genres]

    # Collect all matching buckets
    matching_buckets: list[str] = []
    
    for bucket in buckets:
        bucket_matches = False
        for genre in genres_lower:
            for tag in bucket.genre_tags:
                if _word_match(tag, genre):
                    bucket_matches = True
                    break
            if bucket_matches:
                break
        
        if bucket_matches:
            matching_buckets.append(bucket.name)

    # Determine confidence based on number of matches
    if len(matching_buckets) == 0:
        # No match - use fallback
        return fallback, "low"
    elif len(matching_buckets) == 1:
        # Single clear match - high confidence
        return matching_buckets[0], "high"
    else:
        # Multiple matches - ambiguous, use first but mark low confidence for review
        return matching_buckets[0], "low"


def classify_tracks(
    tracks: list[Track],
    buckets: list[GenreBucket] | None = None,
    fallback: str = FALLBACK_BUCKET,
) -> list[Track]:
    """Classify all tracks and set their bucket + confidence fields.

    Returns the same tracks list (mutated).
    """
    if buckets is None:
        buckets = get_buckets()

    for track in tracks:
        bucket_name, confidence = classify_track(track, buckets, fallback)
        track.bucket = bucket_name
        track.confidence = confidence
        track.era = track.compute_era()

    return tracks


def consolidate_small_buckets(
    tracks: list[Track],
    min_size: int = 3,
    fallback: str = FALLBACK_BUCKET,
) -> list[Track]:
    """Merge buckets with fewer than min_size tracks into the fallback bucket.

    Returns the same tracks list (mutated).
    """
    # Count tracks per bucket
    counts: dict[str, int] = {}
    for track in tracks:
        bucket = track.bucket or fallback
        counts[bucket] = counts.get(bucket, 0) + 1

    # Find small buckets
    small_buckets = {b for b, count in counts.items() if count < min_size and b != fallback}

    # Merge into fallback
    for track in tracks:
        if track.bucket in small_buckets:
            track.bucket = fallback
            track.confidence = "low"

    return tracks
