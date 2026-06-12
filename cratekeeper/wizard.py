"""Interactive wizard — guides users through the full CLI pipeline step by step."""

from __future__ import annotations

import json as _json
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import questionary
from questionary import Choice
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

from cratekeeper.models import EventPlan, LibraryImportPlan, Plan

console = Console()


# ---------------------------------------------------------------------------
# Interactive prompt helpers (arrow-key menus with non-TTY fallback)
# ---------------------------------------------------------------------------

def _interactive() -> bool:
    """True when both stdin and stdout are attached to a real terminal."""
    return sys.stdin.isatty() and sys.stdout.isatty()


def select(message: str, choices: list[Choice], default: str | None = None) -> str:
    """Single-select arrow-key menu.

    Falls back to a typed Rich prompt when not running on a TTY (e.g. piped
    input, CI, or tests) so the wizard remains scriptable.
    """
    if _interactive():
        answer = questionary.select(
            message,
            choices=choices,
            default=default,
            instruction="(use ↑/↓ arrows, Enter to confirm)",
        ).ask()
        if answer is None:  # user pressed Ctrl-C / Esc
            raise KeyboardInterrupt
        return answer
    values = [c.value for c in choices]
    return Prompt.ask(message, choices=values, default=default)


def confirm(message: str, default: bool = True) -> bool:
    """Yes/no arrow-key confirmation with non-TTY fallback to a Rich prompt."""
    if _interactive():
        answer = questionary.confirm(message, default=default).ask()
        if answer is None:  # user pressed Ctrl-C / Esc
            raise KeyboardInterrupt
        return answer
    return Confirm.ask(message, default=default)


# ---------------------------------------------------------------------------
# Step descriptor
# ---------------------------------------------------------------------------

@dataclass
class Step:
    """Describes one pipeline step the wizard can execute."""

    id: str
    label: str
    required: bool
    needs_docker: bool = False
    needs_input: list[str] = field(default_factory=list)
    run: Callable[..., Any] = field(default=lambda **kw: None)
    is_complete: Callable[[Plan], bool] = field(default=lambda plan: False)


# ---------------------------------------------------------------------------
# is_complete helpers
# ---------------------------------------------------------------------------

def _fetch_complete(plan: Plan) -> bool:
    return len(plan.tracks) > 0


def _classify_complete(plan: Plan) -> bool:
    return bool(plan.tracks) and all(t.bucket for t in plan.tracks)


def _enrich_complete(plan: Plan) -> bool:
    candidates = [t for t in plan.tracks if t.isrc]
    if not candidates:
        return True
    return all(t.artist_genres for t in candidates)


def _match_complete(plan: Plan) -> bool:
    return bool(plan.tracks) and all(t.local_path for t in plan.tracks if t.bucket)


def _analyze_mood_complete(plan: Plan) -> bool:
    with_path = [t for t in plan.tracks if t.local_path]
    if not with_path:
        return False
    return all(t.bpm is not None and t.audio_mood for t in with_path)


def _apply_tags_complete(plan: Plan) -> bool:
    with_path = [t for t in plan.tracks if t.local_path]
    if not with_path:
        return False
    return all(t.energy and t.function for t in with_path)


def _tag_complete(plan: Plan) -> bool:
    """No tags_written field exists — use bucket + local_path + bpm as proxy."""
    with_path = [t for t in plan.tracks if t.local_path and t.bucket]
    if not with_path:
        return False
    # After tagging, tracks should have bpm written. This is a heuristic.
    return all(t.bpm is not None for t in with_path)


def _review_library_complete(plan: Plan) -> bool:
    candidates = [t for t in plan.tracks if t.local_path and t.bucket]
    if not candidates:
        return False
    return all(t.library_approval != "undecided" for t in candidates)


def _build_library_complete(plan: Plan) -> bool:
    # Can't detect from plan alone. Always return False to let the user re-run.
    return False


def _build_event_complete(plan: Plan) -> bool:
    return False


def _scan_complete(plan: Plan) -> bool:
    # Scan doesn't modify the plan — always runnable.
    return False


