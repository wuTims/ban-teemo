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
| Feature | Description | Status |
|---------|-------------|--------|
| Draft Tracker UI | Real-time ban/pick visualization | ✅ Done |
| Layered Analytics | Meta, tendencies, proficiency, synergies | 🔄 In Progress |
| Pick Recommendations | Top 3-5 suggestions with confidence + flags | 🔄 In Progress |
| Ban Recommendations | Opponent's highest-impact champions | 🔄 In Progress |
| Surprise Pick Detection | Low sample but contextually strong picks | 🔄 In Progress |
| Replay Mode | Step through historical drafts | ✅ Done |
| LLM Insights | Natural language draft commentary | ⏳ Not Started |

### 2.2 Stretch Goals (Week 4 - if time)

| Feature | Demo Impact | Status |
|---------|-------------|--------|
| **Post-Game Analysis** | "Here's what optimal draft would've been" | ⏳ Not Started |
| **What-If Simulator** | Drag-drop to explore alternate drafts | ⏳ Not Started |
| **Win Probability** | Live % that updates with each pick | ⏳ Not Started |
| **Head-to-Head History** | "Last 5 times these teams met..." | ⏳ Not Started |

### 2.3 Explicitly Out of Scope

- Mobile app
- User accounts/auth
- Solo queue data integration
- Full historical ingestion pipeline
- Production deployment/scaling
- Multi-language support

---

## 3. Technical Architecture

> **Full Details:** See dedicated design documents in Appendix B

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
  - Fast inference for real-time insights

Data:
  - Riot Data Dragon (champion icons)
  - GRID API (match data) - already extracted to CSV
  - DuckDB querying CSV files directly (zero ETL)
  - Domain expert knowledge files (JSON)
```

### 3.2 High-Level Architecture

```
┌────────────────────────────────────────────────────────────────────┐
│                        FRONTEND (React)                            │
│   Draft Board │ Recommendation Cards │ AI Insight Panel           │
└───────────────────────────┬────────────────────────────────────────┘
                            │ WebSocket / REST
                            ▼
┌────────────────────────────────────────────────────────────────────┐
│                        BACKEND (FastAPI)                           │
│  Services: Draft, Replay, Recommendation, Archetype, Synergy      │
│  Knowledge: Pre-computed JSON files for fast lookups              │
└───────────────────────────┬────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┬────────────────────┐
        ▼                   ▼                   ▼                    ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌───────────────┐
│  GRID API    │    │   DuckDB     │    │  Llama 3.1   │    │ Domain Expert │
│  (Live Data) │    │  (Analytics) │    │  (Insights)  │    │ Knowledge     │
└──────────────┘    │  → CSV Files │    │  via Groq    │    │ (JSON)        │
                    └──────────────┘    └──────────────┘    └───────────────┘
