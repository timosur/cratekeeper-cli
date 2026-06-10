"""CLI command for Rekordbox export."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from cratekeeper.models import Plan

console = Console()


def register(app: typer.Typer) -> None:
    """Attach the export command to *app*."""

    @app.command(name="export-rekordbox")
    def export_rekordbox_cmd(
        ctx: typer.Context,
        library: Path = typer.Option(None, "--library", "-l", help="Library directory (default: active profile's library_target)"),
        output: Path = typer.Option(None, "--output", "-o", help="Output XML path (default: <library>/rekordbox.xml)"),
        buckets: str = typer.Option(None, "--buckets", "-b", help="Comma-separated genre buckets to include (default: all)"),
    ) -> None:
        """Generate a Rekordbox XML from the active profile's built library."""
        from cratekeeper.export.rekordbox import EmptyLibraryError, export_rekordbox

        profile = ctx.obj
        library_dir = library if library is not None else profile.library_target
        out_path = output if output is not None else Path(library_dir) / "rekordbox.xml"
        bucket_filter = [b.strip() for b in buckets.split(",")] if buckets else None

        console.print(
            f"Exporting Rekordbox XML from [cyan]{library_dir}[/cyan] "
            f"[dim](profile: {profile.name})[/dim]"
        )

        try:
            track_count, bucket_count = export_rekordbox(
                library_dir, out_path, buckets_filter=bucket_filter, sort=profile.sort
            )
        except EmptyLibraryError as exc:
            console.print(f"[red]{exc}[/red]")
            raise typer.Exit(1)

        console.print(f"[green]Wrote {track_count} tracks across {bucket_count} playlist(s)[/green] to {out_path}")