def _import_library_complete(plan: Plan) -> bool:
    return _fetch_complete(plan)  # same check — tracks exist


def _create_playlists_complete(plan: Plan) -> bool:
    if isinstance(plan, EventPlan):
        return bool(plan.created_playlists)
    return False


def _sync_tidal_complete(plan: Plan) -> bool:
    if isinstance(plan, EventPlan):
        return bool(plan.tidal_playlists)
    return False


def _export_rekordbox_complete(plan: Plan) -> bool:
    return False


# ---------------------------------------------------------------------------
# Step runner functions
# ---------------------------------------------------------------------------

def _run_fetch(plan: Plan, profile: Any, inputs: dict) -> tuple[Plan, str]:
    from cratekeeper.spotify.client import (
        enrich_tracks_with_artist_genres,
        extract_playlist_id,
        fetch_playlist_tracks,
        get_spotify_client,
    )

    console.print("[bold]Connecting to Spotify...[/bold]")
    sp = get_spotify_client()

    playlist_url = inputs["playlist_url"]
    playlist_id = extract_playlist_id(playlist_url)
    console.print(f"Fetching playlist [cyan]{playlist_id}[/cyan]...")

    playlist_name, tracks = fetch_playlist_tracks(sp, playlist_id)
    console.print(f"Found [green]{len(tracks)}[/green] tracks in '{playlist_name}'")

    all_artist_ids = list({aid for t in tracks for aid in t.artist_ids})
    console.print(f"Fetching genres for [cyan]{len(all_artist_ids)}[/cyan] unique artists...")
    enrich_tracks_with_artist_genres(sp, tracks)

    plan = EventPlan(
        source_playlist_id=playlist_id,
        source_playlist_name=playlist_name,
        tracks=tracks,
    )

    output = profile.plan_path(playlist_name)
    plan.save(output)

    return plan, f"Fetched {len(tracks)} tracks → {output}"


def _run_classify(plan: Plan, profile: Any, inputs: dict) -> tuple[Plan, str]:
    from cratekeeper.pipeline.classifier import classify_tracks, consolidate_small_buckets

    classify_tracks(plan.tracks, buckets=profile.buckets, fallback=profile.fallback)
    consolidate_small_buckets(plan.tracks, min_size=3, fallback=profile.fallback)

    buckets = plan.bucket_summary()
    summary_parts = [f"{name}: {len(tracks)}" for name, tracks in buckets.items()]
    return plan, f"Classified into {len(buckets)} buckets ({', '.join(summary_parts)})"


def _run_enrich(plan: Plan, profile: Any, inputs: dict) -> tuple[Plan, str]:
    from cratekeeper.spotify.musicbrainz import enrich_tracks_genres

    missing = sum(1 for t in plan.tracks if not t.artist_genres and t.isrc)
    if not missing:
        return plan, "All tracks already have genre data"

    console.print(f"Querying MusicBrainz for {missing} tracks (~{missing}s)...")

    def _progress(i, total, track, genres, mb_year=None):
        tag = f" → {', '.join(genres[:3])}" if genres else ""
        console.print(f"  [{i}/{total}] {track.display_name()}{tag}")

    enriched = enrich_tracks_genres(plan.tracks, progress_callback=_progress)
    return plan, f"Enriched {enriched} of {missing} tracks"


def _run_review(plan: Plan, profile: Any, inputs: dict) -> tuple[Plan, str]:
    low = sum(1 for t in plan.tracks if t.confidence == "low")
    med = sum(1 for t in plan.tracks if t.confidence == "medium")
    high = sum(1 for t in plan.tracks if t.confidence == "high")

    table = Table(title="Classification Confidence")
    table.add_column("Level", style="cyan")
    table.add_column("Count", justify="right")
    table.add_row("High", f"[green]{high}[/green]")
    table.add_row("Medium", f"[yellow]{med}[/yellow]")
    table.add_row("Low", f"[red]{low}[/red]")
    console.print(table)

    return plan, f"{high} high, {med} medium, {low} low confidence"


