"""Audio analysis using essentia feature extraction.

Extracts BPM, energy, danceability, key, and optionally mood classifiers
(happy, party, relaxed, sad, aggressive), arousal/valence, and
voice/instrumental detection from local audio files.

Basic features (BPM, energy, danceability, key, loudness) use built-in
essentia algorithms. Advanced features (mood classifiers, arousal/valence,
voice detection) require essentia-tensorflow and pre-trained models.

This module requires essentia to be installed (Linux: pip install essentia,
or use the provided Dockerfile).
"""

from __future__ import annotations

import os
import urllib.request
from dataclasses import dataclass
from pathlib import Path

# Suppress TF networking/logging noise before anything imports TF
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")          # hide INFO/WARNING
os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")         # no oneDNN warnings
os.environ.setdefault("GRPC_VERBOSITY", "ERROR")             # silence gRPC
os.environ.setdefault("GRPC_DNS_RESOLVER", "native")         # avoid c-ares DNS warnings
os.environ.setdefault("NO_GCE_CHECK", "true")                # skip GCE metadata probe
os.environ.setdefault("GCS_READ_CACHE_DISABLED", "true")     # no GCS network calls
os.environ.setdefault("ABSL_MIN_LOG_LEVEL", "2")             # silence absl INFO/WARNING

# Directory for downloaded TF models.
# Inside Docker the image bakes models into /app/models; locally we cache in
# the user's XDG cache dir so non-root users can write models on first run.
def _default_models_dir() -> Path:
    if Path("/.dockerenv").exists():
        return Path("/app/models")
    cache_home = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(cache_home) / "cratekeeper" / "models"


MODELS_DIR = Path(os.environ.get("ESSENTIA_MODELS_DIR", str(_default_models_dir())))

# Base URL for essentia model downloads
_MODELS_BASE = "https://essentia.upf.edu/models"

# Models we use and their download paths
_MODEL_FILES = {
    # Embedding extractor
    "discogs-effnet": "feature-extractors/discogs-effnet/discogs-effnet-bs64-1.pb",
    # Mood classifiers (binary, based on discogs-effnet embeddings)
    "mood_happy": "classification-heads/mood_happy/mood_happy-discogs-effnet-1.pb",
    "mood_party": "classification-heads/mood_party/mood_party-discogs-effnet-1.pb",
    "mood_relaxed": "classification-heads/mood_relaxed/mood_relaxed-discogs-effnet-1.pb",
    "mood_sad": "classification-heads/mood_sad/mood_sad-discogs-effnet-1.pb",
    "mood_aggressive": "classification-heads/mood_aggressive/mood_aggressive-discogs-effnet-1.pb",
    # Voice/instrumental
    "voice_instrumental": "classification-heads/voice_instrumental/voice_instrumental-discogs-effnet-1.pb",
    # Danceability (TF-based, more accurate than built-in)
    "danceability": "classification-heads/danceability/danceability-discogs-effnet-1.pb",
    # MusiCNN embedding extractor (for arousal/valence)
    "msd-musicnn": "feature-extractors/musicnn/msd-musicnn-1.pb",
    # Arousal/valence regression (DEAM dataset)
    "deam": "classification-heads/deam/deam-msd-musicnn-1.pb",
}


@dataclass
class AudioFeatures:
    """Extracted audio features for a single track."""

    # Basic features (always available)
    bpm: float = 0.0
    energy: float = 0.0  # RMS-based, 0-1
    danceability: float = 0.0  # 0-1
    loudness: float = 0.0  # LUFS
    key: str = ""  # e.g. "C minor", "A major"

    # Advanced features (require essentia-tensorflow + models)
    mood_happy: float = 0.0  # 0-1 probability
    mood_party: float = 0.0
    mood_relaxed: float = 0.0
    mood_sad: float = 0.0
    mood_aggressive: float = 0.0
    arousal: float = 0.0  # 1-9
    valence: float = 0.0  # 1-9
    voice_instrumental: str = ""  # "voice" or "instrumental"
    danceability_ml: float = 0.0  # ML-based danceability, 0-1


def _ensure_model(name: str) -> Path:
    """Download a model file if not present. Returns the local path."""
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    rel_path = _MODEL_FILES[name]
    filename = rel_path.split("/")[-1]
    local_path = MODELS_DIR / filename
    if not local_path.exists():
        url = f"{_MODELS_BASE}/{rel_path}"
        urllib.request.urlretrieve(url, str(local_path))  # noqa: S310 — trusted URL
    return local_path


