"""CLI commands for Tidal playlist operations."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from cratekeeper.models import EventPlan, Plan

console = Console()


def register(app: typer.Typer) -> None:
    """Attach all Tidal commands to *app*."""

    @app.command(name="sync-to-tidal")
    def sync_to_tidal(
        input_file: Path = typer.Argument(help="Path to classified JSON"),
    ) -> None:
        """Sync classified playlists to Tidal via ISRC matching."""
        from cratekeeper.tidal.auth import get_tidal_session
        from cratekeeper.tidal.client import sync_plan_to_tidal

        plan = Plan.load(input_file)
        if not isinstance(plan, EventPlan):
            console.print("[red]sync-to-tidal is not applicable to library imports.[/red]")
            raise typer.Exit(1)
        session = get_tidal_session()
        console.print("Syncing playlists to Tidal...")

        def _progress(playlist_name, added, failed, skipped=False):
            if skipped:
                console.print(f"  ✗ {playlist_name} — no ISRCs available, skipping")
            else:
                status = f"✓ {added} matched"
                if failed:
                    status += f", {failed} failed"
                console.print(f"  {playlist_name} — {status}")

        total_added, total_failed = sync_plan_to_tidal(session, plan, progress_callback=_progress)
        plan.save(input_file)
        console.print(f"\n[green]Done![/green] Synced {total_added} tracks to Tidal, {total_failed} failed.")
        if total_failed:
            console.print("[yellow]Run 'dj review' to see which tracks failed.[/yellow]")
