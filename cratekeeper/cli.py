"""Cratekeeper — DJ library management CLI.

Command registration is split across domain sub-modules:

  cli_spotify.py   — fetch, classify, enrich, review, create-playlists,
                     build-masters, sync-to-tidal
  cli_local.py     — scan, match, import-library
  cli_pipeline.py  — analyze-mood, apply-tags, tag, tag-untagged
  cli_builder.py   — review-library, build-library, build-event
  cli_export.py    — export-rekordbox
  cli_profile.py   — profile list/show/use/init
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

import cratekeeper.cli_spotify as _spotify
import cratekeeper.cli_local as _local
import cratekeeper.cli_pipeline as _pipeline
import cratekeeper.cli_builder as _builder
import cratekeeper.cli_export as _export
import cratekeeper.cli_profile as _profile

app = typer.Typer(help="Cratekeeper — DJ library management CLI")
console = Console()


@app.callback()
def main(
    ctx: typer.Context,
    profile: str = typer.Option(
        None, "--profile", "-p",
        help="Profile to use for this invocation (overrides config active_profile)",
    ),
) -> None:
    """Resolve the active profile once and stash it on the Typer context."""
    from cratekeeper.config import ConfigError, resolve_profile

    try:
        ctx.obj = resolve_profile(profile)
    except ConfigError as exc:
        console.print(f"[red]Config error:[/red] {exc}")
        raise typer.Exit(1)


@app.command("spotify-auth")
def spotify_auth() -> None:
    """Authenticate with Spotify — prompts for credentials and runs OAuth flow."""
    from cratekeeper.spotify.auth import run_auth_flow

    run_auth_flow()


@app.command()
def wizard(
    ctx: typer.Context,
    plan: Path = typer.Option(None, "--plan", help="Existing plan file to resume from"),
) -> None:
    """Interactive wizard — guides you through the full pipeline step by step."""
    from cratekeeper.wizard import run_wizard

    run_wizard(profile=ctx.obj, plan_path=plan)


# Register all domain command groups onto the shared app
_spotify.register(app)
_local.register(app)
_pipeline.register(app)
_builder.register(app)
_export.register(app)
_profile.register(app)


if __name__ == "__main__":
    app()