def extract_features(file_path: str | Path, use_tf: bool = True) -> AudioFeatures:
    """Extract audio features from a local audio file using essentia.

    Args:
        file_path: Path to the audio file.
        use_tf: If True, attempt to use TF models for advanced features.
                Falls back gracefully if essentia-tensorflow is not installed.

    Raises ImportError if essentia is not installed at all.
    """
    try:
        import essentia.standard as es
    except ImportError:
        raise ImportError(
            "essentia is not installed. Use the Docker image or install on Linux:\n"
            "  pip install essentia\n"
            "Or run: docker compose run dj analyze-mood ..."
        )

    file_path = str(file_path)
    features = AudioFeatures()

    # --- Load audio at 44100 Hz for basic analysis ---
    audio_44k = es.MonoLoader(filename=file_path, sampleRate=44100)()

    # BPM detection
    rhythm_extractor = es.RhythmExtractor2013(method="multifeature")
    bpm, beats, beats_confidence, _, beats_intervals = rhythm_extractor(audio_44k)
    features.bpm = round(bpm, 1)

    # Energy (RMS-based, normalized to 0-1)
    rms = es.RMS()
    energy_values = []
    for frame in es.FrameGenerator(audio_44k, frameSize=2048, hopSize=1024):
        energy_values.append(rms(frame))

    if energy_values:
        avg_rms = sum(energy_values) / len(energy_values)
        features.energy = round(min(1.0, avg_rms / 0.2), 3)

    # Basic danceability
    danceability_extractor = es.Danceability()
    danceability_val, _ = danceability_extractor(audio_44k)
    features.danceability = round(danceability_val, 3)

    # Loudness (integrated LUFS)
    try:
        stereo_loader = es.AudioLoader(filename=file_path)
        stereo_audio, sr, channels, md5, bit_rate, codec = stereo_loader()
        loudness_extractor = es.LoudnessEBUR128(sampleRate=44100)
        momentary, short_term, integrated, loudness_range = loudness_extractor(stereo_audio)
        features.loudness = round(integrated, 1)
    except Exception:
        features.loudness = -14.0

    # Key detection (built-in algorithm, no TF needed)
    try:
        key_extractor = es.KeyExtractor(profileType="edma")
        key_val, scale_val, strength = key_extractor(audio_44k)
        features.key = f"{key_val} {scale_val}"
    except Exception:
        features.key = ""

    # --- Advanced TF-based features ---
    if use_tf:
        try:
            _extract_tf_features(file_path, features, es)
        except Exception as exc:  # noqa: BLE001 — surface once so user can debug
            global _tf_warned
            if not _tf_warned:
                import sys
                print(f"[mood_analyzer] TF feature extraction unavailable: {exc}", file=sys.stderr)
                _tf_warned = True

    return features


_tf_warned = False


def _extract_tf_features(file_path: str, features: AudioFeatures, es) -> None:
    """Extract advanced features using essentia TensorFlow models.

    Requires essentia-tensorflow to be installed.
    Mutates the features dataclass in place.
    """
    import essentia
    import numpy as np

    # Suppress essentia streaming network warnings and TF graph-load info
    essentia.log.warningActive = False
    essentia.log.infoActive = False

    predictors = _get_tf_predictors(es)

    # Load audio at 16kHz for TF models
    audio_16k = es.MonoLoader(filename=file_path, sampleRate=16000)()

    # --- Discogs-EffNet embeddings (shared across multiple classifiers) ---
    embeddings = predictors["effnet"](audio_16k)

    # Mood classifiers (binary, probability of positive class)
    for mood_name in ["mood_happy", "mood_party", "mood_relaxed", "mood_sad", "mood_aggressive"]:
        try:
            preds = predictors[mood_name](embeddings)
            # Average across time, take positive class probability (index 0)
            prob = float(np.mean(preds[:, 0]))
            setattr(features, mood_name, round(prob, 3))
        except Exception:
            pass

    # Voice/instrumental
    try:
        vi_preds = predictors["voice_instrumental"](embeddings)
        vi_avg = np.mean(vi_preds, axis=0)
        features.voice_instrumental = "voice" if vi_avg[0] > vi_avg[1] else "instrumental"
    except Exception:
        pass

    # ML-based danceability
    try:
        dance_preds = predictors["danceability"](embeddings)
        features.danceability_ml = round(float(np.mean(dance_preds[:, 0])), 3)
    except Exception:
        pass

    # --- Arousal/Valence (using MusiCNN embeddings + DEAM model) ---
    try:
        musicnn_embeddings = predictors["musicnn"](audio_16k)
        av_preds = predictors["deam"](musicnn_embeddings)
        av_avg = np.mean(av_preds, axis=0)
        features.valence = round(float(av_avg[0]), 2)
        features.arousal = round(float(av_avg[1]), 2)
    except Exception:
        pass


# Cached predictor instances — loaded once, reused across tracks
_tf_predictors: dict | None = None


