FROM --platform=linux/amd64 python:3.12-slim

# System deps for audio processing and PostgreSQL client
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        libpq-dev \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Install Essentia with TensorFlow predictors
# Do not install plain "essentia" alongside this package because it can shadow
# the TF-enabled wheel and remove TensorflowPredict* algorithms.
RUN pip install --no-cache-dir essentia-tensorflow

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

# Install cratekeeper dependencies first (cache layer)
COPY pyproject.toml .
RUN pip install --no-cache-dir .

# Copy source code
COPY cratekeeper/ cratekeeper/

# Reinstall with source
RUN pip install --no-cache-dir -e .

# Mount points for data and music library
VOLUME ["/data", "/music"]

ENTRYPOINT ["crate"]
