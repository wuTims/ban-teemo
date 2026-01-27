# Draft Simulator Design

> **For Claude:** Use superpowers:writing-plans to create an implementation plan from this design.

**Goal:** Build an interactive draft simulator where users practice drafting against AI-controlled pro teams, showcasing the recommendation engine in action.

**Status:** Design approved, ready for implementation planning.

---

## Overview

The simulator lets users:
1. Select two pro teams and choose which side to coach
2. Pick/ban champions on their turns while AI handles the opponent
3. See recommendations powered by the scoring engine
4. Play Bo1/Bo3/Bo5 series with optional Fearless mode

The AI generates realistic picks/bans based on the enemy team's historical draft data.

---

## User Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ 1. SETUP                                                                     │
│    User clicks "Start Simulator" → Modal appears                             │
│    Selects: Blue team, Red team, coaching side, series format, draft mode    │
│    Clicks "Start Draft"                                                      │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 2. DRAFT LOOP (20 actions per game)                                          │
│                                                                              │
│    Our turn:                                                                 │
│      → Active slot highlights                                                │
│      → Recommendations panel shows suggestions                               │
│      → User clicks champion in pool (or recommendation)                      │
│      → Champion locks in, draft advances                                     │
│                                                                              │
│    Enemy turn:                                                               │
│      → "Enemy picking..." indicator                                          │
│      → 1s delay                                                              │
│      → AI selects champion from historical data                              │
│      → Champion locks in, draft advances                                     │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 3. GAME COMPLETE                                                             │
│                                                                              │
│    Shows: final comps, team evaluation, draft analysis                       │
│    User selects winner (for series tracking)                                 │
│                                                                              │
│    More games? → "Next Game" → back to step 2                                │
│    Series done? → Summary → return to setup                                  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## UI Layout

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ [Mode: Replay | Simulator]              Game 2 of 3 │ T1 1-0 Gen.G │ Fearless│
├──────────────────────────────────────────────────────────────────────────────┤
│                              [BAN PHASE 1 - Blue Banning]                    │
├─────────────────┬────────────────────────────────────┬──────────────────────┤
│   BLUE TEAM     │        CHAMPION POOL               │      RED TEAM        │
│   ★ coaching    │                                    │                      │
│                 │  [Search 🔍] [All][Top][Jg][Mid].. │                      │
│  ┌───────────┐  │  ┌──┬──┬──┬──┬──┬──┬──┬──┐        │  ┌───────────┐       │
│  │  Pick 1   │  │  │  │  │XX│  │🚫│  │XX│  │        │  │  Pick 1   │       │
│  ├───────────┤  │  ├──┼──┼──┼──┼──┼──┼──┼──┤        │  ├───────────┤       │
│  │  Pick 2   │  │  │  │🚫│  │  │  │  │  │  │        │  │  Pick 2   │       │
│  ├───────────┤  │  ├──┼──┼──┼──┼──┼──┼──┼──┤        │  ├───────────┤       │
│  │  Pick 3   │  │  │  │  │  │  │  │  │  │  │        │  │  Pick 3   │       │
│  ├───────────┤  │  └──┴──┴──┴──┴──┴──┴──┴──┘        │  ├───────────┤       │
│  │  Pick 4   │  │  (scrollable, ~8 cols)            │  │  Pick 4   │       │
│  ├───────────┤  │                                    │  ├───────────┤       │
│  │  Pick 5   │  │  XX = unavailable (picked/banned) │  │  Pick 5   │       │
│  └───────────┘  │  🚫 = Fearless blocked             │  └───────────┘       │
│                 │                                    │                      │
├─────────────────┴────────────────────────────────────┴──────────────────────┤
│            [B1][B2][B3][B4][B5]              [B1][B2][B3][B4][B5]            │
│            ─── Blue Bans ───                ─── Red Bans ───                │
├─────────────────────────────────────────────────────────────────────────────┤
│                         RECOMMENDATIONS                                      │
│  Pick: [Azir ⭐0.85 "Strong proficiency"] [Orianna ⭐0.82] [Syndra ⭐0.78]    │
│  Ban:  [Aurora 🎯Zeus "73% presence"] [Yone 🎯Chovy "Signature pick"]        │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Key layout decisions:**
- 3-column layout: Blue Team | Champion Pool | Red Team
- Bans displayed as compact row below picks
- Recommendations panel at bottom (clickable to select)
- Coached team marked with ★
- Champion pool shows unavailable (XX) and Fearless blocked (🚫) states

---

## Enemy Pick Generation

AI generates enemy picks using a priority cascade:

### Step 1: Reference Game Script

On session start:
- Load enemy team's last 20 games from database
- Randomly select one as "reference game"
- Extract their draft actions in sequence order

On enemy turn:
- Get action at current sequence from reference script
- If champion is **available** → use it ✓
- If champion is **unavailable** → go to Step 2

### Step 2: Fallback Games

