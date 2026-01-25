# LoL Draft Assistant - Hackathon Spec v2

**Category:** AI Draft Assistant / Draft Predictor
**Timeline:** 1 month
**Team:** 1 LoL domain expert, 2 software engineers, AI assistance
**Required:** GRID API, JetBrains IDE

---

## 1. Hackathon Strategy

### 1.1 Judging Criteria Mapping

| Criteria | Weight | Our Approach |
|----------|--------|--------------|
| **Technological Implementation** | 25% | Clean architecture, layered analytics, quality code with tests |
| **Design** | 25% | Polished draft UI with real-time updates, intuitive recommendation cards |
| **Potential Impact** | 25% | Coaches/analysts save hours of prep; democratizes pro-level draft analysis |
| **Quality of Idea** | 25% | LLM explains *why* picks matter, "Surprise Pick" detection, layered confidence |

### 1.2 Demo Strategy: Historical Replay as "Live"

Since we can't guarantee a live match during judging, we'll build a **replay system** that:

1. Pre-ingests 50+ compelling historical series (upsets, comebacks, interesting drafts)
2. Replays draft actions with configurable delays (e.g., 3-5 seconds between picks)
3. UI behaves **identically** to true live mode
4. Recommendations generate in real-time as actions arrive

**Why this works:**
- Demonstrates all live functionality with zero risk
- Can select narratively interesting drafts ("watch how we would've advised against this upset")
- Judge sees the same experience a user would during a real match

**For video:** Record a "live" replay with voiceover explaining recommendations as they appear.

---

## 2. Feature Prioritization

### 2.1 MVP (Must Have - Weeks 1-3)

```
┌─────────────────────────────────────────────────────────────────────┐
│                     CORE DRAFT EXPERIENCE                           │
├─────────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────────┐  │
│  │  BLUE SIDE  │  │  BAN TRACK  │  │        RED SIDE             │  │
│  │  Team BDS   │  │  ────────── │  │        G2 Esports           │  │
│  │             │  │  B1: Draven │  │                             │  │
│  │  Picks:     │  │  R1: Cait   │  │  Picks:                     │  │
│  │  [Kalista]  │  │  B2: Bel'V  │  │  [Neeko]                    │  │
│  │  [Nocturne] │  │  R2: Ashe   │  │  [Aphelios]                 │  │
│  │  [Akali]    │  │  ...        │  │  [Renata]                   │  │
│  │  [ ? ]      │  │             │  │  [ ? ]                      │  │
│  │  [ ? ]      │  │             │  │  [ ? ]                      │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────────┘  │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │              RECOMMENDATION PANEL                            │    │
│  │  ─────────────────────────────────────────────────────────  │    │
│  │  TOP PICK: Renekton (78% confidence)                        │    │
│  │     • Adam plays this 23 games, 67% WR                      │    │
│  │     • Counters enemy Neeko top                              │    │
│  │     • Strong synergy with Nocturne dive comp                │    │
│  │                                                             │    │
│  │  SURPRISE PICK: Aurora (55% confidence)                     │    │
│  │     • S-tier meta (78% presence)                            │    │
│  │     • Only 2 stage games, but fits playstyle               │    │
│  │                                                             │    │
│  │  Also Consider:                                              │    │
│  │     3. Jax (71%) - Scales well, Adam comfort pick           │    │
│  │     4. Gragas (65%) - Flex potential, team fight            │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  AI INSIGHT                                                  │    │
│  │  "G2 has banned 3 ADCs - they're targeting Hans Sama's      │    │
│  │   pool. Consider prioritizing a hypercarry if it gets       │    │
│  │   through ban phase 2."                                     │    │
│  └─────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
```

**MVP Features:**
| Feature | Description | Effort |
|---------|-------------|--------|
| Draft Tracker UI | Real-time ban/pick visualization | M |
| Layered Analytics | Meta, tendencies, proficiency, synergies | L |
| Pick Recommendations | Top 3-5 suggestions with confidence + flags | M |
| Ban Recommendations | Opponent's highest-impact champions | S |
| Surprise Pick Detection | Low sample but contextually strong picks | M |
| Replay Mode | Step through historical drafts | M |
| LLM Insights | Natural language draft commentary | M |

### 2.2 Stretch Goals (Week 4 - if time)

