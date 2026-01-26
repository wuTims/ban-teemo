# DeepDraft - LoL Draft Assistant

An AI-powered League of Legends draft assistant that replays professional matches and provides real-time pick/ban recommendations backed by pro match data and layered analytics.

## Demo Concept

Since live matches can't be guaranteed during judging, DeepDraft uses a **historical replay system** that:

1. Pre-loads 1,400+ professional series from LCK, LEC, LCS, and LPL
2. Replays draft actions with configurable delays (simulating live experience)
3. Generates AI recommendations in real-time as actions appear
4. UI behaves identically to true live mode

**Why this works:** Judges see the same experience users would during a real match - with zero risk of technical issues from live data feeds.

## Key Features

- **Draft Visualization** - Real-time ban/pick tracking with champion portraits from Riot Data Dragon
- **Layered Analytics** - Recommendations based on meta strength, player proficiency, synergies, and counters
- **Replay Mode** - Step through historical drafts at adjustable speeds
- **LLM Insights** - Natural language explanations of draft strategy (via Groq)

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    FRONTEND (React + TypeScript)                 │
│   Draft Board │ Ban/Pick Tracks │ Recommendation Cards           │
└────────────────────────────┬────────────────────────────────────┘
                             │ WebSocket / REST
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    BACKEND (FastAPI + Python)                    │
│   /api/replay/{series_id}  - Stream draft actions               │
│   /api/recommend/pick      - Get pick recommendations           │
│   /api/series              - List available series              │
└────────────────────────────┬────────────────────────────────────┘
                             │
         ┌───────────────────┼───────────────────┐
         ▼                   ▼                   ▼
┌──────────────┐     ┌──────────────┐    ┌───────────────┐
│  CSV Data    │     │  Knowledge   │    │  Llama 3.1    │
│  (68K+ acts) │     │  (JSON)      │    │  via Groq     │
└──────────────┘     └──────────────┘    └───────────────┘
```

## Tech Stack

**Backend:**
- Python 3.12+ with [uv](https://docs.astral.sh/uv/)
- FastAPI + uvicorn
- DuckDB for CSV analytics (zero ETL)
- Groq for LLM inference

**Frontend:**
- React 19 + TypeScript
- Vite
- Tailwind CSS v4
- Riot Data Dragon for champion assets

**Data:**
- GRID Open Access API (pro match data)
- Pre-computed analytics in JSON knowledge files

## Quick Start

### Prerequisites

- Python 3.12+ with [uv](https://docs.astral.sh/uv/)
- Node.js 18+ with npm
- GitHub CLI (`gh`) for data download
- Make (optional)

### Installation

```bash
# Clone the repository
git clone https://github.com/your-org/ban-teemo.git
cd ban-teemo

# Install all dependencies
make install

# Or manually:
cd backend && uv sync
cd ../deepdraft && npm install
```

### Download Match Data

The pro match data is stored in GitHub releases to keep the repo lightweight:

```bash
# Download and extract data (requires gh CLI)
./scripts/download-data.sh

# This creates outputs/full_2024_2025_v2/csv/ with:
#   - 68,529 draft actions
#   - 3,436 games
#   - 1,482 series
#   - 445 players
#   - 57 teams
```

### Run the Demo

```bash
# Terminal 1: Start backend (port 8000)
make dev-backend

# Terminal 2: Start frontend (port 5173)
make dev-frontend
```

Open [http://localhost:5173](http://localhost:5173) to view the app.

## Project Structure

```
ban-teemo/
├── backend/                    # FastAPI service
│   └── src/ban_teemo/
│       ├── api/               # REST + WebSocket endpoints
│       ├── services/          # Draft logic, recommendations
│       └── models/            # Pydantic schemas
│
├── deepdraft/                  # React frontend
│   └── src/
│       ├── components/        # Draft UI components
│       │   ├── draft/         # DraftBoard, TeamPanel, BanTrack
│       │   ├── ActionLog/     # Draft action history
│       │   └── ReplayControls/ # Series/game selectors
│       ├── hooks/             # useReplaySession, useWebSocket
│       └── utils/             # Data Dragon helpers
│
├── knowledge/                  # Pre-computed analytics (JSON)
│   ├── matchup_stats.json # Role-specific matchup win rates
│   ├── champion_synergies.json # Normalized pair synergies
│   ├── player_proficiency.json # Player-champion performance
│   ├── flex_champions.json    # Champion role distributions
│   └── ...
│
├── outputs/                    # Downloaded CSV data (not in git)
│   └── full_2024_2025_v2/csv/
│
├── docs/                       # Architecture docs & specs
│   ├── lol_draft_assistant_hackathon_spec_v2.md
│   └── architecture-v2-review.md
│
└── .claude/skills/             # Data fetching tools
    └── grid-lol-data-skill/   # GRID API client
