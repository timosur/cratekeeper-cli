"""Match Spotify tracks to local audio files using a TrackRepository."""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from thefuzz import fuzz

from cratekeeper.local.repository import TrackRepository
from cratekeeper.local.scanner import DEFAULT_DB_URL
from cratekeeper.models import Track


def _normalize(text: str) -> str:
    """Normalize a string for comparison: lowercase, strip accents, remove punctuation."""
    text = text.lower().strip()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    # Remove common suffixes that differ between platforms
    text = re.sub(r"\s*[-–—]\s*(radio\s*(edit|mix|version)|remaster(ed)?(\s*\d{4})?|single\s*version|original\s*mix|feat\.?\s*.+)$", "", text, flags=re.IGNORECASE)
    # Remove parenthesized suffixes
    text = re.sub(r"\s*\(.*?\)\s*$", "", text)
    # Remove punctuation
    text = re.sub(r"[^\w\s]", "", text)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _normalize_artist(text: str) -> str:
    """Normalize artist name for comparison."""
    text = _normalize(text)
    text = re.sub(r"^the\s+", "", text)
    return text


class MatchResult:
    """Result of matching a single Track to a local file."""

    def __init__(self, track: Track, local_path: str | None, method: str, score: int):
        self.track = track
        self.local_path = local_path
        self.method = method  # "isrc", "exact", "fuzzy", "none"
        self.score = score


def match_tracks(
    tracks: list[Track],
    repo: TrackRepository | None = None,
    db_url: str | None = None,
    fuzzy_threshold: int = 85,
    progress_callback=None,
) -> list[MatchResult]:
    """Match Spotify tracks to local files via a TrackRepository.

    Strategy order:
    1. ISRC exact match
    2. Artist + Title exact match (normalized)
    3. Fuzzy match on Artist + Title
    4. Unmatched

    If ``repo`` is None, a PostgresTrackRepository is constructed from
    ``db_url`` / ``DATABASE_URL`` env var (backward-compat).
    """
    _owns_repo = False
    if repo is None:
        from cratekeeper.local.pg_repository import PostgresTrackRepository
        repo = PostgresTrackRepository(db_url)
        _owns_repo = True

    matched_paths: set[str] = set()
    results: list[MatchResult] = []

    for i, track in enumerate(tracks):
        result = _match_single(track, repo, fuzzy_threshold, matched_paths)
        results.append(result)
        if result.local_path:
            matched_paths.add(result.local_path)
            track.local_path = result.local_path
        if progress_callback:
            progress_callback(i + 1, len(tracks), track, result)

    if _owns_repo:
        repo.close()
    return results


def _match_single(
    track: Track,
    repo: TrackRepository,
    fuzzy_threshold: int,
    matched_paths: set[str],
) -> MatchResult:
    """Try to match a single track using all strategies."""

    # Strategy 1: ISRC
    if track.isrc:
        lt = repo.find_by_isrc(track.isrc.upper())
        if lt and lt.path not in matched_paths:
            return MatchResult(track, lt.path, "isrc", 100)

    # Strategy 2: Exact artist + title (normalized)
    title_norm = _normalize(track.name)
    for artist in track.artists:
        artist_norm = _normalize_artist(artist)
        lt = repo.find_by_exact(artist_norm, title_norm)
        if lt and lt.path not in matched_paths:
            return MatchResult(track, lt.path, "exact", 100)

    # Strategy 3: Fuzzy match
    if track.artists:
        query = f"{_normalize_artist(track.artists[0])} {_normalize(track.name)}"
        artist_prefix = _normalize_artist(track.artists[0])[:3]
        if artist_prefix:
            candidates = repo.find_candidates(artist_prefix)
            best_score = 0
            best_path = None
            for lt in candidates:
                if lt.path in matched_paths or not lt.artist_norm or not lt.title_norm:
                    continue
                candidate_str = f"{lt.artist_norm} {lt.title_norm}"
                score = fuzz.token_sort_ratio(query, candidate_str)
                if score > best_score:
                    best_score = score
                    best_path = lt.path
            if best_path and best_score >= fuzzy_threshold:
                return MatchResult(track, best_path, "fuzzy", best_score)

    return MatchResult(track, None, "none", 0)


def write_missing_report(
    results: list[MatchResult],
    plan_file: Path,
    tidal_url_map: dict[str, str | None] | None = None,
) -> tuple[Path, Path, Path | None]:
    """Write .missing.txt, .missing-isrcs.txt, and optionally .missing-tidal.txt.

    Returns (missing_file, isrc_file, tidal_file_or_None).
    """
    missing = [r.track for r in results if r.method == "none"]
    tidal_url_map = tidal_url_map or {}

    missing_file = plan_file.with_suffix(".missing.txt")
    lines = []
    for t in missing:
        line = f"{t.display_name()} (ISRC: {t.isrc or 'none'})"
        if t.isrc and tidal_url_map.get(t.isrc):
            line += f"  {tidal_url_map[t.isrc]}"
        lines.append(line)
    missing_file.write_text("\n".join(lines))

    isrc_file = plan_file.with_suffix(".missing-isrcs.txt")
    isrcs = [t.isrc for t in missing if t.isrc]
    isrc_file.write_text("\n".join(isrcs))

    tidal_file: Path | None = None
    tidal_lines = [tidal_url_map[t.isrc] for t in missing if t.isrc and tidal_url_map.get(t.isrc)]
    if tidal_lines:
        tidal_file = plan_file.with_suffix(".missing-tidal.txt")
        tidal_file.write_text("\n".join(tidal_lines))

    return missing_file, isrc_file, tidal_file
