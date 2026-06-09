"""Cratekeeper — DJ library management CLI."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from cratekeeper.models import EventPlan, LibraryImportPlan, Plan

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


@app.command()
def fetch(
    ctx: typer.Context,
    playlist_url: str = typer.Argument(help="Spotify playlist URL or ID"),
    output: Path = typer.Option(None, "--output", "-o", help="Output JSON path (default: <profile data_dir>/<playlist-name>.json)"),
) -> None:
    """Fetch all tracks from a Spotify playlist, enrich with artist genres, save to JSON."""
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

    # Determine plan type
    import sys

    plan: Plan
    if sys.stdin.isatty():
        from rich.prompt import Prompt

        plan_choice = Prompt.ask(
            "Is this for an event or a library import?",
            choices=["event", "library"],
            default="event",
        )
        if plan_choice == "library":
            plan = LibraryImportPlan(
                source_playlist_id=playlist_id,
                source_playlist_name=playlist_name,
                tracks=tracks,
            )
            console.print("[cyan]Creating library-import plan[/cyan]")
        else:
            plan = EventPlan(
                source_playlist_id=playlist_id,
                source_playlist_name=playlist_name,
                tracks=tracks,
            )
            console.print("[cyan]Creating event plan[/cyan]")
    else:
        # Non-interactive: default to EventPlan
        plan = EventPlan(
            source_playlist_id=playlist_id,
            source_playlist_name=playlist_name,
            tracks=tracks,
        )

    if output is None:
        data_dir = ctx.obj.data_dir
        data_dir.mkdir(parents=True, exist_ok=True)
        safe_name = playlist_name.lower().replace(" ", "-").replace("/", "-")[:50]
        output = data_dir / f"{safe_name}.json"

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

    # Print summary table
    buckets = plan.bucket_summary()
    table = Table(title=f"Genre Classification — {plan.source_playlist_name} ({len(plan.tracks)} tracks)")
    table.add_column("Bucket", style="cyan")
    table.add_column("Tracks", justify="right", style="green")
    table.add_column("High", justify="right")
    table.add_column("Medium", justify="right")
    table.add_column("Low", justify="right")

    for bucket_name, bucket_tracks in buckets.items():
        high = sum(1 for t in bucket_tracks if t.confidence == "high")
        med = sum(1 for t in bucket_tracks if t.confidence == "medium")
        low = sum(1 for t in bucket_tracks if t.confidence == "low")
        table.add_row(bucket_name, str(len(bucket_tracks)), str(high), str(med), str(low))

    console.print(table)

    # Save classified version
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
    missing_year = sum(1 for t in plan.tracks if not t.release_year and t.isrc)
    candidates = sum(1 for t in plan.tracks if (not t.artist_genres or not t.release_year) and t.isrc)
    console.print(f"Loaded [green]{len(plan.tracks)}[/green] tracks, [cyan]{missing_genres}[/cyan] missing genres, [cyan]{missing_year}[/cyan] missing release year")

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
    plan = Plan.load(input_file)

    low_conf = [t for t in plan.tracks if t.confidence == "low"]
    med_conf = [t for t in plan.tracks if t.confidence == "medium"]

    if not low_conf and not med_conf:
        console.print("[green]All tracks classified with high confidence![/green]")
        return

    if med_conf:
        table = Table(title=f"Medium Confidence ({len(med_conf)} tracks)")
        table.add_column("#", justify="right", style="dim")
        table.add_column("Track")
        table.add_column("Bucket", style="cyan")
        table.add_column("Year", justify="right")
        table.add_column("Genres", style="dim")

        for i, t in enumerate(med_conf, 1):
            table.add_row(str(i), t.display_name(), t.bucket or "?", str(t.release_year or "?"), ", ".join(t.artist_genres[:3]) or "none")

        console.print(table)

    if low_conf:
        table = Table(title=f"Low Confidence / Fallback ({len(low_conf)} tracks)")
        table.add_column("#", justify="right", style="dim")
        table.add_column("Track")
        table.add_column("Bucket", style="yellow")
        table.add_column("Year", justify="right")
        table.add_column("Genres", style="dim")

        for i, t in enumerate(low_conf, 1):
            table.add_row(str(i), t.display_name(), t.bucket or "?", str(t.release_year or "?"), ", ".join(t.artist_genres[:3]) or "none")

        console.print(table)

    console.print(f"\nEdit the classified JSON directly to move tracks between buckets.")
    console.print(f"Or use the LLM skill for AI-assisted review.")


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


@app.command(name="sync-to-tidal")
def sync_to_tidal(
    input_file: Path = typer.Argument(help="Path to classified JSON"),
) -> None:
    """Sync classified playlists to Tidal via ISRC matching."""
    from cratekeeper.spotify.tidal import get_tidal_session, sync_plan_to_tidal

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


@app.command()
def scan(
    directory: Path = typer.Argument(help="Path to local music directory (e.g., /Volumes/home/Music/Library)"),
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
    from cratekeeper.local.matcher import match_tracks
    from cratekeeper.local.pg_repository import PostgresTrackRepository

    plan = Plan.load(input_file)

    console.print(f"Loaded [green]{len(plan.tracks)}[/green] tracks, matching against PostgreSQL...")

    def _progress(i, total, track, result):
        if result.local_path:
            console.print(f"  [{i}/{total}] {track.display_name()} → [green]{result.method}[/green] ({result.score}%)")

    repo = PostgresTrackRepository()
    results = match_tracks(plan.tracks, repo=repo, fuzzy_threshold=fuzzy_threshold, progress_callback=_progress)
    repo.close()

    # Summary
    by_method: dict[str, int] = {}
    for r in results:
        by_method[r.method] = by_method.get(r.method, 0) + 1

    table = Table(title="Match Results")
    table.add_column("Method", style="cyan")
    table.add_column("Tracks", justify="right", style="green")
    for method in ["isrc", "exact", "fuzzy", "none"]:
        count = by_method.get(method, 0)
        style = "red" if method == "none" else ""
        label = {"isrc": "ISRC match", "exact": "Artist+Title exact", "fuzzy": "Fuzzy match", "none": "Not found"}[method]
        table.add_row(label, f"[{style}]{count}[/{style}]" if style else str(count))
    console.print(table)

    # Save updated plan with local_path
    plan.save(input_file)
    console.print(f"Saved to [green]{input_file}[/green]")

    missing = [r.track for r in results if r.method == "none"]
    if missing:
        from cratekeeper.local.matcher import write_missing_report

        tidal_url_map: dict[str, str | None] = {}
        if tidal_urls:
            from cratekeeper.spotify.tidal import get_tidal_session, resolve_tidal_urls

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
    already = sum(1 for t in plan.tracks if t.local_path and _is_analyzed(t))
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

    # Energy summary
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


# ---------------------------------------------------------------------------
# review-library helpers
# ---------------------------------------------------------------------------

def _print_review_summary(candidates: list) -> None:
    """Print approve / reject / undecided counts for the review-library summary."""
    approved = sum(1 for t in candidates if t.library_approval == "approved")
    rejected = sum(1 for t in candidates if t.library_approval == "rejected")
    undecided = sum(1 for t in candidates if t.library_approval == "undecided")
    table = Table(title="Review Summary")
    table.add_column("Decision", style="cyan")
    table.add_column("Count", justify="right")
    table.add_row("Approved", f"[green]{approved}[/green]")
    table.add_row("Rejected", f"[red]{rejected}[/red]")
    table.add_row("Remaining undecided", f"[yellow]{undecided}[/yellow]")
    console.print(table)


@app.command(name="review-library")
def review_library_cmd(
    ctx: typer.Context,
    input_file: Path = typer.Argument(help="Path to classified JSON plan"),
) -> None:
    """Interactively approve or reject candidate tracks for the master library."""
    import sys
    from rich.panel import Panel
    from cratekeeper.builder.review_library import candidate_tracks, is_admission_complete, undecided_candidates

    profile = ctx.obj
    required_fields = profile.required_fields

    # EC-5: refuse to run when stdin is not an interactive terminal.
    if not sys.stdin.isatty():
        console.print("[red]review-library requires an interactive terminal. Stdin is not a TTY.[/red]")
        raise typer.Exit(1)

    plan = Plan.load(input_file)

    candidates = candidate_tracks(plan.tracks)
    if not candidates:
        # EC-1
        console.print("[yellow]Nothing to review — no tracks have both a local file and a bucket. Run match/classify first.[/yellow]")
        return

    pending = undecided_candidates(plan.tracks)
    if not pending:
        # EC-2
        console.print("[green]All candidates already reviewed.[/green]")
        _print_review_summary(candidates)
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
                # EC-5: piped stdin exhausted mid-loop
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
                # library_approval stays "undecided" — will reappear next run (AC-4)
                console.print("  [dim]Skipped (will reappear next run)[/dim]")
                break
            elif key == "q":
                console.print("  [yellow]Quitting and saving...[/yellow]")
                quit_requested = True
                break
            else:
                # EC-4: invalid key → re-prompt
                console.print("  [yellow]Invalid key — press a, r, s, or q[/yellow]")

        if quit_requested:
            break

    plan.save(input_file)
    console.print(f"Saved to [green]{input_file}[/green]")
    _print_review_summary(candidates)


@app.command(name="build-library")
def build_library_cmd(
    ctx: typer.Context,
    input_file: Path = typer.Argument(help="Path to classified JSON with local_path"),
    target: Path = typer.Option(None, "--target", "-t", help="Target directory (default: active profile's library_target)"),
) -> None:
    """Copy approved, fully-tagged matched files into a Genre/ folder structure."""
    from cratekeeper.builder.library_builder import build_library
    from cratekeeper.pipeline.tag_writer import is_fully_tagged

    profile = ctx.obj
    if target is None:
        target = profile.library_target
    required_fields = profile.required_fields

    plan = Plan.load(input_file)

    candidates = [t for t in plan.tracks if t.local_path and t.bucket]
    approved_tagged = [t for t in candidates if t.library_approval == "approved" and is_fully_tagged(t, required_fields)]

    console.print(
        f"Loaded [green]{len(plan.tracks)}[/green] tracks, "
        f"[cyan]{len(candidates)}[/cyan] candidates, "
        f"[green]{len(approved_tagged)}[/green] approved+tagged "
        f"[dim](profile: {profile.name} → {target})[/dim]"
    )

    # AC-6: candidates exist but none qualify → warn and exit non-zero without copying.
    if candidates and not approved_tagged:
        undecided_count = sum(1 for t in candidates if t.library_approval == "undecided")
        rejected_count = sum(1 for t in candidates if t.library_approval == "rejected")
        untagged_count = sum(
            1 for t in candidates
            if t.library_approval == "approved" and not is_fully_tagged(t, required_fields)
        )
        console.print("[red]No tracks qualify for the master library.[/red]")
        if undecided_count:
            console.print(
                f"  [yellow]{undecided_count} track(s) are undecided — "
                f"run [bold]crate review-library {input_file}[/bold] first.[/yellow]"
            )
        if untagged_count:
            console.print(
                f"  [yellow]{untagged_count} track(s) are approved but missing structured tags — "
                f"run [bold]crate apply-tags[/bold] then [bold]crate tag[/bold].[/yellow]"
            )
        if rejected_count:
            console.print(f"  [dim]{rejected_count} track(s) were rejected.[/dim]")
        raise typer.Exit(1)

    def _progress(i, total, track, dest_path):
        if i % 20 == 0 or i == total:
            console.print(f"  [{i}/{total}] {track.display_name()}")

    result = build_library(
        plan.tracks, target, progress_callback=_progress,
        required_fields=required_fields, sort=profile.sort,
    )

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
    output: Path = typer.Option(..., "--output", "-o", help="Output directory for event folder (e.g., ~/Music/Events/Wedding/)"),
) -> None:
    """Copy fully-tagged tracks flat into an event folder (no Genre/ subfolders)."""
    from cratekeeper.builder.event_builder import build_event_folder
    from cratekeeper.pipeline.tag_writer import is_fully_tagged as _is_fully_tagged

    profile = ctx.obj
    required_fields = profile.required_fields

    plan = Plan.load(input_file)
    if not isinstance(plan, EventPlan):
        console.print("[red]build-event is not applicable to library imports. Use build-library instead.[/red]")
        raise typer.Exit(1)
    console.print(f"Loaded [green]{len(plan.tracks)}[/green] tracks [dim](profile: {profile.name})[/dim]")

    # AC-7: warn early if nothing will qualify (plan-field check only — fast pre-scan)
    candidates = [t for t in plan.tracks if t.local_path]
    fully_tagged_candidates = [t for t in candidates if _is_fully_tagged(t, required_fields)]
    if candidates and not fully_tagged_candidates:
        untagged_count = len(candidates) - len(fully_tagged_candidates)
        console.print("[red]No tracks qualify for the event folder — none have all required tags.[/red]")
        console.print(
            f"  [yellow]{untagged_count} track(s) are missing structured tags "
            f"(energy, function, crowd, mood_tags). Run [bold]crate apply-tags[/bold] "
            f"then [bold]crate tag[/bold] first.[/yellow]"
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
    # AC-7: zero eligible after the full dual gate
    if not total_eligible and (candidates or fully_tagged_candidates):
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
    """Write basic metadata (title, artist, album, year, ISRC) into untagged audio files.

    Matches tracks from the classified JSON to audio files by normalizing
    filenames against track titles. Useful for purchased or acquired files
    that are missing ID3/MP4 tags.
    """
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
    console.print(
        f"Importing local files under [cyan]{source_path}[/cyan] "
        f"[dim](profile: {profile.name})[/dim]"
    )

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
        data_dir = profile.data_dir
        data_dir.mkdir(parents=True, exist_ok=True)
        safe_name = (source.name or "import").lower().replace(" ", "-").replace("/", "-")[:50]
        output = data_dir / f"{safe_name}.json"

    plan.save(output)

    # Bucket summary
    summary = plan.bucket_summary()
    table = Table(title=f"Imported {len(tracks)} tracks — {profile.name}")
    table.add_column("Bucket", style="cyan")
    table.add_column("Tracks", justify="right", style="green")
    for bucket_name, bucket_tracks in summary.items():
        table.add_row(bucket_name, str(len(bucket_tracks)))
    console.print(table)

    console.print(f"Saved library-import plan to [green]{output}[/green]")
    console.print("Next: [bold]crate review-library[/bold] then [bold]crate build-library[/bold].")


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

    console.print(
        f"[green]Wrote {track_count} tracks across {bucket_count} playlist(s)[/green] to {out_path}"
    )


# ---------------------------------------------------------------------------
# profile subcommands
# ---------------------------------------------------------------------------

profile_app = typer.Typer(help="Inspect and manage configuration profiles")
app.add_typer(profile_app, name="profile")


@profile_app.command("list")
def profile_list() -> None:
    """List defined profiles and mark the active one."""
    from cratekeeper.config import active_profile_name, load_settings

    settings = load_settings()
    if settings is None:
        console.print("No config file found — using the implicit [green]commercial[/green] profile.")
        console.print("Run [bold]crate profile init[/bold] to create a config with multiple profiles.")
        return

    active = active_profile_name(settings)
    table = Table(title="Profiles")
    table.add_column("", style="green")
    table.add_column("Name", style="cyan")
    table.add_column("Buckets", justify="right")
    table.add_column("DJ software")
    table.add_column("Tag format")
    for name, prof in settings.profiles.items():
        marker = "*" if name == active else ""
        table.add_row(marker, name, str(len(prof.buckets)), prof.dj_software, prof.tag_format)
    console.print(table)


@profile_app.command("show")
def profile_show(
    name: str = typer.Argument(None, help="Profile name (default: active profile)"),
) -> None:
    """Print the fully resolved settings for a profile."""
    from cratekeeper.config import ConfigError, resolve_profile

    try:
        prof = resolve_profile(name)
    except ConfigError as exc:
        console.print(f"[red]Config error:[/red] {exc}")
        raise typer.Exit(1)

    info = prof.describe()
    table = Table(title=f"Profile: {info['name']}")
    table.add_column("Setting", style="cyan")
    table.add_column("Value")
    table.add_row("Buckets", ", ".join(info["buckets"]))
    table.add_row("Fallback", info["fallback"])
    table.add_row("DJ software", info["dj_software"])
    table.add_row("Tag format", info["tag_format"])
    table.add_row("Library target", info["library_target"])
    table.add_row("Data dir", info["data_dir"])
    table.add_row("Required fields", ", ".join(info["required_fields"]))
    sort = info["sort"]
    table.add_row("Sort", "none" if sort is None else f"{', '.join(sort['keys'])} ({sort['direction']})")
    console.print(table)


@profile_app.command("use")
def profile_use(
    name: str = typer.Argument(help="Profile name to activate"),
) -> None:
    """Set the active profile in the config file."""
    from cratekeeper.config import ConfigError, set_active_profile

    try:
        path = set_active_profile(name)
    except ConfigError as exc:
        console.print(f"[red]Config error:[/red] {exc}")
        raise typer.Exit(1)
    console.print(f"[green]Active profile set to '{name}'[/green] in {path}")


@profile_app.command("init")
def profile_init() -> None:
    """Scaffold a config file with commercial + electronic example profiles."""
    from cratekeeper.config import ConfigError, _legacy_data_dir, write_default_config

    try:
        path = write_default_config()
    except ConfigError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1)
    console.print(f"[green]Created config at {path}[/green]")
    console.print(
        "[yellow]Note:[/yellow] existing plans in "
        f"[dim]{_legacy_data_dir()}[/dim] are not auto-migrated. "
        "Move them into a profile's data_dir or re-import."
    )


@app.command()
def wizard(
    ctx: typer.Context,
    plan: Path = typer.Option(None, "--plan", help="Existing plan file to resume from"),
) -> None:
    """Interactive wizard — guides you through the full pipeline step by step."""
    from cratekeeper.wizard import run_wizard

    run_wizard(profile=ctx.obj, plan_path=plan)


if __name__ == "__main__":
    app()
