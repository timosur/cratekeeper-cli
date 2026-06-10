"""CLI commands for library and event folder building."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from cratekeeper.models import EventPlan, Plan

console = Console()


def _print_review_summary(summary) -> None:
    table = Table(title="Review Summary")
    table.add_column("Decision", style="cyan")
    table.add_column("Count", justify="right")
    table.add_row("Approved", f"[green]{summary.approved}[/green]")
    table.add_row("Rejected", f"[red]{summary.rejected}[/red]")
    table.add_row("Remaining undecided", f"[yellow]{summary.undecided}[/yellow]")
    console.print(table)


def register(app: typer.Typer) -> None:
    """Attach all builder commands to *app*."""

    @app.command(name="review-library")
    def review_library_cmd(
        ctx: typer.Context,
        input_file: Path = typer.Argument(help="Path to classified JSON plan"),
    ) -> None:
        """Interactively approve or reject candidate tracks for the master library."""
        import sys
        from cratekeeper.builder.review_library import (
            candidate_tracks, is_admission_complete, review_summary, undecided_candidates,
        )

        profile = ctx.obj
        required_fields = profile.required_fields

        if not sys.stdin.isatty():
            console.print("[red]review-library requires an interactive terminal. Stdin is not a TTY.[/red]")
            raise typer.Exit(1)

        plan = Plan.load(input_file)
        candidates = candidate_tracks(plan.tracks)
        if not candidates:
            console.print("[yellow]Nothing to review — no tracks have both a local file and a bucket. Run match/classify first.[/yellow]")
            return

        pending = undecided_candidates(plan.tracks)
        if not pending:
            console.print("[green]All candidates already reviewed.[/green]")
            _print_review_summary(review_summary(candidates))
            return

        console.print(
            f"[cyan]{len(candidates)}[/cyan] candidate(s) total, "
            f"[yellow]{len(pending)}[/yellow] undecided. Press [bold]a[/bold]=approve  "
            f"[bold]r[/bold]=reject  [bold]s[/bold]=skip  [bold]q[/bold]=quit."
        )

        quit_requested = False
        for idx, track in enumerate(pending, 1):
            info_lines = [f"[bold]{track.display_name()}[/bold]"]
            info_lines.append(f"Bucket: [cyan]{track.bucket}[/cyan]   Year: {track.release_year or '?'}")
            if track.bpm or track.key:
                info_lines.append(f"BPM: {track.bpm or '?'}   Key: {track.key or '?'}")
            if track.energy or track.function or track.crowd:
                info_lines.append(
                    f"Energy: {track.energy or '?'}   "
                    f"Function: {', '.join(track.function) or '?'}   "
                    f"Crowd: {', '.join(track.crowd) or '?'}"
                )
            if track.mood_tags:
                info_lines.append(f"Mood: {', '.join(track.mood_tags)}")
            if is_admission_complete(track, required_fields):
                info_lines.append("[green]Fully tagged for this profile[/green]")
            else:
                info_lines.append(f"[yellow]Not yet fully tagged (needs: {', '.join(required_fields)})[/yellow]")
            console.print(Panel("\n".join(info_lines), title=f"[{idx}/{len(pending)}]"))

            while True:
                try:
                    raw = input("  a=approve  r=reject  s=skip  q=quit > ").strip().lower()
                except EOFError:
                    console.print("\n[red]Stdin closed unexpectedly. Saving progress and exiting.[/red]")
                    plan.save(input_file)
                    raise typer.Exit(1)

                if not raw:
                    continue
                key = raw[0]
                if key == "a":
                    track.library_approval = "approved"
                    console.print("  [green]Approved[/green]")
                    break
                elif key == "r":
                    track.library_approval = "rejected"
                    console.print("  [red]Rejected[/red]")
                    break
                elif key == "s":
                    console.print("  [dim]Skipped (will reappear next run)[/dim]")
                    break
                elif key == "q":
                    console.print("  [yellow]Quitting and saving...[/yellow]")
                    quit_requested = True
                    break
                else:
                    console.print("  [yellow]Invalid key — press a, r, s, or q[/yellow]")

            if quit_requested:
                break

        plan.save(input_file)
        console.print(f"Saved to [green]{input_file}[/green]")
        _print_review_summary(review_summary(candidates))

    @app.command(name="build-library")
    def build_library_cmd(
        ctx: typer.Context,
        input_file: Path = typer.Argument(help="Path to classified JSON with local_path"),
        target: Path = typer.Option(None, "--target", "-t", help="Target directory (default: active profile's library_target)"),
    ) -> None:
        """Copy approved, fully-tagged matched files into a Genre/ folder structure."""
        from cratekeeper.builder.library_builder import build_library, library_preflight

        profile = ctx.obj
        if target is None:
            target = profile.library_target
        required_fields = profile.required_fields

        plan = Plan.load(input_file)
        pre = library_preflight(plan.tracks, required_fields)

        console.print(
            f"Loaded [green]{len(plan.tracks)}[/green] tracks, "
            f"[cyan]{pre.candidates}[/cyan] candidates, "
            f"[green]{pre.approved_tagged}[/green] approved+tagged "
            f"[dim](profile: {profile.name} → {target})[/dim]"
        )

        if pre.candidates and not pre.qualifies:
            console.print("[red]No tracks qualify for the master library.[/red]")
            if pre.undecided:
                console.print(
                    f"  [yellow]{pre.undecided} track(s) are undecided — "
                    f"run [bold]crate review-library {input_file}[/bold] first.[/yellow]"
                )
            if pre.untagged:
                console.print(
                    f"  [yellow]{pre.untagged} track(s) are approved but missing structured tags — "
                    f"run [bold]crate apply-tags[/bold] then [bold]crate tag[/bold].[/yellow]"
                )
            if pre.rejected:
                console.print(f"  [dim]{pre.rejected} track(s) were rejected.[/dim]")
            raise typer.Exit(1)

        def _progress(i, total, track, dest_path):
            if i % 20 == 0 or i == total:
                console.print(f"  [{i}/{total}] {track.display_name()}")

        result = build_library(plan.tracks, target, progress_callback=_progress, required_fields=required_fields, sort=profile.sort)

        table = Table(title="Library Build Results")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", justify="right")
        table.add_row("Copied", f"[green]{result.copied}[/green]")
        table.add_row("Already existed", f"[dim]{result.already_existed}[/dim]")
        table.add_row("Missing (no local file)", f"[yellow]{len(result.missing)}[/yellow]")
        table.add_row("Rejected", f"[dim]{result.rejected}[/dim]")
        table.add_row("Undecided / un-reviewed", f"[yellow]{result.undecided}[/yellow]")
        table.add_row("Excluded (missing tags)", f"[yellow]{result.missing_tags}[/yellow]")
        console.print(table)

        plan.save(input_file)
        console.print(f"Saved to [green]{input_file}[/green]")

    @app.command(name="build-event")
    def build_event_cmd(
        ctx: typer.Context,
        input_file: Path = typer.Argument(help="Path to classified JSON with local_path"),
        output: Path = typer.Option(..., "--output", "-o", help="Output directory for event folder"),
    ) -> None:
        """Copy fully-tagged tracks flat into an event folder (no Genre/ subfolders)."""
        from cratekeeper.builder.event_builder import build_event_folder, event_preflight

        profile = ctx.obj
        required_fields = profile.required_fields

        plan = Plan.load(input_file)
        if not isinstance(plan, EventPlan):
            console.print("[red]build-event is not applicable to library imports. Use build-library instead.[/red]")
            raise typer.Exit(1)
        console.print(f"Loaded [green]{len(plan.tracks)}[/green] tracks [dim](profile: {profile.name})[/dim]")

        pre = event_preflight(plan.tracks, required_fields)
        if pre.candidates and not pre.qualifies:
            console.print("[red]No tracks qualify for the event folder — none have all required tags.[/red]")
            console.print(
                f"  [yellow]{pre.untagged} track(s) are missing structured tags. "
                f"Run [bold]crate apply-tags[/bold] then [bold]crate tag[/bold] first.[/yellow]"
            )
            raise typer.Exit(1)

        def _progress(i, total, track, target_path):
            if i % 20 == 0 or i == total:
                console.print(f"  [{i}/{total}] {track.display_name()}")

        result = build_event_folder(
            plan.tracks, output, progress_callback=_progress,
            required_fields=required_fields, tag_format=profile.tag_format,
        )

        total_eligible = result.copied + result.already_existed
        if not total_eligible and pre.candidates:
            console.print("[red]No tracks were copied — none passed all eligibility gates.[/red]")
            if result.untagged_tracks:
                console.print(
                    f"  [yellow]{len(result.untagged_tracks)} track(s) were skipped for missing tags or "
                    f"unembedded comment. Run [bold]crate tag[/bold] on your local files, then retry.[/yellow]"
                )
            raise typer.Exit(1)

        table = Table(title="Event Folder Results")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", justify="right")
        table.add_row("Files copied", f"[green]{result.copied}[/green]")
        table.add_row("Already existed", f"[dim]{result.already_existed}[/dim]")
        table.add_row("Missing (no local file)", f"[yellow]{len(result.missing_tracks)}[/yellow]")
        table.add_row("Skipped (untagged / collision)", f"[yellow]{len(result.untagged_tracks)}[/yellow]")
        console.print(table)

        if result.missing_tracks:
            console.print(f"[yellow]{len(result.missing_tracks)} track(s) listed in {output / '_missing.txt'}[/yellow]")
        if result.untagged_tracks:
            untagged_count = len(result.untagged_tracks)
            collision_count = len(result.collision_tracks)
            detail = f" ({collision_count} collision(s))" if collision_count else ""
            console.print(
                f"[yellow]{untagged_count} track(s){detail} listed in {output / '_untagged.txt'} — "
                f"run [bold]crate tag[/bold] then retry.[/yellow]"
            )