def _run_scan(plan: Plan, profile: Any, inputs: dict) -> tuple[Plan, str]:
    from cratekeeper.local.pg_repository import PostgresTrackRepository
    from cratekeeper.local.scanner import scan_directory

    directory = Path(inputs["music_directory"])
    console.print(f"Scanning [cyan]{directory}[/cyan]...")

    def _progress(new, skip, path):
        name = path.name if path else "done"
        console.print(f"  [green]+{new}[/green], [dim]{skip} skipped[/dim] — {name}")

    repo = PostgresTrackRepository()
    new_count, skipped, _ = scan_directory(directory, repo=repo, incremental=True, progress_callback=_progress)
    repo.close()

    return plan, f"Indexed {new_count} new files, {skipped} skipped"


def _run_import_library(plan: Plan, profile: Any, inputs: dict) -> tuple[Plan, str]:
    from cratekeeper.local.bulk_import import import_tracks
    from cratekeeper.pipeline.classifier import classify_tracks

    source_path = Path(inputs["music_directory"])
    tracks = import_tracks(source_path)
    classify_tracks(tracks, buckets=profile.buckets, fallback=profile.fallback)

    plan = LibraryImportPlan(
        source_playlist_id=f"import:{source_path}",
        source_playlist_name=source_path.name or str(source_path),
        tracks=tracks,
    )

    output = profile.plan_path(source_path.name or "import")
    plan.save(output)

    return plan, f"Imported {len(tracks)} tracks → {output}"


def _run_match(plan: Plan, profile: Any, inputs: dict) -> tuple[Plan, str]:
    from cratekeeper.local.matcher import match_tracks
    from cratekeeper.local.pg_repository import PostgresTrackRepository

    console.print(f"Matching {len(plan.tracks)} tracks against local library...")

    def _progress(i, total, track, result):
        if result.local_path:
            console.print(f"  [{i}/{total}] {track.display_name()} → [green]{result.method}[/green]")

    repo = PostgresTrackRepository()
    results = match_tracks(plan.tracks, repo=repo, fuzzy_threshold=85, progress_callback=_progress)
    repo.close()

    matched = sum(1 for r in results if r.method != "none")
    missing = sum(1 for r in results if r.method == "none")
    return plan, f"Matched {matched}, missing {missing}"


def _run_analyze_mood(plan: Plan, profile: Any, inputs: dict) -> tuple[Plan, str]:
    from cratekeeper.analysis.mood_analyzer import analyze_tracks

    with_path = sum(1 for t in plan.tracks if t.local_path)
    console.print(f"Analyzing {with_path} tracks with essentia...")

    # Initialize analysis cache (graceful fallback if DB unavailable)
    cache_repo = None
    try:
        from cratekeeper.local.pg_analysis_cache import PostgresAnalysisCacheRepository
        cache_repo = PostgresAnalysisCacheRepository()
    except Exception as cache_err:
        console.print(f"[yellow]Analysis cache unavailable ({cache_err}), proceeding without cache[/yellow]")

    def _progress(i, total, track, mood, error):
        if error:
            console.print(f"  [{i}/{total}] {track.display_name()} → [red]{error}[/red]")
        elif track.bpm:
            console.print(f"  [{i}/{total}] {track.display_name()} → {track.bpm} BPM, {track.key}")

    analyzed = analyze_tracks(plan.tracks, progress_callback=_progress, force=False, cache_repo=cache_repo)

    if cache_repo:
        cache_repo.close()

    return plan, f"Analyzed {analyzed} of {with_path} tracks"