```

### 3.3 Data Setup

```bash
./scripts/download-data.sh
```

Downloads 114 MB CSV data from GitHub releases to `outputs/full_2024_2025_v2/`.

| Entity | Records |
|--------|---------|
| Teams | 57 |
| Players | 445 |
| Series | 1,482 |
| Games | 3,436 |
| Draft Actions | 68,529 |
| Player Stats | 34,416 |

**Regions:** LCK (409), LEC (323), LCS (174), LPL (458), International (117)

---

## 4. Development Plan

### Week 1: Foundation & Data
- Project setup (repo, CI, uv, FastAPI skeleton) - ✅ Done
- GRID API client - ✅ Done (68K+ records)
- DuckDB analytics service + query functions - ✅ Done
- Domain expert: provide knowledge files - ✅ Done
- Champion Data Dragon icon mapping - ✅ Done
- Knowledge file generation - ✅ Done

**Deliverable:** DuckDB analytics layer with all query functions, knowledge files ready

### Week 2: Core Backend Logic
- Pick recommendation algorithm (all 4 layers) - 🔄 In Progress
- Ban recommendation service with multi-factor scoring - 🔄 In Progress
- Surprise pick detection logic - 🔄 In Progress
- Archetype service (team comp classification + RPS matchups) - 🔄 In Progress
- Synergy service (S/A/B/C rating multipliers) - 🔄 In Progress
- Team evaluation service (cumulative scoring) - 🔄 In Progress
- Replay controller (timer-driven action release) - ✅ Done
- WebSocket endpoint for draft streaming - ✅ Done
- REST endpoints for analytics - ✅ Done

**Deliverable:** Backend that can replay drafts and generate layered recommendations with team evaluation

### Week 3: Frontend & LLM
- React app scaffold - ✅ Done
- Data Dragon utilities + icon mapping - ✅ Done
- Draft board component implementation - ✅ Done
- Recommendation panel component - 🔄 In Progress
- LLM integration (Groq/Together client) - ⏳ Not Started
- Insight prompt engineering + iteration - ⏳ Not Started
- WebSocket client integration - ✅ Done
- Series selector / replay controls UI - ✅ Done

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

## 5. Demo Script (3 minutes)

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

## 6. Submission Checklist

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

## 7. Domain Expert Request List

Please provide the following to maximize AI insight quality:

### Required (Week 1) - ✅ Complete
1. **Team profiles** for top 20 teams (LCK, LEC priority)
2. **200 interesting series** to ingest
3. **Current meta summary** (2025)

### Required (Week 2) - ✅ Complete
4. **Player hidden pools**
5. **Comp archetype definitions**
6. **Champion flex mappings**

### Required (Week 3) - ⏳ Pending
7. **Prompt review** - Review AI insights for accuracy
8. **Draft rules document** - Phase-by-phase priorities

### Nice to Have - ✅ Complete
9. **Champion rework dates** - In `knowledge/rework_patch_mapping.json`
10. **Skill transfer mappings** - In `knowledge/skill_transfers.json`
11. **Red flag picks** - TBD

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

## Appendix B: Technical Design Documents

This spec provides the project charter and high-level overview. Implementation details live in dedicated design documents:

### Architecture & System Design
| Document | Purpose |
|----------|---------|
| [recommendation-service-overview.md](./recommendation-service-overview.md) | System design: uncertainty handling, confidence weighting, flex pick resolution |
| [recommendation-service-architecture.md](./recommendation-service-architecture.md) | Implementation: data structures, algorithms, service interfaces |
| [architecture-v2-review.md](./architecture-v2-review.md) | Data quality analysis, DuckDB queries, gap analysis |
| [duckdb-analysis.md](./duckdb-analysis.md) | Database technology decision rationale |

### Implementation Plans
| Document | Purpose |
|----------|---------|
| [plans/2026-01-26-coach-mode-recommendation-system.md](./plans/2026-01-26-coach-mode-recommendation-system.md) | Coach mode with enemy pool analysis |
| [plans/2026-01-26-recommendation-system-enhancements.md](./plans/2026-01-26-recommendation-system-enhancements.md) | Archetype system, synergy service, ban recommendations |
| [plans/2026-01-25-computed-datasets-design.md](./plans/2026-01-25-computed-datasets-design.md) | Pre-computed knowledge file generation |
| [plans/2026-01-25-data-organization-design.md](./plans/2026-01-25-data-organization-design.md) | GitHub release strategy for data files |
| [plans/2026-01-24-frontend-draft-visualization.md](./plans/2026-01-24-frontend-draft-visualization.md) | Draft board UI components |
| [plans/2026-01-23-draft-simulation-service-design.md](./plans/2026-01-23-draft-simulation-service-design.md) | Replay system architecture |

### UI/UX
| Document | Purpose |
|----------|---------|
| [lol-draft-assistant-style-guide.md](./lol-draft-assistant-style-guide.md) | Design guidelines and visual standards |

---

*Spec Version: Hackathon v3.0 | January 2026*
*v3.0 changes: Slimmed to project charter; moved implementation details to dedicated design documents*
*v2.4 changes: Added archetype system, ban scoring weights, team evaluation, updated knowledge files*
*v2.3 changes: Refactored to high-level spec; moved implementation details to dedicated design documents*
