# Cratekeeper CLI

DJ library management toolkit — classify, analyze, tag, and organize music crates from Spotify wish playlists into event-ready folders with genre sorting, audio analysis, and LLM-powered tagging.

## What It Does

1. **Genre-classified tracks** — sorted into 18 genre buckets (Schlager → Pop fallback)
2. **Audio analysis** — BPM, key, energy, danceability, mood classifiers, arousal/valence via essentia + TensorFlow models
3. **LLM-tagged metadata** — energy level, function tags (floorfiller, singalong, bridge…), crowd fit, mood tags — assigned by Claude/GPT using audio data
4. **Tagged local files** — genre, BPM, key, and structured tags written into ID3/FLAC comment fields
5. **Organized folder structure** — `Genre/Artist - Title.ext` ready for djay PRO or any DJ software
6. **Multi-platform playlists** — sub-playlists on both Spotify and Tidal

## Project Structure

```
cratekeeper/
├── cratekeeper-cli/       # CLI pipeline (Python)
│   ├── cratekeeper/
│   │   ├── cli.py             # All CLI commands
│   │   ├── models.py          # Track, EventPlan data models
│   │   ├── genre_buckets.py   # 18 genre bucket definitions
│   │   ├── classifier.py      # Rule-based genre classification
│   │   ├── mood_analyzer.py   # essentia + TF audio analysis
│   │   ├── mood_config.py     # Genre-specific mood thresholds
│   │   ├── llm_classifier.py  # LLM batch tag classification
│   │   ├── tag_writer.py      # ID3/FLAC tag writing
│   │   ├── event_builder.py   # Build event folder (Genre/)
│   │   ├── library_builder.py # Build master library (Genre/)
│   │   ├── matcher.py         # Match Spotify tracks to local files
│   │   ├── spotify_client.py  # Spotify API wrapper
│   │   ├── tidal_client.py    # Tidal sync
│   │   ├── musicbrainz_client.py  # MusicBrainz genre/year enrichment
│   │   └── local_scanner.py   # PostgreSQL audio file indexer
│   ├── Dockerfile             # essentia + TF models (Linux x86_64)
│   └── pyproject.toml
├── spotify-mcp/           # Spotify MCP server (TypeScript)
├── tidal-mcp/             # Tidal MCP server (Python)
├── data/                  # Event JSON files
└── docker-compose.yml
```

## Requirements