def _run_apply_tags(plan: Plan, profile: Any, inputs: dict) -> tuple[Plan, str]:
    from cratekeeper.pipeline.tag_prompt import build_tag_prompt
    from cratekeeper.pipeline.tag_writer import apply_tags_from_data

    # Generate prompt file so DJ knows what to feed the LLM
    slug = plan.source_playlist_name.lower().replace(" ", "-") if plan.source_playlist_name else "plan"
    prompt_path = Path(f"data/{slug}.tag-prompt.txt")
    prompt_path.parent.mkdir(parents=True, exist_ok=True)

    prompt_text = build_tag_prompt(plan.tracks)
    prompt_path.write_text(prompt_text)
    console.print(f"\n  [cyan]Tag prompt saved to:[/cyan] [green]{prompt_path}[/green]")
    console.print("  Feed this prompt to an LLM (e.g. opencode run) to generate the tags JSON.\n")

    # Ask for tags file path (may already be in inputs from needs_input)
    tags_file_str = inputs.get("tags_file") or Prompt.ask("  Path to tags JSON file")
    tags_file = Path(tags_file_str)

    if not tags_file.exists():
        raise FileNotFoundError(f"Tags file not found: {tags_file}")

    tags_data = _json.loads(tags_file.read_text())

    if not isinstance(tags_data, list):
        raise ValueError("Tags file must contain a JSON array")

    applied, warnings = apply_tags_from_data(plan.tracks, tags_data)
    return plan, f"Applied tags to {applied} of {len(tags_data)} tracks"


def _run_tag(plan: Plan, profile: Any, inputs: dict) -> tuple[Plan, str]:
    from cratekeeper.pipeline.tag_writer import tag_tracks

    def _progress(i, total, track, ok):
        if i % 20 == 0 or i == total or not ok:
            status = "[green]ok[/green]" if ok else "[red]failed[/red]"
            console.print(f"  [{i}/{total}] {track.display_name()} → {status}")

    success, failed = tag_tracks(plan.tracks, progress_callback=_progress, tag_format=profile.tag_format)
    return plan, f"Tagged {success}, {failed} failed"


def _run_review_library(plan: Plan, profile: Any, inputs: dict) -> tuple[Plan, str]:
    from cratekeeper.builder.review_library import candidate_tracks, is_admission_complete, undecided_candidates

    if not sys.stdin.isatty():
        raise RuntimeError("review-library requires an interactive terminal")

    candidates = candidate_tracks(plan.tracks)
    pending = undecided_candidates(plan.tracks)
    required_fields = profile.required_fields

    if not pending:
        approved = sum(1 for t in candidates if t.library_approval == "approved")
        return plan, f"All {len(candidates)} candidates already reviewed ({approved} approved)"

    console.print(
        f"[cyan]{len(pending)}[/cyan] tracks to review. "
        "[bold]a[/bold]=approve  [bold]r[/bold]=reject  [bold]s[/bold]=skip  [bold]q[/bold]=quit"
    )

    for idx, track in enumerate(pending, 1):
        info_lines = [f"[bold]{track.display_name()}[/bold]"]
        info_lines.append(f"Bucket: [cyan]{track.bucket}[/cyan]   Year: {track.release_year or '?'}")
        if track.bpm or track.key:
            info_lines.append(f"BPM: {track.bpm or '?'}   Key: {track.key or '?'}")
        if is_admission_complete(track, required_fields):
            info_lines.append("[green]Fully tagged[/green]")
        else:
            info_lines.append(f"[yellow]Needs: {', '.join(required_fields)}[/yellow]")
        console.print(Panel("\n".join(info_lines), title=f"[{idx}/{len(pending)}]"))

        while True:
            try:
                raw = input("  a=approve  r=reject  s=skip  q=quit > ").strip().lower()
            except EOFError:
                approved = sum(1 for t in candidates if t.library_approval == "approved")
                return plan, f"Stdin closed. {approved} approved so far"
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
                console.print("  [dim]Skipped[/dim]")
                break
            elif key == "q":
                approved = sum(1 for t in candidates if t.library_approval == "approved")
                return plan, f"Quit early. {approved} approved so far"
            else:
                console.print("  [yellow]Invalid key[/yellow]")

    approved = sum(1 for t in candidates if t.library_approval == "approved")
    return plan, f"Reviewed {len(pending)} tracks. {approved} total approved"


