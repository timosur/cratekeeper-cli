"""Smoke-tests for CRATE-18 event_builder rewrite."""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from cratekeeper.event_builder import (
    _is_fully_tagged,
    _track_filename,
    build_event_folder,
)
from cratekeeper.models import Track


def make_track(idx: int, **kwargs) -> Track:
    defaults = dict(id=str(idx), name=f"Track {idx}", artists=["DJ Test"],
                    artist_ids=[], album="Album", duration_ms=180000)
    defaults.update(kwargs)
    return Track(**defaults)


def tagged(t: Track) -> Track:
    t.energy = "high"
    t.function = ["floorfiller"]
    t.crowd = ["mixed-age"]
    t.mood_tags = ["euphoric"]
    return t


# --- _is_fully_tagged ---
t_bare = make_track(1)
assert not _is_fully_tagged(t_bare), "bare track should not be fully tagged"
assert _is_fully_tagged(tagged(make_track(2))), "fully tagged track should pass"
# partial
t_partial = make_track(3)
t_partial.energy = "high"
assert not _is_fully_tagged(t_partial), "partial tags should fail"
print("_is_fully_tagged OK")

# --- _track_filename sanitization ---
t_special = make_track(4, name="Song: Remix/Club", artists=["A/B"])
fn = _track_filename(t_special)
for ch in ['/', '\\', ':', '*', '?', '"', '<', '>', '|']:
    assert ch not in fn, f"Unsafe char {ch!r} in filename {fn!r}"
print(f"_track_filename sanitize OK: {fn!r}")

# --- missing local_path ---
with tempfile.TemporaryDirectory() as tmp:
    out = Path(tmp) / "event"
    t = tagged(make_track(5))  # no local_path
    result = build_event_folder([t], out)
    assert len(result.missing_tracks) == 1
    assert result.copied == 0
    assert (out / "_missing.txt").exists()
    print("missing local_path -> _missing.txt OK")

# --- file on disk but untagged plan fields ---
with tempfile.TemporaryDirectory() as tmp:
    out = Path(tmp) / "event"
    # create a dummy audio file
    src = Path(tmp) / "song.mp3"
    src.write_bytes(b"\xff\xfb" + b"\x00" * 100)
    t = make_track(6, local_path=str(src))  # no plan tags, no embedded comment
    result = build_event_folder([t], out)
    # plan tags missing -> untagged (not missing, because file exists)
    assert len(result.untagged_tracks) == 1
    assert result.copied == 0
    assert (out / "_untagged.txt").exists()
    print("untagged plan fields -> _untagged.txt OK")

# --- collision detection ---
with tempfile.TemporaryDirectory() as tmp:
    out = Path(tmp) / "event"
    # two source files that map to the same Artist - Title.mp3
    src1 = Path(tmp) / "v1.mp3"
    src2 = Path(tmp) / "v2.mp3"
    src1.write_bytes(b"A" * 50)
    src2.write_bytes(b"B" * 50)

    def _make_tagged_embedded(src: Path) -> Track:
        from mutagen.id3 import ID3, COMM
        import mutagen.id3
        try:
            tags = ID3(str(src))
        except mutagen.id3.ID3NoHeaderError:
            tags = ID3()
        tags.add(COMM(encoding=3, lang="eng", desc="", text=["energy:high; function:floorfiller"]))
        tags.save(str(src))
        t = tagged(make_track(99, name="Same Song", artists=["Same Artist"], local_path=str(src)))
        return t

    t1 = _make_tagged_embedded(src1)
    t2 = _make_tagged_embedded(src2)

    result = build_event_folder([t1, t2], out)
    # first copy lands, second is a collision
    assert result.copied == 1, f"Expected 1 copied, got {result.copied}"
    assert len(result.collision_tracks) == 1
    assert (out / "_untagged.txt").exists()
    print("collision detection OK")

# --- idempotent re-run ---
with tempfile.TemporaryDirectory() as tmp:
    out = Path(tmp) / "event"
    src = Path(tmp) / "unique.mp3"
    src.write_bytes(b"X" * 50)
    from mutagen.id3 import ID3, COMM
    import mutagen.id3
    try:
        tags = ID3(str(src))
    except mutagen.id3.ID3NoHeaderError:
        tags = ID3()
    tags.add(COMM(encoding=3, lang="eng", desc="", text=["energy:mid; function:bridge"]))
    tags.save(str(src))
    t = tagged(make_track(7, name="Idempotent", artists=["DJ Re"], local_path=str(src)))

    r1 = build_event_folder([t], out)
    r2 = build_event_folder([t], out)
    assert r1.copied == 1
    assert r2.copied == 0 and r2.already_existed == 1
    print("idempotent re-run OK")

print("\nAll CRATE-18 checks passed")