- **Python ≥ 3.11**
- **Docker** — for audio analysis (essentia + TF models require Linux x86_64)
- **PostgreSQL** — local file index (`postgresql://dj:dj@localhost:5432/djlib`, override with `DATABASE_URL`)
- **NAS / music library** mounted locally (e.g., `/Volumes/Music`)
- **Spotify Developer App** — [create one here](https://developer.spotify.com/dashboard)
- **Tidal account** — HiFi or HiFi Plus
- **Anthropic API key** — for LLM tag classification (`ANTHROPIC_API_KEY` env var)

## Setup

### 1. Install Cratekeeper

```bash
cd cratekeeper-cli
pip install -e .
```

This gives you the `crate` command.

### 2. Build Docker Image (for audio analysis)

```bash
docker compose build
```

The Docker image includes essentia, essentia-tensorflow, and 10 pre-trained TF models (~300 MB total) for mood classification, key detection, arousal/valence, and voice/instrumental detection.

### 3. Setup Spotify MCP Server

```bash
cd spotify-mcp
npm install
cp spotify-config.example.json spotify-config.json
# Edit spotify-config.json with your clientId and clientSecret
npm run auth    # Opens browser for OAuth
npm run build
```

### 4. Setup Tidal MCP Server

```bash
cd tidal-mcp
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
python -m tidal_mcp.auth   # Prints a link — open it to log in
```

### 5. Connect MCP Servers

Add to your MCP client config (VS Code Copilot, Claude Desktop, etc.):

```json
{
  "mcpServers": {
    "spotify": {
      "command": "node",
      "args": ["/absolute/path/to/spotify-mcp/build/index.js"]
    },
    "tidal": {
      "command": "/absolute/path/to/tidal-mcp/.venv/bin/python",
      "args": ["-m", "tidal_mcp.server"]
    }
  }
}
```

## CLI Commands

All commands use the `crate` CLI:

| Command | Description |
|---------|-------------|
| `crate fetch <playlist-url>` | Fetch tracks from Spotify playlist → JSON |
| `crate enrich <file>` | Enrich missing genres/years via MusicBrainz |
| `crate classify <file>` | Classify tracks into 18 genre buckets |
| `crate review <file>` | Show low-confidence classifications for review |
| `crate scan <directory>` | Index local audio files into PostgreSQL |
| `crate match <file>` | Match Spotify tracks to local files (ISRC → exact → fuzzy) |
| `crate match <file> --tidal-urls` | …and resolve Tidal URLs for missing tracks |
| `crate analyze-mood <file>` | Extract audio features via essentia + TF models (**Docker**) |
| `crate classify-tags <file>` | Assign structured tags via LLM (energy, function, crowd, mood) |
| `crate build-library <file>` | Copy files into `Genre/` master library structure |
| `crate build-event <file>` | Copy files into event-specific `Genre/` folder |
| `crate tag <file>` | Write genre, BPM, key, and tags into audio file metadata |
| `crate create-playlists <file>` | Create Spotify sub-playlists per genre bucket |
| `crate build-masters <file>` | Add tracks to cross-event `[DJ] Genre` master playlists |
| `crate sync-to-tidal <file>` | Sync classified playlists to Tidal via ISRC |

## Full Pipeline

```bash
# 1. Fetch wish playlist from Spotify
crate fetch "https://open.spotify.com/playlist/..." --output data/wedding.json

# 2. Enrich with MusicBrainz genres and release years
crate enrich data/wedding.json

# 3. Classify into genre buckets
crate classify data/wedding.json
# → creates data/wedding.classified.json

# 4. Review classification (optional)
crate review data/wedding.classified.json

# 5. Scan local music library (skip if already done)
crate scan /Volumes/Music

# 6. Match tracks to local audio files
crate match data/wedding.classified.json
# Add --tidal-urls to get Tidal download links for missing tracks:
# crate match data/wedding.classified.json --tidal-urls
# → creates .missing-tidal.txt with URLs

# 7. Analyze audio features (Docker required)
docker compose run --rm crate analyze-mood /data/wedding.classified.json

# 8. Classify tags via LLM
crate classify-tags data/wedding.classified.json

# 9. Build master library
crate build-library data/wedding.classified.json --target ~/Music/Library

# 10. Build event folder
crate build-event data/wedding.classified.json --output ~/Music/Events/Wedding/

# 11. Write metadata tags into audio files
crate tag data/wedding.classified.json

# 12. Create Spotify sub-playlists (optional)
crate create-playlists data/wedding.classified.json --event "Wedding Smith" --date "2026-06-15"

# 13. Sync to Tidal (optional)
crate sync-to-tidal data/wedding.classified.json
```

## Genre Buckets (18)

Tracks are classified into genre buckets in order of specificity (first match wins):

| # | Bucket | Example Tags |
|---|--------|-------------|
| 1 | Schlager | schlager, discofox, volksmusik |
| 2 | Drum & Bass | drum and bass, jungle, liquid dnb |
| 3 | Hardstyle | hardstyle, hardcore, gabber |
| 4 | Melodic Techno | melodic techno, indie dance |
| 5 | Techno | techno, hard techno, industrial techno |
| 6 | Minimal / Tech House | minimal techno, tech house |
| 7 | Deep House | deep house, organic house, tropical house |
| 8 | Progressive House | progressive house, progressive trance |
| 9 | Trance | trance, psytrance, uplifting trance |
| 10 | House | house, electro house, funky house, uk garage |
| 11 | EDM / Big Room | edm, big room, electro |
| 12 | Dance / Hands Up | dance, hands up, eurodance |
| 13 | Hip-Hop / R&B | hip hop, rap, r&b, trap |
| 14 | Latin / Global | reggaeton, latin, salsa, bachata |
| 15 | Disco / Funk / Soul | disco, funk, soul, motown |
| 16 | Rock | rock, indie, alternative, punk |
| 17 | Ballads / Slow | ballad, slow, acoustic, singer-songwriter |
| 18 | Pop | pop, dance pop, europop (fallback) |

Era (80s, 90s, 2000s, Oldschool) is derived from release year and stored as a comment tag, not a genre bucket.

## Tag System

The LLM classifier (`crate classify-tags`) assigns structured tags based on audio analysis + metadata:

| Tag | Values | Description |
|-----|--------|-------------|
| **energy** | low, mid, high | Energy level for set planning |
| **function** | floorfiller, singalong, bridge, reset, closer, opener | Role in a DJ set |
| **crowd** | mixed-age, older, younger, family | Target audience |
| **mood** | feelgood, emotional, euphoric, nostalgic, romantic, melancholic, dark, aggressive, uplifting, dreamy, funky, groovy | Emotional tone |

Tags are written into the ID3 comment field (MP3) or comment tag (FLAC):
```
era:90s; energy:high; function:floorfiller,singalong; crowd:mixed-age; mood:feelgood,euphoric
```

Additional audio metadata written to tags:
- **Genre** (TCON / genre) — bucket name
- **BPM** (TBPM / bpm) — beats per minute from essentia
- **Key** (TKEY / initialkey) — musical key (e.g., "C minor")

## Audio Analysis (essentia)

The `analyze-mood` command extracts features via Docker (essentia requires Linux x86_64):

**Basic features** (built-in essentia algorithms):
- BPM (RhythmExtractor2013)
- Energy (RMS, normalized 0-1)
- Danceability (0-1)
- Loudness (LUFS)
- Key + scale (KeyExtractor, EDMA profile for electronic music)

**ML features** (essentia-tensorflow, pre-trained models):
- Mood classifiers: happy, party, relaxed, sad, aggressive (0-1 probability each, discogs-effnet)
- Arousal / Valence (1-9 scale, DEAM model via msd-musicnn)
- Voice / Instrumental detection (discogs-effnet)
- ML Danceability (discogs-effnet, more accurate than built-in)

All audio data is stored in the event JSON and fed to the LLM for informed tag assignment.

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | For `classify-tags` | — | Anthropic API key |
| `OPENAI_API_KEY` | If using `--provider openai` | — | OpenAI API key |
| `DATABASE_URL` | No | `postgresql://dj:dj@localhost:5432/djlib` | PostgreSQL connection |
| `ESSENTIA_MODELS_DIR` | No | `/app/models` | Directory for TF model files |

## Docker

The Docker image is used only for audio analysis (essentia + TF models). All other commands run locally.

```bash
# Build
docker compose build

# Run audio analysis
docker compose run --rm crate analyze-mood /data/<file>.classified.json

# The docker-compose.yml maps:
#   ./data → /data
#   /Volumes/Music → /music (read-only)
#   ~/Music/Library → /library
```

## MCP Servers

### Spotify MCP (29 tools)

| Category | Tools |
|----------|-------|
| Search & Discovery | Search tracks/albums/artists/playlists |
| Playlist Management | Create, update, add/remove/reorder tracks |
| Track Analysis | Audio features (BPM, key, energy, danceability), artist genres |
| Playback Control | Play, pause, skip, queue, volume, devices |
| Library | Saved tracks, saved albums, recently played |

### Tidal MCP (19 tools)

| Category | Tools |
|----------|-------|
| Search & Discovery | Search tracks/albums/artists, track/artist details |
| Playlist Management | Create, update, add/remove tracks, add by ISRC, merge |
| Albums | Get album details/tracks, save/remove albums |
| Favorites | Get/add/remove favorite tracks, artists, albums |

## Design Decisions

- **18 genre buckets** — specific enough for electronic sub-genres, broad enough to keep folders manageable
- **Era as tag, not genre** — "Yeah!" by Usher belongs in Hip-Hop/R&B, not "2000s"
- **Flat folder structure** (`Genre/`) — no mood sub-folders; tags in the comment field are searchable in djay PRO
- **LLM for semantic tags** — audio analysis provides objective data, the LLM interprets it contextually (a "sad" ballad vs. a "sad" techno track serve different functions)
- **Batch processing** — LLM classifies 15 tracks at a time for efficiency
- **Docker for essentia only** — essentia + TF require Linux x86_64; everything else runs natively on macOS
- **Master playlist naming** — `[DJ] Genre` pattern for cross-event playlists
- **ISRC-first matching** — most reliable way to match Spotify tracks to local files

## Copilot Skill

The `prepare-event` skill automates the full pipeline via GitHub Copilot. Invoke it with a Spotify playlist URL, event name, and date — it runs all steps in sequence with interactive review points.

See [.github/skills/prepare-event/SKILL.md](.github/skills/prepare-event/SKILL.md) for the full procedure.