def _run_build_library(plan: Plan, profile: Any, inputs: dict) -> tuple[Plan, str]:
    from cratekeeper.builder.library_builder import build_library

    target = Path(inputs.get("library_target", "")) if inputs.get("library_target") else profile.library_target

    def _progress(i, total, track, dest_path):
        if i % 20 == 0 or i == total:
            console.print(f"  [{i}/{total}] {track.display_name()}")

    result = build_library(
        plan.tracks, target, progress_callback=_progress,
        required_fields=profile.required_fields, sort=profile.sort,
    )
    return plan, f"Copied {result.copied}, {result.already_existed} existed, {result.missing_tags} excluded"


def _run_build_event(plan: Plan, profile: Any, inputs: dict) -> tuple[Plan, str]:
    from cratekeeper.builder.event_builder import build_event_folder

    output = Path(inputs["output_path"])

    def _progress(i, total, track, target_path):
        if i % 20 == 0 or i == total:
            console.print(f"  [{i}/{total}] {track.display_name()}")

    result = build_event_folder(
        plan.tracks, output, progress_callback=_progress,
        required_fields=profile.required_fields, tag_format=profile.tag_format,
    )
    return plan, f"Copied {result.copied} to {output}"


def _run_create_playlists(plan: Plan, profile: Any, inputs: dict) -> tuple[Plan, str]:
    from cratekeeper.spotify.client import create_event_playlists, get_spotify_client

    if not isinstance(plan, EventPlan):
        return plan, "Skipped — not an event plan"

    sp = get_spotify_client()
    event = inputs["event_name"]
    date = inputs["event_date"]
    plan.event_name = event
    plan.event_date = date

    def _progress(playlist_name, track_count):
        console.print(f"  {playlist_name} — {track_count} tracks")

    create_event_playlists(sp, plan, event, date, progress_callback=_progress)
    return plan, f"Created {len(plan.created_playlists)} Spotify playlists"


def _run_sync_tidal(plan: Plan, profile: Any, inputs: dict) -> tuple[Plan, str]:
    from cratekeeper.tidal.auth import get_tidal_session
    from cratekeeper.tidal.client import sync_plan_to_tidal

    if not isinstance(plan, EventPlan):
        return plan, "Skipped — not an event plan"

    session = get_tidal_session()

    def _progress(playlist_name, added, failed, skipped=False):
        if not skipped:
            console.print(f"  {playlist_name} — {added} matched")

    total_added, _ = sync_plan_to_tidal(session, plan, progress_callback=_progress)
    return plan, f"Synced {total_added} tracks to Tidal"


def _run_export_rekordbox(plan: Plan, profile: Any, inputs: dict) -> tuple[Plan, str]:
    from cratekeeper.export.rekordbox import export_rekordbox

    library_dir = profile.library_target
    out_path = Path(library_dir) / "rekordbox.xml"

    track_count, bucket_count = export_rekordbox(library_dir, out_path, sort=profile.sort)
    return plan, f"Exported {track_count} tracks, {bucket_count} playlists → {out_path}"


# ---------------------------------------------------------------------------
# Pipeline definitions
# ---------------------------------------------------------------------------

EVENT_PIPELINE: list[Step] = [
    Step(id="fetch", label="Fetch Spotify playlist", required=True,
         needs_input=["playlist_url"], run=_run_fetch, is_complete=_fetch_complete),
    Step(id="classify", label="Classify into genre buckets", required=True,
         run=_run_classify, is_complete=_classify_complete),
    Step(id="enrich", label="Enrich genres via MusicBrainz", required=False,
         run=_run_enrich, is_complete=_enrich_complete),
    Step(id="review", label="Review low-confidence classifications", required=False,
         run=_run_review, is_complete=lambda _: False),
    Step(id="match", label="Match tracks to local audio files", required=True,
         run=_run_match, is_complete=_match_complete),
    Step(id="analyze-mood", label="Analyze audio features (essentia)", required=True,
         needs_docker=True, run=_run_analyze_mood, is_complete=_analyze_mood_complete),
    Step(id="apply-tags", label="Apply LLM-classified tags from JSON", required=True,
         run=_run_apply_tags, is_complete=_apply_tags_complete),
    Step(id="tag", label="Write tags into audio files", required=True,
         run=_run_tag, is_complete=_tag_complete),
    Step(id="create-playlists", label="Create Spotify sub-playlists", required=False,
         needs_input=["event_name", "event_date"], run=_run_create_playlists,
         is_complete=_create_playlists_complete),
    Step(id="sync-to-tidal", label="Sync playlists to Tidal", required=False,
         run=_run_sync_tidal, is_complete=_sync_tidal_complete),
    Step(id="build-event", label="Build event folder", required=True,
         needs_input=["output_path"], run=_run_build_event, is_complete=_build_event_complete),
]