def _get_tf_predictors(es) -> dict:
    """Load and cache all TF predictor instances."""
    import contextlib
    import io
    import sys

    global _tf_predictors
    if _tf_predictors is not None:
        return _tf_predictors

    _tf_predictors = {}

    # Suppress TF C++ absl/MLIR warnings emitted to stderr on first graph load
    _real_stderr = sys.stderr
    sys.stderr = io.StringIO()
    try:
        # Embedding extractor
        effnet_model = _ensure_model("discogs-effnet")
        _tf_predictors["effnet"] = es.TensorflowPredictEffnetDiscogs(
            graphFilename=str(effnet_model),
            output="PartitionedCall:1",
        )
    finally:
        sys.stderr = _real_stderr

    # Mood classifiers
    for mood_name in ["mood_happy", "mood_party", "mood_relaxed", "mood_sad", "mood_aggressive"]:
        model_path = _ensure_model(mood_name)
        _tf_predictors[mood_name] = es.TensorflowPredict2D(
            graphFilename=str(model_path),
            output="model/Softmax",
        )

    # Voice/instrumental
    vi_model = _ensure_model("voice_instrumental")
    _tf_predictors["voice_instrumental"] = es.TensorflowPredict2D(
        graphFilename=str(vi_model),
        output="model/Softmax",
    )

    # Danceability
    dance_model = _ensure_model("danceability")
    _tf_predictors["danceability"] = es.TensorflowPredict2D(
        graphFilename=str(dance_model),
        output="model/Softmax",
    )

    # MusiCNN embedding extractor
    musicnn_model = _ensure_model("msd-musicnn")
    _tf_predictors["musicnn"] = es.TensorflowPredictMusiCNN(
        graphFilename=str(musicnn_model),
        output="model/dense/BiasAdd",
    )

    # DEAM arousal/valence
    deam_model = _ensure_model("deam")
    _tf_predictors["deam"] = es.TensorflowPredict2D(
        graphFilename=str(deam_model),
        input="flatten_in_input",
        output="dense_out",
    )

    return _tf_predictors


def analyze_track(file_path: str | Path, genre: str | None = None, use_tf: bool = True) -> AudioFeatures:
    """Extract all features for a single track.

    Returns AudioFeatures with all available data populated.
    """
    return extract_features(file_path, use_tf=use_tf)


def _remap_path(file_path: str) -> str:
    """Remap host paths to container paths when running inside Docker."""
    if not Path("/.dockerenv").exists():
        return file_path
    mappings = [
        ("/Volumes/home/Music/", "/music/"),
        (str(Path.home() / "Music" / "Library") + "/", "/library/"),
    ]
    for host_prefix, container_prefix in mappings:
        if file_path.startswith(host_prefix):
            return container_prefix + file_path[len(host_prefix):]
    return file_path


def _classify_energy(energy_value: float) -> str:
    """Map raw 0-1 energy to low/mid/high."""
    if energy_value < 0.33:
        return "low"
    elif energy_value < 0.66:
        return "mid"
    return "high"


def analyze_tracks(tracks: list, progress_callback=None, use_tf: bool = True) -> int:
    """Analyze audio features for tracks that have a local_path set.

    Mutates tracks: sets bpm, key, energy, audio_energy, danceability,
    audio_mood, arousal, valence, and legacy mood field.
    Returns number of tracks analyzed.
    """
    from cratekeeper.mood_config import classify_mood

    candidates = [
        t for t in tracks
        if t.local_path and Path(_remap_path(t.local_path)).exists()
    ]
    analyzed = 0

    for i, track in enumerate(candidates):
        try:
            features = analyze_track(_remap_path(track.local_path), genre=track.bucket, use_tf=use_tf)

            # Populate Track fields from audio analysis
            track.bpm = features.bpm
            track.key = features.key
            track.danceability = features.danceability
            track.audio_energy = features.energy

            # Preliminary energy classification (LLM can override)
            track.energy = _classify_energy(features.energy)

            # Audio mood scores
            track.audio_mood = {
                "happy": features.mood_happy,
                "party": features.mood_party,
                "relaxed": features.mood_relaxed,
                "sad": features.mood_sad,
                "aggressive": features.mood_aggressive,
            }
            track.arousal = features.arousal
            track.valence = features.valence

            # Legacy mood field (backward compat)
            track.mood = classify_mood(
                features.bpm, features.energy, features.danceability, track.bucket,
            )

            analyzed += 1
        except Exception as e:
            if progress_callback:
                progress_callback(i + 1, len(candidates), track, None, str(e))
            continue

        if progress_callback:
            progress_callback(i + 1, len(candidates), track, track.mood, None)

    return analyzed
