"""CLI commands for local library scanning, matching, and import."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from cratekeeper.models import LibraryImportPlan, Plan

console = Console()


def register(app: typer.Typer) -> None:
    """Attach all local-library commands to *app*."""

    @app.command()
    def scan(
        directory: Path = typer.Argument(help="Path to local music directory"),
        full: bool = typer.Option(False, "--full", "--force", help="Full re-scan (ignore existing entries)"),
    ) -> None:
        """Scan a local directory for audio files and index their metadata into PostgreSQL."""
        from cratekeeper.local.pg_repository import PostgresTrackRepository
        from cratekeeper.local.scanner import scan_directory

        console.print(f"Scanning [cyan]{directory}[/cyan] for audio files...")
        if not full:
            console.print("[dim]Incremental mode — skipping already indexed files[/dim]")

        def _progress(new, skip, path):
            name = path.name if path else "done"
            console.print(f"  [green]+{new} new[/green], [dim]{skip} skipped[/dim] — {name}")

        repo = PostgresTrackRepository()
        new_count, skipped, updated_count = scan_directory(
            directory, repo=repo, incremental=not full, progress_callback=_progress,
        )
        stats = repo.get_stats()
        repo.close()

        table = Table(title="Scan Summary")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", justify="right", style="green")
        table.add_row("New files indexed", str(new_count))
        if updated_count:
            table.add_row("Updated (re-scanned)", str(updated_count))
        table.add_row("Skipped (already indexed)", str(skipped))
        table.add_row("Total in database", str(stats["total"]))
        table.add_row("With title+artist tags", str(stats["with_tags"]))
        table.add_row("With ISRC", str(stats["with_isrc"]))
        for fmt, count in sorted(stats.get("formats", {}).items(), key=lambda x: -x[1]):
            table.add_row(f"Format: .{fmt}", str(count))
        console.print(table)

    @app.command()
    def match(
        input_file: Path = typer.Argument(help="Path to classified JSON"),
        fuzzy_threshold: int = typer.Option(85, "--threshold", "-t", help="Fuzzy match threshold (0-100)"),
        tidal_urls: bool = typer.Option(False, "--tidal-urls", help="Resolve Tidal URLs for missing tracks (requires Tidal auth)"),
    ) -> None:
        """Match classified Spotify tracks to local audio files."""
        from cratekeeper.local.matcher import match_tracks, write_missing_report
        from cratekeeper.local.pg_repository import PostgresTrackRepository

        plan = Plan.load(input_file)
        console.print(f"Loaded [green]{len(plan.tracks)}[/green] tracks, matching against PostgreSQL...")

        def _progress(i, total, track, result):
            if result.local_path:
                console.print(f"  [{i}/{total}] {track.display_name()} → [green]{result.method}[/green] ({result.score}%)")

        repo = PostgresTrackRepository()
        results = match_tracks(plan.tracks, repo=repo, fuzzy_threshold=fuzzy_threshold, progress_callback=_progress)
        repo.close()

        by_method: dict[str, int] = {}
        for r in results:
            by_method[r.method] = by_method.get(r.method, 0) + 1

        table = Table(title="Match Results")
        table.add_column("Method", style="cyan")
        table.add_column("Tracks", justify="right", style="green")
        labels = {"isrc": "ISRC match", "exact": "Artist+Title exact", "fuzzy": "Fuzzy match", "none": "Not found"}
        for method in ["isrc", "exact", "fuzzy", "none"]:
            count = by_method.get(method, 0)
            style = "red" if method == "none" else ""
            table.add_row(labels[method], f"[{style}]{count}[/{style}]" if style else str(count))
        console.print(table)

        plan.save(input_file)
        console.print(f"Saved to [green]{input_file}[/green]")

        missing = [r.track for r in results if r.method == "none"]
        if missing:
            tidal_url_map: dict[str, str | None] = {}
            if tidal_urls:
                from cratekeeper.tidal.auth import get_tidal_session
                from cratekeeper.tidal.client import resolve_tidal_urls
                console.print(f"\nResolving Tidal URLs for [cyan]{len(missing)}[/cyan] missing tracks...")
                session = get_tidal_session()
                isrcs = [t.isrc for t in missing if t.isrc]

                def _tidal_progress(i, total, isrc, url):
                    status = f"[green]{url}[/green]" if url else "[dim]not found[/dim]"
                    console.print(f"  [{i}/{total}] {isrc} → {status}")

                tidal_url_map = resolve_tidal_urls(session, isrcs, progress_callback=_tidal_progress)
                found = sum(1 for u in tidal_url_map.values() if u)
                console.print(f"Resolved [green]{found}[/green] of {len(isrcs)} Tidal URLs")

            missing_file, isrc_file, tidal_file = write_missing_report(results, input_file, tidal_url_map)
            isrc_count = len([t.isrc for t in missing if t.isrc])
            console.print(f"[yellow]{len(missing)} unmatched tracks written to {missing_file}[/yellow]")
            console.print(f"[yellow]{isrc_count} ISRCs written to {isrc_file}[/yellow]")
            if tidal_file:
                console.print(f"[yellow]Tidal URLs written to {tidal_file}[/yellow]")

    @app.command(name="import-library")
    def import_library(
        ctx: typer.Context,
        source_path: Path = typer.Argument(help="Directory of scanned local files to import into the active profile"),
        output: Path = typer.Option(None, "--output", "-o", help="Output plan path (default: <profile data_dir>/<source>.json)"),
    ) -> None:
        """Import scanned local files into the active profile using their ID3 genre tags."""
        from cratekeeper.local.bulk_import import SourceNotScannedError, import_tracks
        from cratekeeper.pipeline.classifier import classify_tracks

        profile = ctx.obj
        console.print(f"Importing local files under [cyan]{source_path}[/cyan] [dim](profile: {profile.name})[/dim]")

        try:
            tracks = import_tracks(source_path)
        except SourceNotScannedError as exc:
            console.print(f"[red]{exc}[/red]")
            raise typer.Exit(1)

        console.print(f"Found [green]{len(tracks)}[/green] scanned files")
        classify_tracks(tracks, buckets=profile.buckets, fallback=profile.fallback)

        source = Path(source_path).expanduser()
        plan = LibraryImportPlan(
            source_playlist_id=f"import:{source}",
            source_playlist_name=source.name or str(source),
            tracks=tracks,
        )

        if output is None:
            output = profile.plan_path(source.name or "import")

        plan.save(output)

        summary = plan.bucket_summary()
        table = Table(title=f"Imported {len(tracks)} tracks — {profile.name}")
        table.add_column("Bucket", style="cyan")
        table.add_column("Tracks", justify="right", style="green")
        for bucket_name, bucket_tracks in summary.items():
            table.add_row(bucket_name, str(len(bucket_tracks)))
        console.print(table)

        console.print(f"Saved library-import plan to [green]{output}[/green]")
        console.print("Next: [bold]crate review-library[/bold] then [bold]crate build-library[/bold].")