| Feature | Demo Impact | Effort |
|---------|-------------|--------|
| **Post-Game Analysis** | "Here's what optimal draft would've been" | M |
| **What-If Simulator** | Drag-drop to explore alternate drafts | L |
| **Win Probability** | Live % that updates with each pick | M |
| **Head-to-Head History** | "Last 5 times these teams met..." | S |

### 2.3 Explicitly Out of Scope

- Mobile app
- User accounts/auth
- Solo queue data integration
- Full historical ingestion pipeline
- Production deployment/scaling
- Multi-language support

---

## 3. Technical Architecture

### 3.1 Tech Stack

```yaml
Backend:
  - Python 3.12+
  - FastAPI
  - uv (package management)
  - DuckDB (zero-config analytics engine)
  - websockets (FastAPI's built-in WebSocket support)
  - httpx (async HTTP for LLM API)

Frontend:
  - React 18+
  - TypeScript
  - shadcn/ui + Tailwind
  - Vite (build tool)
  - Native WebSocket API

LLM:
  - Llama 3.1 70B via Groq or Together.ai
  - ~$0.90/1M tokens
  - Fast inference for real-time insights

Data:
  - Riot Data Dragon (champion icons)
  - GRID API (match data) - already extracted to CSV
  - DuckDB querying CSV files directly (zero ETL)
  - Domain expert knowledge files (JSON/MD)
```

### 3.2 System Architecture

```
┌────────────────────────────────────────────────────────────────────┐
│                        FRONTEND (React)                            │
│   Draft Board │ Recommendation Cards │ AI Insight Panel           │
└───────────────────────────┬────────────────────────────────────────┘
                            │ WebSocket / REST
                            ▼
┌────────────────────────────────────────────────────────────────────┐
│                        BACKEND (FastAPI)                           │
│  /draft/live/{series_id}     - Stream draft updates                │
│  /draft/replay/{series_id}   - Replay historical draft             │
│  /recommend/pick             - Get pick recommendations            │
│  /recommend/ban              - Get ban recommendations             │
│  /insight/generate           - LLM-powered analysis                │
│  /analysis/post-game         - Post-draft analysis (stretch)       │
└───────────────────────────┬────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┬────────────────────┐
        ▼                   ▼                   ▼                    ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌───────────────┐
│  GRID API    │    │   DuckDB     │    │  Llama 3.1   │    │ Domain Expert │
│  (Live Data) │    │  (Analytics) │    │  (Insights)  │    │ Knowledge     │
│              │    │  ↓ queries   │    │  via Groq    │    │ (JSON/MD)     │
└──────────────┘    │  CSV Files   │    └──────────────┘    └───────────────┘
                    └──────────────┘
```

### 3.3 Knowledge Directory Structure

Pre-computed analytics and reference data committed to the repository:

```
knowledge/
├── # Computed Analytics (generated from GRID data)
├── champion_counters.json     # Matchup win rates between champions
├── champion_synergies.json    # Normalized synergy scores between champion pairs
├── flex_champions.json        # Champions with multi-role probabilities
├── meta_stats.json            # Current patch meta statistics
├── patch_info.json            # Patch dates and game counts per patch
├── player_proficiency.json    # Player performance metrics per champion
├── role_baselines.json        # Statistical baselines for normalization by role
├── skill_transfers.json       # Champion similarity from co-play patterns
│
├── # Reference Data
├── knowledge_base.json        # Champion metadata (positions, damage types, stats)
├── synergies.json             # Detailed synergy relationships
├── player_roles.json          # Player primary role assignments
├── patch_dates.json           # Patch version → date mapping
└── rework_patch_mapping.json  # Champion rework history for data filtering
```

> **Implementation Details:** See [recommendation-service-architecture.md](./recommendation-service-architecture.md) Section 2.3 for the full knowledge file schema and data generation approach.

---

## 4. Layered Analysis System

### 4.1 Core Insight

**Different analyses have different time sensitivities.**

| Layer | Purpose | Time Range | Why |
|-------|---------|------------|-----|
| **Layer 1: Meta Strength** | Champion viability | Last 3-6 months | Patches change everything |
| **Layer 2: Player Tendencies** | Playstyle indicators | 2-3 years | Habits persist across metas |
| **Layer 3: Proficiency** | Player-champion mastery | 2-3 years, recency-weighted | Balance sample size + recency |
| **Layer 4: Relationships** | Synergies & counters | 2-3 years | Need volume for significance |

### 4.2 Recommendation Weighting

The recommendation engine combines all layers with confidence-adjusted weights:

