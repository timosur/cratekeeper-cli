"""CLI commands for audio analysis and tagging."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from cratekeeper.models import Plan

console = Console()


def register(app: typer.Typer) -> None:
    """Attach all pipeline/tagging commands to *app*."""

    @app.command(name="analyze-mood")
    def analyze_mood(
        input_file: Path = typer.Argument(help="Path to classified JSON (tracks must have local_path set)"),
        force: bool = typer.Option(False, "--force", "-f", help="Re-analyze tracks that already have audio features"),
    ) -> None:
        """Analyze audio features and assign mood to each locally matched track.

        Already-analyzed tracks are skipped unless --force is given.
        Requires essentia — run via Docker if not installed locally.
        """
        from cratekeeper.analysis.mood_analyzer import _is_analyzed, analyze_tracks

        plan = Plan.load(input_file)
        with_path = sum(1 for t in plan.tracks if t.local_path)
        already   = sum(1 for t in plan.tracks if t.local_path and _is_analyzed(t))
        console.print(f"Loaded [green]{len(plan.tracks)}[/green] tracks, [cyan]{with_path}[/cyan] have local files")

        if not with_path:
            console.print("[red]No tracks have local_path set. Run 'dj match' first.[/red]")
            raise typer.Exit(1)

        if already and not force:
            console.print(f"Skipping [yellow]{already}[/yellow] already-analyzed tracks (use --force to re-analyze)")

        console.print("Analyzing audio features with essentia...")

        def _progress(i, total, track, mood, error):
            if error:
                console.print(f"  [{i}/{total}] {track.display_name()} → [red]error: {error}[/red]")
            else:
                parts = []
                if track.bpm:
                    parts.append(f"{track.bpm} BPM")
                if track.key:
                    parts.append(track.key)
                if track.energy:
                    parts.append(f"energy={track.energy}")
                console.print(f"  [{i}/{total}] {track.display_name()} → [cyan]{', '.join(parts)}[/cyan]")

        analyzed = analyze_tracks(plan.tracks, progress_callback=_progress, force=force)
        console.print(f"\nAnalyzed [green]{analyzed}[/green] of {with_path} tracks")

        energies: dict[str, int] = {}
        for t in plan.tracks:
            if t.energy:
                energies[t.energy] = energies.get(t.energy, 0) + 1
        if energies:
            table = Table(title="Energy Distribution")
            table.add_column("Energy", style="cyan")
            table.add_column("Tracks", justify="right", style="green")
            for energy, count in sorted(energies.items()):
                table.add_row(energy, str(count))
            console.print(table)

        plan.save(input_file)
        console.print(f"Saved to [green]{input_file}[/green]")

    @app.command(name="apply-tags")
    def apply_tags(
        input_file: Path = typer.Argument(help="Path to classified JSON"),
        tags_file: Path = typer.Argument(help="Path to tags JSON (array of {id, energy, function, crowd, mood_tags})"),
    ) -> None:
        """Apply pre-classified tags from a JSON file into the classified event plan."""
        import json as _json
        from cratekeeper.pipeline.tag_writer import apply_tags_from_data

        plan = Plan.load(input_file)
        tags_data = _json.loads(tags_file.read_text())

        if not isinstance(tags_data, list):
            console.print("[red]Tags file must contain a JSON array[/red]")
            raise typer.Exit(1)

        applied, warnings = apply_tags_from_data(plan.tracks, tags_data)

        for track in plan.tracks:
            if track.energy or track.function or track.crowd or track.mood_tags:
                console.print(
                    f"  {track.display_name()} → energy={track.energy} "
                    f"func={track.function} crowd={track.crowd} mood={track.mood_tags}"
                )

        plan.save(input_file)
        console.print(f"\n[green]Applied tags to {applied} tracks[/green]", end="")
        if warnings:
            console.print(f", [yellow]{warnings} warnings[/yellow]")
        else:
            console.print()
        console.print(f"Saved to [green]{input_file}[/green]")

    @app.command()
    def tag(
        ctx: typer.Context,
        input_file: Path = typer.Argument(help="Path to classified JSON with local_path"),
    ) -> None:
        """Write genre, BPM, key, and structured tags into audio file ID3/FLAC tags."""
        from cratekeeper.pipeline.tag_writer import tag_tracks

        profile = ctx.obj
        plan = Plan.load(input_file)
        candidates = sum(1 for t in plan.tracks if t.local_path)
        console.print(
            f"Loaded [green]{len(plan.tracks)}[/green] tracks, [cyan]{candidates}[/cyan] with local files "
            f"[dim](tag format: {profile.tag_format})[/dim]"
        )

        def _progress(i, total, track, ok):
            status = "[green]ok[/green]" if ok else "[red]failed[/red]"
            if i % 20 == 0 or i == total or not ok:
                console.print(f"  [{i}/{total}] {track.display_name()} → {status}")

        success, failed = tag_tracks(plan.tracks, progress_callback=_progress, tag_format=profile.tag_format)

        console.print(f"\n[green]Tagged {success} tracks[/green]", end="")
        if failed:
            console.print(f", [red]{failed} failed[/red]")
        else:
            console.print()

        plan.save(input_file)
        console.print(f"Saved to [green]{input_file}[/green]")

    @app.command(name="tag-untagged")
    def tag_untagged(
        input_file: Path = typer.Argument(help="Path to classified JSON"),
        audio_dir: Path = typer.Argument(help="Directory containing untagged audio files"),
    ) -> None:
        """Write basic metadata (title, artist, album, year, ISRC) into untagged audio files."""
        from cratekeeper.pipeline.tag_writer import tag_untagged_files

        plan = Plan.load(input_file)
        unmatched = [t for t in plan.tracks if not t.local_path]
        console.print(
            f"Loaded [green]{len(plan.tracks)}[/green] tracks, "
            f"[cyan]{len(unmatched)}[/cyan] without local files"
        )

        if not audio_dir.is_dir():
            console.print(f"[red]Directory not found: {audio_dir}[/red]")
            raise typer.Exit(1)

        def _progress(track, matched_file, exc):
            if exc:
                console.print(f"  [red]✗[/red] {track.display_name()} → error: {exc}")
            elif matched_file:
                console.print(f"  [green]✓[/green] {track.display_name()} → {matched_file.name}")
            else:
                console.print(f"  [red]✗[/red] {track.display_name()} → no matching file")

        tagged, not_found, errors = tag_untagged_files(plan.tracks, audio_dir, progress_callback=_progress)
        console.print(f"\n[green]Tagged {tagged}[/green], [yellow]{not_found} not found[/yellow], [red]{errors} errors[/red]")