For each remaining game in fallback queue:
- Load that game's draft script
- Find action at same sequence position
- If champion is **available** → use it ✓
- If **unavailable** → try next fallback

If all fallbacks exhausted → go to Step 3

### Step 3: Weighted Random

Pre-computed on session start:
```
champion_weights = COUNT(picks by champion) / total_picks
e.g., { "Azir": 0.15, "Orianna": 0.12, "Ahri": 0.08, ... }
```

On fallback:
- Filter to available champions only
- Weighted random selection based on historical frequency
- Use selected champion ✓

### Availability Rules

A champion is **unavailable** if:
- Already picked (either team)
- Already banned (either team)
- Blocked by Fearless (if enabled)

---

## Fearless Mode

**Rules:**
- Once picked, a champion is blocked for the rest of the series
- Applies to both teams (10 champions blocked per game)
- Bans don't carry over, only picks

**Implementation:**
```python
def on_game_complete(session, winner):
    session.game_results.append({
        "game": session.current_game,
        "winner": winner,
        "blue_comp": session.draft_state.blue_picks,
        "red_comp": session.draft_state.red_picks,
    })

    if session.draft_mode == "fearless":
        session.fearless_blocked.update(session.draft_state.blue_picks)
        session.fearless_blocked.update(session.draft_state.red_picks)
```

**UI display:**
- Fearless blocked champions show darker overlay + lock icon
- Tooltip: "Used in Game 1 by [Team]"
- Series status bar shows blocked count

---

## Setup Modal

```
┌─────────────────────────────────────────────────────────────────┐
│                    START NEW DRAFT SESSION                       │
│                                                                  │
│  Blue Side Team        vs        Red Side Team                   │
│  ┌─────────────────┐            ┌─────────────────┐             │
│  │ Select Team ▼   │            │ Select Team ▼   │             │
│  └─────────────────┘            └─────────────────┘             │
│                                                                  │
│  You are coaching:  ○ Blue Side    ○ Red Side                   │
│                                                                  │
│  Series Format:     ○ Bo1   ○ Bo3   ○ Bo5                       │
│                                                                  │
│  Draft Mode:        ○ Normal   ○ Fearless                       │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ Game 1 of 3                              [Start Draft]     │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

**Team dropdowns:** Pro teams only (from GRID data)

**After game completes:**
- "Game Complete" screen shows winner selection
- "Next Game" advances with previous winner auto-tracked
- Fearless blocked champions carry over

---

## API Endpoints

### Create Session

```
POST /api/simulator/start

Request:
{
  "blue_team_id": "oe:team:abc123",
  "red_team_id": "oe:team:def456",
  "coaching_side": "blue",
  "series_length": 3,
  "draft_mode": "fearless"
}

Response:
{
  "session_id": "sim_abc123",
  "game_number": 1,
  "blue_team": { "id", "name", "logo_url", "players": [...] },
  "red_team": { "id", "name", "logo_url", "players": [...] },
  "draft_state": { "phase": "BAN_PHASE_1", "next_team": "blue", ... },
  "recommendations": { "picks": [...], "bans": [...] }
}
```

### User Action

```
POST /api/simulator/{session_id}/action

Request:
{
  "champion": "Azir"
}

Response:
{
  "action": { "sequence": 1, "action_type": "ban", "team_side": "blue", "champion": "Azir" },
  "draft_state": { ... },
  "recommendations": { ... },
  "is_our_turn": false
}
```

### Enemy Action

```
POST /api/simulator/{session_id}/enemy-action

Response:
{
  "action": { "sequence": 2, "action_type": "ban", "team_side": "red", "champion": "Yone" },
  "draft_state": { ... },
  "recommendations": { ... },
  "is_our_turn": true,
  "source": "reference_game" | "fallback_game" | "weighted_random"
}
```

### Complete Game

```
POST /api/simulator/{session_id}/complete-game

Request:
{
  "winner": "blue"
}

Response:
{
  "series_status": { "blue_wins": 1, "red_wins": 0, "series_complete": false },
  "fearless_blocked": ["Azir", "Orianna", ...],
  "next_game_ready": true
}
```

### Next Game

```
POST /api/simulator/{session_id}/next-game

Response:
{
  "game_number": 2,
  "draft_state": { ... },
  "recommendations": { ... },
  "fearless_blocked": [...]
}
```

### Get Session State

```
GET /api/simulator/{session_id}

Response:
{
  "session_id": "sim_abc123",
  "status": "drafting",
  "game_number": 2,
  "draft_state": { ... },
  "series_status": { ... },
  "fearless_blocked": [...]
}
```

### End Session

```
DELETE /api/simulator/{session_id}