| Factor | Base Weight | Notes |
|--------|-------------|-------|
| Meta Score | 15% | Global champion strength |
| Proficiency | 30% | How well THIS player performs on champion |
| Matchup | 20% | Counter value against enemy picks |
| Synergy | 20% | Pair value with ally picks |
| Counter | 15% | Threat value against enemy team |

When data is uncertain (flex picks, low sample size), weights automatically redistribute toward more certain factors.

> **Implementation Details:** See [recommendation-service-overview.md](./recommendation-service-overview.md) for the complete scoring algorithm, including flex pick resolution and uncertainty handling.

### 4.3 Recency Weighting

```
Recent (0-12 months):  100% weight
Older (12-24 months):  50% weight
Ancient (24+ months):  25% weight
```

### 4.4 Confidence Levels

| Games Played | Confidence | Behavior |
|--------------|------------|----------|
| 8+ games | HIGH | Trust proficiency score directly |
| 4-7 games | MEDIUM | Trust with caution |
| 1-3 games | LOW | Check contextual strength |
| 0 games | NO DATA | Rely on skill transfer + context |

---

## 5. Surprise Pick Detection

A "surprise pick" is flagged when:
- Player has low stage games on champion (< 3)
- BUT other signals are strong (meta tier, counter value, synergy, style fit)

### 5.1 Contextual Strength Signals

When direct proficiency data is lacking, use:
- **Meta tier** - Is this champion S/A-tier?
- **Counter value** - Does it counter enemy picks?
- **Synergy value** - Does it pair well with allies?
- **Skill transfer** - Does player excel on similar champions?

### 5.2 UI Representation

| Proficiency | Flag | Display |
|-------------|------|---------|
| HIGH (8+ games) | None | "Zeus: 23 games, 67% WR" |
| LOW + surprise eligible | `SURPRISE_PICK` | "2 stage games, but strong meta + style fit" |
| LOW + weak context | `LOW_CONFIDENCE` | "Limited data, consider safer options" |

> **Implementation Details:** See [recommendation-service-architecture.md](./recommendation-service-architecture.md) Section 5 for the proficiency scoring algorithm and contextual strength calculation.

---

## 6. Data Foundation

### 6.1 Available Data (Exceeds Targets)

| Entity | Spec Target | Actual | Status |
|--------|-------------|--------|--------|
| Teams | ~30 | 57 | 1.9x target |
| Players | ~150 | 445 | 3.0x target |
| Champions | ~170 | 162 | Near complete |
| Series | ~200 | 1,482 | 7.4x target |
| Games | ~500 | 3,436 | 6.9x target |
| Draft Actions | ~10,000 | 68,529 | 6.9x target |
| Player Stats | ~5,000 | 34,416 | 6.9x target |

**Regions Covered:** LCK (409), LEC (323), LCS (174), LPL (458), International (117)

### 6.2 Layer Support Status

| Layer | Status | Notes |
|-------|--------|-------|
| Layer 1 (Meta) | Fully supported | Pick/ban rates, win rates |
| Layer 2 (Tendencies) | Mostly supported | Vision 61.3%, damage 61.3%, KP 96.3% |
| Layer 3 (Proficiency) | Fully supported | KDA, win rate, games |
| Layer 4 (Relationships) | Fully supported | Synergies + counters both calculable |

### 6.3 Data Architecture

DuckDB queries CSV files directly with zero ETL. Pre-computed JSON files in `knowledge/` provide fast API lookups.

> **Implementation Details:** See [architecture-v2-review.md](./architecture-v2-review.md) for:
> - Complete data quality assessment
> - All DuckDB query patterns
> - Gap analysis and workarounds
> - Pre-computed knowledge file schemas

> **Database Decision:** See [duckdb-analysis.md](./duckdb-analysis.md) for why DuckDB over SQLite/pandas.

### 6.4 Data Setup

**Quick Start:**
```bash
./scripts/download-data.sh
```

This downloads the CSV data from GitHub releases to `outputs/full_2024_2025_v2/`.

**Data Releases:**

| Version | Tag | Contents |
|---------|-----|----------|
| v1.0.0 | `data-v1.0.0` | Full 2024-2025 season, v2 schema with team_objectives + tournaments |

**CSV Schema (v2):**