LIBRARY_PIPELINE: list[Step] = [
    # scan → index local directory into PostgreSQL
    Step(id="scan", label="Scan local music directory", required=True,
         needs_input=["music_directory"], run=_run_scan, is_complete=_scan_complete),
    # import-library → pull tracks from PostgreSQL, set local_path on each, classify
    # (no separate classify or match step: tracks ARE the local files)
    Step(id="import-library", label="Import scanned files into profile", required=True,
         needs_input=["music_directory"], run=_run_import_library, is_complete=_import_library_complete),
    Step(id="enrich", label="Enrich genres via MusicBrainz", required=False,
         run=_run_enrich, is_complete=_enrich_complete),
    Step(id="analyze-mood", label="Analyze audio features (essentia)", required=True,
         needs_docker=True, run=_run_analyze_mood, is_complete=_analyze_mood_complete),
    Step(id="apply-tags", label="Apply LLM-classified tags from JSON", required=True,
         run=_run_apply_tags, is_complete=_apply_tags_complete),
    Step(id="tag", label="Write tags into audio files", required=True,
         run=_run_tag, is_complete=_tag_complete),
    Step(id="review-library", label="Review tracks for master library", required=True,
         run=_run_review_library, is_complete=_review_library_complete),
    Step(id="build-library", label="Build master library", required=True,
         needs_input=["library_target"], run=_run_build_library, is_complete=_build_library_complete),
    Step(id="export-rekordbox", label="Export Rekordbox XML", required=False,
         run=_run_export_rekordbox, is_complete=_export_rekordbox_complete),
]


# ---------------------------------------------------------------------------
# Progress detector
# ---------------------------------------------------------------------------

def detect_resume_index(pipeline: list[Step], plan: Plan) -> int:
    """Return the index of the first incomplete step, or len(pipeline) if all done."""
    for i, step in enumerate(pipeline):
        if not step.is_complete(plan):
            return i
    return len(pipeline)


# ---------------------------------------------------------------------------
# Input collection
# ---------------------------------------------------------------------------

INPUT_PROMPTS: dict[str, str] = {
    "playlist_url": "Spotify playlist URL",
    "music_directory": "Local music directory path",
    "output_path": "Event output directory",
    "tags_file": "Path to tags JSON file",
    "event_name": "Event name (e.g. 'Wedding Tim & Lea')",
    "event_date": "Event date (e.g. '2026-06-15')",
    "library_target": "Library target directory (leave blank for profile default)",
}


def collect_inputs(step: Step, collected: dict[str, str]) -> dict[str, str]:
    """Prompt for any inputs this step needs that haven't been collected yet."""
    for key in step.needs_input:
        if key not in collected or not collected[key]:
            prompt_text = INPUT_PROMPTS.get(key, key)
            value = Prompt.ask(f"  {prompt_text}")
            collected[key] = value
    return {k: collected[k] for k in step.needs_input if k in collected}


# ---------------------------------------------------------------------------
# Main wizard flow
# ---------------------------------------------------------------------------