```

## Data Pipeline

### Source: GRID Open Access API

Match data was fetched using the GRID LoL Data Skill:

```bash
# Set API key
export GRID_API_KEY=your_key

# Fetch series data
python .claude/skills/grid-lol-data-skill/scripts/fetch_lol_series_v3.py \
  --input LoLSeriesGames_2024_2025.csv \
  --limit 1500

# Export to CSVs
python .claude/skills/grid-lol-data-skill/scripts/fetch_lol_series_v3.py \
  --export --run latest
```

### Data Coverage

| Metric | Count |
|--------|-------|
| Series | 1,482 |
| Games | 3,436 |
| Draft Actions | 68,529 |
| Players | 445 |
| Teams | 57 |
| Champions | 162 |

**Regions:** LCK (409), LEC (323), LCS (174), LPL (458), International (117)

**Time Range:** January 2024 - September 2025

### Pre-Computed Knowledge Files

The `knowledge/` directory contains pre-computed analytics for fast API lookups:

| File | Description |
|------|-------------|
| `matchup_stats.json` | Role-specific matchup win rates |
| `champion_synergies.json` | Normalized synergy scores |
| `player_proficiency.json` | Player-champion performance metrics |
| `flex_champions.json` | Champion role probability distributions |
| `role_baselines.json` | Statistical baselines for normalization |
| `skill_transfers.json` | Similar champions from co-play patterns |

These are generated from the CSV data using DuckDB queries (see `docs/architecture-v2-review.md` for query patterns).

## Configuration

Create a `.env` file in the project root:

```bash
# LLM API (for AI insights)
GROQ_API_KEY=your_groq_api_key

# Optional: Database path (default: uses CSV files directly)
DATABASE_URL=outputs/full_2024_2025_v2/csv
```

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/series` | List available series with filters |
| `GET /api/series/{id}` | Series detail with games |
| `GET /api/draft/{series_id}/{game}` | Draft actions for a game |
| `WS /api/replay/{series_id}/{game}` | Stream draft replay |
| `POST /api/recommend/pick` | Get pick recommendations |
| `POST /api/recommend/ban` | Get ban recommendations |
| `GET /docs` | OpenAPI documentation |

## Available Commands

```bash
make install        # Install all dependencies
make dev-backend    # Start FastAPI dev server (port 8000)
make dev-frontend   # Start Vite dev server (port 5173)
make test           # Run all tests
make lint           # Run linters
make build          # Build for production
make clean          # Remove build artifacts
```

## Layered Analytics System

Recommendations combine multiple analysis layers:

| Layer | Weight | Description |
|-------|--------|-------------|
| Meta Strength | 15% | Champion presence + win rate |
| Player Proficiency | 30% | Player's performance on champion |
| Matchup | 20% | Counter value vs enemy picks |
| Synergy | 20% | Pair value with ally picks |
| Counter | 15% | Threat value against enemy team |

See [recommendation-service-overview.md](docs/recommendation-service-overview.md) for the complete scoring algorithm.

## Documentation

- [Hackathon Spec v2](docs/lol_draft_assistant_hackathon_spec_v2.md) - Product vision and feature specs
- [Architecture Review](docs/architecture-v2-review.md) - Data quality analysis and DuckDB queries
- [Draft Simulation Design](docs/plans/2026-01-23-draft-simulation-service-design.md) - Replay service design

## License

MIT

---

*Built for the GRID Esports Hackathon 2026*
