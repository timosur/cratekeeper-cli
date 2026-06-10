"""Tidal PKCE authentication flow.

Handles login via tidalapi's built-in PKCE session file mechanism,
persisting the session to ~/.config/cratekeeper/tidal-session.json.
"""

from __future__ import annotations

import os
from pathlib import Path

import tidalapi
from rich.console import Console
from rich.prompt import Prompt

console = Console()

_SESSION_FILENAME = "tidal-session.json"


def _session_path() -> Path:
    """Return the canonical session path (XDG-compliant)."""
    xdg = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(xdg) / "cratekeeper" / _SESSION_FILENAME


def get_tidal_session() -> tidalapi.Session:
    """Return an authenticated Tidal session.

    Loads from the persisted session file. Raises FileNotFoundError
    if no session exists, RuntimeError if the session is expired.
    """
    session_file = _session_path()
    if not session_file.exists():
        raise FileNotFoundError(
            f"Tidal session not found at {session_file}.\n"
            "Run `crate tidal-auth` to authenticate."
        )
    session = tidalapi.Session()
    session.login_session_file(session_file, do_pkce=True)
    if not session.check_login():
        raise RuntimeError(
            "Tidal session expired and could not be refreshed.\n"
            "Re-run `crate tidal-auth` to re-authenticate."
        )
    return session


def run_tidal_auth() -> None:
    """Run the full Tidal PKCE authentication flow interactively."""
    session_file = _session_path()

    # Check if already authenticated
    if session_file.exists():
        try:
            session = tidalapi.Session()
            session.login_session_file(session_file, do_pkce=True)
            if session.check_login():
                console.print(f"[dim]Existing session found at {session_file}[/dim]")
                reauth = Prompt.ask(
                    "Already authenticated. Re-authenticate?",
                    choices=["y", "n"],
                    default="n",
                )
                if reauth == "n":
                    console.print("[green]Using existing session.[/green]")
                    _show_user_info(session)
                    return
        except Exception:
            console.print("[yellow]Existing session invalid. Starting fresh login.[/yellow]")

    # Ensure parent directory exists
    session_file.parent.mkdir(parents=True, exist_ok=True)

    console.print()
    console.print("[bold]Tidal PKCE Authentication[/bold]")
    console.print("You will be asked to visit a URL in your browser,")
    console.print("log in to Tidal, and paste the redirect URL back here.")
    console.print()

    session = tidalapi.Session()
    session.login_session_file(session_file, do_pkce=True)

    if session.check_login():
        console.print()
        console.print(
            f"[green bold]Authenticated![/green bold] Session saved to {session_file}"
        )
        _show_user_info(session)
    else:
        console.print("[red]Authentication failed. Please try again.[/red]")


def _show_user_info(session: tidalapi.Session) -> None:
    """Display the logged-in Tidal user info."""
    try:
        user = session.user
        console.print(f"Logged in as: [bold]{user.first_name} {user.last_name}[/bold]")
    except Exception:
        console.print("[yellow]Session valid but could not retrieve user info.[/yellow]")
