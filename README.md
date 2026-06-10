# Cratekeeper CLI

DJ library management toolkit — classify, analyze, tag, and organize music crates from Spotify wish playlists into event-ready folders with genre sorting, audio analysis, and LLM-powered tagging.

## What It Does

1. **Genre-classified tracks** — sorted into 18 genre buckets (Schlager → Pop fallback)
2. **Audio analysis** — BPM, key, energy, danceability, mood classifiers, arousal/valence via essentia + TensorFlow models
3. **LLM-tagged metadata** — energy level, function tags (floorfiller, singalong, bridge…), crowd fit, mood tags — assigned by Claude/GPT using audio data
4. **Tagged local files** — genre, BPM, key, and structured tags written into ID3/FLAC comment fields
5. **Organized output** — `Genre/Artist - Title.ext` master library, plus flat event folders filtered by tags in djay PRO
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
│   │   ├── event_builder.py   # Build flat event folder (tag-driven, no Genre/ subfolders)
│   │   ├── library_builder.py # Build master library (Genre/)
│   │   ├── review_library.py  # Library candidate selection helpers
│   │   ├── matcher.py         # Match Spotify tracks to local files
│   │   ├── spotify_client.py  # Spotify API wrapper
│   │   ├── tidal_client.py    # Tidal sync
│   │   ├── musicbrainz_client.py  # MusicBrainz genre/year enrichment
│   │   └── local_scanner.py   # PostgreSQL audio file indexer
│   └── pyproject.toml
├── tidal-mcp/             # Tidal MCP server (Python)
├── data/                  # Event JSON files
└── docker-compose.yml
```

## Requirements

- **Python ≥ 3.11**
- **macOS 15+ (Apple Silicon or x86_64) or Linux x86_64** — for native audio analysis via essentia-tensorflow
- **PostgreSQL** — local file index (`postgresql://dj:dj@localhost:5432/djlib`, override with `DATABASE_URL`)
- **NAS / music library** mounted locally (e.g., `/Volumes/Music`)
- **Spotify Developer App** — [create one here](https://developer.spotify.com/dashboard)
- **Tidal account** — HiFi or HiFi Plus
- **Anthropic API key** — for LLM tag classification (`ANTHROPIC_API_KEY` env var)

## Local Development

A `Makefile` provides all common dev tasks. Run `make help` to see available targets.

### Quick Start

```bash
make venv          # create .venv with Python ≥3.11, install package + dev deps
./crate --help
```

The `venv` target auto-discovers `python3.11`/`3.12`/`3.13` from your PATH or Homebrew. A `.python-version` file is included for pyenv users.

### Running CLI Commands

A `./crate` wrapper script at the repo root runs the CLI from the `.venv` without activation:

```bash
./crate fetch https://open.spotify.com/playlist/...
./crate classify data/wedding.json
./crate scan /Volumes/Music
./crate profile list
```

### Available Targets

| Target | Description |
|--------|-------------|
| `make venv` | Create `.venv` and install `cratekeeper[dev]` (pytest, ruff) |
| `make install` | Re-install package + dev deps into existing venv |
| `make test` | Run pytest (`make test ARGS="-k test_config"` to filter) |
| `make lint` | Run ruff check |
| `make format` | Run ruff format |
| `make check` | Lint + test combined |
| `make db` | Start Postgres via docker compose |
| `make db-stop` | Stop docker compose services |
| `make spotify-auth` | Authenticate with Spotify (OAuth flow) |
| `make clean` | Remove `.venv`, caches, build artifacts |

### 3. Setup Spotify

```bash
crate spotify-auth
# or: make spotify-auth
```

Prompts for your Spotify Developer App credentials (Client ID, Client Secret), opens the browser for OAuth authorization, and saves tokens to `~/.config/cratekeeper/spotify-config.json`.

Create a Spotify Developer App at [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard). Set the redirect URI to `http://127.0.0.1:8888/callback`.

### 4. Setup Tidal MCP Server

```bash
cd tidal-mcp
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
python -m tidal_mcp.auth   # Prints a link — open it to log in
```

### 5. Connect MCP Servers (optional)

Add to your MCP client config (VS Code Copilot, Claude Desktop, etc.):

```json
{
  "mcpServers": {
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
| `crate spotify-auth` | Authenticate with Spotify (interactive OAuth flow) |
| `crate fetch <playlist-url>` | Fetch tracks from Spotify playlist → JSON |
| `crate enrich <file>` | Enrich missing genres/years via MusicBrainz |
| `crate classify <file>` | Classify tracks into 18 genre buckets |
| `crate review <file>` | Show low-confidence classifications for review |
| `crate scan <directory>` | Index local audio files into PostgreSQL |
| `crate match <file>` | Match Spotify tracks to local files (ISRC → exact → fuzzy) |
| `crate match <file> --tidal-urls` | …and resolve Tidal URLs for missing tracks |
| `crate analyze-mood <file>` | Extract audio features via essentia + TF models (native) |
| `crate apply-tags <file> <tags.json>` | Apply LLM-classified tags (energy, function, crowd, mood) from a JSON file into the plan |
| `crate tag <file>` | Write genre, BPM, key, and structured tags into audio file metadata |
| `crate review-library <file>` | Interactively approve/reject matched tracks before they enter the master library |
| `crate build-library <file>` | Copy **approved + fully-tagged** files into `Genre/` master library structure |
| `crate build-event <file>` | Copy fully-tagged files into a **flat** event folder; both plan tags and embedded comment required (for djay PRO quick filters) |
| `crate import-library <dir>` | Bulk-import scanned local files into the active profile using their ID3 genre tags (no Spotify) |
| `crate export-rekordbox` | Generate `rekordbox.xml` from the active profile's built library (collection + per-bucket playlists) |
| `crate profile list` | List configured profiles and mark the active one |
| `crate profile show [name]` | Print the fully resolved settings for a profile |
| `crate profile use <name>` | Set the active profile in the config file |
| `crate profile init` | Scaffold `~/.cratekeeper/config.toml` with example profiles |
| `crate create-playlists <file>` | Create Spotify sub-playlists per genre bucket |
| `crate build-masters <file>` | Add tracks to cross-event `[DJ] Genre` master playlists |
| `crate sync-to-tidal <file>` | Sync classified playlists to Tidal via ISRC |

## Profiles & Configuration

Cratekeeper supports **named profiles** so you can run different libraries (e.g. a
commercial wedding library and an electronic library) with different genre
buckets, DJ-software targets, tag formats, admission criteria, and sort orders —
without editing code.

Profiles live in `~/.cratekeeper/config.toml`. Create one with:

```bash
crate profile init        # scaffolds commercial + electronic example profiles
crate profile list        # show profiles, '*' marks the active one
crate profile show electronic
crate profile use electronic   # switch the active profile
```

Override the active profile for a single command with the global `--profile`
flag (available on every command):

```bash
crate classify data/set.json --profile electronic
crate -p electronic build-library data/set.json
```

If **no config file exists**, Cratekeeper uses an implicit `commercial` profile
that reproduces the historical defaults, so existing setups keep working
unchanged.

### Profile settings

Each `[profiles.<name>]` table supports:

| Key | Values | Description |
|-----|--------|-------------|
| `buckets` | `"commercial"` \| `"electronic"` \| inline list | Genre bucket preset or custom `[{ name, genre_tags }]` list |
| `dj_software` | `djay_pro` \| `rekordbox` | Target DJ software (gates auto-XML behaviour) |
| `tag_format` | `structured_comment` \| `id3_only` | `structured_comment` writes the era/energy/function/crowd/mood comment; `id3_only` writes only genre/BPM/key |
| `library_target` | path | Master library output directory |
| `data_dir` | path | Per-profile plan JSON directory (defaults to `~/.cratekeeper/<name>/data`) |
| `required_fields` | list | Tag fields that must be populated for library/event admission |
| `[profiles.<name>.sort]` | `keys`, `direction` | Sort order within genre buckets (e.g. `keys = ["bpm"]`, `direction = "asc"`) |

The bundled `electronic` preset uses finer EDM sub-genres with a `House`
fallback and excludes commercial genres (Schlager, Pop, Rock, Latin).

### Bulk library import (no Spotify)

Import everything already scanned under a directory directly into a profile,
classifying by each file's ID3 genre tag:

```bash
crate scan /Volumes/Music/Electronic            # index files first
crate import-library /Volumes/Music/Electronic --profile electronic
crate review-library <plan>                      # then the normal pipeline
crate build-library <plan>
```

### Rekordbox export

Rekordbox profiles do **not** auto-generate XML during `build-library`. Produce
an importable `rekordbox.xml` on demand from the built library:

```bash
crate export-rekordbox --profile electronic
crate export-rekordbox --buckets House,Techno -o ~/rekordbox.xml
```

> **Breaking change:** existing plans in the legacy `data/` directory are **not**
> auto-migrated to a profile's `data_dir`. After adopting profiles, move your
> existing plan JSON files into the relevant profile's `data_dir` (shown by
> `crate profile show`) or re-import them. The shared PostgreSQL scan index is
> unaffected and remains shared across profiles.

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

# 7. Analyze audio features (downloads ~300 MB TF models on first run)
crate analyze-mood data/wedding.classified.json

# 8. Classify tags via LLM sub-agent → apply results
# (Run the prepare-event skill Step 8: sub-agent produces tags JSON, then:)
crate apply-tags data/wedding.classified.json data/wedding.tags.json

# 9. Write metadata tags into audio files (required before building folders)
crate tag data/wedding.classified.json

# 10. Review tracks for master library (approve / reject interactively)
crate review-library data/wedding.classified.json

# 11. Build master library (approved + fully-tagged tracks only)
crate build-library data/wedding.classified.json --target ~/Music/Library
# → ~/Music/Library/Genre/Artist - Title.ext

# 12. Build event folder (flat, fully-tagged tracks only)
crate build-event data/wedding.classified.json --output ~/Music/Events/Wedding/
# → flat folder; filter by energy/function/crowd/mood in djay PRO
# → _untagged.txt lists tracks that need crate tag re-run before they qualify

# 13. Create Spotify sub-playlists (optional)
crate create-playlists data/wedding.classified.json --event "Wedding Smith" --date "2026-06-15"

# 14. Sync to Tidal (optional)
crate sync-to-tidal data/wedding.classified.json
```

## Purchasing Missing Tracks

After running `crate match`, any tracks not found in your local library are reported in `.missing.txt` and `.missing-isrcs.txt`. With the `--tidal-urls` flag, you also get `.missing-tidal.txt` with direct purchase links.

To integrate purchased tracks back into the pipeline:

```bash
# 1. Review what's missing
cat data/wedding.missing.txt

# 2. Buy tracks from Tidal, Beatport, Bandcamp, etc.
#    Download files to a staging directory

# 3. Tag purchased files with metadata from the plan
crate tag-untagged data/wedding.classified.json ~/Downloads/purchased/
# Matches files to unmatched tracks by filename, writes title/artist/album/year/ISRC tags

# 4. Move tagged files to your NAS library manually
#    e.g., cp ~/Downloads/purchased/*.flac /Volumes/Music/New/

# 5. Re-scan to pick up new files
crate scan /Volumes/Music

# 6. Re-match to verify purchased tracks are now found
crate match data/wedding.classified.json --tidal-urls

# 7. Continue with the rest of the pipeline (analyze-mood, tag, build-event, etc.)
```

**Note**: `crate tag-untagged` matches downloaded files to plan tracks by normalizing filenames against track titles. Most music stores name files close to the track title, so this works out of the box. If a file isn't matched, rename it closer to the expected track title and re-run.

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

The `analyze-mood` command extracts features natively via pip-installed essentia-tensorflow:

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
| `ESSENTIA_MODELS_DIR` | No | `~/.cache/cratekeeper/models` | Directory for TF model files |

## Docker

Docker is used only for PostgreSQL. Start the database with:

```bash
make db        # docker compose up -d db
make db-stop   # docker compose down
```

Audio analysis runs natively — no Docker container needed.

## MCP Servers

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
- **Genre folders for the library, flat folders for events** — the master library uses `Genre/` for browsing/archival; event folders are flat and sliced live by tag-based quick filters in djay PRO
- **LLM for semantic tags** — audio analysis provides objective data, the LLM interprets it contextually (a "sad" ballad vs. a "sad" techno track serve different functions)
- **Batch processing** — LLM classifies 15 tracks at a time for efficiency
- **Native essentia** — essentia-tensorflow installs natively on macOS 15+ (Apple Silicon and x86_64) and Linux x86_64; Docker is not required for audio analysis
- **Master playlist naming** — `[DJ] Genre` pattern for cross-event playlists
- **ISRC-first matching** — most reliable way to match Spotify tracks to local files

## Copilot Skill

The `prepare-event` skill automates the full pipeline via GitHub Copilot. Invoke it with a Spotify playlist URL, event name, and date — it runs all steps in sequence with interactive review points.

See [.github/skills/prepare-event/SKILL.md](.github/skills/prepare-event/SKILL.md) for the full procedure.