| File | Records | Description |
|------|---------|-------------|
| `champions.csv` | 162 | Champion metadata |
| `draft_actions.csv` | 68K+ | All pick/ban actions |
| `games.csv` | 3,436 | Game outcomes |
| `player_game_stats.csv` | 34K+ | Player performance per game |
| `players.csv` | 445 | Player roster |
| `series.csv` | 1,482 | Series metadata |
| `teams.csv` | 57 | Team info |
| `team_objectives.csv` | NEW | Team objective stats per game |
| `tournaments.csv` | NEW | Tournament metadata |

**Version Bump Rules:**
- Patch (`v1.0.1`): Bug fixes, re-fetch same timeframe
- Minor (`v1.1.0`): New data fetched, same schema
- Major (`v2.0.0`): Schema changes

---

## 7. Draft Simulation Service

The replay system is the core demo mechanism. It loads historical drafts and streams actions over WebSocket.

### 7.1 Key Capabilities

- Load any historical series/game from CSV data
- Stream draft actions with configurable delays
- Generate recommendations at each step
- Support pause/resume/jump controls

### 7.2 Draft Order Reference

Standard pro draft (20 actions):
- Bans 1-6 (alternating)
- Picks 1-6 (B, RR, BB, R)
- Bans 7-10 (RB, RB)
- Picks 7-10 (R, BB, R)

> **Implementation Details:** See [plans/2026-01-23-draft-simulation-service-design.md](./plans/2026-01-23-draft-simulation-service-design.md) for:
> - Complete data models (DraftState, ReplaySession)
> - Module structure
> - API endpoints and WebSocket protocol
> - DuckDB queries for loading data

---

## 8. LLM Integration

### 8.1 Model Selection

| Model | Provider | Cost | Use Case |
|-------|----------|------|----------|
| Llama 3.1 70B | Groq | ~$0.59/1M in, $0.79/1M out | Production insights |
| Llama 3.1 8B | Groq (free tier) | Free | Development/testing |
| Mixtral 8x7B | Together.ai | ~$0.60/1M | Fallback option |

**Recommendation:** Start with Groq free tier for development, upgrade to 70B for final demo.

### 8.2 Prompt Design Principles

- Provide full draft state context
- Include team/player profiles from knowledge files
- Include current meta context
- Request specific, actionable insights (not hedging)
- Limit response to 1-2 sentences

---

## 9. Development Plan

### Week 1: Foundation & Data
- Project setup (repo, CI, uv, FastAPI skeleton) - ✅ Done
- GRID API client - ✅ Done (68K+ records)
- DuckDB analytics service + query functions
- Domain expert: provide knowledge files (team profiles, archetypes)
- Champion Data Dragon icon mapping
- Knowledge file integration (JSON/MD loading)

**Deliverable:** DuckDB analytics layer with all query functions, knowledge files ready

### Week 2: Core Backend Logic
- Pick recommendation algorithm (all 4 layers)
- Ban recommendation algorithm
- Surprise pick detection logic
- Replay controller (timer-driven action release)
- WebSocket endpoint for draft streaming
- REST endpoints for analytics
- Comp archetype detection

**Deliverable:** Backend that can replay drafts and generate layered recommendations

### Week 3: Frontend & LLM
- React app scaffold - ✅ Done
- Data Dragon utilities + icon mapping - ✅ Done
- Draft board component implementation
- Recommendation panel component
- LLM integration (Groq/Together client)
- Insight prompt engineering + iteration
- WebSocket client integration
- Series selector / replay controls UI

**Deliverable:** Working end-to-end demo with AI insights

### Week 4: Polish & Stretch Features
- Bug fixes and edge cases
- UI polish pass (animations, loading states)
- Post-game analysis feature (stretch)
- What-if simulator (stretch, if time)
- Demo video recording
- README, documentation, submission prep

**Deliverable:** Polished submission with video

---

## 10. Demo Script (3 minutes)

### 0:00-0:15 - Hook
*"What if you had a pro analyst whispering in your ear during every draft?"*

Show: App loading, sleek UI

### 0:15-0:40 - Setup
*"We're watching LEC Finals - G2 vs BDS. Our AI has analyzed 200 pro matches to understand these teams..."*

Show: Select series, show team cards with playstyle summaries

### 0:40-1:30 - Live Draft (Ban Phase)
*"Watch as real-time recommendations appear..."*

Show: Draft replay at 2x speed, ban recommendations appearing

Highlight: "Notice how we flagged this - G2 is target-banning Hans Sama's champion pool"

### 1:30-2:15 - Live Draft (Pick Phase + Surprise Pick)
*"Here's where it gets interesting..."*

