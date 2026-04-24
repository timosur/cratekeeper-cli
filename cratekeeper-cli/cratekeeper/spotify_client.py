"""Spotify API client — wraps spotipy, reuses spotify-config.json tokens."""

from __future__ import annotations

import json
from pathlib import Path

import spotipy

from cratekeeper.models import Track

# Look for spotify-config.json relative to the project root
_CONFIG_SEARCH_PATHS = [
    Path(__file__).resolve().parent.parent.parent / "spotify-mcp" / "spotify-config.json",
]


def _find_config() -> Path:
    for p in _CONFIG_SEARCH_PATHS:
        if p.exists():
            return p
    raise FileNotFoundError(
        "spotify-config.json not found. Expected at: "
        + ", ".join(str(p) for p in _CONFIG_SEARCH_PATHS)
    )


def _load_config() -> dict:
    config_path = _find_config()
    return json.loads(config_path.read_text())


def _save_config(config: dict) -> None:
    config_path = _find_config()
    config_path.write_text(json.dumps(config, indent=2))


def get_spotify_client() -> spotipy.Spotify:
    """Create an authenticated Spotify client using existing tokens."""
    config = _load_config()

    token_info = {
        "access_token": config["accessToken"],
        "refresh_token": config["refreshToken"],
        "token_type": "Bearer",
        "expires_at": config.get("expiresAt", 0) // 1000,  # ms → seconds
        "scope": "user-read-private playlist-read-private playlist-modify-private playlist-modify-public user-library-read",
    }

    auth_manager = spotipy.SpotifyOAuth(
        client_id=config["clientId"],
        client_secret=config["clientSecret"],
        redirect_uri=config["redirectUri"],
        scope=token_info["scope"],
    )
    # Inject existing token
    auth_manager.token_info = token_info

    # Try to refresh if needed
    if auth_manager.is_token_expired(token_info):
        refreshed = auth_manager.refresh_access_token(config["refreshToken"])
        # Save refreshed tokens back
        config["accessToken"] = refreshed["access_token"]
        config["expiresAt"] = refreshed["expires_at"] * 1000  # seconds → ms
        if "refresh_token" in refreshed:
            config["refreshToken"] = refreshed["refresh_token"]
        _save_config(config)
        auth_manager.token_info = refreshed

    return spotipy.Spotify(auth_manager=auth_manager)


def extract_playlist_id(url_or_id: str) -> str:
    """Extract playlist ID from a Spotify URL or return as-is if already an ID."""
    if "/" in url_or_id:
        # https://open.spotify.com/playlist/5WzfuZrfmVfyKY7kvgNxaR?si=...
        parts = url_or_id.split("/")
        for i, part in enumerate(parts):
            if part == "playlist" and i + 1 < len(parts):
                return parts[i + 1].split("?")[0]
    return url_or_id.split("?")[0]


def fetch_playlist_tracks(sp: spotipy.Spotify, playlist_id: str) -> tuple[str, list[Track]]:
    """Fetch all tracks from a playlist, including artist IDs, ISRCs, and release years.

    Returns (playlist_name, tracks).
    """
    playlist = sp.playlist(playlist_id, fields="name")
    playlist_name = playlist["name"]

    tracks: list[Track] = []
    offset = 0
    limit = 100

    while True:
        results = sp.playlist_items(
            playlist_id,
            offset=offset,
            limit=limit,
            fields="items(track(id,name,duration_ms,artists(id,name),album(name,release_date),external_ids)),total",
        )

        for item in results.get("items", []):
            track_data = item.get("track")
            if not track_data or not track_data.get("id"):
                continue

            artists = [a["name"] for a in track_data.get("artists", [])]
            artist_ids = [a["id"] for a in track_data.get("artists", []) if a.get("id")]
            isrc = track_data.get("external_ids", {}).get("isrc")

            release_year = None
            release_date = track_data.get("album", {}).get("release_date", "")
            if release_date and len(release_date) >= 4:
                try:
                    release_year = int(release_date[:4])
                except ValueError:
                    pass

            tracks.append(Track(
                id=track_data["id"],
                name=track_data["name"],
                artists=artists,
                artist_ids=artist_ids,
                album=track_data.get("album", {}).get("name", "Unknown"),
                duration_ms=track_data.get("duration_ms", 0),
                isrc=isrc,
                release_year=release_year,
            ))

        total = results.get("total", 0)
        offset += limit
        if offset >= total:
            break

    return playlist_name, tracks


def fetch_artist_genres(sp: spotipy.Spotify, artist_ids: list[str]) -> dict[str, list[str]]:
    """Fetch genres for artists in batches of 50.

    Returns {artist_id: [genre1, genre2, ...]}.
    """
    genres: dict[str, list[str]] = {}

    for i in range(0, len(artist_ids), 50):
        batch = artist_ids[i : i + 50]
        results = sp.artists(batch)
        for artist in results.get("artists", []):
            if artist:
                genres[artist["id"]] = artist.get("genres", [])

    return genres


def create_playlist(sp: spotipy.Spotify, name: str, description: str = "") -> str:
    """Create a new playlist. Returns playlist ID."""
    user_id = sp.current_user()["id"]
    result = sp.user_playlist_create(user_id, name, public=False, description=description)
    return result["id"]


def add_tracks_to_playlist(sp: spotipy.Spotify, playlist_id: str, track_ids: list[str]) -> None:
    """Add tracks to a playlist in batches of 100."""
    for i in range(0, len(track_ids), 100):
        batch = track_ids[i : i + 100]
        sp.playlist_add_items(playlist_id, batch)


def get_user_playlists(sp: spotipy.Spotify) -> list[dict]:
    """Get all of the current user's playlists."""
    playlists = []
    offset = 0
    while True:
        results = sp.current_user_playlists(limit=50, offset=offset)
        playlists.extend(results.get("items", []))
        if not results.get("next"):
            break
        offset += 50
    return playlists


def get_playlist_track_ids(sp: spotipy.Spotify, playlist_id: str) -> set[str]:
    """Get all track IDs in a playlist (for deduplication)."""
    ids: set[str] = set()
    offset = 0
    while True:
        results = sp.playlist_items(playlist_id, offset=offset, limit=100, fields="items(track(id)),total")
        for item in results.get("items", []):
            track = item.get("track")
            if track and track.get("id"):
                ids.add(track["id"])
        total = results.get("total", 0)
        offset += 100
        if offset >= total:
            break
    return ids
