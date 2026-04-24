"""Tidal API client — wraps tidalapi, reuses tidal-session.json."""

from __future__ import annotations

from pathlib import Path

import tidalapi

_SESSION_SEARCH_PATHS = [
    Path(__file__).resolve().parent.parent.parent / "tidal-mcp" / "tidal-session.json",
]


def _find_session_file() -> Path:
    for p in _SESSION_SEARCH_PATHS:
        if p.exists():
            return p
    raise FileNotFoundError(
        "tidal-session.json not found. Run `python -m tidal_mcp.auth` first. "
        "Expected at: " + ", ".join(str(p) for p in _SESSION_SEARCH_PATHS)
    )


def get_tidal_session() -> tidalapi.Session:
    """Return an authenticated Tidal session."""
    session_file = _find_session_file()
    session = tidalapi.Session()
    session.login_session_file(session_file)
    if not session.check_login():
        raise RuntimeError("Tidal session expired. Re-run `python -m tidal_mcp.auth`.")
    return session


def create_playlist(session: tidalapi.Session, name: str, description: str = "") -> str:
    """Create a Tidal playlist. Returns playlist UUID."""
    playlist = session.user.create_playlist(title=name, description=description)
    return str(playlist.id)


def add_tracks_by_isrc(session: tidalapi.Session, playlist_id: str, isrc_codes: list[str]) -> tuple[list[str], list[str]]:
    """Add tracks to a Tidal playlist by ISRC.

    Returns (added_isrcs, failed_isrcs).
    """
    playlist = session.playlist(playlist_id)
    added = []
    failed = []
    for isrc in isrc_codes:
        try:
            playlist.add_by_isrc(isrc)
            added.append(isrc)
        except Exception:
            failed.append(isrc)
    return added, failed


def get_user_playlists(session: tidalapi.Session) -> list[dict]:
    """Get all of the user's playlists as dicts with id, name."""
    playlists = session.user.playlist_and_favorite_playlists()
    return [{"id": str(p.id), "name": p.name} for p in playlists]


def search_track_by_isrc(session: tidalapi.Session, isrc: str) -> str | None:
    """Search Tidal for a track by ISRC. Returns a Tidal track URL or None."""
    try:
        tracks = session.get_tracks_by_isrc(isrc)
        if not tracks:
            return None
        track = tracks[0]
        return f"https://tidal.com/browse/track/{track.id}"
    except Exception:
        return None


def resolve_tidal_urls(
    session: tidalapi.Session,
    isrcs: list[str],
    progress_callback=None,
) -> dict[str, str | None]:
    """Resolve a list of ISRCs to Tidal URLs.

    Returns a dict mapping ISRC → Tidal URL (or None if not found).
    """
    results: dict[str, str | None] = {}
    for i, isrc in enumerate(isrcs):
        results[isrc] = search_track_by_isrc(session, isrc)
        if progress_callback:
            progress_callback(i + 1, len(isrcs), isrc, results[isrc])
    return results