Show: Pick recommendations with confidence scores

Highlight surprise pick: "Aurora shows as a surprise pick - low stage games, but our AI recognizes Caps has the mechanics from his Ahri play"

### 2:15-2:40 - AI Insight
*"Stats alone don't tell the story. Our LLM explains the WHY..."*

Show: Zoom on AI insight panel

Read aloud: One compelling insight about draft strategy

### 2:40-2:55 - Post-Draft Summary (if built)
*"After the draft, get your full analysis..."*

Show: Draft grade, comp archetype, prediction

### 2:55-3:00 - Close
*"Draft smarter. [App Name]."*

Show: GitHub link, team credits

---

## 11. Submission Checklist

- [ ] Public GitHub repo with MIT license
- [ ] README with:
  - [ ] Project description
  - [ ] Tech stack
  - [ ] Setup instructions (uv, database seeding)
  - [ ] Demo video link
  - [ ] Screenshots
  - [ ] Architecture diagram
  - [ ] Team credits
- [ ] Category: AI Draft Assistant / Draft Predictor
- [ ] 3-minute demo video (YouTube)
- [ ] All source code included
- [ ] Pre-seeded database or seeding script
- [ ] Knowledge files (domain expert contributions)
- [ ] LICENSE file (MIT)

---

## 12. Domain Expert Request List

Please provide the following to maximize AI insight quality:

### Required (Week 1)
1. **Team profiles** for top 20 teams (LCK, LEC priority):
   - Playstyle (aggressive/scaling/flexible)
   - Draft tendencies
   - Signature strategies

2. **200 interesting series** to ingest:
   - Series IDs or "Tournament + Teams + Game" identifiers
   - Brief note on why (upset, draft diff, creative picks)

3. **Current meta summary** (2025):
   - S/A tier champions by role
   - What defines good drafts now
   - Key strategic principles

### Required (Week 2)
4. **Player hidden pools**:
   - Champions players are known for but rarely pick on stage
   - Solo queue comfort picks

5. **Comp archetype definitions**:
   - Champion markers for each archetype
   - Win conditions
   - Counter archetypes

6. **Champion flex mappings**:
   - Which champions flex to which roles
   - "Trap" flexes to avoid

### Required (Week 3)
7. **Prompt review**:
   - Review AI insights for accuracy
   - Suggest domain-specific language
   - Flag any nonsensical outputs

8. **Draft rules document**:
   - Phase-by-phase priorities
   - Blue vs red side strategy
   - Common mistakes to flag

### Nice to Have
9. **Champion rework dates** (for data filtering)
10. **Skill transfer mappings** (if good at X, can play Y)
11. **Red flag picks** (statistically okay but strategically bad)

---

## Appendix A: Sample Series Selection Criteria

Domain expert should prioritize:

| Criteria | Weight | Example |
|----------|--------|---------|
| **Upsets** | High | Lower seed wins; draft was a factor |
| **Draft Disasters** | High | Clear mistakes we would've flagged |
| **Creative Drafts** | Medium | Unusual picks that worked |
| **Meta-Defining** | Medium | Drafts that showed new strategies |
| **Rivalry Matches** | Low | T1 vs Gen.G (audience familiarity) |
| **Recent (2024-2025)** | High | Current rosters, relevant meta |

---

## Appendix B: Related Documents

| Document | Purpose |
|----------|---------|
| [recommendation-service-architecture.md](./recommendation-service-architecture.md) | Detailed scoring algorithms, flex pick resolution, data structures |
| [recommendation-service-overview.md](./recommendation-service-overview.md) | High-level system overview, uncertainty handling, UI representation |
| [architecture-v2-review.md](./architecture-v2-review.md) | Data quality analysis, DuckDB queries, gap analysis |
| [duckdb-analysis.md](./duckdb-analysis.md) | Database technology decision |
| [plans/2026-01-23-draft-simulation-service-design.md](./plans/2026-01-23-draft-simulation-service-design.md) | Draft replay service design |

---

*Spec Version: Hackathon v2.3 | January 2026*
*v2.3 changes: Refactored to high-level spec; moved implementation details to dedicated design documents*
*v2.2 changes: Added DuckDB + FastAPI async/sync implementation patterns*
*v2.1 changes: Switched from SQLite to DuckDB for zero-ETL CSV querying*
*v2.0: Layered analysis, recency weighting, surprise pick detection, open source LLM, domain knowledge integration*
