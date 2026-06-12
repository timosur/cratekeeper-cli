"""Generate a self-contained LLM prompt for DJ tag classification.

Produces a prompt that, when fed to any LLM, returns a JSON array compatible
with ``crate apply-tags``.  No LLM dependency — just text generation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from cratekeeper.models import Track

if TYPE_CHECKING:
    from cratekeeper.config import TagConfig


def _track_context_line(track: Track) -> str:
    """Render a single track as a pipe-delimited context line."""
    era = track.era or track.compute_era() or "unknown"
    artists = ", ".join(track.artists)
    bpm = f"{track.bpm:.0f}" if track.bpm else "unknown"
    key = track.key or "unknown"
    energy_score = f"{track.audio_energy:.2f}" if track.audio_energy is not None else "unknown"

    # Compact mood dict: top moods with scores
    if track.audio_mood:
        mood_parts = [f"{k}={v:.2f}" for k, v in sorted(track.audio_mood.items(), key=lambda x: -x[1])[:3]]
        mood_str = ",".join(mood_parts)
    else:
        mood_str = "unknown"

    arousal = f"{track.arousal:.1f}" if track.arousal is not None else "unknown"
    valence = f"{track.valence:.1f}" if track.valence is not None else "unknown"

    return (
        f"{track.id} | {track.name} | {artists} | "
        f"bucket:{track.bucket or 'unclassified'} | era:{era} | "
        f"bpm:{bpm} | key:{key} | energy_score:{energy_score} | "
        f"mood:{mood_str} | arousal:{arousal} | valence:{valence}"
    )


def build_tag_prompt(tracks: list[Track], tag_config: "TagConfig | None" = None) -> str:
    """Build a self-contained LLM prompt for tag classification.

    The resulting prompt includes:
    - All track context (analysis data)
    - Vocabulary constraints from the profile's TagConfig
    - The exact JSON output schema expected by ``crate apply-tags``
    - Classification guidance from TagConfig
    - Instruction to return only valid JSON
    """
    from cratekeeper.config import default_tag_config

    if tag_config is None:
        tag_config = default_tag_config()

    # Vocabulary section — dynamic from TagConfig
    vocab_lines = ["## Valid Vocabulary\n"]
    for fname, fdef in tag_config.fields.items():
        if fdef.type == "single":
            vocab_lines.append(f"- {fname}: {sorted(fdef.values)}")
        else:
            pick_hint = f" (pick {fdef.pick[0]}-{fdef.pick[1]})" if fdef.pick else ""
            vocab_lines.append(f"- {fname}{pick_hint}: {sorted(fdef.values)}")
    vocab = "\n".join(vocab_lines) + "\n"

    # JSON schema section — dynamic from TagConfig
    schema_fields = []
    for fname, fdef in tag_config.fields.items():
        if fdef.type == "single":
            schema_fields.append(f'  "{fname}": "<{"|".join(fdef.values)}>"')
        else:
            schema_fields.append(f'  "{fname}": ["<value>", ...]')

    schema = (
        "## Output JSON Schema\n\n"
        "Return a JSON array. Each element:\n"
        "```\n"
        "{\n"
        '  "id": "<spotify-track-id>",\n'
        + ",\n".join(f"  {f.split(':')[0]}:{f.split(':',1)[1]}" if False else f for f in schema_fields)
        + ",\n"
        '  "genre_suggestion": "<optional: only if you disagree with the bucket>"\n'
        "}\n"
        "```\n"
        "- `genre_suggestion` is optional. Only include it if you believe the assigned bucket is wrong.\n"
        "- All other fields are required for every track.\n"
    )

    # Track context
    track_lines = "\n".join(_track_context_line(t) for t in tracks)
    tracks_section = (
        f"## Tracks ({len(tracks)} total)\n\n"
        "Format: id | name | artists | bucket | era | bpm | key | energy_score | mood | arousal | valence\n\n"
        f"{track_lines}\n"
    )

    # Classification guidance — from TagConfig
    if tag_config.guidance:
        guidance = f"## Classification Guidance\n\n{tag_config.guidance}\n"
    else:
        guidance = ""

    # Final assembly
    prompt = (
        "You are a DJ assistant classifying tracks for a DJ set.\n\n"
        "Classify each track below using ONLY the valid vocabulary provided. "
        "Base your classification on the audio analysis data, genre bucket, era, and your knowledge of the track.\n\n"
        f"{vocab}\n"
        f"{schema}\n"
        f"{guidance}\n"
        f"{tracks_section}\n"
        "Return ONLY the JSON array. No markdown fences, no commentary, no explanation."
    )

    return prompt