def run_wizard(profile: Any, plan_path: Path | None = None) -> None:
    """Run the interactive wizard."""
    console.print(Panel("[bold]Cratekeeper Wizard[/bold]\nGuided pipeline — step by step", style="cyan"))

    # Pipeline selection
    pipeline_choice = select(
        "Which pipeline?",
        choices=[
            Choice(
                title="Event — Spotify/Tidal playlist → DJ-ready event folder",
                value="event",
            ),
            Choice(
                title="Library — import local music into your master library",
                value="library",
            ),
        ],
        default="event",
    )

    if pipeline_choice == "library":
        pipeline = LIBRARY_PIPELINE
        console.print(f"\n[cyan]Library-import pipeline[/cyan] — {len(pipeline)} steps")
    else:
        pipeline = EVENT_PIPELINE
        console.print(f"\n[cyan]Event pipeline[/cyan] — {len(pipeline)} steps")

    # Show steps overview
    for i, step in enumerate(pipeline, 1):
        req = "[green]required[/green]" if step.required else "[dim]optional[/dim]"
        console.print(f"  {i:2}. {step.label} ({req})")
    console.print()

    # Resume detection
    plan: Plan | None = None
    start_index = 0

    if plan_path and plan_path.exists():
        plan = Plan.load(plan_path)
        start_index = detect_resume_index(pipeline, plan)
        if start_index >= len(pipeline):
            console.print("[green]All steps already complete![/green]")
            return
        if start_index > 0:
            console.print(
                f"[yellow]Detected progress:[/yellow] {start_index}/{len(pipeline)} steps complete. "
                f"Resuming from step {start_index + 1}: [cyan]{pipeline[start_index].label}[/cyan]"
            )
            if not confirm("Resume from here?", default=True):
                start_index = 0
                console.print("Starting from the beginning.")

    # Shared input state
    collected_inputs: dict[str, str] = {}

    # Track outcomes for summary
    outcomes: list[tuple[str, str, str]] = []  # (step_label, status, detail)

    # Mark completed steps
    for i in range(start_index):
        outcomes.append((pipeline[i].label, "skipped", "already complete"))

    # Step loop
    for i in range(start_index, len(pipeline)):
        step = pipeline[i]

        console.print(Panel(
            f"[bold]Step {i + 1}/{len(pipeline)}:[/bold] {step.label}"
            + (" [dim](optional)[/dim]" if not step.required else ""),
            style="blue",
        ))

        # Optional step — offer skip
        if not step.required:
            if not confirm("Run this step?", default=True):
                console.print("  [dim]Skipped[/dim]")
                outcomes.append((step.label, "skipped", "user skipped"))
                continue

        # Collect inputs
        step_inputs = collect_inputs(step, collected_inputs)

        # Execute
        try:
            plan, detail = step.run(plan=plan, profile=profile, inputs=step_inputs)

            # Save after each step if we have a plan and a path
            if plan is not None:
                save_path = plan_path
                if save_path is None:
                    save_path = profile.plan_path(plan.source_playlist_name)
                    plan_path = save_path
                plan.save(save_path)

            console.print(f"  [green]Done:[/green] {detail}")
            outcomes.append((step.label, "done", detail))

        except Exception as exc:
            console.print(f"  [red]Error:[/red] {exc}")
            outcomes.append((step.label, "error", str(exc)))
            # Save progress on error
            if plan is not None and plan_path is not None:
                plan.save(plan_path)
                console.print(f"  [dim]Progress saved to {plan_path}[/dim]")
            break

        # Continue prompt (unless last step)
        if i < len(pipeline) - 1:
            if not confirm("Continue to next step?", default=True):
                if plan is not None and plan_path is not None:
                    plan.save(plan_path)
                console.print(f"\n[yellow]Paused.[/yellow] Resume with: ./crate wizard --plan {plan_path}")
                _print_summary(outcomes)
                return

    # Completion summary
    console.print()
    _print_summary(outcomes)

    if plan_path:
        console.print(f"\nPlan saved to [green]{plan_path}[/green]")


def _print_summary(outcomes: list[tuple[str, str, str]]) -> None:
    """Print a summary table of all steps and their outcomes."""
    table = Table(title="Wizard Summary")
    table.add_column("Step", style="cyan")
    table.add_column("Status")
    table.add_column("Detail", style="dim")

    for label, status, detail in outcomes:
        if status == "done":
            status_str = "[green]done[/green]"
        elif status == "skipped":
            status_str = "[dim]skipped[/dim]"
        elif status == "error":
            status_str = "[red]error[/red]"
        else:
            status_str = status
        table.add_row(label, status_str, detail)

    console.print(table)
