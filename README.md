# Ban Teemo - LoL Draft Assistant

An AI-powered League of Legends draft assistant that replays professional matches and provides real-time pick/ban recommendations backed by pro match data and layered analytics.

## Demo Concept

Since live matches can't be guaranteed during judging, Ban Teemo uses a **historical replay system** that:

1. Pre-loads 1,400+ professional series from LCK, LEC, LCS, and LPL
2. Replays draft actions with configurable delays (simulating live experience)
3. Generates AI recommendations in real-time as actions appear
4. UI behaves identically to true live mode

**Why this works:** Judges see the same experience users would during a real match - with zero risk of technical issues from live data feeds.

## Key Features

- **Draft Visualization** - Real-time ban/pick tracking with champion portraits from Riot Data Dragon
- **Layered Analytics** - Recommendations based on meta strength, player proficiency, synergies, and counters
- **Replay Mode** - Step through historical drafts at adjustable speeds
- **LLM Insights** - Natural language explanations of draft strategy (requires [Nebius API key](https://docs.tokenfactory.nebius.com/quickstart#get-api-key))

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
│   DuckDB     │     │  Knowledge   │    │  LLM Insights │
│  (68K+ acts) │     │  (JSON)      │    │  via Nebius   │
└──────────────┘     └──────────────┘    └───────────────┘
```

## Tech Stack

**Backend:**
- Python 3.12+ with [uv](https://docs.astral.sh/uv/)
- FastAPI + uvicorn
- DuckDB for fast queries
- Nebius AI Studio for LLM inference (optional, for AI insights)

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

Install these system dependencies before running the project:

| Dependency | Installation |
|------------|--------------|
| **Python 3.12+** | [python.org](https://python.org) or `brew install python` / `apt install python3` |
| **uv** (Python package manager) | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| **Node.js 18+** | [nodejs.org](https://nodejs.org) or use [nvm](https://github.com/nvm-sh/nvm) / [fnm](https://github.com/Schniz/fnm) |
| **GitHub CLI** (for data download) | [cli.github.com](https://cli.github.com) or `brew install gh` / `apt install gh` |
| **Make** (optional) | Pre-installed on macOS/Linux; Windows: use WSL or [GnuWin32](http://gnuwin32.sourceforge.net/packages/make.htm) |

### First-Time Setup

```bash
# 1. Clone the repository
git clone https://github.com/your-org/ban-teemo.git
cd ban-teemo

# 2. Install dependencies
make install

# 3. Download data and build database
make setup-data
```

That's it! The `setup-data` command:
1. Downloads CSV data from GitHub releases (~50MB) → `outputs/full_2024_2025_v2/csv/`
2. Builds DuckDB for fast queries → `data/draft_data.duckdb`

Knowledge files (`knowledge/*.json`) are pre-committed to the repo, so no regeneration is needed.

**Manual setup** (if you prefer not to use Make):
```bash
cd backend && uv sync
cd ../frontend && npm install
./scripts/download-data.sh
cd backend && uv run python scripts/build_duckdb.py
```

### Run the Demo

```bash
# Terminal 1: Start backend (port 8000)
make dev-backend

# Terminal 2: Start frontend (port 5173)
make dev-frontend
```

Open [http://localhost:5173](http://localhost:5173) to view the app.

### Troubleshooting

| Issue | Solution |
|-------|----------|
| `gh: command not found` | Install GitHub CLI: https://cli.github.com/ |
| `FileNotFoundError: draft_data.duckdb` | Run `make build-db` to create the database |
| `No CSV files found` | Run `make download-data` first |

## Project Structure

```
ban-teemo/
├── backend/                    # FastAPI service
│   ├── src/ban_teemo/
│   │   ├── api/               # REST + WebSocket endpoints
│   │   ├── services/          # Draft logic, recommendations
│   │   └── models/            # Pydantic schemas
│   ├── scripts/               # build_duckdb.py
│   └── tests/
│
├── frontend/                   # React + Vite frontend
│   └── src/
│       ├── components/        # Draft UI components
│       ├── hooks/             # useReplaySession, useWebSocket
│       └── utils/             # Data Dragon helpers
│
├── knowledge/                  # Analytics JSON (pre-committed)
│   ├── meta_stats.json        # Meta strength scores
│   ├── player_proficiency.json # Player-champion stats
│   ├── matchup_stats.json     # Lane matchup win rates
│   └── ...
│
├── scripts/                    # Data pipeline scripts
│   ├── build_computed_datasets.py  # CSV → knowledge/*.json
│   ├── build_tournament_meta.py    # Tournament data
│   └── download-data.sh            # Fetch CSVs from releases
│
├── outputs/                    # Downloaded CSV data (gitignored)
│   └── full_2024_2025_v2/csv/
│
├── data/                       # Runtime data
│   └── draft_data.duckdb       # DuckDB database (built from CSVs)
│
└── docs/                       # Architecture docs & specs
```

## Data Pipeline

### Data Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│  GitHub Release (data-v1.0.0.tar.gz)                                    │
│  Downloaded via: make download-data                                     │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  outputs/full_2024_2025_v2/csv/                                         │
│  ├── player_game_stats.csv   (player performance per game)              │
│  ├── games.csv               (game metadata, patches, winners)          │
│  ├── series.csv              (match information)                        │
│  └── draft_actions.csv       (ban/pick sequence)                        │
└─────────────────┬───────────────────────────────────┬───────────────────┘
                  │                                   │
                  ▼                                   ▼
    ┌─────────────────────────┐         ┌─────────────────────────────────┐
    │  make build-db          │         │  make build-knowledge           │
    │  (required)             │         │  (optional - files pre-committed)│
    └────────────┬────────────┘         └─────────────┬───────────────────┘
                 │                                    │
                 ▼                                    ▼
    ┌─────────────────────────┐         ┌─────────────────────────────────┐
    │  data/draft_data.duckdb │         │  knowledge/*.json               │
    │  (fast SQL queries)     │         │  (analytics for recommendations)│
    └─────────────────────────┘         └─────────────────────────────────┘
```

### Source: GRID Open Access API

Match data was fetched using the GRID LoL Data Skill (see `.claude/skills/grid-lol-data-skill/`).

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

### Knowledge Files

The `knowledge/` directory contains analytics for fast API lookups:

| File | Source | Description |
|------|--------|-------------|
| `meta_stats.json` | Generated | Pick/ban rates, win rates, meta tiers |
| `player_proficiency.json` | Generated | Player-champion performance (1.9MB) |
| `matchup_stats.json` | Generated | Role-specific matchup win rates |
| `champion_synergies.json` | Generated | Statistical synergy scores |
| `champion_role_history.json` | Generated | Role distributions per patch |
| `skill_transfers.json` | Generated | Similar champions from co-play |
| `role_baselines.json` | Generated | Statistical baselines for normalization |
| `knowledge_base.json` | Manual | Champion metadata and abilities |
| `synergies.json` | Manual | Curated synergy ratings (S/A/B/C) |
| `archetype_counters.json` | Manual | Team archetype analysis |
| `player_roles.json` | Manual | Authoritative player role mappings |
| `tournament_meta.json` | Manual | Recent tournament pick/ban data |

**Generated files** are created by `scripts/build_computed_datasets.py` from CSV data.
**Manual files** are curated and maintained separately.

## Configuration

Create a `.env` file in the project root:

```bash
# Nebius API key (optional, enables AI insights feature)
# Get your key: https://docs.tokenfactory.nebius.com/quickstart#get-api-key
NEBIUS_API_KEY=your_nebius_api_key

# Optional: Database path (default: data/draft_data.duckdb)
DATABASE_PATH=data/draft_data.duckdb
```

> **Note:** The AI Insights feature requires a Nebius API key. Without it, the app works fully but won't generate natural language draft explanations. See the [Nebius quickstart guide](https://docs.tokenfactory.nebius.com/quickstart#get-api-key) to get your free API key.

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
# Setup
make install          # Install all dependencies (Python + Node)
make setup-data       # Download CSVs + build DuckDB

# Development
make dev-backend      # Start FastAPI dev server (port 8000)
make dev-frontend     # Start Vite dev server (port 5173)

# Data management
make download-data    # Download CSVs from GitHub releases
make build-db         # Build DuckDB from CSV files
make build-knowledge  # Regenerate knowledge/*.json from CSVs

# Quality
make test             # Run all tests
make lint             # Run linters
make build            # Build for production
make clean            # Remove build artifacts
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

This project is licensed under the [GNU Affero General Public License v3.0](LICENSE) (AGPL-3.0).

---
