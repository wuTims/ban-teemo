# Ban Teemo - LoL Draft Assistant

An AI-powered League of Legends draft assistant that replays professional matches and provides real-time pick/ban recommendations backed by pro match data and layered analytics.

## Overview

Ban Teemo analyzes 68,000+ draft actions from professional League of Legends matches to provide data-driven pick and ban recommendations. The system combines tournament meta analysis, player proficiency data, champion synergies, and matchup statistics into a multi-factor scoring engine.

## Key Features

- **Draft Replay** - Step through 1,488 professional series from LCK, LEC, LCS, and LPL with configurable playback speeds
- **Draft Simulator** - Practice drafting against AI-controlled pro teams with historical pick patterns
- **Pick Recommendations** - Tournament-weighted scoring with synergy multipliers and phase-aware adjustments
- **Ban Recommendations** - Tiered priority system targeting meta power picks, player comfort champions, and strategic counters
- **Team Evaluation** - Archetype analysis (engage, split, teamfight, protect, pick) with composition scoring
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
1. Downloads data from GitHub releases (~30MB) → CSVs, DuckDB, replay metadata
2. Extracts to `outputs/` and `data/` directories

Knowledge files (`knowledge/*.json`) are pre-committed to the repo, so no regeneration is needed.

**Current data release:** `v1.0.0` (68,529 draft actions, 1,565 replay meta files)

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
│   │   │   └── scorers/       # Core scoring components
│   │   └── models/            # Pydantic schemas
│   ├── scripts/               # build_duckdb.py, build_replay_metas.py
│   └── tests/
│
├── frontend/                   # React + Vite frontend
│   └── src/
│       ├── components/
│       │   ├── replay/        # Replay mode (DraftBoard, ActionLog, etc.)
│       │   ├── simulator/     # Simulator mode (ChampionPool, etc.)
│       │   └── shared/        # Shared (ChampionPortrait, TeamPanel)
│       ├── hooks/             # useReplaySession, useSimulator
│       └── utils/             # Data Dragon helpers, role utils
│
├── knowledge/                  # Analytics JSON (pre-committed)
│   ├── meta_stats.json        # Meta strength scores
│   ├── player_proficiency.json # Player-champion stats (1.9MB)
│   ├── matchup_stats.json     # Lane matchup win rates
│   ├── tournament_meta.json   # Tournament pick/ban data
│   ├── role_pick_phase.json   # Role pick frequency by phase
│   └── replay_meta/           # Per-series metadata (1,565 files)
│
├── scripts/                    # Data pipeline scripts
│   ├── build_computed_datasets.py  # CSV → knowledge/*.json
│   ├── build_tournament_meta.py    # Tournament data
│   └── download-data.sh            # Fetch data from releases
│
├── outputs/                    # Downloaded CSV data (gitignored)
│   └── full_2024_2025_v2/csv/
│
├── data/                       # Runtime data
│   └── draft_data.duckdb       # DuckDB database
│
└── docs/                       # Architecture docs & specs
    └── mvp-design-decisions.md # Design rationale
```

## Data Pipeline

### Data Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│  GitHub Release (ban-teemo-data.tar.gz)                                 │
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
| Series | 1,488 |
| Games | 3,446 |
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
| `role_pick_phase.json` | Generated | Role pick frequency by draft phase |
| `patch_info.json` | Generated | Patch metadata and dates |
| `knowledge_base.json` | Manual | Champion metadata and abilities |
| `synergies.json` | Manual | Curated synergy ratings (S/A/B/C) |
| `archetype_counters.json` | Manual | Team archetype RPS counters |
| `player_roles.json` | Manual | Authoritative player role mappings |
| `tournament_meta.json` | Manual | Tournament pick/ban priority data |
| `replay_meta/` | Generated | Per-series metadata (1,565 files) |

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

### Replay Mode
| Endpoint | Description |
|----------|-------------|
| `GET /api/series` | List available series with filters |
| `GET /api/series/{id}` | Series detail with games |
| `GET /api/draft/{series_id}/{game}` | Draft actions for a game |
| `WS /api/replay/{series_id}/{game}` | Stream draft replay with recommendations |

### Simulator Mode
| Endpoint | Description |
|----------|-------------|
| `POST /api/simulator/setup` | Initialize simulator session |
| `POST /api/simulator/pick` | Submit user pick |
| `POST /api/simulator/ban` | Submit user ban |
| `POST /api/simulator/enemy-action` | Get AI enemy action |
| `GET /api/simulator/state` | Get current draft state |

### Recommendations
| Endpoint | Description |
|----------|-------------|
| `POST /api/recommend/pick` | Get pick recommendations |
| `POST /api/recommend/ban` | Get ban recommendations |

### Documentation
| Endpoint | Description |
|----------|-------------|
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

## Scoring System

### Pick Recommendations

Base scoring components with phase-aware weight adjustments:

| Component | Weight | Description |
|-----------|--------|-------------|
| Tournament Priority | 25% | How often pros contest this champion |
| Tournament Performance | 20% | Role-specific adjusted win rate |
| Matchup/Counter | 25% | Combined lane + team matchup advantage |
| Archetype | 15% | Team composition fit |
| Proficiency | 15% | Player comfort level |

**Synergy** is applied as a multiplier (0.75x to 1.25x) rather than an additive component. This prevents weak picks from being "rescued" by good synergy.

### Ban Recommendations

Tiered priority system:

| Phase 1 Tier | Target |
|--------------|--------|
| T1 Signature Power | High meta + high proficiency |
| T2 Meta Power | High tournament priority |
| T3 Comfort Pick | Player-specific targeting |

| Phase 2 Tier | Target |
|--------------|--------|
| T1 Counter & Pool | Counters our picks + in enemy pool |
| T2 Archetype & Pool | Completes enemy comp + in pool |
| T3 Counter Only | Counters our picks |

See [mvp-design-decisions.md](docs/mvp-design-decisions.md) for the complete scoring algorithm and design rationale.

## Documentation

- [MVP Design Decisions](docs/mvp-design-decisions.md) - Complete design rationale, experiments, and final architecture
- [Hackathon Spec v2](docs/lol_draft_assistant_hackathon_spec_v2.md) - Product vision and feature specs
- [Architecture Review](docs/architecture-v2-review.md) - Data quality analysis and DuckDB queries
- [Draft Simulation Design](docs/plans/2026-01-23-draft-simulation-service-design.md) - Replay service design
- [Unified Recommendation System](docs/plans/2026-01-26-unified-recommendation-system.md) - Multi-factor scoring architecture

## License

This project is licensed under the [GNU Affero General Public License v3.0](LICENSE) (AGPL-3.0).

---
