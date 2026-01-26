# Draft Simulation Service Design

**Date:** 2026-01-23
**Status:** Implemented ✓
**Scope:** Replay-first draft simulation for demo
**Implementation:** `backend/src/ban_teemo/services/draft_service.py`, `replay_manager.py`

---

## Overview

Service layer for simulating pick/ban phase replays. Loads historical draft data from CSVs via DuckDB, streams actions over WebSocket with configurable delays, and provides stub recommendation data flow.

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Data access | DuckDB (direct CSV) | Zero ETL, fast analytics, simpler than SQLite seed |
| Session storage | In-memory dict | Demo-only, no persistence needed |
| Primary mode | Replay-first | Spec recommendation, simpler than interactive |
| Recommendations | Stub for now | Get simulation working first, add intelligence later |

---

## Data Models

### Core Types

```python
class DraftPhase(str, Enum):
    BAN_PHASE_1 = "BAN_PHASE_1"      # Bans 1-6
    PICK_PHASE_1 = "PICK_PHASE_1"    # Picks 1-6
    BAN_PHASE_2 = "BAN_PHASE_2"      # Bans 7-10
    PICK_PHASE_2 = "PICK_PHASE_2"    # Picks 7-10
    COMPLETE = "COMPLETE"

@dataclass
class Player:
    id: str
    name: str
    role: str  # TOP, JNG, MID, ADC, SUP

@dataclass
class TeamContext:
    id: str
    name: str
    side: str  # "blue" or "red"
    players: list[Player]

@dataclass
class DraftAction:
    sequence: int          # 1-20
    action_type: str       # "ban" or "pick"
    team_side: str         # "blue" or "red"
    champion_id: str
    champion_name: str

@dataclass
class DraftState:
    game_id: str
    series_id: str
    game_number: int
    patch_version: str
    match_date: datetime
    blue_team: TeamContext
    red_team: TeamContext
    actions: list[DraftAction]
    current_phase: DraftPhase
    next_team: str | None
    next_action: str | None

    @property
    def blue_bans(self) -> list[str]: ...
    @property
    def red_bans(self) -> list[str]: ...
    @property
    def blue_picks(self) -> list[str]: ...
    @property
    def red_picks(self) -> list[str]: ...
```

### Replay Session

```python
class ReplayStatus(str, Enum):
    PENDING = "pending"
    PLAYING = "playing"
    PAUSED = "paused"
    COMPLETE = "complete"

@dataclass
class ReplaySession:
    id: str
    game_id: str
    series_id: str
    game_number: int
    status: ReplayStatus
    current_index: int
    speed: float
    delay_seconds: float
    all_actions: list[DraftAction]
    draft_state: DraftState
    websocket: WebSocket | None
    timer_task: asyncio.Task | None
```

### Recommendations (Stub)

```python
@dataclass
class PickRecommendation:
    champion_name: str
    confidence: float
    flag: str | None
    reasons: list[str]

@dataclass
class BanRecommendation:
    champion_name: str
    priority: float
    target_player: str | None
    reasons: list[str]

@dataclass
class Recommendations:
    for_team: str
    picks: list[PickRecommendation]
    bans: list[BanRecommendation]
```

---

## Module Structure

```
backend/src/ban_teemo/
├── main.py                     # FastAPI app, lifespan, CORS
├── config.py                   # Settings (existing)
│
├── api/
│   ├── routes/
│   │   ├── replay.py           # POST /api/replay/start, GET /api/series
│   │   └── health.py           # GET /health
│   └── websockets/
│       └── replay_ws.py        # WS /ws/replay/{session_id}
│
├── models/
│   ├── draft.py                # DraftState, DraftAction, DraftPhase
│   ├── team.py                 # TeamContext, Player
│   └── recommendations.py      # Recommendation types
│
├── services/
│   ├── draft_service.py        # DraftService (business logic)
│   └── replay_manager.py       # ReplayManager, ReplaySession
│
├── repositories/
│   └── draft_repository.py     # DraftRepository (DuckDB queries)
│
└── analytics/                  # Future: recommendation engine
    └── draft_analytics.py      # Stub
```

---

## API Endpoints

### REST

```
POST /api/replay/start
  Body: { series_id, game_number, speed? }
  Response: { session_id, total_actions, blue_team, red_team, websocket_url }

GET /api/series
  Query: ?limit=50
  Response: { series: [{ id, match_date, blue_team_name, red_team_name }] }
```

### WebSocket

```
WS /ws/replay/{session_id}

Server → Client messages:
- session_start: { blue_team, red_team, total_actions, patch }
- draft_action: { action, draft_state, recommendations }
- draft_complete: { draft_state }
```

---

## Data Flow

1. `POST /api/replay/start` → load game from CSVs, create session
2. Client connects to `WS /ws/replay/{session_id}`
3. Server sends `session_start` with team info
4. Loop every N seconds:
   - Send `draft_action` with action + state + recommendations
   - Increment index
5. After action 20: send `draft_complete`

---

## DuckDB Queries

### Get Series List
```sql
SELECT s.id, s.match_date, s.format, t1.name as blue_team_name, t2.name as red_team_name
FROM series.csv s
JOIN teams.csv t1 ON s.blue_team_id = t1.id
JOIN teams.csv t2 ON s.red_team_id = t2.id
ORDER BY s.match_date DESC
```

### Get Game Info
```sql
SELECT g.id, g.series_id, g.game_number, g.patch_version, s.match_date, s.blue_team_id, s.red_team_id
FROM games.csv g
JOIN series.csv s ON g.series_id = s.id
WHERE g.series_id = ? AND g.game_number = ?
```

### Get Players for Game
```sql
SELECT DISTINCT player_id, player_name, role, team_side
FROM player_game_stats.csv
WHERE game_id = ? AND team_id = ?
ORDER BY CASE role WHEN 'TOP' THEN 1 ... END
```

### Get Draft Actions
```sql
SELECT da.sequence_number, da.action_type, da.champion_id, da.champion_name,
       CASE WHEN da.team_id = s.blue_team_id THEN 'blue' ELSE 'red' END as team_side
FROM draft_actions.csv da
JOIN games.csv g ON da.game_id = g.id
JOIN series.csv s ON g.series_id = s.id
WHERE da.game_id = ?
ORDER BY da.sequence_number
```

---

## Draft Order Reference

Standard pro draft (20 actions):

| # | Type | Team | Phase |
|---|------|------|-------|
| 1-3 | Ban | B-R-B | BAN_PHASE_1 |
| 4-6 | Ban | R-B-R | BAN_PHASE_1 |
| 7 | Pick | B | PICK_PHASE_1 |
| 8-9 | Pick | R-R | PICK_PHASE_1 |
| 10-11 | Pick | B-B | PICK_PHASE_1 |
| 12 | Pick | R | PICK_PHASE_1 |
| 13-14 | Ban | R-B | BAN_PHASE_2 |
| 15-16 | Ban | R-B | BAN_PHASE_2 |
| 17 | Pick | R | PICK_PHASE_2 |
| 18-19 | Pick | B-B | PICK_PHASE_2 |
| 20 | Pick | R | PICK_PHASE_2 |

---

## Extension Points

| Component | Future Enhancement |
|-----------|-------------------|
| `DraftService.get_recommendations()` | Replace stub with 4-layer analytics |
| `analytics/draft_analytics.py` | Meta stats, synergies, counters, proficiency |
| WebSocket | Add pause/resume/jump controls |
| Replay | Add LLM insight generation per action |

---

*Design approved: 2026-01-23*