Response: { "status": "ended" }
```

---

## Component Structure

### New Components

```
deepdraft/src/components/
├── SimulatorSetupModal/
│   └── index.tsx                # Pre-session configuration
│
├── ChampionPool/
│   ├── index.tsx                # Container with search + filter
│   ├── ChampionGrid.tsx         # Scrollable champion grid
│   ├── RoleFilter.tsx           # Top/Jg/Mid/ADC/Sup tabs
│   └── SearchBar.tsx            # Champion name search
│
├── SimulatorControls/
│   └── index.tsx                # Series status bar
│
├── GameCompleteModal/
│   └── index.tsx                # End of game summary
│
└── draft/
    └── BanRow.tsx               # Horizontal ban display
```

### Modified Components

- `DraftBoard/index.tsx` - 3-column layout with champion pool
- `draft/TeamPanel.tsx` - Add click handlers for simulator
- `RecommendationPanel/index.tsx` - Clickable recommendation cards
- `App.tsx` - Mode toggle (Replay | Simulator)

### New Hook

```typescript
// hooks/useSimulatorSession.ts

interface SimulatorState {
  status: "setup" | "drafting" | "game_complete" | "series_complete";
  session: SimulatorSession | null;
  draftState: DraftState | null;
  recommendations: Recommendations | null;
  isOurTurn: boolean;
  isEnemyThinking: boolean;
  fearlessBlocked: string[];
  seriesStatus: SeriesStatus | null;

  // Actions
  startSession: (config: SimulatorConfig) => Promise<void>;
  submitAction: (champion: string) => Promise<void>;
  triggerEnemyAction: () => Promise<void>;
  recordWinner: (winner: "blue" | "red") => Promise<void>;
  nextGame: () => Promise<void>;
  endSession: () => void;
}
```

---

## Backend Structure

### New Files

```
backend/src/ban_teemo/
├── services/
│   ├── enemy_simulator_service.py   # Generates enemy picks
│   └── simulator_session.py         # Session state management
│
├── models/
│   └── simulator.py                 # SimulatorSession, EnemyStrategy models
│
└── api/routes/
    └── simulator.py                 # REST endpoints
```

### EnemySimulatorService

```python
class EnemySimulatorService:
    """Generates enemy picks/bans from historical data."""

    def initialize_enemy_strategy(self, enemy_team_id: str) -> EnemyStrategy:
        """Load reference game, fallbacks, and champion weights."""
        ...

    def generate_action(
        self,
        strategy: EnemyStrategy,
        sequence: int,
        unavailable: set[str]
    ) -> tuple[str, str]:  # (champion, source)
        """Generate enemy's next pick/ban using priority cascade."""
        ...
```

### SimulatorSession Model

```python
@dataclass
class SimulatorSession:
    session_id: str
    blue_team: TeamContext
    red_team: TeamContext
    coaching_side: Literal["blue", "red"]
    series_length: Literal[1, 3, 5]
    draft_mode: Literal["normal", "fearless"]

    # Current game
    current_game: int
    draft_state: DraftState
    enemy_strategy: EnemyStrategy

    # Series tracking
    game_results: list[GameResult]
    fearless_blocked: set[str]
```

---

## Integration with Recommendation System Plan

The simulator integrates with `docs/plans/2026-01-26-unified-recommendation-system.md`:

| Stage | Original Plan | With Simulator |
|-------|--------------|----------------|
| 1 | Core Scorers | **Keep as-is** |
| 2 | Enhancement Services | **Keep as-is** |
| 3 | PickRecommendationEngine | **Keep as-is** |
| 4 | Coach Mode | **Partial** - use EnemyPoolService only |
| 5 | Frontend | **Replace** - simulator UI instead |

### Implementation Order

**Phase 1: Core Infrastructure (Stages 1-3)**
- Build scorers + recommendation engine
- These power recommendations in simulator

**Phase 2: Enemy Simulation (Stage 4 partial + new)**
- Build EnemyPoolService (from Stage 4)
- Build EnemySimulatorService (new)
- Build SimulatorSession management (new)
- Build REST endpoints

**Phase 3: Simulator Frontend (replaces Stage 5)**
- SimulatorSetupModal
- ChampionPool component
- Modified DraftBoard layout
- useSimulatorSession hook
- Mode toggle in App

**Phase 4: Polish**
- Fearless mode
- Series management
- Game complete flow
- Error handling

---

## Technical Decisions Summary

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Layout | 3-column with center pool | Matches industry standard (drafter.lol) |
| Bans | Row below picks | Saves vertical space |
| Communication | REST (not WebSocket) | Turn-based, no streaming needed |
| Enemy pacing | Fixed 1s delay | Simple, keeps flow moving |
| Team data | Pro teams only | Have historical data, player proficiency |
| Fearless tracking | Server-side | Single source of truth |
| Mode switching | Toggle in header | Keep replay mode accessible |

---

## Success Criteria

1. User can start a draft against any pro team
2. AI makes realistic picks matching team's historical style
3. Recommendations update each turn with relevant picks/bans
4. Fearless mode correctly blocks champions across games
5. Series tracking works for Bo3/Bo5
6. UI is responsive and matches LoL draft aesthetic
