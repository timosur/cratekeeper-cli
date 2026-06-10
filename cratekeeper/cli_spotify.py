"""CLI commands for Spotify playlist operations."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from cratekeeper.models import EventPlan, LibraryImportPlan, Plan

console = Console()


def register(app: typer.Typer) -> None:
    """Attach all Spotify commands to *app*."""

    @app.command()
    def fetch(
        ctx: typer.Context,
        playlist_url: str = typer.Argument(help="Spotify playlist URL or ID"),
        output: Path = typer.Option(None, "--output", "-o", help="Output JSON path (default: <profile data_dir>/<playlist-name>.json)"),
    ) -> None:
        """Fetch all tracks from a Spotify playlist, enrich with artist genres, save to JSON."""
        import sys
        from cratekeeper.spotify.client import (
            enrich_tracks_with_artist_genres,
            extract_playlist_id,
            fetch_playlist_tracks,
            get_spotify_client,
        )

        console.print("[bold]Connecting to Spotify...[/bold]")
        sp = get_spotify_client()

        playlist_id = extract_playlist_id(playlist_url)
        console.print(f"Fetching playlist [cyan]{playlist_id}[/cyan]...")

        playlist_name, tracks = fetch_playlist_tracks(sp, playlist_id)
        console.print(f"Found [green]{len(tracks)}[/green] tracks in '{playlist_name}'")

        all_artist_ids = list({aid for t in tracks for aid in t.artist_ids})
        console.print(f"Fetching genres for [cyan]{len(all_artist_ids)}[/cyan] unique artists...")
        enrich_tracks_with_artist_genres(sp, tracks)

        plan: Plan
        if sys.stdin.isatty():
            from rich.prompt import Prompt
            plan_choice = Prompt.ask(
                "Is this for an event or a library import?",
                choices=["event", "library"],
                default="event",
            )
            if plan_choice == "library":
                plan = LibraryImportPlan(source_playlist_id=playlist_id, source_playlist_name=playlist_name, tracks=tracks)
                console.print("[cyan]Creating library-import plan[/cyan]")
            else:
                plan = EventPlan(source_playlist_id=playlist_id, source_playlist_name=playlist_name, tracks=tracks)
                console.print("[cyan]Creating event plan[/cyan]")
        else:
            plan = EventPlan(source_playlist_id=playlist_id, source_playlist_name=playlist_name, tracks=tracks)

        if output is None:
            output = ctx.obj.plan_path(playlist_name)

        plan.save(output)
        console.print(f"Saved to [green]{output}[/green]")

    @app.command()
    def classify(
        ctx: typer.Context,
        input_file: Path = typer.Argument(help="Path to fetched playlist JSON"),
        min_bucket_size: int = typer.Option(3, "--min-bucket", help="Minimum tracks per bucket (smaller buckets get merged)"),
        enrich: bool = typer.Option(False, "--enrich", "-e", help="Enrich missing genres via MusicBrainz before classifying"),
    ) -> None:
        """Classify tracks into genre buckets and print a summary."""
        from rich.table import Table
        from cratekeeper.pipeline.classifier import classify_tracks, consolidate_small_buckets

        profile = ctx.obj
        plan = Plan.load(input_file)
        console.print(
            f"Loaded [green]{len(plan.tracks)}[/green] tracks from '{plan.source_playlist_name}' "
            f"[dim](profile: {profile.name})[/dim]"
        )

        if enrich:
            from cratekeeper.spotify.musicbrainz import enrich_tracks_genres
            missing = sum(1 for t in plan.tracks if not t.artist_genres and t.isrc)
            if missing:
                console.print(f"Enriching [cyan]{missing}[/cyan] tracks via MusicBrainz (≈{missing}s)...")
                def _progress(i, total, track, genres):
                    tag = f" → {', '.join(genres[:3])}" if genres else " → no tags"
                    console.print(f"  [{i}/{total}] {track.display_name()}{tag}")
                enriched = enrich_tracks_genres(plan.tracks, progress_callback=_progress)
                console.print(f"Enriched [green]{enriched}[/green] of {missing} tracks with MusicBrainz tags")
            else:
                console.print("[dim]No tracks need enrichment[/dim]")

        classify_tracks(plan.tracks, buckets=profile.buckets, fallback=profile.fallback)
        consolidate_small_buckets(plan.tracks, min_size=min_bucket_size, fallback=profile.fallback)

        buckets = plan.bucket_summary()
        table = Table(title=f"Genre Classification — {plan.source_playlist_name} ({len(plan.tracks)} tracks)")
        table.add_column("Bucket", style="cyan")
        table.add_column("Tracks", justify="right", style="green")
        table.add_column("High", justify="right")
        table.add_column("Medium", justify="right")
        table.add_column("Low", justify="right")
        for bucket_name, bucket_tracks in buckets.items():
            high = sum(1 for t in bucket_tracks if t.confidence == "high")
            med  = sum(1 for t in bucket_tracks if t.confidence == "medium")
            low  = sum(1 for t in bucket_tracks if t.confidence == "low")
            table.add_row(bucket_name, str(len(bucket_tracks)), str(high), str(med), str(low))
        console.print(table)

        output = input_file.with_suffix(".classified.json")
        plan.save(output)
        console.print(f"Saved classified plan to [green]{output}[/green]")

    @app.command()
    def enrich(
        input_file: Path = typer.Argument(help="Path to fetched/classified playlist JSON"),
    ) -> None:
        """Enrich tracks missing genre data via MusicBrainz ISRC lookup."""
        from cratekeeper.spotify.musicbrainz import enrich_tracks_genres

        plan = Plan.load(input_file)
        missing_genres = sum(1 for t in plan.tracks if not t.artist_genres and t.isrc)
        missing_year   = sum(1 for t in plan.tracks if not t.release_year and t.isrc)
        candidates     = sum(1 for t in plan.tracks if (not t.artist_genres or not t.release_year) and t.isrc)
        console.print(
            f"Loaded [green]{len(plan.tracks)}[/green] tracks, "
            f"[cyan]{missing_genres}[/cyan] missing genres, [cyan]{missing_year}[/cyan] missing release year"
        )
        if not candidates:
            console.print("[green]All tracks already have genre and year data![/green]")
            return

        console.print(f"Querying MusicBrainz for {candidates} tracks (≈{candidates}s due to rate limit)...")

        def _progress(i, total, track, genres, mb_year):
            parts = []
            if genres:
                parts.append(", ".join(genres[:3]))
            if mb_year:
                parts.append(f"year={mb_year}")
            tag = f" → {'; '.join(parts)}" if parts else " → no tags"
            console.print(f"  [{i}/{total}] {track.display_name()}{tag}")

        enriched = enrich_tracks_genres(plan.tracks, progress_callback=_progress)
        console.print(f"\nEnriched [green]{enriched}[/green] of {candidates} tracks")
        plan.save(input_file)
        console.print(f"Saved to [green]{input_file}[/green]")

    @app.command()
    def review(
        input_file: Path = typer.Argument(help="Path to classified JSON"),
    ) -> None:
        """Print tracks with low-confidence classification for manual review."""
        from rich.table import Table

        plan = Plan.load(input_file)
        low_conf = [t for t in plan.tracks if t.confidence == "low"]
        med_conf = [t for t in plan.tracks if t.confidence == "medium"]

        if not low_conf and not med_conf:
            console.print("[green]All tracks classified with high confidence![/green]")
            return

        for title, tracks, style in [
            (f"Medium Confidence ({len(med_conf)} tracks)", med_conf, "cyan"),
            (f"Low Confidence / Fallback ({len(low_conf)} tracks)", low_conf, "yellow"),
        ]:
            if not tracks:
                continue
            table = Table(title=title)
            table.add_column("#", justify="right", style="dim")
            table.add_column("Track")
            table.add_column("Bucket", style=style)
            table.add_column("Year", justify="right")
            table.add_column("Genres", style="dim")
            for i, t in enumerate(tracks, 1):
                table.add_row(str(i), t.display_name(), t.bucket or "?", str(t.release_year or "?"), ", ".join(t.artist_genres[:3]) or "none")
            console.print(table)

        console.print("\nEdit the classified JSON directly to move tracks between buckets.")
        console.print("Or use the LLM skill for AI-assisted review.")

    @app.command(name="create-playlists")
    def create_playlists(
        input_file: Path = typer.Argument(help="Path to classified JSON"),
        event: str = typer.Option(..., "--event", "-e", help="Event name (e.g., 'Wedding Tim & Lea')"),
        date: str = typer.Option(..., "--date", "-d", help="Event date (e.g., '2026-04-22')"),
    ) -> None:
        """Create Spotify sub-playlists from classified tracks."""
        from cratekeeper.spotify.client import create_event_playlists, get_spotify_client

        plan = Plan.load(input_file)
        if not isinstance(plan, EventPlan):
            console.print("[red]create-playlists is not applicable to library imports.[/red]")
            raise typer.Exit(1)
        plan.event_name = event
        plan.event_date = date

        sp = get_spotify_client()
        console.print(f"Creating playlists for '{event}'...")

        def _progress(playlist_name, track_count):
            console.print(f"  ✓ {playlist_name} — {track_count} tracks")

        create_event_playlists(sp, plan, event, date, progress_callback=_progress)
        plan.save(input_file)
        console.print(f"\n[green]Done![/green] Created {len(plan.created_playlists)} playlists.")

    @app.command(name="build-masters")
    def build_masters(
        input_file: Path = typer.Argument(help="Path to classified JSON"),
    ) -> None:
        """Add classified tracks to cross-event [DJ] master playlists on Spotify."""
        from cratekeeper.spotify.client import build_master_playlists, get_spotify_client

        plan = Plan.load(input_file)
        sp = get_spotify_client()

        def _progress(master_name, new_count, dupes):
            status = f"+{new_count} new"
            if dupes:
                status += f", {dupes} dupes skipped"
            console.print(f"  {master_name} — {status}")

        total_added, total_dupes = build_master_playlists(sp, plan, progress_callback=_progress)
        console.print(f"\n[green]Done![/green] Added {total_added} tracks, skipped {total_dupes} duplicates.")


