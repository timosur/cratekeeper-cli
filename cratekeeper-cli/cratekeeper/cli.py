"""Cratekeeper — DJ library management CLI."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from cratekeeper.models import EventPlan

app = typer.Typer(help="Cratekeeper — DJ library management CLI")
console = Console()

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"


@app.command()
def fetch(
    playlist_url: str = typer.Argument(help="Spotify playlist URL or ID"),
    output: Path = typer.Option(None, "--output", "-o", help="Output JSON path (default: data/<playlist-name>.json)"),
) -> None:
    """Fetch all tracks from a Spotify playlist, enrich with artist genres, save to JSON."""
    from cratekeeper.spotify_client import (
        extract_playlist_id,
        fetch_artist_genres,
        fetch_playlist_tracks,
        get_spotify_client,
    )

    console.print("[bold]Connecting to Spotify...[/bold]")
    sp = get_spotify_client()

    playlist_id = extract_playlist_id(playlist_url)
    console.print(f"Fetching playlist [cyan]{playlist_id}[/cyan]...")

    playlist_name, tracks = fetch_playlist_tracks(sp, playlist_id)
    console.print(f"Found [green]{len(tracks)}[/green] tracks in '{playlist_name}'")

    # Collect unique artist IDs
    all_artist_ids = list({aid for t in tracks for aid in t.artist_ids})
    console.print(f"Fetching genres for [cyan]{len(all_artist_ids)}[/cyan] unique artists...")
    artist_genres = fetch_artist_genres(sp, all_artist_ids)

    # Enrich tracks with genres
    for track in tracks:
        genres: list[str] = []
        for aid in track.artist_ids:
            genres.extend(artist_genres.get(aid, []))
        track.artist_genres = list(set(genres))

    # Save
    plan = EventPlan(
        source_playlist_id=playlist_id,
        source_playlist_name=playlist_name,
        tracks=tracks,
    )

    if output is None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        safe_name = playlist_name.lower().replace(" ", "-").replace("/", "-")[:50]
        output = DATA_DIR / f"{safe_name}.json"

    plan.save(output)
    console.print(f"Saved to [green]{output}[/green]")


@app.command()
def classify(
    input_file: Path = typer.Argument(help="Path to fetched playlist JSON"),
    min_bucket_size: int = typer.Option(3, "--min-bucket", help="Minimum tracks per bucket (smaller buckets get merged)"),
    enrich: bool = typer.Option(False, "--enrich", "-e", help="Enrich missing genres via MusicBrainz before classifying"),
) -> None:
    """Classify tracks into genre buckets and print a summary."""
    from cratekeeper.classifier import classify_tracks, consolidate_small_buckets

    plan = EventPlan.load(input_file)
    console.print(f"Loaded [green]{len(plan.tracks)}[/green] tracks from '{plan.source_playlist_name}'")

    if enrich:
        from cratekeeper.musicbrainz_client import enrich_tracks_genres

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

    classify_tracks(plan.tracks)
    consolidate_small_buckets(plan.tracks, min_size=min_bucket_size)

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
    from cratekeeper.musicbrainz_client import enrich_tracks_genres

    plan = EventPlan.load(input_file)
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
    plan = EventPlan.load(input_file)

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
    from cratekeeper.spotify_client import (
        add_tracks_to_playlist,
        create_playlist,
        get_spotify_client,
    )

    plan = EventPlan.load(input_file)
    plan.event_name = event
    plan.event_date = date

    sp = get_spotify_client()
    buckets = plan.bucket_summary()

    console.print(f"Creating [cyan]{len(buckets)}[/cyan] playlists for '{event}'...")

    for bucket_name, bucket_tracks in buckets.items():
        if bucket_name == "Unclassified":
            continue

        playlist_name = f"{event} — {bucket_name}"
        description = f"{event} — {date} — {bucket_name} — Auto-sorted from wish playlist"

        playlist_id = create_playlist(sp, playlist_name, description)
        track_ids = [t.id for t in bucket_tracks]
        add_tracks_to_playlist(sp, playlist_id, track_ids)

        plan.created_playlists[bucket_name] = playlist_id
        console.print(f"  ✓ {playlist_name} — {len(track_ids)} tracks")

    plan.save(input_file)
    console.print(f"\n[green]Done![/green] Created {len(plan.created_playlists)} playlists.")


@app.command(name="build-masters")
def build_masters(
    input_file: Path = typer.Argument(help="Path to classified JSON"),
) -> None:
    """Add classified tracks to cross-event [DJ] master playlists on Spotify."""
    from cratekeeper.spotify_client import (
        add_tracks_to_playlist,
        create_playlist,
        get_playlist_track_ids,
        get_spotify_client,
        get_user_playlists,
    )

    plan = EventPlan.load(input_file)
    sp = get_spotify_client()
    buckets = plan.bucket_summary()

    # Find existing [DJ] playlists
    user_playlists = get_user_playlists(sp)
    dj_playlists = {p["name"]: p["id"] for p in user_playlists if p["name"].startswith("[DJ] ")}

    console.print(f"Found [cyan]{len(dj_playlists)}[/cyan] existing [DJ] master playlists")

    total_added = 0
    total_dupes = 0

    for bucket_name, bucket_tracks in buckets.items():
        if bucket_name == "Unclassified":
            continue

        master_name = f"[DJ] {bucket_name}"
        track_ids = [t.id for t in bucket_tracks]

        if master_name in dj_playlists:
            playlist_id = dj_playlists[master_name]
            existing_ids = get_playlist_track_ids(sp, playlist_id)
            new_ids = [tid for tid in track_ids if tid not in existing_ids]
            dupes = len(track_ids) - len(new_ids)
        else:
            playlist_id = create_playlist(sp, master_name, f"Cross-event master playlist — {bucket_name}")
            dj_playlists[master_name] = playlist_id
            new_ids = track_ids
            dupes = 0

        if new_ids:
            add_tracks_to_playlist(sp, playlist_id, new_ids)

        total_added += len(new_ids)
        total_dupes += dupes

        status = f"+{len(new_ids)} new"
        if dupes:
            status += f", {dupes} dupes skipped"
        console.print(f"  {master_name} — {status}")

    console.print(f"\n[green]Done![/green] Added {total_added} tracks, skipped {total_dupes} duplicates.")


@app.command(name="sync-to-tidal")
def sync_to_tidal(
    input_file: Path = typer.Argument(help="Path to classified JSON"),
) -> None:
    """Sync classified playlists to Tidal via ISRC matching."""
    from cratekeeper.tidal_client import (
        add_tracks_by_isrc,
        create_playlist,
        get_tidal_session,
    )

    plan = EventPlan.load(input_file)
    session = get_tidal_session()
    buckets = plan.bucket_summary()

    event_prefix = plan.event_name or plan.source_playlist_name

    console.print(f"Syncing [cyan]{len(buckets)}[/cyan] playlists to Tidal...")

    total_added = 0
    total_failed = 0

    for bucket_name, bucket_tracks in buckets.items():
        if bucket_name == "Unclassified":
            continue

        isrcs = [t.isrc for t in bucket_tracks if t.isrc]
        if not isrcs:
            console.print(f"  ✗ {bucket_name} — no ISRCs available, skipping")
            continue

        playlist_name = f"{event_prefix} — {bucket_name}"
        tidal_playlist_id = create_playlist(session, playlist_name)
        added, failed = add_tracks_by_isrc(session, tidal_playlist_id, isrcs)

        plan.tidal_playlists[bucket_name] = tidal_playlist_id
        total_added += len(added)
        total_failed += len(failed)

        status = f"✓ {len(added)}/{len(isrcs)} matched"
        if failed:
            status += f", {len(failed)} failed"
        console.print(f"  {playlist_name} — {status}")

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
    from cratekeeper.local_scanner import get_db_stats, scan_directory

    console.print(f"Scanning [cyan]{directory}[/cyan] for audio files...")
    if not full:
        console.print("[dim]Incremental mode — skipping already indexed files[/dim]")

    def _progress(new, skip, path):
        name = path.name if path else "done"
        console.print(f"  [green]+{new} new[/green], [dim]{skip} skipped[/dim] — {name}")

    conn, new_count, skipped, updated_count = scan_directory(
        directory, incremental=not full, progress_callback=_progress,
    )
    conn.close()

    stats = get_db_stats()
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
    from cratekeeper.matcher import match_tracks

    plan = EventPlan.load(input_file)

    console.print(f"Loaded [green]{len(plan.tracks)}[/green] tracks, matching against PostgreSQL...")

    def _progress(i, total, track, result):
        if result.local_path:
            console.print(f"  [{i}/{total}] {track.display_name()} → [green]{result.method}[/green] ({result.score}%)")

    results = match_tracks(plan.tracks, fuzzy_threshold=fuzzy_threshold, progress_callback=_progress)

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

    # Write missing report
    missing = [r.track for r in results if r.method == "none"]
    if missing:
        # Optionally resolve Tidal URLs for missing tracks
        tidal_url_map: dict[str, str | None] = {}
        if tidal_urls:
            from cratekeeper.tidal_client import get_tidal_session, resolve_tidal_urls

            console.print(f"\nResolving Tidal URLs for [cyan]{len(missing)}[/cyan] missing tracks...")
            session = get_tidal_session()
            isrcs = [t.isrc for t in missing if t.isrc]

            def _tidal_progress(i, total, isrc, url):
                status = f"[green]{url}[/green]" if url else "[dim]not found[/dim]"
                console.print(f"  [{i}/{total}] {isrc} → {status}")

            tidal_url_map = resolve_tidal_urls(session, isrcs, progress_callback=_tidal_progress)
            found = sum(1 for u in tidal_url_map.values() if u)
            console.print(f"Resolved [green]{found}[/green] of {len(isrcs)} Tidal URLs")

        # Write human-readable missing file
        missing_file = input_file.with_suffix(".missing.txt")
        lines = []
        for t in missing:
            line = f"{t.display_name()} (ISRC: {t.isrc or 'none'})"
            if tidal_urls and t.isrc and tidal_url_map.get(t.isrc):
                line += f"  {tidal_url_map[t.isrc]}"
            lines.append(line)
        missing_file.write_text("\n".join(lines))

        # Write ISRC-only file
        isrc_file = input_file.with_suffix(".missing-isrcs.txt")
        isrcs = [t.isrc for t in missing if t.isrc]
        isrc_file.write_text("\n".join(isrcs))

        console.print(f"[yellow]{len(missing)} unmatched tracks written to {missing_file}[/yellow]")
        console.print(f"[yellow]{len(isrcs)} ISRCs written to {isrc_file}[/yellow]")

        # Write Tidal URLs file if requested
        if tidal_urls:
            tidal_file = input_file.with_suffix(".missing-tidal.txt")
            tidal_lines = [tidal_url_map[t.isrc] for t in missing if t.isrc and tidal_url_map.get(t.isrc)]
            if tidal_lines:
                tidal_file.write_text("\n".join(tidal_lines))
                console.print(f"[yellow]{len(tidal_lines)} Tidal URLs written to {tidal_file}[/yellow]")


@app.command(name="analyze-mood")
def analyze_mood(
    input_file: Path = typer.Argument(help="Path to classified JSON (tracks must have local_path set)"),
) -> None:
    """Analyze audio features and assign mood to each locally matched track.

    Requires essentia — run via Docker if not installed locally.
    """
    from cratekeeper.mood_analyzer import analyze_tracks

    plan = EventPlan.load(input_file)
    with_path = sum(1 for t in plan.tracks if t.local_path)
    console.print(f"Loaded [green]{len(plan.tracks)}[/green] tracks, [cyan]{with_path}[/cyan] have local files")

    if not with_path:
        console.print("[red]No tracks have local_path set. Run 'dj match' first.[/red]")
        raise typer.Exit(1)

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

    analyzed = analyze_tracks(plan.tracks, progress_callback=_progress)
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


@app.command(name="build-library")
def build_library_cmd(
    input_file: Path = typer.Argument(help="Path to classified JSON with local_path"),
    target: Path = typer.Option(Path.home() / "Music" / "Library", "--target", "-t", help="Target directory for the master library"),
) -> None:
    """Copy matched local files into a Genre/ folder structure."""
    from cratekeeper.library_builder import build_library

    plan = EventPlan.load(input_file)
    candidates = sum(1 for t in plan.tracks if t.local_path)
    with_bucket = sum(1 for t in plan.tracks if t.local_path and t.bucket)
    console.print(f"Loaded [green]{len(plan.tracks)}[/green] tracks, [cyan]{candidates}[/cyan] with local files, [cyan]{with_bucket}[/cyan] with bucket")

    if with_bucket == 0 and candidates > 0:
        console.print("[red]No tracks have a bucket set. Run 'dj classify' first.[/red]")
        raise typer.Exit(1)

    def _progress(i, total, track, dest_path):
        if i % 20 == 0 or i == total:
            console.print(f"  [{i}/{total}] {track.display_name()}")

    copied, skipped, missing = build_library(plan.tracks, target, progress_callback=_progress)

    table = Table(title="Library Build Results")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right", style="green")
    table.add_row("Copied", str(copied))
    table.add_row("Already existed", str(skipped))
    table.add_row("Missing (no local file)", str(len(missing)))
    console.print(table)

    plan.save(input_file)
    console.print(f"Saved to [green]{input_file}[/green]")


@app.command(name="build-event")
def build_event_cmd(
    input_file: Path = typer.Argument(help="Path to classified JSON with local_path"),
    output: Path = typer.Option(..., "--output", "-o", help="Output directory for event folder (e.g., ~/Music/Events/Wedding/)"),
) -> None:
    """Create an event folder with copies organized by Genre/."""
    from cratekeeper.event_builder import build_event_folder

    plan = EventPlan.load(input_file)
    console.print(f"Loaded [green]{len(plan.tracks)}[/green] tracks")

    def _progress(i, total, track, target_path):
        if i % 20 == 0 or i == total:
            console.print(f"  [{i}/{total}] {track.display_name()}")

    created, skipped, missing = build_event_folder(plan.tracks, output, progress_callback=_progress)

    table = Table(title="Event Folder Results")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right", style="green")
    table.add_row("Files copied", str(created))
    table.add_row("Already existed", str(skipped))
    table.add_row("Missing (no local file)", str(len(missing)))
    console.print(table)

    if missing:
        console.print(f"[yellow]{len(missing)} tracks written to {output / '_missing.txt'}[/yellow]")


@app.command(name="apply-tags")
def apply_tags(
    input_file: Path = typer.Argument(help="Path to classified JSON"),
    tags_file: Path = typer.Argument(help="Path to tags JSON (array of {id, energy, function, crowd, mood_tags})"),
) -> None:
    """Apply pre-classified tags from a JSON file into the classified event plan."""
    import json as _json

    VALID_ENERGY = {"low", "mid", "high"}
    VALID_FUNCTION = {"floorfiller", "singalong", "bridge", "reset", "closer", "opener"}
    VALID_CROWD = {"mixed-age", "older", "younger", "family"}
    VALID_MOOD = {
        "feelgood", "emotional", "euphoric", "nostalgic",
        "romantic", "melancholic", "dark", "aggressive",
        "uplifting", "dreamy", "funky", "groovy",
    }

    plan = EventPlan.load(input_file)
    tags_data = _json.loads(tags_file.read_text())

    if not isinstance(tags_data, list):
        console.print("[red]Tags file must contain a JSON array[/red]")
        raise typer.Exit(1)

    track_map = {t.id: t for t in plan.tracks}
    applied = 0
    warnings = 0

    for entry in tags_data:
        tid = entry.get("id")
        track = track_map.get(tid)
        if not track:
            console.print(f"  [yellow]Warning: unknown track id {tid}, skipping[/yellow]")
            warnings += 1
            continue

        # Energy
        energy = entry.get("energy")
        if energy and energy in VALID_ENERGY:
            track.energy = energy

        # Function
        funcs = entry.get("function", [])
        track.function = [f for f in funcs if f in VALID_FUNCTION]

        # Crowd
        crowd = entry.get("crowd", [])
        track.crowd = [c for c in crowd if c in VALID_CROWD]

        # Mood tags
        mood_tags = entry.get("mood_tags", [])
        track.mood_tags = [m for m in mood_tags if m in VALID_MOOD]

        # Genre re-assignment
        genre = entry.get("genre_suggestion")
        if genre and genre != track.bucket:
            console.print(f"  [cyan]{track.display_name()}[/cyan]: bucket {track.bucket} → {genre}")
            track.bucket = genre

        applied += 1
        console.print(f"  [{applied}/{len(tags_data)}] {track.display_name()} → energy={track.energy} func={track.function} crowd={track.crowd} mood={track.mood_tags}")

    plan.save(input_file)
    console.print(f"\n[green]Applied tags to {applied} tracks[/green]", end="")
    if warnings:
        console.print(f", [yellow]{warnings} warnings[/yellow]")
    else:
        console.print()
    console.print(f"Saved to [green]{input_file}[/green]")


@app.command()
def tag(
    input_file: Path = typer.Argument(help="Path to classified JSON with local_path"),
) -> None:
    """Write genre, BPM, key, and structured tags into audio file ID3/FLAC tags."""
    from cratekeeper.tag_writer import tag_tracks

    plan = EventPlan.load(input_file)
    candidates = sum(1 for t in plan.tracks if t.local_path)
    console.print(f"Loaded [green]{len(plan.tracks)}[/green] tracks, [cyan]{candidates}[/cyan] with local files")

    def _progress(i, total, track, ok):
        status = "[green]ok[/green]" if ok else "[red]failed[/red]"
        if i % 20 == 0 or i == total or not ok:
            console.print(f"  [{i}/{total}] {track.display_name()} → {status}")

    success, failed = tag_tracks(plan.tracks, progress_callback=_progress)

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
    import unicodedata
    import re
    from mutagen.mp4 import MP4

    plan = EventPlan.load(input_file)
    unmatched = [t for t in plan.tracks if not t.local_path]
    console.print(
        f"Loaded [green]{len(plan.tracks)}[/green] tracks, "
        f"[cyan]{len(unmatched)}[/cyan] without local files"
    )

    if not audio_dir.is_dir():
        console.print(f"[red]Directory not found: {audio_dir}[/red]")
        raise typer.Exit(1)

    # Collect all audio files in directory
    audio_files: list[Path] = []
    for ext in ("*.m4a", "*.mp4", "*.flac", "*.mp3"):
        audio_files.extend(audio_dir.rglob(ext))

    console.print(f"Found [cyan]{len(audio_files)}[/cyan] audio files in {audio_dir}")

    def _norm(text: str) -> str:
        text = text.lower().strip()
        text = unicodedata.normalize("NFKD", text)
        text = "".join(c for c in text if not unicodedata.combining(c))
        text = re.sub(r"[^\w\s]", "", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    # Build lookup: normalized stem -> file path
    file_map: dict[str, Path] = {}
    for f in audio_files:
        file_map[_norm(f.stem)] = f

    tagged = 0
    skipped = 0
    not_found = 0

    for track in unmatched:
        norm_title = _norm(track.name)
        matched_file = file_map.get(norm_title)

        if not matched_file:
            # Try partial matching
            for norm_stem, fpath in file_map.items():
                if norm_title in norm_stem or norm_stem in norm_title:
                    matched_file = fpath
                    break

        if not matched_file:
            console.print(f"  [red]✗[/red] {track.display_name()} → no matching file")
            not_found += 1
            continue

        suffix = matched_file.suffix.lower()
        try:
            if suffix in (".m4a", ".mp4"):
                audio = MP4(str(matched_file))
                audio["\xa9nam"] = [track.name]
                audio["\xa9ART"] = [", ".join(track.artists)]
                audio["\xa9alb"] = [track.album]
                if track.release_year:
                    audio["\xa9day"] = [str(track.release_year)]
                if track.isrc:
                    audio["----:com.apple.iTunes:ISRC"] = [track.isrc.encode("utf-8")]
                audio.save()
            else:
                import mutagen
                audio = mutagen.File(str(matched_file), easy=True)
                if audio is None:
                    raise ValueError("Cannot open file")
                audio["title"] = track.name
                audio["artist"] = ", ".join(track.artists)
                audio["album"] = track.album
                if track.release_year:
                    audio["date"] = str(track.release_year)
                audio.save()

            console.print(f"  [green]✓[/green] {track.display_name()} → {matched_file.name}")
            tagged += 1
        except Exception as e:
            console.print(f"  [red]✗[/red] {track.display_name()} → error: {e}")
            skipped += 1

    console.print(f"\n[green]Tagged {tagged}[/green], [yellow]{not_found} not found[/yellow], [red]{skipped} errors[/red]")


if __name__ == "__main__":
    app()
