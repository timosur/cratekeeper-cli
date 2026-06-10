# syntax=docker/dockerfile:1
# essentia-tensorflow requires Linux x86_64 — QEMU emulation is unavoidable on
# Apple Silicon, but we minimise the pain by:
#   - pinning to bookworm (stable) so ffmpeg does NOT pull in libllvm
#   - using BuildKit cache mounts for apt and pip so reruns are fast
FROM --platform=linux/amd64 python:3.11-slim-bookworm

# System deps for audio processing and PostgreSQL client
# BuildKit apt cache: the package lists are cached between builds.
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        libpq-dev \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Install Essentia with TensorFlow predictors.
# BuildKit pip cache: the large TF wheels are cached — reruns skip the download.
# Do not install plain "essentia" alongside this package because it shadows
# the TF-enabled wheel and removes TensorflowPredict* algorithms.
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install essentia-tensorflow

ENV ESSENTIA_MODELS_DIR=/app/models

# Bundle pre-trained models in the image so analyze-mood does not depend on
# runtime network access.
RUN mkdir -p "$ESSENTIA_MODELS_DIR" && \
        cd "$ESSENTIA_MODELS_DIR" && \
        for u in \
            https://essentia.upf.edu/models/feature-extractors/discogs-effnet/discogs-effnet-bs64-1.pb \
            https://essentia.upf.edu/models/classification-heads/mood_happy/mood_happy-discogs-effnet-1.pb \
            https://essentia.upf.edu/models/classification-heads/mood_party/mood_party-discogs-effnet-1.pb \
            https://essentia.upf.edu/models/classification-heads/mood_relaxed/mood_relaxed-discogs-effnet-1.pb \
            https://essentia.upf.edu/models/classification-heads/mood_sad/mood_sad-discogs-effnet-1.pb \
            https://essentia.upf.edu/models/classification-heads/mood_aggressive/mood_aggressive-discogs-effnet-1.pb \
            https://essentia.upf.edu/models/classification-heads/voice_instrumental/voice_instrumental-discogs-effnet-1.pb \
            https://essentia.upf.edu/models/classification-heads/danceability/danceability-discogs-effnet-1.pb \
            https://essentia.upf.edu/models/feature-extractors/musicnn/msd-musicnn-1.pb \
            https://essentia.upf.edu/models/classification-heads/deam/deam-msd-musicnn-1.pb; do \
            curl -fL --retry 3 --connect-timeout 20 --max-time 180 -O "$u"; \
        done

WORKDIR /app

# Install cratekeeper dependencies first (separate layer — only invalidated when
# pyproject.toml changes, not when source code changes).
COPY pyproject.toml .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install .

# Copy source and reinstall in editable mode so the container gets the CLI entry point.
COPY cratekeeper/ cratekeeper/
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -e .

# Mount points for data and music library
VOLUME ["/data", "/music"]

ENTRYPOINT ["crate"]
