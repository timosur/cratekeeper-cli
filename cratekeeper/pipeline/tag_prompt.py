"""Generate a self-contained LLM prompt for DJ tag classification.

Produces a prompt that, when fed to any LLM, returns a JSON array compatible
with ``crate apply-tags``.  No LLM dependency — just text generation.
"""

from __future__ import annotations

from cratekeeper.models import Track
from cratekeeper.pipeline.tag_writer import (
    VALID_ENERGY,
    VALID_FUNCTION,
    VALID_CROWD,
    VALID_MOOD,
)


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


def build_tag_prompt(tracks: list[Track]) -> str:
    """Build a self-contained LLM prompt for tag classification.

    The resulting prompt includes:
    - All track context (analysis data)
    - Vocabulary constraints for each tag field
    - The exact JSON output schema expected by ``crate apply-tags``
    - Instruction to return only valid JSON
    """
    # Vocabulary section
    vocab = (
        "## Valid Vocabulary\n\n"
        f"- energy: {sorted(VALID_ENERGY)}\n"
        f"- function (pick 1-3): {sorted(VALID_FUNCTION)}\n"
        f"- crowd (pick 1-2): {sorted(VALID_CROWD)}\n"
        f"- mood_tags (pick 1-4): {sorted(VALID_MOOD)}\n"
    )

    # JSON schema section
    schema = (
        "## Output JSON Schema\n\n"
        "Return a JSON array. Each element:\n"
        "```\n"
        "{\n"
        '  "id": "<spotify-track-id>",\n'
        '  "energy": "<low|mid|high>",\n'
        '  "function": ["<value>", ...],\n'
        '  "crowd": ["<value>", ...],\n'
        '  "mood_tags": ["<value>", ...],\n'
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

    # Classification guidance
    guidance = (
        "## Classification Guidance\n\n"
        "- **energy**: Based on audio energy score, BPM, and genre context. "
        "A hip-hop track at 95 BPM can be 'mid'; an electronic track at 95 BPM is 'low'.\n"
        "- **function**: What role does this track play in a DJ set? "
        "Consider energy, singability, and typical crowd response.\n"
        "- **crowd**: Which audience does this track resonate with most? "
        "Consider era, genre, and lyrical content.\n"
        "- **mood_tags**: The emotional qualities of the track. "
        "Use arousal/valence scores and audio mood as guidance.\n"
    )

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
