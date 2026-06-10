"""Spotify OAuth authentication flow.

Handles the complete setup: prompts for client credentials if needed,
runs the OAuth2 Authorization Code flow via a temporary local HTTP server,
and saves the resulting tokens to spotify-config.json.
"""

from __future__ import annotations

import json
import os
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import spotipy
from rich.console import Console
from rich.prompt import Prompt

# Scopes required by cratekeeper for playlist/artist operations
_SCOPES = (
    "user-read-private "
    "playlist-read-private "
    "playlist-modify-private "
    "playlist-modify-public "
    "user-library-read"
)

_DEFAULT_REDIRECT_URI = "http://127.0.0.1:8888/callback"

console = Console()


def _config_path() -> Path:
    """Return the canonical config path (XDG-compliant)."""
    xdg = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(xdg) / "cratekeeper" / "spotify-config.json"


def _load_existing_config(path: Path) -> dict | None:
    if path.exists():
        try:
            return json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            return None
    return None


def _save_config(path: Path, config: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, indent=2) + "\n")


def _prompt_credentials(existing: dict | None) -> dict:
    """Prompt user for Spotify app credentials."""
    console.print()
    console.print("[bold]Spotify Developer App Setup[/bold]")
    console.print(
        "Create an app at [link=https://developer.spotify.com/dashboard]"
        "developer.spotify.com/dashboard[/link]"
    )
    console.print(
        f"Set the redirect URI to [cyan]{_DEFAULT_REDIRECT_URI}[/cyan] in the app settings."
    )
    console.print()

    default_id = (existing or {}).get("clientId", "")
    default_secret = (existing or {}).get("clientSecret", "")
    default_uri = (existing or {}).get("redirectUri", _DEFAULT_REDIRECT_URI)

    client_id = Prompt.ask(
        "Client ID",
        default=default_id or None,
    )
    client_secret = Prompt.ask(
        "Client Secret",
        default=default_secret or None,
    )
    redirect_uri = Prompt.ask(
        "Redirect URI",
        default=default_uri,
    )

    return {
        "clientId": client_id.strip(),
        "clientSecret": client_secret.strip(),
        "redirectUri": redirect_uri.strip(),
    }


def _extract_auth_code(redirect_uri: str) -> str:
    """Start a temporary HTTP server to capture the OAuth callback code."""
    parsed = urlparse(redirect_uri)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 8888
    path = parsed.path or "/callback"

    auth_code: list[str] = []  # mutable container for closure
    error: list[str] = []

    class CallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            qs = parse_qs(urlparse(self.path).query)
            if "code" in qs:
                auth_code.append(qs["code"][0])
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(
                    b"<html><body><h2>Authenticated!</h2>"
                    b"<p>You can close this tab and return to the terminal.</p>"
                    b"</body></html>"
                )
            elif "error" in qs:
                error.append(qs["error"][0])
                self.send_response(400)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(
                    f"<html><body><h2>Error: {qs['error'][0]}</h2></body></html>".encode()
                )
            else:
                self.send_response(404)
                self.end_headers()

        def log_message(self, format, *args):  # noqa: A002
            pass  # silence request logging

    server = HTTPServer((host, port), CallbackHandler)
    server.timeout = 120  # 2 minutes to complete auth

    # Handle exactly one request
    server.handle_request()
    server.server_close()

    if error:
        raise RuntimeError(f"Spotify authorization failed: {error[0]}")
    if not auth_code:
        raise RuntimeError("No authorization code received (timed out after 120s)")

    return auth_code[0]


def run_auth_flow() -> None:
    """Run the full Spotify authentication flow interactively."""
    config_path = _config_path()
    existing = _load_existing_config(config_path)

    # Check if already authenticated
    if existing and existing.get("accessToken") and existing.get("refreshToken"):
        console.print(f"[dim]Existing config found at {config_path}[/dim]")
        reauth = Prompt.ask(
            "Already authenticated. Re-authenticate?",
            choices=["y", "n"],
            default="n",
        )
        if reauth == "n":
            console.print("[green]Using existing credentials.[/green]")
            return

    # Get or confirm credentials
    config = _prompt_credentials(existing)

    # Build auth URL
    auth_manager = spotipy.SpotifyOAuth(
        client_id=config["clientId"],
        client_secret=config["clientSecret"],
        redirect_uri=config["redirectUri"],
        scope=_SCOPES,
    )
    auth_url = auth_manager.get_authorize_url()

    console.print()
    console.print("[bold]Opening browser for Spotify authorization...[/bold]")
    console.print(f"If the browser doesn't open, visit: [link={auth_url}]{auth_url}[/link]")
    console.print("[dim]Waiting for callback...[/dim]")

    # Open browser
    webbrowser.open(auth_url)

    # Wait for callback
    code = _extract_auth_code(config["redirectUri"])

    # Exchange code for tokens
    console.print("[dim]Exchanging code for tokens...[/dim]")
    token_info = auth_manager.get_access_token(code, as_dict=True)

    # Save complete config
    config["accessToken"] = token_info["access_token"]
    config["refreshToken"] = token_info["refresh_token"]
    config["expiresAt"] = token_info["expires_at"] * 1000  # seconds → ms

    _save_config(config_path, config)

    console.print()
    console.print(f"[green bold]Authenticated![/green bold] Config saved to {config_path}")

    # Quick verification
    try:
        sp = spotipy.Spotify(auth=token_info["access_token"])
        user = sp.current_user()
        console.print(f"Logged in as: [bold]{user['display_name']}[/bold] ({user['id']})")
    except Exception:
        console.print("[yellow]Token saved but could not verify. Try running a command.[/yellow]")
