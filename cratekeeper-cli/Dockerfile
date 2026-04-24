FROM --platform=linux/amd64 python:3.12-slim

# System deps for audio processing and PostgreSQL client
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        libpq-dev \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Install essentia with TensorFlow support
RUN pip install --no-cache-dir essentia essentia-tensorflow

# Download pre-trained models
ENV ESSENTIA_MODELS_DIR=/app/models
RUN mkdir -p $ESSENTIA_MODELS_DIR && \
    cd $ESSENTIA_MODELS_DIR && \
    curl -SLO https://essentia.upf.edu/models/feature-extractors/discogs-effnet/discogs-effnet-bs64-1.pb && \
    curl -SLO https://essentia.upf.edu/models/classifiers/mood_happy/mood_happy-discogs-effnet-1.pb && \
    curl -SLO https://essentia.upf.edu/models/classifiers/mood_party/mood_party-discogs-effnet-1.pb && \
    curl -SLO https://essentia.upf.edu/models/classifiers/mood_relaxed/mood_relaxed-discogs-effnet-1.pb && \
    curl -SLO https://essentia.upf.edu/models/classifiers/mood_sad/mood_sad-discogs-effnet-1.pb && \
    curl -SLO https://essentia.upf.edu/models/classifiers/mood_aggressive/mood_aggressive-discogs-effnet-1.pb && \
    curl -SLO https://essentia.upf.edu/models/classifiers/voice_instrumental/voice_instrumental-discogs-effnet-1.pb && \
    curl -SLO https://essentia.upf.edu/models/classifiers/danceability/danceability-discogs-effnet-1.pb && \
    curl -SLO https://essentia.upf.edu/models/feature-extractors/musicnn/msd-musicnn-1.pb && \
    curl -SLO https://essentia.upf.edu/models/classifiers/deam/deam-msd-musicnn-1.pb

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
