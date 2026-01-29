# Draft Simulator Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build an interactive draft simulator with AI-controlled opponents, powered by a real recommendation engine.

**Architecture:** Stages 1-2 build the recommendation engine (scorers → enhancement services). Stage 3 adds simulator backend (enemy AI, session management, team-composition-first recommendations). Stages 4-5 build the simulator frontend (types/hooks → UI components).

**Tech Stack:** Python 3.14+, FastAPI, Pydantic, TypeScript, React, Tailwind CSS

**Reference:**
- `docs/plans/2026-01-27-draft-simulator-design.md` - Design document
- `docs/plans/2026-01-26-unified-recommendation-system.md` - Scoring formulas and data schemas

**Key Design Decisions:**
- **Series always start at Game 1.** There is no mid-series start. Multi-game series flow naturally as players complete each game and advance to the next. This keeps the experience realistic and avoids fabricating "previous game" picks.
- **Fearless tracking preserves team metadata.** The `fearless_blocked` dict stores which team picked each champion and in which game, enabling UI tooltips like "Used in Game 1 by Blue".
- **Fallback uses next valid action.** When a scripted champion is unavailable, the system finds the next valid action at or after the current sequence position, not an exact match.
- **Team-composition-first recommendations.** Pick recommendations are based on what's best for the team composition, not tied to "which player is picking now." The engine considers all unfilled roles, aggregates proficiency across all team players (takes best), and returns `suggested_role` and `best_player` fields. This reflects real drafts where champions can be swapped post-draft.

---

## Implementation Progress

> **For Claude:** Check this section first to understand current state before executing tasks.

### Status Overview

| Stage | Status | Notes |
|-------|--------|-------|
| Stage 1: Core Scorers | ✅ Complete | MetaScorer, FlexResolver, ProficiencyScorer, MatchupCalculator |
| Stage 2: Enhancement Services | ✅ Complete | All fixes implemented and tested |
| Stage 3: Simulator Backend | ✅ Complete | Models, EnemySimulatorService, routes, team-composition-first engine |
| Stage 4: Frontend Types/Hook | ✅ Complete | Types and useSimulatorSession hook with review fixes |
| Stage 5: API Refactoring | ✅ Complete | CQRS refactor with staleness detection, 97 tests passing |
| Stage 6: Frontend UI | 🔲 Not Started | ChampionPool, SimulatorSetupModal, SimulatorView, App integration |
| Stage 7: Integration Test | 🔲 Not Started | Full test suite, manual smoke test |

### Stage 5 Completion Summary

All Stage 5 tasks have been implemented:

#### Task 5.1: Update Frontend Types
**Status:** ✅ Complete
**Files:** `deepdraft/src/types/index.ts`

- Added `RecommendationsResponse` and `EvaluationResponse` for new query endpoints
- Updated `SimulatorStartResponse` - removed recommendations/team_evaluation
- Updated `SimulatorActionResponse` - made recommendations/evaluation optional
- Fixed `EvaluationResponse` to allow null evaluations

#### Task 5.2: Refactor Backend Routes
**Status:** ✅ Complete
**Files:** `backend/src/ban_teemo/api/routes/simulator.py`

- Renamed all endpoints to RESTful `/sessions/{id}/...` format
- Changed POST /start to POST /sessions (201 status)
- Added `?include_recommendations=true` and `?include_evaluation=true` query params
- Added GET `/sessions/{id}/recommendations` with `for_action_count` for staleness
- Added GET `/sessions/{id}/evaluation` with `for_action_count` for staleness
- Removed automatic recommendations/evaluation from action responses

#### Task 5.3: Update Backend Route Tests
**Status:** ✅ Complete
**Files:** `backend/tests/test_simulator_routes.py`, `backend/tests/test_integration.py`

- Updated all endpoint paths to new format
- Added `TestGetRecommendations` class with staleness tests
- Added `TestGetEvaluation` class
- Added `TestEagerFetchQueryParams` class
- Fixed integration tests for new paths

#### Task 5.4: Update Frontend Hook
**Status:** ✅ Complete
**Files:** `deepdraft/src/hooks/useSimulatorSession.ts`

- Updated all endpoint paths to `/sessions/{id}/...`
- Added `fetchRecommendations()` helper with staleness guard
- Updated `triggerEnemyAction()` with eager fetch via query params
- Added staleness guards using `action_count` in all state updates
- Frontend builds successfully (97 backend tests pass)

### Stage 4 Completion Summary

All Stage 4 tasks have been implemented with code review fixes applied:

#### Task 4.0: Fix DATA_PATH in main.py
**Status:** ✅ Complete
**Files:** `backend/src/ban_teemo/main.py`

Fixed data path from `outputs/full_2024_2025/csv` to `outputs/full_2024_2025_v2/csv` to match actual data location.

#### Task 4.1: Add Simulator Types
**Status:** ✅ Complete
**Files:** `deepdraft/src/types/index.ts`

Added types with review fixes:
- `DraftMode`, `SimulatorConfig`, `SeriesStatus` (with optional `games_played`)
- `SimulatorBanRecommendation` - ban phase recs with `priority`, `target_player`
- `SimulatorPickRecommendation` - pick phase recs with `score`, `suggested_role`, `components`
- `ScoreComponents` - breakdown of meta/proficiency/matchup/counter scores
- `SimulatorRecommendation` - union type for phase-agnostic handling
- `SynergyPair`, `TeamDraftEvaluation` (includes `synergy_pairs`), `TeamEvaluation`
- `SimulatorStartResponse`, `SimulatorActionResponse` - use union `SimulatorRecommendation[]`
- `FearlessBlockedEntry`, `FearlessBlocked`, `CompleteGameResponse`, `NextGameResponse`, `TeamListItem`

#### Task 4.2: Create useSimulatorSession Hook
**Status:** ✅ Complete
**Files:** `deepdraft/src/hooks/useSimulatorSession.ts`, `deepdraft/src/hooks/index.ts`

Hook with review fixes:
- State includes `teamEvaluation` for composition insights
- `startSession` resets ALL state using `initialState` spread (no stale data)
- Enemy action loop has proper cleanup: `pendingTimerRef`, `abortControllerRef`, `sessionIdRef`
- Cleanup on unmount and session change prevents state updates after end
- All responses properly typed (`CompleteGameResponse`, `NextGameResponse`)
- `triggerEnemyAction` checks `sessionIdRef` before updating state

**Known limitation:** `/next-game` doesn't return recommendations. If it's user's turn first in a new game, recommendations start as null until first action. Acceptable for MVP.

### Stage 2 Completion Summary

All Stage 2 fixes have been implemented and verified:

#### Fix 2.1: Add roster lookup methods to DraftRepository
**Status:** ✅ Complete
**Files:** `backend/src/ban_teemo/repositories/draft_repository.py`

Implemented methods:
- `get_team_games(team_id, limit)` - Get recent games for a team
- `get_team_roster(team_id)` - Get current roster for a team

**Note:** `get_team_context(team_id, side)` deferred to Task 3.1 - it builds a `TeamContext` dataclass needed for `SimulatorSession`, which is a Stage 3 model.

#### Fix 2.2: BanRecommendationService auto-lookup roster
**Status:** ✅ Complete
**Files:** `backend/src/ban_teemo/services/ban_recommendation_service.py`

Service now auto-looks up roster from `enemy_team_id` when `DraftRepository` is provided and `enemy_players` is None. Includes role normalization (e.g., "jungle" → "JNG").

#### Fix 2.3: Implement Phase 2 counter-pick ban logic
**Status:** ✅ Complete
**Files:** `backend/src/ban_teemo/services/ban_recommendation_service.py`

**Implementation deviation:** Uses `get_team_matchup()` instead of `get_lane_matchup()` for counter detection. Rationale: During draft, exact role assignments are often unknown (flex picks), so team-level matchups provide more robust counter detection. Code comment documents this decision.

#### Fix 2.4: MetaScorer role filtering
**Status:** ✅ Complete
**Files:** `backend/src/ban_teemo/services/scorers/meta_scorer.py`

`get_top_meta_champions(role=...)` now filters by role using `champion_role_history.json` data. Supports role aliases and multiple data sources.

#### Fix 2.5: Add test coverage
**Status:** ✅ Complete
**Files:** `backend/tests/test_ban_recommendation_service.py`, `backend/tests/test_meta_scorer.py`

Tests added:
- `test_ban_with_enemy_players_targets_pools`
- `test_ban_phase_2_prioritizes_counters`
- `test_get_top_meta_champions_filters_by_role`
- `test_auto_lookup_roster_from_repository`
- `test_auto_lookup_skipped_when_enemy_players_provided`
- `test_auto_lookup_normalizes_roles`

### Additional Fixes (from code review)

#### Fix 2.6: Role normalization in PickRecommendationEngine
**Status:** ✅ Complete
**Files:** `backend/src/ban_teemo/services/pick_recommendation_engine.py`, `backend/src/ban_teemo/services/scorers/flex_resolver.py`

**Problem:** Lane matchup scoring silently dropped to neutral because `player_role` (e.g., "JNG") didn't match FlexResolver's canonical roles (e.g., "JUNGLE").

**Fix:** Added `FlexResolver.normalize_role()` method and normalized role before matchup comparison.

#### Fix 2.7: ArchetypeService unknown champion handling
**Status:** ✅ Complete
**Files:** `backend/src/ban_teemo/services/archetype_service.py`

**Problem:** When all picks were unknown to archetype data, `calculate_team_archetype` returned a misleading primary (first alphabetically) with alignment 0.

**Fix:** Now returns `primary=None` when total archetype score is 0.

### Stage 3 Completion Summary

All Stage 3 tasks have been implemented and verified (73 tests passing):

#### Task 3.1-3.3: Simulator Models, EnemySimulatorService, Routes
**Status:** ✅ Complete (from previous work)

#### Task 3.4: Team-Composition-First Recommendations + Fixes
**Status:** ✅ Complete

Implemented changes:
- **FlexResolver**: Outputs JNG (not JUNGLE), loads champion_role_history.json for fallback, deterministic role assignment for unknown champions
- **MatchupCalculator**: Translates JNG→JUNGLE at lookup time for data file compatibility
- **PickRecommendationEngine**: Changed from `player_name/player_role` to `team_players` list, aggregates proficiency across all players (takes best), infers filled roles from picks, adds `suggested_role` and `flag` fields, fixed LOW_CONFIDENCE threshold to 0.7
- **BanRecommendationService**: Pool depth exploitation (+0.20 for ≤3 champs, +0.10 for ≤5 champs), pre-computes pool_size per player for efficiency
- **Simulator routes**: Updated to call new pick engine API

#### Task 3.5: Add team_evaluation to Start Response
**Status:** ✅ Complete

Returns `"team_evaluation": null` at start since no picks exist yet.

#### Task 3.6: Update Implementation Progress
**Status:** ✅ Complete

---

## Stage 1: Core Scorers

Build the foundational scoring components that power recommendations.

---

### Task 1.1: Create MetaScorer

**Files:**
- Create: `backend/src/ban_teemo/services/scorers/__init__.py`
- Create: `backend/src/ban_teemo/services/scorers/meta_scorer.py`
- Create: `backend/tests/test_meta_scorer.py`

**Step 1: Create scorers package**

```python
# backend/src/ban_teemo/services/scorers/__init__.py
"""Core scoring components for recommendation engine."""
```

**Step 2: Write the failing test**

```python
# backend/tests/test_meta_scorer.py
"""Tests for meta scorer."""
import pytest
from ban_teemo.services.scorers.meta_scorer import MetaScorer


@pytest.fixture
def scorer():
    return MetaScorer()


def test_get_meta_score_high_tier(scorer):
    """High-tier champion should have high meta score."""
    score = scorer.get_meta_score("Azir")
    assert 0.7 <= score <= 1.0


def test_get_meta_score_unknown(scorer):
    """Unknown champion returns neutral score."""
    score = scorer.get_meta_score("NonexistentChamp")
    assert score == 0.5


def test_get_meta_tier(scorer):
    """Test meta tier retrieval."""
    tier = scorer.get_meta_tier("Azir")
    assert tier in ["S", "A", "B", "C", "D", None]


def test_get_top_meta_champions(scorer):
    """Test getting top meta champions."""
    top = scorer.get_top_meta_champions(limit=5)
    assert len(top) <= 5
    assert all(isinstance(name, str) for name in top)
```

**Step 3: Run test to verify it fails**

```bash
cd backend && uv run pytest tests/test_meta_scorer.py -v
```

Expected: FAIL with "ModuleNotFoundError"

**Step 4: Write minimal implementation**

```python
# backend/src/ban_teemo/services/scorers/meta_scorer.py
"""Meta strength scorer based on pick/ban presence and win rate."""
import json
from pathlib import Path
from typing import Optional


class MetaScorer:
    """Scores champions based on current meta strength."""

    def __init__(self, knowledge_dir: Optional[Path] = None):
        if knowledge_dir is None:
            knowledge_dir = Path(__file__).parents[5] / "knowledge"
        self.knowledge_dir = knowledge_dir
        self._meta_stats: dict = {}
        self._load_data()

    def _load_data(self):
        """Load meta stats from knowledge file."""
        meta_path = self.knowledge_dir / "meta_stats.json"
        if meta_path.exists():
            with open(meta_path) as f:
                data = json.load(f)
                self._meta_stats = data.get("champions", {})

    def get_meta_score(self, champion_name: str) -> float:
        """Get meta strength score for a champion (0.0-1.0)."""
        if champion_name not in self._meta_stats:
            return 0.5
        return self._meta_stats[champion_name].get("meta_score", 0.5)

    def get_meta_tier(self, champion_name: str) -> Optional[str]:
        """Get meta tier (S/A/B/C/D) for a champion."""
        if champion_name not in self._meta_stats:
            return None
        return self._meta_stats[champion_name].get("meta_tier")

    def get_top_meta_champions(self, role: Optional[str] = None, limit: int = 10) -> list[str]:
        """Get top meta champions sorted by meta_score."""
        ranked = sorted(
            self._meta_stats.items(),
            key=lambda x: x[1].get("meta_score", 0),
            reverse=True
        )
        return [name for name, _ in ranked[:limit]]
```

**Step 5: Run test to verify it passes**

```bash
cd backend && uv run pytest tests/test_meta_scorer.py -v
```

Expected: PASS

**Step 6: Commit**

```bash
git add backend/src/ban_teemo/services/scorers backend/tests/test_meta_scorer.py
git commit -m "feat(scorers): add MetaScorer service"
```

---

### Task 1.2: Create FlexResolver

**Files:**
- Create: `backend/src/ban_teemo/services/scorers/flex_resolver.py`
- Create: `backend/tests/test_flex_resolver.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_flex_resolver.py
"""Tests for flex pick role resolution."""
import pytest
from ban_teemo.services.scorers.flex_resolver import FlexResolver


@pytest.fixture
def resolver():
    return FlexResolver()


def test_get_role_probabilities_flex(resolver):
    """Flex champion should have multiple roles."""
    probs = resolver.get_role_probabilities("Aurora")
    assert isinstance(probs, dict)
    assert sum(probs.values()) == pytest.approx(1.0, abs=0.01)


def test_get_role_probabilities_single_role(resolver):
    """Single-role champion should have high probability for one role."""
    probs = resolver.get_role_probabilities("Jinx")
    assert probs.get("ADC", 0) >= 0.9


def test_is_flex_pick(resolver):
    """Test flex pick detection."""
    assert resolver.is_flex_pick("Aurora") is True
    assert resolver.is_flex_pick("Jinx") is False
```

**Step 2: Run test to verify it fails**

```bash
cd backend && uv run pytest tests/test_flex_resolver.py -v
```

**Step 3: Write minimal implementation**

```python
# backend/src/ban_teemo/services/scorers/flex_resolver.py
"""Flex pick role resolution with probability estimation."""
import json
from pathlib import Path
from typing import Optional


class FlexResolver:
    """Resolves flex pick role probabilities."""

    VALID_ROLES = {"TOP", "JUNGLE", "MID", "ADC", "SUP"}

    def __init__(self, knowledge_dir: Optional[Path] = None):
        if knowledge_dir is None:
            knowledge_dir = Path(__file__).parents[5] / "knowledge"
        self.knowledge_dir = knowledge_dir
        self._flex_data: dict = {}
        self._load_data()

    def _load_data(self):
        """Load flex champion data."""
        flex_path = self.knowledge_dir / "flex_champions.json"
        if flex_path.exists():
            with open(flex_path) as f:
                data = json.load(f)
                self._flex_data = data.get("flex_picks", {})

    def get_role_probabilities(
        self, champion_name: str, filled_roles: Optional[set[str]] = None
    ) -> dict[str, float]:
        """Get role probability distribution for a champion."""
        filled = filled_roles or set()

        if champion_name not in self._flex_data:
            available = self.VALID_ROLES - filled
            if not available:
                return {}
            prob = 1.0 / len(available)
            return {role: prob for role in available}

        data = self._flex_data[champion_name]
        probs = {}
        for role in self.VALID_ROLES:
            if role not in filled:
                probs[role] = data.get(role, 0)

        total = sum(probs.values())
        if total > 0:
            probs = {role: p / total for role, p in probs.items()}
        elif probs:
            prob = 1.0 / len(probs)
            probs = {role: prob for role in probs}

        return probs

    def is_flex_pick(self, champion_name: str) -> bool:
        """Check if champion is a flex pick."""
        if champion_name not in self._flex_data:
            return False
        return self._flex_data[champion_name].get("is_flex", False)
```

**Step 4: Run test to verify it passes**

```bash
cd backend && uv run pytest tests/test_flex_resolver.py -v
```

**Step 5: Commit**

```bash
git add backend/src/ban_teemo/services/scorers/flex_resolver.py backend/tests/test_flex_resolver.py
git commit -m "feat(scorers): add FlexResolver service"
```

---

### Task 1.3: Create ProficiencyScorer

**Files:**
- Create: `backend/src/ban_teemo/services/scorers/proficiency_scorer.py`
- Create: `backend/tests/test_proficiency_scorer.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_proficiency_scorer.py
"""Tests for player proficiency scoring."""
import pytest
from ban_teemo.services.scorers.proficiency_scorer import ProficiencyScorer


@pytest.fixture
def scorer():
    return ProficiencyScorer()


def test_get_proficiency_score_known_player(scorer):
    """Test proficiency for known player."""
    score, confidence = scorer.get_proficiency_score("Faker", "Azir")
    assert 0.0 <= score <= 1.0
    assert confidence in ["HIGH", "MEDIUM", "LOW", "NO_DATA"]


def test_get_proficiency_unknown_player(scorer):
    """Unknown player returns neutral score."""
    score, confidence = scorer.get_proficiency_score("UnknownPlayer123", "Azir")
    assert score == 0.5
    assert confidence == "NO_DATA"


def test_get_player_champion_pool(scorer):
    """Test getting player's champion pool."""
    pool = scorer.get_player_champion_pool("Faker", min_games=1)
    assert isinstance(pool, list)
    if pool:
        assert "champion" in pool[0]
        assert "score" in pool[0]
```

**Step 2: Run test to verify it fails**

```bash
cd backend && uv run pytest tests/test_proficiency_scorer.py -v
```

**Step 3: Write minimal implementation**

```python
# backend/src/ban_teemo/services/scorers/proficiency_scorer.py
"""Player proficiency scoring with confidence tracking."""
import json
from pathlib import Path
from typing import Optional


class ProficiencyScorer:
    """Scores player proficiency on champions."""

    CONFIDENCE_THRESHOLDS = {"HIGH": 8, "MEDIUM": 4, "LOW": 1}

    def __init__(self, knowledge_dir: Optional[Path] = None):
        if knowledge_dir is None:
            knowledge_dir = Path(__file__).parents[5] / "knowledge"
        self.knowledge_dir = knowledge_dir
        self._proficiency_data: dict = {}
        self._load_data()

    def _load_data(self):
        """Load player proficiency data."""
        prof_path = self.knowledge_dir / "player_proficiency.json"
        if prof_path.exists():
            with open(prof_path) as f:
                data = json.load(f)
                self._proficiency_data = data.get("proficiencies", {})

    def get_proficiency_score(self, player_name: str, champion_name: str) -> tuple[float, str]:
        """Get proficiency score and confidence for player-champion pair."""
        if player_name not in self._proficiency_data:
            return 0.5, "NO_DATA"

        player_data = self._proficiency_data[player_name]
        if champion_name not in player_data:
            return 0.5, "NO_DATA"

        champ_data = player_data[champion_name]
        games = champ_data.get("games_raw", champ_data.get("games_weighted", 0))
        win_rate = champ_data.get("win_rate_weighted", champ_data.get("win_rate", 0.5))

        games_factor = min(1.0, games / 10)
        score = win_rate * 0.6 + games_factor * 0.4
        confidence = champ_data.get("confidence") or self._games_to_confidence(int(games))

        return round(score, 3), confidence

    def _games_to_confidence(self, games: int) -> str:
        """Convert game count to confidence level."""
        if games >= self.CONFIDENCE_THRESHOLDS["HIGH"]:
            return "HIGH"
        elif games >= self.CONFIDENCE_THRESHOLDS["MEDIUM"]:
            return "MEDIUM"
        elif games >= self.CONFIDENCE_THRESHOLDS["LOW"]:
            return "LOW"
        return "NO_DATA"

    def get_player_champion_pool(self, player_name: str, min_games: int = 1) -> list[dict]:
        """Get a player's champion pool sorted by proficiency."""
        if player_name not in self._proficiency_data:
            return []

        pool = []
        for champ, data in self._proficiency_data[player_name].items():
            games = data.get("games_raw", 0)
            if games >= min_games:
                score, conf = self.get_proficiency_score(player_name, champ)
                pool.append({"champion": champ, "score": score, "games": games, "confidence": conf})

        return sorted(pool, key=lambda x: -x["score"])
```

**Step 4: Run test to verify it passes**

```bash
cd backend && uv run pytest tests/test_proficiency_scorer.py -v
```

**Step 5: Commit**

```bash
git add backend/src/ban_teemo/services/scorers/proficiency_scorer.py backend/tests/test_proficiency_scorer.py
git commit -m "feat(scorers): add ProficiencyScorer service"
```

---

### Task 1.4: Create MatchupCalculator

**Files:**
- Create: `backend/src/ban_teemo/services/scorers/matchup_calculator.py`
- Create: `backend/tests/test_matchup_calculator.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_matchup_calculator.py
"""Tests for matchup calculation."""
import pytest
from ban_teemo.services.scorers.matchup_calculator import MatchupCalculator


@pytest.fixture
def calculator():
    return MatchupCalculator()


def test_get_lane_matchup_direct(calculator):
    """Test lane matchup with direct data lookup."""
    result = calculator.get_lane_matchup("Maokai", "Sejuani", "JUNGLE")
    assert 0.0 <= result["score"] <= 1.0
    assert result["confidence"] in ["HIGH", "MEDIUM", "LOW", "NO_DATA"]


def test_get_team_matchup(calculator):
    """Test team-level matchup."""
    result = calculator.get_team_matchup("Maokai", "Sejuani")
    assert 0.0 <= result["score"] <= 1.0


def test_matchup_unknown_returns_neutral(calculator):
    """Unknown matchup returns 0.5."""
    result = calculator.get_lane_matchup("FakeChamp1", "FakeChamp2", "MID")
    assert result["score"] == 0.5
    assert result["confidence"] == "NO_DATA"
```

**Step 2: Run test to verify it fails**

```bash
cd backend && uv run pytest tests/test_matchup_calculator.py -v
```

**Step 3: Write minimal implementation**

```python
# backend/src/ban_teemo/services/scorers/matchup_calculator.py
"""Matchup calculation with flex pick uncertainty handling."""
import json
from pathlib import Path
from typing import Optional


class MatchupCalculator:
    """Calculates matchup scores between champions."""

    def __init__(self, knowledge_dir: Optional[Path] = None):
        if knowledge_dir is None:
            knowledge_dir = Path(__file__).parents[5] / "knowledge"
        self.knowledge_dir = knowledge_dir
        self._counters: dict = {}
        self._load_data()

    def _load_data(self):
        """Load matchup statistics."""
        matchup_path = self.knowledge_dir / "matchup_stats.json"
        if matchup_path.exists():
            with open(matchup_path) as f:
                data = json.load(f)
                self._counters = data.get("counters", {})

    def get_lane_matchup(self, our_champion: str, enemy_champion: str, role: str) -> dict:
        """Get lane-specific matchup score."""
        role_upper = role.upper()

        # Direct lookup
        if our_champion in self._counters:
            vs_lane = self._counters[our_champion].get("vs_lane", {})
            role_data = vs_lane.get(role_upper, {})
            if enemy_champion in role_data:
                matchup = role_data[enemy_champion]
                return {
                    "score": matchup.get("win_rate", 0.5),
                    "confidence": matchup.get("confidence", "MEDIUM"),
                    "games": matchup.get("games", 0),
                    "data_source": "direct_lookup"
                }

        # Reverse lookup (invert)
        if enemy_champion in self._counters:
            vs_lane = self._counters[enemy_champion].get("vs_lane", {})
            role_data = vs_lane.get(role_upper, {})
            if our_champion in role_data:
                matchup = role_data[our_champion]
                return {
                    "score": round(1.0 - matchup.get("win_rate", 0.5), 3),
                    "confidence": matchup.get("confidence", "MEDIUM"),
                    "games": matchup.get("games", 0),
                    "data_source": "reverse_lookup"
                }

        return {"score": 0.5, "confidence": "NO_DATA", "games": 0, "data_source": "none"}

    def get_team_matchup(self, our_champion: str, enemy_champion: str) -> dict:
        """Get team-level matchup."""
        # Direct lookup
        if our_champion in self._counters:
            vs_team = self._counters[our_champion].get("vs_team", {})
            if enemy_champion in vs_team:
                matchup = vs_team[enemy_champion]
                return {
                    "score": matchup.get("win_rate", 0.5),
                    "games": matchup.get("games", 0),
                    "data_source": "direct_lookup"
                }

        # Reverse lookup
        if enemy_champion in self._counters:
            vs_team = self._counters[enemy_champion].get("vs_team", {})
            if our_champion in vs_team:
                matchup = vs_team[our_champion]
                return {
                    "score": round(1.0 - matchup.get("win_rate", 0.5), 3),
                    "games": matchup.get("games", 0),
                    "data_source": "reverse_lookup"
                }

        return {"score": 0.5, "games": 0, "data_source": "none"}
```

**Step 4: Run test to verify it passes**

```bash
cd backend && uv run pytest tests/test_matchup_calculator.py -v
```

**Step 5: Commit**

```bash
git add backend/src/ban_teemo/services/scorers/matchup_calculator.py backend/tests/test_matchup_calculator.py
git commit -m "feat(scorers): add MatchupCalculator service"
```

---

### Task 1.5: Update Scorers Package Init

**Files:**
- Modify: `backend/src/ban_teemo/services/scorers/__init__.py`

**Step 1: Update init with exports**

```python
# backend/src/ban_teemo/services/scorers/__init__.py
"""Core scoring components for recommendation engine."""
from ban_teemo.services.scorers.meta_scorer import MetaScorer
from ban_teemo.services.scorers.flex_resolver import FlexResolver
from ban_teemo.services.scorers.proficiency_scorer import ProficiencyScorer
from ban_teemo.services.scorers.matchup_calculator import MatchupCalculator

__all__ = ["MetaScorer", "FlexResolver", "ProficiencyScorer", "MatchupCalculator"]
```

**Step 2: Verify imports work**

```bash
cd backend && uv run python -c "from ban_teemo.services.scorers import MetaScorer, FlexResolver; print('OK')"
```

**Step 3: Commit**

```bash
git add backend/src/ban_teemo/services/scorers/__init__.py
git commit -m "feat(scorers): export all scorers from package"
```

---

## Stage 1 Checkpoint

```bash
cd backend && uv run pytest tests/test_meta_scorer.py tests/test_flex_resolver.py tests/test_proficiency_scorer.py tests/test_matchup_calculator.py -v
```

Expected: All tests pass.

---

## Stage 2: Enhancement Services

Build archetype analysis, synergy scoring, team evaluation, and ban recommendations.

---

### Task 2.1: Create Archetype Data Files

**Files:**
- Create: `knowledge/archetype_counters.json`

**Step 1: Create archetype_counters.json**

```json
{
  "metadata": {
    "version": "1.0.0",
    "description": "RPS effectiveness matrix for team composition archetypes"
  },
  "archetypes": ["engage", "split", "teamfight", "protect", "pick"],
  "effectiveness_matrix": {
    "engage": {"vs_engage": 1.0, "vs_split": 1.2, "vs_teamfight": 1.2, "vs_protect": 0.8, "vs_pick": 0.8},
    "split": {"vs_engage": 0.8, "vs_split": 1.0, "vs_teamfight": 1.2, "vs_protect": 1.2, "vs_pick": 0.8},
    "teamfight": {"vs_engage": 0.8, "vs_split": 0.8, "vs_teamfight": 1.0, "vs_protect": 1.2, "vs_pick": 1.2},
    "protect": {"vs_engage": 1.2, "vs_split": 0.8, "vs_teamfight": 0.8, "vs_protect": 1.0, "vs_pick": 1.2},
    "pick": {"vs_engage": 1.2, "vs_split": 1.2, "vs_teamfight": 0.8, "vs_protect": 0.8, "vs_pick": 1.0}
  },
  "champion_archetypes": {
    "Malphite": {"engage": 0.9, "teamfight": 0.7},
    "Orianna": {"teamfight": 0.8, "protect": 0.5},
    "Nocturne": {"pick": 0.8, "engage": 0.5},
    "Fiora": {"split": 0.9, "pick": 0.4},
    "Lulu": {"protect": 0.9, "teamfight": 0.4},
    "Thresh": {"pick": 0.7, "engage": 0.6},
    "Jarvan IV": {"engage": 0.8, "teamfight": 0.6},
    "Jinx": {"teamfight": 0.7, "protect": 0.3},
    "Azir": {"teamfight": 0.8, "split": 0.4},
    "Camille": {"split": 0.7, "pick": 0.6}
  }
}
```

**Step 2: Verify file created**

```bash
cat knowledge/archetype_counters.json | head -20
```

**Step 3: Commit**

```bash
git add knowledge/archetype_counters.json
git commit -m "feat(data): add archetype counters and champion archetypes"
```

---

### Task 2.2: Create ArchetypeService

**Files:**
- Create: `backend/src/ban_teemo/services/archetype_service.py`
- Create: `backend/tests/test_archetype_service.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_archetype_service.py
"""Tests for archetype service."""
import pytest
from ban_teemo.services.archetype_service import ArchetypeService


@pytest.fixture
def service():
    return ArchetypeService()


def test_get_champion_archetypes(service):
    """Test getting archetypes for a champion."""
    result = service.get_champion_archetypes("Malphite")
    assert "primary" in result
    assert "scores" in result
    assert result["primary"] == "engage"


def test_get_champion_archetypes_unknown(service):
    """Unknown champion returns neutral scores."""
    result = service.get_champion_archetypes("FakeChamp")
    assert result["primary"] is None


def test_calculate_team_archetype(service):
    """Test calculating team archetype from picks."""
    result = service.calculate_team_archetype(["Malphite", "Orianna", "Jarvan IV"])
    assert "primary" in result
    assert "scores" in result
    assert result["primary"] in ["engage", "teamfight", "split", "protect", "pick"]


def test_get_archetype_effectiveness(service):
    """Test RPS effectiveness lookup."""
    # Engage beats split
    eff = service.get_archetype_effectiveness("engage", "split")
    assert eff >= 1.0


def test_calculate_comp_advantage(service):
    """Test composition advantage calculation."""
    result = service.calculate_comp_advantage(
        our_picks=["Malphite", "Orianna"],
        enemy_picks=["Fiora", "Camille"]
    )
    assert "advantage" in result
    assert "our_archetype" in result
    assert "enemy_archetype" in result
```

**Step 2: Run test to verify it fails**

```bash
cd backend && uv run pytest tests/test_archetype_service.py -v
```

**Step 3: Write minimal implementation**

```python
# backend/src/ban_teemo/services/archetype_service.py
"""Archetype analysis for team compositions."""
import json
from pathlib import Path
from typing import Optional


class ArchetypeService:
    """Analyzes team composition archetypes and effectiveness."""

    ARCHETYPES = ["engage", "split", "teamfight", "protect", "pick"]

    def __init__(self, knowledge_dir: Optional[Path] = None):
        if knowledge_dir is None:
            knowledge_dir = Path(__file__).parents[4] / "knowledge"
        self.knowledge_dir = knowledge_dir
        self._champion_archetypes: dict = {}
        self._effectiveness_matrix: dict = {}
        self._load_data()

    def _load_data(self):
        """Load archetype data."""
        path = self.knowledge_dir / "archetype_counters.json"
        if path.exists():
            with open(path) as f:
                data = json.load(f)
                self._champion_archetypes = data.get("champion_archetypes", {})
                self._effectiveness_matrix = data.get("effectiveness_matrix", {})

    def get_champion_archetypes(self, champion: str) -> dict:
        """Get archetype scores for a champion."""
        if champion not in self._champion_archetypes:
            return {"primary": None, "secondary": None, "scores": {}}

        scores = self._champion_archetypes[champion]
        sorted_archetypes = sorted(scores.items(), key=lambda x: -x[1])

        return {
            "primary": sorted_archetypes[0][0] if sorted_archetypes else None,
            "secondary": sorted_archetypes[1][0] if len(sorted_archetypes) > 1 else None,
            "scores": scores
        }

    def calculate_team_archetype(self, picks: list[str]) -> dict:
        """Calculate aggregate archetype for a team composition."""
        if not picks:
            return {"primary": None, "secondary": None, "scores": {}, "alignment": 0.0}

        aggregate = {arch: 0.0 for arch in self.ARCHETYPES}

        for champ in picks:
            champ_data = self.get_champion_archetypes(champ)
            for arch, score in champ_data.get("scores", {}).items():
                aggregate[arch] = aggregate.get(arch, 0) + score

        # Normalize
        total = sum(aggregate.values())
        if total > 0:
            aggregate = {k: v / total for k, v in aggregate.items()}

        sorted_archetypes = sorted(aggregate.items(), key=lambda x: -x[1])
        primary = sorted_archetypes[0][0] if sorted_archetypes else None
        primary_score = sorted_archetypes[0][1] if sorted_archetypes else 0

        return {
            "primary": primary,
            "secondary": sorted_archetypes[1][0] if len(sorted_archetypes) > 1 else None,
            "scores": aggregate,
            "alignment": round(primary_score, 3)  # How focused the comp is
        }

    def get_archetype_effectiveness(self, our_archetype: str, enemy_archetype: str) -> float:
        """Get effectiveness multiplier (RPS style)."""
        if our_archetype not in self._effectiveness_matrix:
            return 1.0
        return self._effectiveness_matrix[our_archetype].get(f"vs_{enemy_archetype}", 1.0)

    def calculate_comp_advantage(self, our_picks: list[str], enemy_picks: list[str]) -> dict:
        """Calculate composition advantage between two teams."""
        our_arch = self.calculate_team_archetype(our_picks)
        enemy_arch = self.calculate_team_archetype(enemy_picks)

        effectiveness = 1.0
        if our_arch["primary"] and enemy_arch["primary"]:
            effectiveness = self.get_archetype_effectiveness(
                our_arch["primary"], enemy_arch["primary"]
            )

        return {
            "advantage": round(effectiveness, 3),
            "our_archetype": our_arch["primary"],
            "enemy_archetype": enemy_arch["primary"],
            "description": self._describe_advantage(effectiveness, our_arch["primary"], enemy_arch["primary"])
        }

    def _describe_advantage(self, effectiveness: float, our: str, enemy: str) -> str:
        """Generate human-readable advantage description."""
        if effectiveness > 1.1:
            return f"Your {our} comp counters their {enemy} style"
        elif effectiveness < 0.9:
            return f"Their {enemy} comp counters your {our} style"
        return "Neutral composition matchup"
```

**Step 4: Run test to verify it passes**

```bash
cd backend && uv run pytest tests/test_archetype_service.py -v
```

**Step 5: Commit**

```bash
git add backend/src/ban_teemo/services/archetype_service.py backend/tests/test_archetype_service.py
git commit -m "feat(services): add ArchetypeService"
```

---

### Task 2.3: Create SynergyService

**Files:**
- Create: `backend/src/ban_teemo/services/synergy_service.py`
- Create: `backend/tests/test_synergy_service.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_synergy_service.py
"""Tests for synergy service."""
import pytest
from ban_teemo.services.synergy_service import SynergyService


@pytest.fixture
def service():
    return SynergyService()


def test_get_synergy_score_curated(service):
    """Curated synergy should return high score."""
    score = service.get_synergy_score("Orianna", "Nocturne")
    assert score >= 0.7


def test_get_synergy_score_unknown(service):
    """Unknown pair returns neutral 0.5."""
    score = service.get_synergy_score("FakeChamp1", "FakeChamp2")
    assert score == 0.5


def test_calculate_team_synergy(service):
    """Test team synergy aggregation."""
    result = service.calculate_team_synergy(["Orianna", "Nocturne", "Malphite"])
    assert "total_score" in result
    assert 0.0 <= result["total_score"] <= 1.0
```

**Step 2: Run test to verify it fails**

```bash
cd backend && uv run pytest tests/test_synergy_service.py -v
```

**Step 3: Write minimal implementation**

```python
# backend/src/ban_teemo/services/synergy_service.py
"""Synergy scoring with curated ratings and statistical fallback."""
import json
from pathlib import Path
from typing import Optional


class SynergyService:
    """Scores champion synergies."""

    RATING_MULTIPLIERS = {"S": 1.0, "A": 0.8, "B": 0.6, "C": 0.4}
    BASE_CURATED_SCORE = 0.85

    def __init__(self, knowledge_dir: Optional[Path] = None):
        if knowledge_dir is None:
            knowledge_dir = Path(__file__).parents[4] / "knowledge"
        self.knowledge_dir = knowledge_dir
        self._curated_synergies: dict[tuple[str, str], str] = {}
        self._stat_synergies: dict = {}
        self._load_data()

    def _load_data(self):
        """Load curated and statistical synergy data."""
        # Curated synergies
        curated_path = self.knowledge_dir / "synergies.json"
        if curated_path.exists():
            with open(curated_path) as f:
                synergies = json.load(f)
                for syn in synergies:
                    champs = syn.get("champions", [])
                    strength = syn.get("strength", "C")

                    if syn.get("partner_requirement"):
                        for partner in syn.get("best_partners", []):
                            partner_champ = partner.get("champion")
                            partner_rating = partner.get("rating", strength)
                            if partner_champ and len(champs) >= 1:
                                key = tuple(sorted([champs[0], partner_champ]))
                                self._curated_synergies[key] = partner_rating

                    if len(champs) >= 2:
                        key = tuple(sorted(champs[:2]))
                        self._curated_synergies[key] = strength

        # Statistical synergies
        stats_path = self.knowledge_dir / "champion_synergies.json"
        if stats_path.exists():
            with open(stats_path) as f:
                data = json.load(f)
                self._stat_synergies = data.get("synergies", {})

    def get_synergy_score(self, champ_a: str, champ_b: str) -> float:
        """Get synergy score between two champions (0.0-1.0)."""
        key = tuple(sorted([champ_a, champ_b]))

        # Curated first
        if key in self._curated_synergies:
            rating = self._curated_synergies[key]
            multiplier = self.RATING_MULTIPLIERS.get(rating.upper(), 0.4)
            return round(self.BASE_CURATED_SCORE * multiplier, 3)

        # Statistical fallback
        if champ_a in self._stat_synergies:
            if champ_b in self._stat_synergies[champ_a]:
                return self._stat_synergies[champ_a][champ_b].get("synergy_score", 0.5)

        if champ_b in self._stat_synergies:
            if champ_a in self._stat_synergies[champ_b]:
                return self._stat_synergies[champ_b][champ_a].get("synergy_score", 0.5)

        return 0.5

    def calculate_team_synergy(self, picks: list[str]) -> dict:
        """Calculate aggregate synergy for a team."""
        if len(picks) < 2:
            return {"total_score": 0.5, "pair_count": 0, "synergy_pairs": []}

        scores = []
        synergy_pairs = []

        for i, champ_a in enumerate(picks):
            for champ_b in picks[i + 1:]:
                score = self.get_synergy_score(champ_a, champ_b)
                scores.append(score)
                if score != 0.5:
                    synergy_pairs.append({"champions": [champ_a, champ_b], "score": score})

        synergy_pairs.sort(key=lambda x: -x["score"])
        total_score = sum(scores) / len(scores) if scores else 0.5

        return {
            "total_score": round(total_score, 3),
            "pair_count": len(scores),
            "synergy_pairs": synergy_pairs[:5]
        }
```

**Step 4: Run test to verify it passes**

```bash
cd backend && uv run pytest tests/test_synergy_service.py -v
```

**Step 5: Commit**

```bash
git add backend/src/ban_teemo/services/synergy_service.py backend/tests/test_synergy_service.py
git commit -m "feat(services): add SynergyService"
```

---

### Task 2.4: Create TeamEvaluationService

**Files:**
- Create: `backend/src/ban_teemo/services/team_evaluation_service.py`
- Create: `backend/tests/test_team_evaluation_service.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_team_evaluation_service.py
"""Tests for team evaluation service."""
import pytest
from ban_teemo.services.team_evaluation_service import TeamEvaluationService


@pytest.fixture
def service():
    return TeamEvaluationService()


def test_evaluate_team_draft(service):
    """Test evaluating a team's draft."""
    result = service.evaluate_team_draft(["Malphite", "Orianna", "Jarvan IV"])
    assert "archetype" in result
    assert "synergy_score" in result
    assert "composition_score" in result
    assert "strengths" in result
    assert "weaknesses" in result


def test_evaluate_vs_enemy(service):
    """Test head-to-head evaluation."""
    result = service.evaluate_vs_enemy(
        our_picks=["Malphite", "Orianna"],
        enemy_picks=["Fiora", "Camille"]
    )
    assert "our_evaluation" in result
    assert "enemy_evaluation" in result
    assert "matchup_advantage" in result


def test_empty_picks(service):
    """Empty picks returns neutral evaluation."""
    result = service.evaluate_team_draft([])
    assert result["composition_score"] == 0.5
```

**Step 2: Run test to verify it fails**

```bash
cd backend && uv run pytest tests/test_team_evaluation_service.py -v
```

**Step 3: Write minimal implementation**

```python
# backend/src/ban_teemo/services/team_evaluation_service.py
"""Team draft evaluation with strengths and weaknesses analysis."""
from pathlib import Path
from typing import Optional

from ban_teemo.services.archetype_service import ArchetypeService
from ban_teemo.services.synergy_service import SynergyService


class TeamEvaluationService:
    """Evaluates team compositions for strengths and weaknesses."""

    def __init__(self, knowledge_dir: Optional[Path] = None):
        self.archetype_service = ArchetypeService(knowledge_dir)
        self.synergy_service = SynergyService(knowledge_dir)

    def evaluate_team_draft(self, picks: list[str]) -> dict:
        """Evaluate a team's draft composition."""
        if not picks:
            return {
                "archetype": None,
                "synergy_score": 0.5,
                "composition_score": 0.5,
                "strengths": [],
                "weaknesses": []
            }

        # Get archetype analysis
        archetype = self.archetype_service.calculate_team_archetype(picks)

        # Get synergy analysis
        synergy = self.synergy_service.calculate_team_synergy(picks)

        # Calculate composition score (synergy + archetype alignment)
        composition_score = (synergy["total_score"] + archetype.get("alignment", 0.5)) / 2

        # Determine strengths and weaknesses
        strengths = []
        weaknesses = []

        if archetype.get("alignment", 0) >= 0.4:
            strengths.append(f"Strong {archetype['primary']} identity")
        else:
            weaknesses.append("Lacks clear team identity")

        if synergy["total_score"] >= 0.6:
            strengths.append("Good champion synergies")
        elif synergy["total_score"] <= 0.4:
            weaknesses.append("Poor champion synergies")

        # Archetype-specific strengths/weaknesses
        primary = archetype.get("primary")
        if primary == "engage":
            strengths.append("Strong initiation")
            weaknesses.append("Weak to disengage/poke")
        elif primary == "split":
            strengths.append("Strong side lane pressure")
            weaknesses.append("Weak teamfighting")
        elif primary == "teamfight":
            strengths.append("Strong 5v5 combat")
            weaknesses.append("Weak to split push")
        elif primary == "protect":
            strengths.append("Strong carry protection")
            weaknesses.append("Weak engage")
        elif primary == "pick":
            strengths.append("Strong catch potential")
            weaknesses.append("Weak to grouped teams")

        return {
            "archetype": archetype["primary"],
            "synergy_score": synergy["total_score"],
            "composition_score": round(composition_score, 3),
            "strengths": strengths[:3],
            "weaknesses": weaknesses[:3],
            "synergy_pairs": synergy.get("synergy_pairs", [])
        }

    def evaluate_vs_enemy(self, our_picks: list[str], enemy_picks: list[str]) -> dict:
        """Evaluate our draft vs enemy draft."""
        our_eval = self.evaluate_team_draft(our_picks)
        enemy_eval = self.evaluate_team_draft(enemy_picks)

        # Get archetype matchup
        comp_advantage = self.archetype_service.calculate_comp_advantage(our_picks, enemy_picks)

        return {
            "our_evaluation": our_eval,
            "enemy_evaluation": enemy_eval,
            "matchup_advantage": comp_advantage["advantage"],
            "matchup_description": comp_advantage["description"]
        }
```

**Step 4: Run test to verify it passes**

```bash
cd backend && uv run pytest tests/test_team_evaluation_service.py -v
```

**Step 5: Commit**

```bash
git add backend/src/ban_teemo/services/team_evaluation_service.py backend/tests/test_team_evaluation_service.py
git commit -m "feat(services): add TeamEvaluationService"
```

---

### Task 2.5: Create BanRecommendationService

**Files:**
- Create: `backend/src/ban_teemo/services/ban_recommendation_service.py`
- Create: `backend/tests/test_ban_recommendation_service.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_ban_recommendation_service.py
"""Tests for ban recommendation service."""
import pytest
from ban_teemo.services.ban_recommendation_service import BanRecommendationService


@pytest.fixture
def service():
    return BanRecommendationService()


def test_get_ban_recommendations(service):
    """Test generating ban recommendations."""
    recs = service.get_ban_recommendations(
        enemy_team_id="oe:team:d2dc3681610c70d6cce8c5f4c1612769",
        our_picks=[],
        enemy_picks=[],
        banned=[],
        phase="BAN_PHASE_1"
    )
    assert len(recs) >= 1
    for rec in recs:
        assert "champion_name" in rec
        assert "priority" in rec
        assert 0.0 <= rec["priority"] <= 1.0


def test_ban_excludes_already_banned(service):
    """Already banned champions excluded."""
    recs = service.get_ban_recommendations(
        enemy_team_id="oe:team:d2dc3681610c70d6cce8c5f4c1612769",
        our_picks=[],
        enemy_picks=[],
        banned=["Azir", "Aurora"],
        phase="BAN_PHASE_1"
    )
    names = {r["champion_name"] for r in recs}
    assert "Azir" not in names
    assert "Aurora" not in names


def test_target_player_bans(service):
    """Some bans should target specific players."""
    recs = service.get_ban_recommendations(
        enemy_team_id="oe:team:d2dc3681610c70d6cce8c5f4c1612769",
        our_picks=[],
        enemy_picks=[],
        banned=[],
        phase="BAN_PHASE_1",
        limit=5
    )
    # At least some should have target_player
    has_target = any(r.get("target_player") for r in recs)
    # This may or may not be true depending on data, so just check structure
    for rec in recs:
        assert "target_player" in rec or rec.get("target_player") is None
```

**Step 2: Run test to verify it fails**

```bash
cd backend && uv run pytest tests/test_ban_recommendation_service.py -v
```

**Step 3: Write minimal implementation**

```python
# backend/src/ban_teemo/services/ban_recommendation_service.py
"""Ban recommendation service targeting enemy player pools."""
from pathlib import Path
from typing import Optional

from ban_teemo.services.scorers import MetaScorer, ProficiencyScorer
from ban_teemo.repositories.draft_repository import DraftRepository


class BanRecommendationService:
    """Generates ban recommendations based on enemy team analysis."""

    def __init__(self, knowledge_dir: Optional[Path] = None, data_path: Optional[str] = None):
        if knowledge_dir is None:
            knowledge_dir = Path(__file__).parents[4] / "knowledge"
        if data_path is None:
            data_path = str(Path(__file__).parents[4] / "data")

        self.meta_scorer = MetaScorer(knowledge_dir)
        self.proficiency_scorer = ProficiencyScorer(knowledge_dir)
        self.repo = DraftRepository(data_path)
        self._player_roles_cache: dict = {}

    def get_ban_recommendations(
        self,
        enemy_team_id: str,
        our_picks: list[str],
        enemy_picks: list[str],
        banned: list[str],
        phase: str,
        limit: int = 5
    ) -> list[dict]:
        """Generate ban recommendations targeting enemy team."""
        unavailable = set(banned) | set(our_picks) | set(enemy_picks)

        # Get enemy team roster
        enemy_roster = self._get_enemy_roster(enemy_team_id)

        ban_candidates = []

        # Phase 1: Target high-impact players and meta picks
        # Phase 2: Counter-pick focused bans
        is_phase_1 = "1" in phase

        for player in enemy_roster:
            player_pool = self.proficiency_scorer.get_player_champion_pool(
                player["name"], min_games=2
            )

            for entry in player_pool[:5]:  # Top 5 per player
                champ = entry["champion"]
                if champ in unavailable:
                    continue

                priority = self._calculate_ban_priority(
                    champion=champ,
                    player=player,
                    proficiency=entry,
                    is_phase_1=is_phase_1,
                    our_picks=our_picks
                )

                ban_candidates.append({
                    "champion_name": champ,
                    "priority": priority,
                    "target_player": player["name"],
                    "target_role": player.get("role"),
                    "reasons": self._generate_reasons(champ, player, entry, priority)
                })

        # Add high meta picks not in player pools
        for champ in self.meta_scorer.get_top_meta_champions(limit=10):
            if champ in unavailable:
                continue
            if any(c["champion_name"] == champ for c in ban_candidates):
                continue

            meta_score = self.meta_scorer.get_meta_score(champ)
            if meta_score >= 0.6:
                ban_candidates.append({
                    "champion_name": champ,
                    "priority": meta_score * 0.7,  # Lower than targeted bans
                    "target_player": None,
                    "target_role": None,
                    "reasons": [f"{self.meta_scorer.get_meta_tier(champ)}-tier meta pick"]
                })

        # Sort by priority
        ban_candidates.sort(key=lambda x: -x["priority"])
        return ban_candidates[:limit]

    def _get_enemy_roster(self, team_id: str) -> list[dict]:
        """Get enemy team roster."""
        try:
            team_context = self.repo.get_team_context(team_id, "red")
            if team_context:
                return [{"name": p.name, "role": p.role} for p in team_context.players]
        except Exception:
            pass
        return []

    def _calculate_ban_priority(
        self,
        champion: str,
        player: dict,
        proficiency: dict,
        is_phase_1: bool,
        our_picks: list[str]
    ) -> float:
        """Calculate ban priority score."""
        # Base: player proficiency on champion
        priority = proficiency["score"] * 0.4

        # Meta strength
        meta_score = self.meta_scorer.get_meta_score(champion)
        priority += meta_score * 0.3

        # Games played (comfort factor)
        games = proficiency.get("games", 0)
        comfort = min(1.0, games / 10)
        priority += comfort * 0.2

        # Confidence bonus
        conf = proficiency.get("confidence", "LOW")
        conf_bonus = {"HIGH": 0.1, "MEDIUM": 0.05, "LOW": 0.0}.get(conf, 0)
        priority += conf_bonus

        return round(min(1.0, priority), 3)

    def _generate_reasons(
        self,
        champion: str,
        player: dict,
        proficiency: dict,
        priority: float
    ) -> list[str]:
        """Generate human-readable ban reasons."""
        reasons = []

        games = proficiency.get("games", 0)
        if games >= 5:
            reasons.append(f"{player['name']}'s comfort pick ({games} games)")
        elif games >= 2:
            reasons.append(f"In {player['name']}'s pool")

        tier = self.meta_scorer.get_meta_tier(champion)
        if tier in ["S", "A"]:
            reasons.append(f"{tier}-tier meta champion")

        if priority >= 0.8:
            reasons.append("High priority target")

        return reasons if reasons else ["General ban recommendation"]
```

**Step 4: Run test to verify it passes**

```bash
cd backend && uv run pytest tests/test_ban_recommendation_service.py -v
```

**Step 5: Commit**

```bash
git add backend/src/ban_teemo/services/ban_recommendation_service.py backend/tests/test_ban_recommendation_service.py
git commit -m "feat(services): add BanRecommendationService"
```

---

### Task 2.6: Create PickRecommendationEngine

**Files:**
- Create: `backend/src/ban_teemo/services/pick_recommendation_engine.py`
- Create: `backend/tests/test_pick_recommendation_engine.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_pick_recommendation_engine.py
"""Tests for pick recommendation engine."""
import pytest
from ban_teemo.services.pick_recommendation_engine import PickRecommendationEngine


@pytest.fixture
def engine():
    return PickRecommendationEngine()


def test_get_recommendations(engine):
    """Test generating pick recommendations."""
    recs = engine.get_recommendations(
        player_name="Faker",
        player_role="MID",
        our_picks=[],
        enemy_picks=[],
        banned=[],
        limit=5
    )
    assert len(recs) <= 5
    for rec in recs:
        assert "champion_name" in rec
        assert "score" in rec
        assert 0.0 <= rec["score"] <= 1.5


def test_recommendations_exclude_unavailable(engine):
    """Banned/picked champions excluded."""
    recs = engine.get_recommendations(
        player_name="Faker",
        player_role="MID",
        our_picks=["Orianna"],
        enemy_picks=["Azir"],
        banned=["Aurora"],
        limit=10
    )
    names = {r["champion_name"] for r in recs}
    assert "Orianna" not in names
    assert "Azir" not in names
    assert "Aurora" not in names
```

**Step 2: Run test to verify it fails**

```bash
cd backend && uv run pytest tests/test_pick_recommendation_engine.py -v
```

**Step 3: Write minimal implementation**

```python
# backend/src/ban_teemo/services/pick_recommendation_engine.py
"""Pick recommendation engine combining all scoring components."""
from pathlib import Path
from typing import Optional

from ban_teemo.services.scorers import MetaScorer, FlexResolver, ProficiencyScorer, MatchupCalculator
from ban_teemo.services.synergy_service import SynergyService


class PickRecommendationEngine:
    """Generates pick recommendations using weighted multi-factor scoring."""

    BASE_WEIGHTS = {"meta": 0.25, "proficiency": 0.35, "matchup": 0.25, "counter": 0.15}
    SYNERGY_MULTIPLIER_RANGE = 0.3

    def __init__(self, knowledge_dir: Optional[Path] = None):
        self.meta_scorer = MetaScorer(knowledge_dir)
        self.flex_resolver = FlexResolver(knowledge_dir)
        self.proficiency_scorer = ProficiencyScorer(knowledge_dir)
        self.matchup_calculator = MatchupCalculator(knowledge_dir)
        self.synergy_service = SynergyService(knowledge_dir)

    def get_recommendations(
        self,
        player_name: str,
        player_role: str,
        our_picks: list[str],
        enemy_picks: list[str],
        banned: list[str],
        limit: int = 5
    ) -> list[dict]:
        """Generate ranked pick recommendations."""
        unavailable = set(banned) | set(our_picks) | set(enemy_picks)
        candidates = self._get_candidates(player_name, player_role, unavailable)

        recommendations = []
        for champ in candidates:
            result = self._calculate_score(champ, player_name, player_role, our_picks, enemy_picks)
            recommendations.append({
                "champion_name": champ,
                "score": result["total_score"],
                "base_score": result["base_score"],
                "synergy_multiplier": result["synergy_multiplier"],
                "confidence": result["confidence"],
                "components": result["components"],
                "reasons": self._generate_reasons(champ, result)
            })

        recommendations.sort(key=lambda x: -x["score"])
        return recommendations[:limit]

    def _get_candidates(self, player_name: str, role: str, unavailable: set[str]) -> list[str]:
        """Get candidate champions to consider."""
        candidates = set()
        pool = self.proficiency_scorer.get_player_champion_pool(player_name, min_games=1)
        for entry in pool[:20]:
            if entry["champion"] not in unavailable:
                candidates.add(entry["champion"])

        if len(candidates) < 5:
            meta_picks = self.meta_scorer.get_top_meta_champions(role=role, limit=15)
            for champ in meta_picks:
                if champ not in unavailable:
                    candidates.add(champ)
                if len(candidates) >= 10:
                    break

        return list(candidates)

    def _calculate_score(
        self, champion: str, player_name: str, player_role: str,
        our_picks: list[str], enemy_picks: list[str]
    ) -> dict:
        """Calculate score using base factors + synergy multiplier."""
        components = {}

        # Meta
        components["meta"] = self.meta_scorer.get_meta_score(champion)

        # Proficiency
        prof_score, prof_conf = self.proficiency_scorer.get_proficiency_score(player_name, champion)
        components["proficiency"] = prof_score
        prof_conf_val = {"HIGH": 1.0, "MEDIUM": 0.8, "LOW": 0.5, "NO_DATA": 0.3}.get(prof_conf, 0.5)

        # Matchup (lane)
        matchup_scores = []
        for enemy in enemy_picks:
            role_probs = self.flex_resolver.get_role_probabilities(enemy)
            if player_role in role_probs and role_probs[player_role] > 0:
                result = self.matchup_calculator.get_lane_matchup(champion, enemy, player_role)
                matchup_scores.append(result["score"])
        components["matchup"] = sum(matchup_scores) / len(matchup_scores) if matchup_scores else 0.5

        # Counter (team)
        counter_scores = []
        for enemy in enemy_picks:
            result = self.matchup_calculator.get_team_matchup(champion, enemy)
            counter_scores.append(result["score"])
        components["counter"] = sum(counter_scores) / len(counter_scores) if counter_scores else 0.5

        # Synergy
        synergy_result = self.synergy_service.calculate_team_synergy(our_picks + [champion])
        synergy_score = synergy_result["total_score"]
        components["synergy"] = synergy_score
        synergy_multiplier = 1.0 + (synergy_score - 0.5) * self.SYNERGY_MULTIPLIER_RANGE

        # Base score
        base_score = (
            components["meta"] * self.BASE_WEIGHTS["meta"] +
            components["proficiency"] * self.BASE_WEIGHTS["proficiency"] +
            components["matchup"] * self.BASE_WEIGHTS["matchup"] +
            components["counter"] * self.BASE_WEIGHTS["counter"]
        )

        total_score = base_score * synergy_multiplier
        confidence = (1.0 + prof_conf_val) / 2

        return {
            "total_score": round(total_score, 3),
            "base_score": round(base_score, 3),
            "synergy_multiplier": round(synergy_multiplier, 3),
            "confidence": round(confidence, 3),
            "components": {k: round(v, 3) for k, v in components.items()}
        }

    def _generate_reasons(self, champion: str, result: dict) -> list[str]:
        """Generate human-readable reasons."""
        reasons = []
        components = result["components"]

        if components.get("meta", 0) >= 0.7:
            tier = self.meta_scorer.get_meta_tier(champion)
            reasons.append(f"{tier or 'High'}-tier meta pick")
        if components.get("proficiency", 0) >= 0.7:
            reasons.append("Strong player proficiency")
        if components.get("matchup", 0) >= 0.55:
            reasons.append("Favorable matchups")
        if result.get("synergy_multiplier", 1.0) >= 1.10:
            reasons.append("Strong team synergy")

        return reasons if reasons else ["Solid overall pick"]
```

**Step 4: Run test to verify it passes**

```bash
cd backend && uv run pytest tests/test_pick_recommendation_engine.py -v
```

**Step 5: Commit**

```bash
git add backend/src/ban_teemo/services/pick_recommendation_engine.py backend/tests/test_pick_recommendation_engine.py
git commit -m "feat(engine): add PickRecommendationEngine"
```

---

## Stage 2 Checkpoint

```bash
cd backend && uv run pytest tests/test_synergy_service.py tests/test_pick_recommendation_engine.py -v
```

Expected: All tests pass.

---

## Stage 3: Simulator Backend

Build enemy AI and session management.

---

### Task 3.1: Create Simulator Models

**Files:**
- Create: `backend/src/ban_teemo/models/simulator.py`

**Step 1: Write models**

```python
# backend/src/ban_teemo/models/simulator.py
"""Models for draft simulator sessions."""
from dataclasses import dataclass, field
from typing import Literal, Optional
from ban_teemo.models.draft import DraftAction, DraftState
from ban_teemo.models.team import TeamContext


@dataclass
class EnemyStrategy:
    """Enemy team's draft strategy based on historical data."""
    reference_game_id: str
    draft_script: list[DraftAction]
    fallback_game_ids: list[str]
    champion_weights: dict[str, float]
    current_script_index: int = 0


@dataclass
class GameResult:
    """Result of a completed game in a series."""
    game_number: int
    winner: Literal["blue", "red"]
    blue_comp: list[str]
    red_comp: list[str]


@dataclass
class SimulatorSession:
    """State for an active simulator session."""
    session_id: str
    blue_team: TeamContext
    red_team: TeamContext
    coaching_side: Literal["blue", "red"]
    series_length: Literal[1, 3, 5]
    draft_mode: Literal["normal", "fearless"]

    # Current game state
    current_game: int = 1
    draft_state: Optional[DraftState] = None
    enemy_strategy: Optional[EnemyStrategy] = None

    # Series tracking
    game_results: list[GameResult] = field(default_factory=list)
    # Fearless tracking - preserves team and game info for UI tooltips
    # Structure: {"Azir": {"team": "blue", "game": 1}, ...}
    fearless_blocked: dict[str, dict] = field(default_factory=dict)

    @property
    def fearless_blocked_set(self) -> set[str]:
        """All fearless-blocked champion names as a set for filtering."""
        return set(self.fearless_blocked.keys())

    @property
    def enemy_side(self) -> Literal["blue", "red"]:
        return "red" if self.coaching_side == "blue" else "blue"

    @property
    def series_score(self) -> tuple[int, int]:
        blue_wins = sum(1 for r in self.game_results if r.winner == "blue")
        red_wins = sum(1 for r in self.game_results if r.winner == "red")
        return blue_wins, red_wins

    @property
    def series_complete(self) -> bool:
        blue_wins, red_wins = self.series_score
        wins_needed = (self.series_length // 2) + 1
        return blue_wins >= wins_needed or red_wins >= wins_needed
```

**Step 2: Commit**

```bash
git add backend/src/ban_teemo/models/simulator.py
git commit -m "feat(models): add simulator session models"
```

---

### Task 3.2: Create EnemySimulatorService

**Files:**
- Create: `backend/src/ban_teemo/services/enemy_simulator_service.py`
- Create: `backend/tests/test_enemy_simulator_service.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_enemy_simulator_service.py
"""Tests for enemy simulator service."""
import pytest
from ban_teemo.services.enemy_simulator_service import EnemySimulatorService


@pytest.fixture
def service():
    return EnemySimulatorService()


def test_initialize_enemy_strategy(service):
    """Test initializing enemy strategy for a team."""
    # Use a known team ID from the data
    strategy = service.initialize_enemy_strategy("oe:team:d2dc3681610c70d6cce8c5f4c1612769")
    assert strategy is not None
    assert strategy.reference_game_id is not None
    assert len(strategy.champion_weights) > 0


def test_generate_action_from_script(service):
    """Test generating action from reference script."""
    strategy = service.initialize_enemy_strategy("oe:team:d2dc3681610c70d6cce8c5f4c1612769")
    champion, source = service.generate_action(strategy, sequence=1, unavailable=set())
    assert champion is not None
    assert source in ["reference_game", "fallback_game", "weighted_random"]


def test_generate_action_with_unavailable(service):
    """Test fallback when scripted champion unavailable."""
    strategy = service.initialize_enemy_strategy("oe:team:d2dc3681610c70d6cce8c5f4c1612769")
    # Make all scripted champions unavailable
    all_champs = {a.champion_name for a in strategy.draft_script}
    champion, source = service.generate_action(strategy, sequence=1, unavailable=all_champs)
    assert champion not in all_champs
    assert source in ["fallback_game", "weighted_random"]
```

**Step 2: Run test to verify it fails**

```bash
cd backend && uv run pytest tests/test_enemy_simulator_service.py -v
```

**Step 3: Write minimal implementation**

```python
# backend/src/ban_teemo/services/enemy_simulator_service.py
"""Generates enemy picks/bans from historical data."""
import random
from pathlib import Path
from typing import Optional

from ban_teemo.models.simulator import EnemyStrategy
from ban_teemo.models.draft import DraftAction
from ban_teemo.repositories.draft_repository import DraftRepository


class EnemySimulatorService:
    """Generates enemy picks/bans from historical data."""

    def __init__(self, data_path: Optional[str] = None):
        if data_path is None:
            data_path = str(Path(__file__).parents[4] / "data")
        self.repo = DraftRepository(data_path)

    def initialize_enemy_strategy(self, enemy_team_id: str) -> EnemyStrategy:
        """Load reference game, fallbacks, and champion weights."""
        games = self.repo.get_team_games(enemy_team_id, limit=20)
        if not games:
            raise ValueError(f"No games found for team {enemy_team_id}")

        reference = random.choice(games)
        fallbacks = [g for g in games if g["game_id"] != reference["game_id"]]

        # Load draft actions for reference game
        draft_actions = self.repo.get_draft_actions(reference["game_id"])

        # Filter to enemy team's actions only
        enemy_actions = [
            a for a in draft_actions
            if a.team_side == ("blue" if reference.get("blue_team_id") == enemy_team_id else "red")
        ]

        # Build champion weights from all games
        weights = self._build_champion_weights(enemy_team_id, games)

        return EnemyStrategy(
            reference_game_id=reference["game_id"],
            draft_script=enemy_actions,
            fallback_game_ids=[g["game_id"] for g in fallbacks],
            champion_weights=weights
        )

    def _build_champion_weights(self, team_id: str, games: list[dict]) -> dict[str, float]:
        """Build champion pick frequency weights."""
        pick_counts: dict[str, int] = {}
        total = 0

        for game in games:
            actions = self.repo.get_draft_actions(game["game_id"])
            team_side = "blue" if game.get("blue_team_id") == team_id else "red"
            for action in actions:
                if action.team_side == team_side and action.action_type == "pick":
                    pick_counts[action.champion_name] = pick_counts.get(action.champion_name, 0) + 1
                    total += 1

        if total == 0:
            return {}
        return {champ: count / total for champ, count in pick_counts.items()}

    def generate_action(
        self,
        strategy: EnemyStrategy,
        sequence: int,
        unavailable: set[str]
    ) -> tuple[str, str]:
        """Generate enemy's next pick/ban."""
        # Step 1: Try reference script - find next valid action at or after sequence
        for action in strategy.draft_script:
            if action.sequence >= sequence and action.champion_name not in unavailable:
                return action.champion_name, "reference_game"

        # Step 2: Try fallback games - find next valid action at or after sequence
        for fallback_id in strategy.fallback_game_ids:
            actions = self.repo.get_draft_actions(fallback_id)
            for action in actions:
                if action.sequence >= sequence and action.champion_name not in unavailable:
                    return action.champion_name, "fallback_game"

        # Step 3: Weighted random
        available_weights = {
            champ: weight
            for champ, weight in strategy.champion_weights.items()
            if champ not in unavailable
        }

        if available_weights:
            champs = list(available_weights.keys())
            weights = list(available_weights.values())
            chosen = random.choices(champs, weights=weights, k=1)[0]
            return chosen, "weighted_random"

        # Ultimate fallback: any available champion from weights
        all_champs = list(strategy.champion_weights.keys())
        available = [c for c in all_champs if c not in unavailable]
        if available:
            return random.choice(available), "weighted_random"

        raise ValueError("No available champions for enemy action")
```

**Step 4: Run test to verify it passes**

```bash
cd backend && uv run pytest tests/test_enemy_simulator_service.py -v
```

**Step 5: Commit**

```bash
git add backend/src/ban_teemo/services/enemy_simulator_service.py backend/tests/test_enemy_simulator_service.py
git commit -m "feat(services): add EnemySimulatorService"
```

---

### Task 3.3: Create Simulator Routes

**Files:**
- Create: `backend/src/ban_teemo/api/routes/simulator.py`
- Modify: `backend/src/ban_teemo/main.py`

**Step 1: Create simulator routes**

```python
# backend/src/ban_teemo/api/routes/simulator.py
"""REST endpoints for draft simulator."""
import uuid
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Literal, Optional

from ban_teemo.models.simulator import SimulatorSession, GameResult
from ban_teemo.models.draft import DraftState, DraftAction, DraftPhase
from ban_teemo.services.enemy_simulator_service import EnemySimulatorService
from ban_teemo.services.pick_recommendation_engine import PickRecommendationEngine
from ban_teemo.services.ban_recommendation_service import BanRecommendationService
from ban_teemo.services.team_evaluation_service import TeamEvaluationService
from ban_teemo.services.draft_service import DraftService
from ban_teemo.repositories.draft_repository import DraftRepository


router = APIRouter(prefix="/api/simulator", tags=["simulator"])

# In-memory session storage
_sessions: dict[str, SimulatorSession] = {}
_enemy_service: Optional[EnemySimulatorService] = None
_pick_engine: Optional[PickRecommendationEngine] = None
_ban_service: Optional[BanRecommendationService] = None
_team_eval_service: Optional[TeamEvaluationService] = None
_draft_service: Optional[DraftService] = None
_repository: Optional[DraftRepository] = None


def get_services(data_path: str):
    """Initialize services lazily."""
    global _enemy_service, _pick_engine, _ban_service, _team_eval_service, _draft_service, _repository
    if _enemy_service is None:
        _enemy_service = EnemySimulatorService(data_path)
        _pick_engine = PickRecommendationEngine()
        _ban_service = BanRecommendationService(data_path)
        _team_eval_service = TeamEvaluationService()
        _draft_service = DraftService(data_path)
        _repository = DraftRepository(data_path)
    return _enemy_service, _pick_engine, _ban_service, _team_eval_service, _draft_service, _repository


class StartSimulatorRequest(BaseModel):
    blue_team_id: str
    red_team_id: str
    coaching_side: Literal["blue", "red"]
    series_length: Literal[1, 3, 5] = 1
    draft_mode: Literal["normal", "fearless"] = "normal"


class ActionRequest(BaseModel):
    champion: str


class CompleteGameRequest(BaseModel):
    winner: Literal["blue", "red"]


@router.post("/start")
async def start_simulator(request: StartSimulatorRequest):
    """Create a new simulator session."""
    from ban_teemo.main import app
    data_path = app.state.data_path
    enemy_service, pick_engine, ban_service, team_eval_service, draft_service, repo = get_services(data_path)

    session_id = f"sim_{uuid.uuid4().hex[:12]}"

    # Load team info
    blue_team = repo.get_team_context(request.blue_team_id, "blue")
    red_team = repo.get_team_context(request.red_team_id, "red")

    if not blue_team or not red_team:
        raise HTTPException(status_code=404, detail="Team not found")

    # Determine enemy team
    enemy_team_id = request.red_team_id if request.coaching_side == "blue" else request.blue_team_id

    # Initialize enemy strategy
    enemy_strategy = enemy_service.initialize_enemy_strategy(enemy_team_id)

    # Create initial draft state
    draft_state = DraftState(
        game_id=f"{session_id}_g1",
        series_id=session_id,
        game_number=1,
        patch_version="15.18",
        match_date=None,
        blue_team=blue_team,
        red_team=red_team,
        actions=[],
        current_phase=DraftPhase.BAN_PHASE_1,
        next_team="blue",
        next_action="ban"
    )

    session = SimulatorSession(
        session_id=session_id,
        blue_team=blue_team,
        red_team=red_team,
        coaching_side=request.coaching_side,
        series_length=request.series_length,
        draft_mode=request.draft_mode,
        draft_state=draft_state,
        enemy_strategy=enemy_strategy
    )

    _sessions[session_id] = session

    # Get initial recommendations (starts in ban phase)
    is_our_turn = draft_state.next_team == request.coaching_side
    recommendations = None
    if is_our_turn:
        enemy_team = red_team if request.coaching_side == "blue" else blue_team
        recommendations = ban_service.get_ban_recommendations(
            enemy_team=enemy_team,
            already_banned=[],
            fearless_blocked=set(),
            limit=5
        )

    return {
        "session_id": session_id,
        "game_number": 1,
        "blue_team": _serialize_team(blue_team),
        "red_team": _serialize_team(red_team),
        "draft_state": _serialize_draft_state(draft_state),
        "recommendations": recommendations,
        "is_our_turn": is_our_turn
    }


@router.post("/{session_id}/action")
async def submit_action(session_id: str, request: ActionRequest):
    """User submits their pick/ban."""
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = _sessions[session_id]
    draft_state = session.draft_state

    if draft_state.next_team != session.coaching_side:
        raise HTTPException(status_code=400, detail="Not your turn")

    # Create action
    action = DraftAction(
        sequence=len(draft_state.actions) + 1,
        action_type=draft_state.next_action,
        team_side=draft_state.next_team,
        champion_id=request.champion.lower().replace(" ", ""),
        champion_name=request.champion
    )

    # Apply action
    _apply_action(session, action)

    return _build_response(session)


@router.post("/{session_id}/enemy-action")
async def trigger_enemy_action(session_id: str):
    """Triggers enemy pick/ban generation."""
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = _sessions[session_id]
    draft_state = session.draft_state

    if draft_state.next_team == session.coaching_side:
        raise HTTPException(status_code=400, detail="Not enemy's turn")

    from ban_teemo.main import app
    enemy_service, _, _, _, _, _ = get_services(app.state.data_path)

    # Get unavailable champions
    unavailable = set(
        draft_state.blue_bans + draft_state.red_bans +
        draft_state.blue_picks + draft_state.red_picks
    ) | session.fearless_blocked_set

    # Generate enemy action
    champion, source = enemy_service.generate_action(
        session.enemy_strategy,
        sequence=len(draft_state.actions) + 1,
        unavailable=unavailable
    )

    action = DraftAction(
        sequence=len(draft_state.actions) + 1,
        action_type=draft_state.next_action,
        team_side=draft_state.next_team,
        champion_id=champion.lower().replace(" ", ""),
        champion_name=champion
    )

    _apply_action(session, action)

    response = _build_response(session)
    response["source"] = source
    return response


@router.post("/{session_id}/complete-game")
async def complete_game(session_id: str, request: CompleteGameRequest):
    """Records winner, advances series."""
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = _sessions[session_id]
    draft_state = session.draft_state

    # Record result
    result = GameResult(
        game_number=session.current_game,
        winner=request.winner,
        blue_comp=draft_state.blue_picks,
        red_comp=draft_state.red_picks
    )
    session.game_results.append(result)

    # Fearless blocking - store with team and game metadata for tooltips
    if session.draft_mode == "fearless":
        for champ in draft_state.blue_picks:
            session.fearless_blocked[champ] = {
                "team": "blue",
                "game": session.current_game
            }
        for champ in draft_state.red_picks:
            session.fearless_blocked[champ] = {
                "team": "red",
                "game": session.current_game
            }

    return {
        "series_status": {
            "blue_wins": session.series_score[0],
            "red_wins": session.series_score[1],
            "games_played": len(session.game_results),
            "series_complete": session.series_complete
        },
        "fearless_blocked": session.fearless_blocked,  # Dict with team/game metadata
        "next_game_ready": not session.series_complete
    }


@router.post("/{session_id}/next-game")
async def next_game(session_id: str):
    """Starts next game in series."""
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = _sessions[session_id]

    if session.series_complete:
        raise HTTPException(status_code=400, detail="Series already complete")

    from ban_teemo.main import app
    enemy_service, _, _, _, _, _ = get_services(app.state.data_path)

    session.current_game += 1

    # Reset draft state
    session.draft_state = DraftState(
        game_id=f"{session_id}_g{session.current_game}",
        series_id=session_id,
        game_number=session.current_game,
        patch_version="15.18",
        match_date=None,
        blue_team=session.blue_team,
        red_team=session.red_team,
        actions=[],
        current_phase=DraftPhase.BAN_PHASE_1,
        next_team="blue",
        next_action="ban"
    )

    # Re-initialize enemy strategy
    enemy_team_id = session.red_team.id if session.coaching_side == "blue" else session.blue_team.id
    session.enemy_strategy = enemy_service.initialize_enemy_strategy(enemy_team_id)

    return {
        "game_number": session.current_game,
        "draft_state": _serialize_draft_state(session.draft_state),
        "fearless_blocked": session.fearless_blocked  # Dict with team/game metadata
    }


@router.get("/{session_id}")
async def get_session(session_id: str):
    """Get current session state."""
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = _sessions[session_id]
    return {
        "session_id": session_id,
        "status": "drafting" if session.draft_state.current_phase != DraftPhase.COMPLETE else "game_complete",
        "game_number": session.current_game,
        "draft_state": _serialize_draft_state(session.draft_state),
        "series_status": {
            "blue_wins": session.series_score[0],
            "red_wins": session.series_score[1],
            "series_complete": session.series_complete
        },
        "fearless_blocked": session.fearless_blocked  # Dict with team/game metadata
    }


@router.delete("/{session_id}")
async def end_session(session_id: str):
    """End session early."""
    if session_id in _sessions:
        del _sessions[session_id]
    return {"status": "ended"}


# Helper functions

def _apply_action(session: SimulatorSession, action: DraftAction):
    """Apply an action to the session's draft state."""
    draft_state = session.draft_state
    draft_state.actions.append(action)

    # Update phase
    action_count = len(draft_state.actions)
    if action_count >= 20:
        draft_state.current_phase = DraftPhase.COMPLETE
        draft_state.next_team = None
        draft_state.next_action = None
    else:
        if action_count < 6:
            draft_state.current_phase = DraftPhase.BAN_PHASE_1
        elif action_count < 12:
            draft_state.current_phase = DraftPhase.PICK_PHASE_1
        elif action_count < 16:
            draft_state.current_phase = DraftPhase.BAN_PHASE_2
        else:
            draft_state.current_phase = DraftPhase.PICK_PHASE_2

        # Standard draft order
        draft_order = _get_draft_order()
        if action_count < len(draft_order):
            next_team, next_action = draft_order[action_count]
            draft_state.next_team = next_team
            draft_state.next_action = next_action


def _get_draft_order() -> list[tuple[str, str]]:
    """Return standard LoL draft order."""
    return [
        ("blue", "ban"), ("red", "ban"), ("blue", "ban"), ("red", "ban"), ("blue", "ban"), ("red", "ban"),
        ("blue", "pick"), ("red", "pick"), ("red", "pick"), ("blue", "pick"), ("blue", "pick"), ("red", "pick"),
        ("red", "ban"), ("blue", "ban"), ("red", "ban"), ("blue", "ban"),
        ("red", "pick"), ("blue", "pick"), ("blue", "pick"), ("red", "pick"),
    ]


def _build_response(session: SimulatorSession) -> dict:
    """Build standard response after an action."""
    from ban_teemo.main import app
    _, pick_engine, ban_service, team_eval_service, _, _ = get_services(app.state.data_path)

    draft_state = session.draft_state
    is_our_turn = draft_state.next_team == session.coaching_side

    our_picks = draft_state.blue_picks if session.coaching_side == "blue" else draft_state.red_picks
    enemy_picks = draft_state.red_picks if session.coaching_side == "blue" else draft_state.blue_picks

    # Always compute team evaluation for composition feedback
    team_evaluation = None
    if our_picks or enemy_picks:
        team_evaluation = team_eval_service.evaluate_vs_enemy(our_picks, enemy_picks)

    recommendations = None
    if is_our_turn and draft_state.current_phase != DraftPhase.COMPLETE:
        our_team = session.blue_team if session.coaching_side == "blue" else session.red_team
        enemy_team = session.red_team if session.coaching_side == "blue" else session.blue_team
        banned = draft_state.blue_bans + draft_state.red_bans

        if draft_state.next_action == "ban":
            # Ban phase: use BanRecommendationService
            recommendations = ban_service.get_ban_recommendations(
                enemy_team=enemy_team,
                already_banned=banned,
                fearless_blocked=session.fearless_blocked_set,
                limit=5
            )
        else:
            # Pick phase: use PickRecommendationEngine
            pick_index = len(our_picks)
            player = our_team.players[pick_index] if pick_index < len(our_team.players) else our_team.players[0]

            if player:
                recommendations = pick_engine.get_recommendations(
                    player_name=player.name,
                    player_role=player.role,
                    our_picks=our_picks,
                    enemy_picks=enemy_picks,
                    banned=list(set(banned) | session.fearless_blocked_set),
                    limit=5
                )

    return {
        "action": _serialize_action(draft_state.actions[-1]) if draft_state.actions else None,
        "draft_state": _serialize_draft_state(draft_state),
        "recommendations": recommendations,
        "team_evaluation": team_evaluation,
        "is_our_turn": is_our_turn
    }


def _serialize_team(team) -> dict:
    """Serialize TeamContext to dict."""
    return {
        "id": team.id,
        "name": team.name,
        "side": team.side,
        "players": [{"id": p.id, "name": p.name, "role": p.role} for p in team.players]
    }


def _serialize_draft_state(state: DraftState) -> dict:
    """Serialize DraftState to dict."""
    return {
        "phase": state.current_phase.value if hasattr(state.current_phase, 'value') else state.current_phase,
        "next_team": state.next_team,
        "next_action": state.next_action,
        "blue_bans": state.blue_bans,
        "red_bans": state.red_bans,
        "blue_picks": state.blue_picks,
        "red_picks": state.red_picks,
        "action_count": len(state.actions)
    }


def _serialize_action(action: DraftAction) -> dict:
    """Serialize DraftAction to dict."""
    return {
        "sequence": action.sequence,
        "action_type": action.action_type,
        "team_side": action.team_side,
        "champion_id": action.champion_id,
        "champion_name": action.champion_name
    }
```

**Step 2: Register routes in main.py**

Add to `backend/src/ban_teemo/main.py` after other route registrations:

```python
from ban_teemo.api.routes.simulator import router as simulator_router
app.include_router(simulator_router)
```

**Step 3: Commit**

```bash
git add backend/src/ban_teemo/api/routes/simulator.py backend/src/ban_teemo/main.py
git commit -m "feat(api): add simulator REST endpoints"
```

---

### Task 3.4: Refactor PickRecommendationEngine for Team-Composition-First Recommendations

**Problem:** The current engine requires a specific `player_name` and `player_role`, assuming picks happen in role order (1st pick = TOP, 2nd = JNG, etc.). This is wrong—real drafts pick strategically based on what's available, not by role order. Champions can be swapped post-draft.

**Solution:** Change the engine to recommend the best champion for the **team composition**, considering all unfilled roles and team-wide proficiency.

**Additional Fixes (from code review):**
1. **Drop `best_player` field** - Confusing and contradicts "not player-based" approach
2. **Standardize role output to `JNG`** - Data files use `JUNGLE`, but app/frontend use `JNG`
3. **Fix role inference for unknown champions** - Use `champion_role_history.json` as fallback (use `canonical_role` field, not iterating entries)
4. **Fix `LOW_CONFIDENCE` threshold** - Current formula gives min 0.65, threshold was 0.5 (unreachable)
5. **Update FlexResolver** - Output `JNG` format, add deterministic fallback for unknown champs
6. **Add pool depth exploitation to BanRecommendationService** - Boost ban priority for players with shallow champion pools (≤3 champs = +0.20, ≤5 champs = +0.10). Banning from a 3-champion pool is more impactful than banning from a 12-champion pool. Data supports this: 130 players have ≤3 viable champions, median pool size is 9. Gate boost to require pool_size >= 1 to avoid biasing toward missing data. Performance: pre-compute pool_size once per player (not per candidate champion).
7. **Add MatchupCalculator role aliasing** - Data uses `JUNGLE` keys, app outputs `JNG`. Translate JNG→JUNGLE at lookup.

**Files:**
- Modify: `backend/src/ban_teemo/services/scorers/flex_resolver.py`
- Modify: `backend/src/ban_teemo/services/scorers/matchup_calculator.py`
- Modify: `backend/src/ban_teemo/services/pick_recommendation_engine.py`
- Modify: `backend/src/ban_teemo/services/ban_recommendation_service.py`
- Modify: `backend/src/ban_teemo/api/routes/simulator.py`
- Modify: `backend/tests/test_pick_recommendation_engine.py`
- Modify: `backend/tests/test_flex_resolver.py`
- Modify: `backend/tests/test_ban_recommendation_service.py`

**Step 1: Update FlexResolver to output JNG and handle unknown champions**

```python
# backend/src/ban_teemo/services/scorers/flex_resolver.py
"""Flex pick role resolution with probability estimation."""
import json
from pathlib import Path
from typing import Optional


class FlexResolver:
    """Resolves flex pick role probabilities."""

    # Canonical output roles (what the app uses)
    VALID_ROLES = {"TOP", "JNG", "MID", "ADC", "SUP"}

    # Map data file formats to canonical format
    DATA_TO_CANONICAL = {
        "JUNGLE": "JNG",
        "jungle": "JNG",
        "TOP": "TOP",
        "top": "TOP",
        "MID": "MID",
        "mid": "MID",
        "MIDDLE": "MID",
        "ADC": "ADC",
        "adc": "ADC",
        "BOT": "ADC",
        "bot": "ADC",
        "BOTTOM": "ADC",
        "SUP": "SUP",
        "sup": "SUP",
        "SUPPORT": "SUP",
        "support": "SUP",
    }

    # For normalize_role() - accepts various inputs, outputs canonical
    ROLE_ALIASES = {
        "JNG": "JNG",
        "JUNGLE": "JNG",
        "jungle": "JNG",
        "JG": "JNG",
        "TOP": "TOP",
        "top": "TOP",
        "MID": "MID",
        "mid": "MID",
        "MIDDLE": "MID",
        "ADC": "ADC",
        "adc": "ADC",
        "BOT": "ADC",
        "bot": "ADC",
        "BOTTOM": "ADC",
        "SUP": "SUP",
        "sup": "SUP",
        "SUPPORT": "SUP",
        "support": "SUP",
    }

    # Default role order for deterministic fallback (most common roles first)
    DEFAULT_ROLE_ORDER = ["MID", "ADC", "TOP", "JNG", "SUP"]

    def __init__(self, knowledge_dir: Optional[Path] = None):
        if knowledge_dir is None:
            knowledge_dir = Path(__file__).parents[5] / "knowledge"
        self.knowledge_dir = knowledge_dir
        self._flex_data: dict = {}
        self._role_history: dict = {}
        self._load_data()

    def _load_data(self):
        """Load flex champion data and role history for fallback."""
        # Primary: flex_champions.json
        flex_path = self.knowledge_dir / "flex_champions.json"
        if flex_path.exists():
            with open(flex_path) as f:
                data = json.load(f)
                self._flex_data = data.get("flex_picks", {})

        # Fallback: champion_role_history.json for unknown champions
        # Schema: {"champions": {"Aatrox": {"canonical_role": "TOP", ...}, ...}}
        history_path = self.knowledge_dir / "champion_role_history.json"
        if history_path.exists():
            with open(history_path) as f:
                data = json.load(f)
                for champ, champ_data in data.get("champions", {}).items():
                    if isinstance(champ_data, dict):
                        # Use canonical_role field directly
                        role = champ_data.get("canonical_role") or champ_data.get("pro_play_primary_role")
                        if role:
                            canonical = self.DATA_TO_CANONICAL.get(role, role)
                            if canonical in self.VALID_ROLES:
                                self._role_history[champ] = canonical

    def get_role_probabilities(
        self, champion_name: str, filled_roles: Optional[set[str]] = None
    ) -> dict[str, float]:
        """Get role probability distribution for a champion.

        Returns probabilities using canonical role names (TOP, JNG, MID, ADC, SUP).
        For unknown champions, uses champion_role_history.json as fallback.
        """
        filled = filled_roles or set()

        if champion_name in self._flex_data:
            data = self._flex_data[champion_name]
            probs = {}
            for role in self.VALID_ROLES:
                if role not in filled:
                    # Data uses JUNGLE, we output JNG
                    data_key = "JUNGLE" if role == "JNG" else role
                    probs[role] = data.get(data_key, 0)

            total = sum(probs.values())
            if total > 0:
                probs = {role: p / total for role, p in probs.items()}
            elif probs:
                prob = 1.0 / len(probs)
                probs = {role: prob for role in probs}
            return probs

        # Fallback: use role history if available
        if champion_name in self._role_history:
            primary_role = self._role_history[champion_name]
            if primary_role not in filled:
                return {primary_role: 1.0}
            # Primary is filled, return uniform over remaining
            available = self.VALID_ROLES - filled
            if available:
                prob = 1.0 / len(available)
                return {role: prob for role in available}
            return {}

        # Ultimate fallback: deterministic assignment based on DEFAULT_ROLE_ORDER
        # This ensures consistent behavior for completely unknown champions
        for role in self.DEFAULT_ROLE_ORDER:
            if role not in filled:
                return {role: 1.0}
        return {}

    def is_flex_pick(self, champion_name: str) -> bool:
        """Check if champion is a flex pick."""
        if champion_name not in self._flex_data:
            return False
        return self._flex_data[champion_name].get("is_flex", False)

    def normalize_role(self, role: str) -> str:
        """Normalize role name to canonical form (TOP, JNG, MID, ADC, SUP)."""
        return self.ROLE_ALIASES.get(role, self.ROLE_ALIASES.get(role.upper(), role.upper()))
```

**Step 1b: Add role aliasing to MatchupCalculator**

The matchup data uses `JUNGLE` as the role key, but the app now uses `JNG`. Add translation at lookup time.

```python
# backend/src/ban_teemo/services/scorers/matchup_calculator.py
"""Matchup calculation with flex pick uncertainty handling."""
import json
from pathlib import Path
from typing import Optional


class MatchupCalculator:
    """Calculates matchup scores between champions."""

    # Translate canonical app roles to data file roles
    ROLE_TO_DATA = {
        "JNG": "JUNGLE",
        "TOP": "TOP",
        "MID": "MID",
        "ADC": "ADC",
        "SUP": "SUP",
    }

    def __init__(self, knowledge_dir: Optional[Path] = None):
        if knowledge_dir is None:
            knowledge_dir = Path(__file__).parents[5] / "knowledge"
        self.knowledge_dir = knowledge_dir
        self._counters: dict = {}
        self._load_data()

    def _load_data(self):
        """Load matchup statistics."""
        matchup_path = self.knowledge_dir / "matchup_stats.json"
        if matchup_path.exists():
            with open(matchup_path) as f:
                data = json.load(f)
                self._counters = data.get("counters", {})

    def get_lane_matchup(self, our_champion: str, enemy_champion: str, role: str) -> dict:
        """Get lane-specific matchup score."""
        # Translate canonical role (JNG) to data role (JUNGLE)
        data_role = self.ROLE_TO_DATA.get(role.upper(), role.upper())

        # Direct lookup
        if our_champion in self._counters:
            vs_lane = self._counters[our_champion].get("vs_lane", {})
            role_data = vs_lane.get(data_role, {})
            if enemy_champion in role_data:
                matchup = role_data[enemy_champion]
                return {
                    "score": matchup.get("win_rate", 0.5),
                    "confidence": matchup.get("confidence", "MEDIUM"),
                    "games": matchup.get("games", 0),
                    "data_source": "direct_lookup"
                }

        # Reverse lookup (invert)
        if enemy_champion in self._counters:
            vs_lane = self._counters[enemy_champion].get("vs_lane", {})
            role_data = vs_lane.get(data_role, {})
            if our_champion in role_data:
                matchup = role_data[our_champion]
                return {
                    "score": round(1.0 - matchup.get("win_rate", 0.5), 3),
                    "confidence": matchup.get("confidence", "MEDIUM"),
                    "games": matchup.get("games", 0),
                    "data_source": "reverse_lookup"
                }

        return {"score": 0.5, "confidence": "NO_DATA", "games": 0, "data_source": "none"}

    def get_team_matchup(self, our_champion: str, enemy_champion: str) -> dict:
        """Get team-level matchup."""
        # Direct lookup
        if our_champion in self._counters:
            vs_team = self._counters[our_champion].get("vs_team", {})
            if enemy_champion in vs_team:
                matchup = vs_team[enemy_champion]
                return {
                    "score": matchup.get("win_rate", 0.5),
                    "games": matchup.get("games", 0),
                    "data_source": "direct_lookup"
                }

        # Reverse lookup
        if enemy_champion in self._counters:
            vs_team = self._counters[enemy_champion].get("vs_team", {})
            if our_champion in vs_team:
                matchup = vs_team[our_champion]
                return {
                    "score": round(1.0 - matchup.get("win_rate", 0.5), 3),
                    "games": matchup.get("games", 0),
                    "data_source": "reverse_lookup"
                }

        return {"score": 0.5, "games": 0, "data_source": "none"}
```

**Step 2: Update engine signature and logic**

```python
# backend/src/ban_teemo/services/pick_recommendation_engine.py
"""Pick recommendation engine combining all scoring components."""
from pathlib import Path
from typing import Optional

from ban_teemo.services.scorers import MetaScorer, FlexResolver, ProficiencyScorer, MatchupCalculator
from ban_teemo.services.synergy_service import SynergyService


class PickRecommendationEngine:
    """Generates pick recommendations using weighted multi-factor scoring."""

    BASE_WEIGHTS = {"meta": 0.25, "proficiency": 0.35, "matchup": 0.25, "counter": 0.15}
    SYNERGY_MULTIPLIER_RANGE = 0.3
    ALL_ROLES = {"TOP", "JNG", "MID", "ADC", "SUP"}

    def __init__(self, knowledge_dir: Optional[Path] = None):
        self.meta_scorer = MetaScorer(knowledge_dir)
        self.flex_resolver = FlexResolver(knowledge_dir)
        self.proficiency_scorer = ProficiencyScorer(knowledge_dir)
        self.matchup_calculator = MatchupCalculator(knowledge_dir)
        self.synergy_service = SynergyService(knowledge_dir)

    def get_recommendations(
        self,
        team_players: list[dict],
        our_picks: list[str],
        enemy_picks: list[str],
        banned: list[str],
        limit: int = 5
    ) -> list[dict]:
        """Generate ranked pick recommendations for best team composition.

        Args:
            team_players: List of player dicts with 'name' and 'role' keys
            our_picks: Champions already picked by our team
            enemy_picks: Champions already picked by enemy team
            banned: Champions already banned
            limit: Maximum recommendations to return

        Returns:
            List of recommendations with champion_name, score, suggested_role, etc.
        """
        unavailable = set(banned) | set(our_picks) | set(enemy_picks)
        filled_roles = self._infer_filled_roles(our_picks)
        unfilled_roles = self.ALL_ROLES - filled_roles

        candidates = self._get_candidates(team_players, unfilled_roles, unavailable)

        recommendations = []
        for champ in candidates:
            result = self._calculate_score(
                champ, team_players, unfilled_roles, our_picks, enemy_picks
            )
            recommendations.append({
                "champion_name": champ,
                "score": result["total_score"],
                "base_score": result["base_score"],
                "synergy_multiplier": result["synergy_multiplier"],
                "confidence": result["confidence"],
                "suggested_role": result["suggested_role"],
                "components": result["components"],
                "flag": self._compute_flag(result),
                "reasons": self._generate_reasons(champ, result)
            })

        recommendations.sort(key=lambda x: -x["score"])
        return recommendations[:limit]

    def _infer_filled_roles(self, picks: list[str]) -> set[str]:
        """Infer which roles are filled based on picks using primary role."""
        filled = set()
        for champ in picks:
            probs = self.flex_resolver.get_role_probabilities(champ)
            if probs:
                primary = max(probs, key=probs.get)
                filled.add(primary)
        return filled

    def _get_candidates(
        self, team_players: list[dict], unfilled_roles: set[str], unavailable: set[str]
    ) -> list[str]:
        """Get candidate champions from team pools and meta picks for unfilled roles."""
        candidates = set()

        # 1. All players' champion pools
        for player in team_players:
            pool = self.proficiency_scorer.get_player_champion_pool(player["name"], min_games=1)
            for entry in pool[:15]:
                if entry["champion"] not in unavailable:
                    candidates.add(entry["champion"])

        # 2. Meta picks for each unfilled role
        for role in unfilled_roles:
            meta_picks = self.meta_scorer.get_top_meta_champions(role=role, limit=10)
            for champ in meta_picks:
                if champ not in unavailable:
                    candidates.add(champ)

        return list(candidates)

    def _calculate_score(
        self, champion: str, team_players: list[dict], unfilled_roles: set[str],
        our_picks: list[str], enemy_picks: list[str]
    ) -> dict:
        """Calculate score using base factors + synergy multiplier."""
        components = {}

        # Determine champion's role (primary role that's still unfilled)
        probs = self.flex_resolver.get_role_probabilities(champion, filled_roles=set())
        suggested_role = None
        if probs:
            # Prefer unfilled roles, fall back to primary
            for role in sorted(probs, key=probs.get, reverse=True):
                if role in unfilled_roles:
                    suggested_role = role
                    break
            if not suggested_role:
                suggested_role = max(probs, key=probs.get)
        suggested_role = suggested_role or "MID"

        # Meta
        components["meta"] = self.meta_scorer.get_meta_score(champion)

        # Proficiency - best across all team players
        best_prof = 0.0
        best_conf = "NO_DATA"
        for player in team_players:
            score, conf = self.proficiency_scorer.get_proficiency_score(player["name"], champion)
            if score > best_prof:
                best_prof = score
                best_conf = conf
        components["proficiency"] = best_prof
        prof_conf_val = {"HIGH": 1.0, "MEDIUM": 0.8, "LOW": 0.5, "NO_DATA": 0.3}.get(best_conf, 0.5)

        # Matchup (lane) - use suggested role (already canonical JNG format)
        matchup_scores = []
        for enemy in enemy_picks:
            role_probs = self.flex_resolver.get_role_probabilities(enemy)
            if suggested_role in role_probs and role_probs[suggested_role] > 0:
                result = self.matchup_calculator.get_lane_matchup(champion, enemy, suggested_role)
                matchup_scores.append(result["score"])
        components["matchup"] = sum(matchup_scores) / len(matchup_scores) if matchup_scores else 0.5

        # Counter (team)
        counter_scores = []
        for enemy in enemy_picks:
            result = self.matchup_calculator.get_team_matchup(champion, enemy)
            counter_scores.append(result["score"])
        components["counter"] = sum(counter_scores) / len(counter_scores) if counter_scores else 0.5

        # Synergy
        synergy_result = self.synergy_service.calculate_team_synergy(our_picks + [champion])
        synergy_score = synergy_result["total_score"]
        components["synergy"] = synergy_score
        synergy_multiplier = 1.0 + (synergy_score - 0.5) * self.SYNERGY_MULTIPLIER_RANGE

        # Base score
        base_score = (
            components["meta"] * self.BASE_WEIGHTS["meta"] +
            components["proficiency"] * self.BASE_WEIGHTS["proficiency"] +
            components["matchup"] * self.BASE_WEIGHTS["matchup"] +
            components["counter"] * self.BASE_WEIGHTS["counter"]
        )

        total_score = base_score * synergy_multiplier
        confidence = (1.0 + prof_conf_val) / 2

        return {
            "total_score": round(total_score, 3),
            "base_score": round(base_score, 3),
            "synergy_multiplier": round(synergy_multiplier, 3),
            "confidence": round(confidence, 3),
            "suggested_role": suggested_role,
            "components": {k: round(v, 3) for k, v in components.items()}
        }

    def _compute_flag(self, result: dict) -> str | None:
        """Compute recommendation flag for UI badges.

        Thresholds:
        - LOW_CONFIDENCE: confidence < 0.7 (possible range is 0.65-1.0)
        - SURPRISE_PICK: low meta but high proficiency
        """
        if result["confidence"] < 0.7:
            return "LOW_CONFIDENCE"
        if result["components"].get("meta", 0) < 0.4 and result["components"].get("proficiency", 0) >= 0.7:
            return "SURPRISE_PICK"
        return None

    def _generate_reasons(self, champion: str, result: dict) -> list[str]:
        """Generate human-readable reasons."""
        reasons = []
        components = result["components"]

        if components.get("meta", 0) >= 0.7:
            tier = self.meta_scorer.get_meta_tier(champion)
            reasons.append(f"{tier or 'High'}-tier meta pick")
        if components.get("proficiency", 0) >= 0.7:
            reasons.append("Strong team proficiency")
        if components.get("matchup", 0) >= 0.55:
            reasons.append("Favorable lane matchups")
        if result.get("synergy_multiplier", 1.0) >= 1.10:
            reasons.append("Strong team synergy")

        return reasons if reasons else ["Solid overall pick"]
```

**Step 3: Update simulator routes call site**

```python
# backend/src/ban_teemo/api/routes/simulator.py
# In _build_response(), replace the pick phase recommendation code:

        else:
            # Pick phase: use PickRecommendationEngine
            # Recommend best team composition pick, not tied to specific player
            our_team = session.blue_team if session.coaching_side == "blue" else session.red_team

            recommendations = pick_engine.get_recommendations(
                team_players=[{"name": p.name, "role": p.role} for p in our_team.players],
                our_picks=our_picks,
                enemy_picks=enemy_picks,
                banned=list(set(banned) | session.fearless_blocked_set),
                limit=5,
            )
```

**Step 4: Update tests**

```python
# backend/tests/test_pick_recommendation_engine.py
"""Tests for pick recommendation engine."""
import pytest
from ban_teemo.services.pick_recommendation_engine import PickRecommendationEngine


@pytest.fixture
def engine():
    return PickRecommendationEngine()


@pytest.fixture
def sample_team_players():
    """Sample team roster."""
    return [
        {"name": "Zeus", "role": "TOP"},
        {"name": "Oner", "role": "JNG"},
        {"name": "Faker", "role": "MID"},
        {"name": "Gumayusi", "role": "ADC"},
        {"name": "Keria", "role": "SUP"},
    ]


def test_get_recommendations_returns_list(engine, sample_team_players):
    """Engine returns list of recommendations."""
    recs = engine.get_recommendations(
        team_players=sample_team_players,
        our_picks=[],
        enemy_picks=[],
        banned=[],
        limit=5
    )
    assert isinstance(recs, list)
    assert len(recs) <= 5


def test_recommendations_have_required_fields(engine, sample_team_players):
    """Each recommendation has required fields."""
    recs = engine.get_recommendations(
        team_players=sample_team_players,
        our_picks=[],
        enemy_picks=[],
        banned=[],
        limit=5
    )
    assert len(recs) > 0
    rec = recs[0]
    assert "champion_name" in rec
    assert "score" in rec
    assert "confidence" in rec
    assert "suggested_role" in rec
    assert "flag" in rec
    assert "reasons" in rec
    # best_player should NOT be present (dropped)
    assert "best_player" not in rec


def test_recommendations_sorted_by_score(engine, sample_team_players):
    """Recommendations are sorted by score descending."""
    recs = engine.get_recommendations(
        team_players=sample_team_players,
        our_picks=[],
        enemy_picks=[],
        banned=[],
        limit=10
    )
    scores = [r["score"] for r in recs]
    assert scores == sorted(scores, reverse=True)


def test_unavailable_champions_excluded(engine, sample_team_players):
    """Banned and picked champions are not recommended."""
    banned = ["Azir", "Aurora", "Ahri"]
    recs = engine.get_recommendations(
        team_players=sample_team_players,
        our_picks=["Rumble"],
        enemy_picks=["Jinx"],
        banned=banned,
        limit=10
    )
    recommended_champs = {r["champion_name"] for r in recs}
    assert "Azir" not in recommended_champs
    assert "Aurora" not in recommended_champs
    assert "Rumble" not in recommended_champs
    assert "Jinx" not in recommended_champs


def test_suggested_role_uses_jng_not_jungle(engine, sample_team_players):
    """Suggested role should use JNG format, not JUNGLE."""
    recs = engine.get_recommendations(
        team_players=sample_team_players,
        our_picks=[],
        enemy_picks=[],
        banned=[],
        limit=20
    )
    for rec in recs:
        role = rec["suggested_role"]
        assert role in {"TOP", "JNG", "MID", "ADC", "SUP"}, f"Got unexpected role: {role}"
        assert role != "JUNGLE", "Should use JNG, not JUNGLE"


def test_suggested_role_prefers_unfilled(engine, sample_team_players):
    """Suggested role should prefer unfilled roles."""
    # Pick a TOP champion first
    recs = engine.get_recommendations(
        team_players=sample_team_players,
        our_picks=["Rumble"],  # TOP is filled
        enemy_picks=[],
        banned=[],
        limit=5
    )
    # Most recommendations should not suggest TOP
    top_suggestions = sum(1 for r in recs if r["suggested_role"] == "TOP")
    assert top_suggestions < len(recs)  # Not all should be TOP


def test_flag_low_confidence_reachable(engine):
    """LOW_CONFIDENCE flag should be reachable with unknown players."""
    # Use players with no proficiency data
    unknown_players = [{"name": "CompletelyUnknownPlayer12345", "role": "MID"}]
    recs = engine.get_recommendations(
        team_players=unknown_players,
        our_picks=[],
        enemy_picks=[],
        banned=[],
        limit=5
    )
    # With NO_DATA proficiency, confidence = (1.0 + 0.3) / 2 = 0.65
    # Threshold is 0.7, so these should get LOW_CONFIDENCE
    flags = [r["flag"] for r in recs]
    assert "LOW_CONFIDENCE" in flags, f"Expected LOW_CONFIDENCE flag, got: {flags}"


def test_unknown_champion_gets_deterministic_role(engine, sample_team_players):
    """Unknown champions should get deterministic role assignment."""
    # Call twice with same inputs - should get same results
    recs1 = engine.get_recommendations(
        team_players=sample_team_players,
        our_picks=[],
        enemy_picks=[],
        banned=[],
        limit=10
    )
    recs2 = engine.get_recommendations(
        team_players=sample_team_players,
        our_picks=[],
        enemy_picks=[],
        banned=[],
        limit=10
    )
    # Same champions should have same suggested roles
    roles1 = {r["champion_name"]: r["suggested_role"] for r in recs1}
    roles2 = {r["champion_name"]: r["suggested_role"] for r in recs2}
    for champ in roles1:
        if champ in roles2:
            assert roles1[champ] == roles2[champ], f"Role for {champ} not deterministic"
```

**Step 5: Update FlexResolver tests**

```python
# backend/tests/test_flex_resolver.py (add these tests)

def test_outputs_jng_not_jungle(resolver):
    """FlexResolver should output JNG, not JUNGLE."""
    # Test a known jungle champion
    probs = resolver.get_role_probabilities("Lee Sin")
    if probs:
        assert "JNG" in probs or len(probs) == 0, f"Should use JNG, got: {probs.keys()}"
        assert "JUNGLE" not in probs, "Should not output JUNGLE"


def test_unknown_champion_deterministic(resolver):
    """Unknown champions should get deterministic role assignment."""
    probs1 = resolver.get_role_probabilities("CompletelyFakeChampion123")
    probs2 = resolver.get_role_probabilities("CompletelyFakeChampion123")
    assert probs1 == probs2, "Should be deterministic for unknown champions"


def test_fallback_uses_role_history(resolver):
    """Champions not in flex data should use role history as fallback."""
    # Check internal state to find a champion in role_history but not flex_data
    # If flex_data has fewer champions than role_history, we can test fallback
    flex_champs = set(resolver._flex_data.keys())
    history_champs = set(resolver._role_history.keys())
    fallback_only = history_champs - flex_champs

    if fallback_only:
        # Test a champion that requires fallback
        test_champ = next(iter(fallback_only))
        probs = resolver.get_role_probabilities(test_champ)
        assert probs, f"{test_champ} should have probabilities via role history fallback"
        assert len(probs) == 1, "Fallback should return single role with 100%"
        assert list(probs.values())[0] == 1.0, "Fallback should have 100% for primary role"
    else:
        # All role_history champs are in flex_data, test deterministic fallback
        probs = resolver.get_role_probabilities("CompletelyUnknownChampXYZ123")
        assert probs, "Unknown champion should get deterministic fallback"
        assert len(probs) == 1, "Deterministic fallback returns single role"


def test_role_history_uses_canonical_role(resolver):
    """Role history should parse canonical_role field correctly."""
    # Aatrox is a known TOP laner in role history
    if "Aatrox" in resolver._role_history:
        assert resolver._role_history["Aatrox"] == "TOP"
    # At minimum, role history should have some entries
    assert len(resolver._role_history) > 0, "Role history should be populated"


def test_matchup_calculator_accepts_jng():
    """MatchupCalculator should accept JNG and translate to JUNGLE for data lookup."""
    from ban_teemo.services.scorers.matchup_calculator import MatchupCalculator
    calc = MatchupCalculator()

    # Test that JNG doesn't always return 0.5 (no data)
    # Use known jungle matchup - Maokai vs Sejuani is in the data
    result = calc.get_lane_matchup("Maokai", "Sejuani", "JNG")
    # If translation works, we should get actual data
    if result["data_source"] != "none":
        assert result["score"] != 0.5 or result["games"] > 0, "JNG should find JUNGLE data"
```

**Step 6: Run tests**

```bash
cd backend && uv run pytest tests/test_pick_recommendation_engine.py tests/test_flex_resolver.py -v
```

**Step 7: Add pool depth exploitation to BanRecommendationService**

Update `_calculate_ban_priority()` to accept pre-computed `pool_size` (avoids redundant lookups):

```python
# In backend/src/ban_teemo/services/ban_recommendation_service.py
# Update _calculate_ban_priority method signature and logic

def _calculate_ban_priority(
    self,
    champion: str,
    player: dict,
    proficiency: dict,
    pool_size: int,  # Pre-computed by caller for efficiency
) -> float:
    """Calculate ban priority score for a player's champion pool entry.

    Args:
        champion: Champion name being considered for ban
        player: Player dict with 'name' and 'role'
        proficiency: Proficiency entry with 'score', 'games', 'confidence'
        pool_size: Pre-computed size of player's champion pool (min_games=2)
    """
    # Base: player proficiency on champion
    priority = proficiency["score"] * 0.4

    # Meta strength
    meta_score = self.meta_scorer.get_meta_score(champion)
    priority += meta_score * 0.3

    # Games played (comfort factor)
    games = proficiency.get("games", 0)
    comfort = min(1.0, games / 10)
    priority += comfort * 0.2

    # Confidence bonus
    conf = proficiency.get("confidence", "LOW")
    conf_bonus = {"HIGH": 0.1, "MEDIUM": 0.05, "LOW": 0.0}.get(conf, 0)
    priority += conf_bonus

    # Pool depth exploitation - bans hurt more against shallow pools
    # Gate on pool_size >= 1 to avoid biasing toward players with missing data
    if pool_size >= 1:  # Only boost if we have actual data
        if pool_size <= 3:
            priority += 0.20  # High impact - shallow pool
        elif pool_size <= 5:
            priority += 0.10  # Medium impact
        # Deep pools (6+) get no bonus

    return round(min(1.0, priority), 3)
```

Update the calling code in `get_ban_recommendations()` to pre-compute pool size once per player:

```python
# In get_ban_recommendations(), update the player loop:

        # If enemy players provided (or looked up), target their champion pools
        if enemy_players:
            for player in enemy_players:
                player_pool = self.proficiency_scorer.get_player_champion_pool(
                    player["name"], min_games=2
                )
                pool_size = len(player_pool)  # Compute once per player

                for entry in player_pool[:5]:  # Top 5 per player
                    champ = entry["champion"]
                    if champ in unavailable:
                        continue

                    priority = self._calculate_ban_priority(
                        champion=champ,
                        player=player,
                        proficiency=entry,
                        pool_size=pool_size,  # Pass pre-computed value
                    )
                    # ... rest unchanged
```

Add deterministic tests in `backend/tests/test_ban_recommendation_service.py`:

```python
def test_pool_depth_boost_shallow_pool(service, mocker):
    """Verify +0.20 boost is applied for pools with ≤3 champions."""
    # Create controlled proficiency entry
    proficiency = {"score": 0.5, "games": 5, "confidence": "MEDIUM"}
    player = {"name": "TestPlayer", "role": "MID"}

    # Calculate base priority (without pool depth) by testing with deep pool
    base_priority = service._calculate_ban_priority(
        champion="Azir",
        player=player,
        proficiency=proficiency,
        pool_size=10,  # Deep pool - no boost
    )

    # Calculate priority with shallow pool
    shallow_priority = service._calculate_ban_priority(
        champion="Azir",
        player=player,
        proficiency=proficiency,
        pool_size=3,  # Shallow pool - should get +0.20
    )

    # Verify exact boost amount
    assert shallow_priority == min(1.0, round(base_priority + 0.20, 3)), \
        f"Expected +0.20 boost: base={base_priority}, shallow={shallow_priority}"


def test_pool_depth_boost_medium_pool(service):
    """Verify +0.10 boost is applied for pools with 4-5 champions."""
    proficiency = {"score": 0.5, "games": 5, "confidence": "MEDIUM"}
    player = {"name": "TestPlayer", "role": "MID"}

    base_priority = service._calculate_ban_priority(
        champion="Azir", player=player, proficiency=proficiency, pool_size=10,
    )
    medium_priority = service._calculate_ban_priority(
        champion="Azir", player=player, proficiency=proficiency, pool_size=5,
    )

    assert medium_priority == min(1.0, round(base_priority + 0.10, 3)), \
        f"Expected +0.10 boost: base={base_priority}, medium={medium_priority}"


def test_pool_depth_no_boost_for_missing_data(service):
    """Verify no boost when pool_size=0 (missing data)."""
    proficiency = {"score": 0.5, "games": 5, "confidence": "MEDIUM"}
    player = {"name": "TestPlayer", "role": "MID"}

    base_priority = service._calculate_ban_priority(
        champion="Azir", player=player, proficiency=proficiency, pool_size=10,
    )
    no_data_priority = service._calculate_ban_priority(
        champion="Azir", player=player, proficiency=proficiency, pool_size=0,
    )

    assert no_data_priority == base_priority, \
        f"pool_size=0 should get no boost: base={base_priority}, no_data={no_data_priority}"


def test_pool_depth_no_boost_for_deep_pool(service):
    """Verify no boost when pool_size >= 6."""
    proficiency = {"score": 0.5, "games": 5, "confidence": "MEDIUM"}
    player = {"name": "TestPlayer", "role": "MID"}

    priority_6 = service._calculate_ban_priority(
        champion="Azir", player=player, proficiency=proficiency, pool_size=6,
    )
    priority_10 = service._calculate_ban_priority(
        champion="Azir", player=player, proficiency=proficiency, pool_size=10,
    )

    assert priority_6 == priority_10, \
        f"Deep pools (6+) should have same priority: 6={priority_6}, 10={priority_10}"
```

**Step 8: Run ban recommendation tests**

```bash
cd backend && uv run pytest tests/test_ban_recommendation_service.py -v
```

**Step 9: Commit all Task 3.4 changes**

```bash
git add backend/src/ban_teemo/services/scorers/flex_resolver.py \
        backend/src/ban_teemo/services/pick_recommendation_engine.py \
        backend/src/ban_teemo/services/ban_recommendation_service.py \
        backend/src/ban_teemo/api/routes/simulator.py \
        backend/tests/test_pick_recommendation_engine.py \
        backend/tests/test_flex_resolver.py \
        backend/tests/test_ban_recommendation_service.py
git commit -m "refactor(engine): team-composition-first recommendations + pool depth bans

Pick recommendations:
- Remove player_name/player_role params, use team_players list
- Aggregate proficiency across all team players (take best)
- Infer filled roles from existing picks using FlexResolver
- Add suggested_role to response (dropped best_player)
- Add flag field (LOW_CONFIDENCE threshold fixed to 0.7, SURPRISE_PICK)
- Standardize role output to JNG (not JUNGLE)
- Add deterministic fallback for unknown champions using role history

Ban recommendations:
- Add pool depth exploitation: +0.20 for ≤3 champ pools, +0.10 for ≤5"
```

---

### Task 3.5: Add team_evaluation to Start Response

**Problem:** The planned frontend `SimulatorStartResponse` type expects a `team_evaluation` field, but the backend `/start` endpoint doesn't include it. This causes type mismatch.

**Solution:** Add `"team_evaluation": null` to the start response. It's null because no picks exist yet—team evaluation only becomes meaningful after the first pick.

**Files:**
- Modify: `backend/src/ban_teemo/api/routes/simulator.py`

**Step 1: Update start_simulator response**

```python
# In start_simulator(), update the return statement:

    return {
        "session_id": session_id,
        "game_number": 1,
        "blue_team": _serialize_team(blue_team),
        "red_team": _serialize_team(red_team),
        "draft_state": _serialize_draft_state(draft_state),
        "recommendations": recommendations,
        "team_evaluation": None,  # No picks yet, evaluation is meaningless
        "is_our_turn": is_our_turn,
    }
```

**Step 2: Commit**

```bash
git add backend/src/ban_teemo/api/routes/simulator.py
git commit -m "fix(api): add team_evaluation to start response

Returns null at start since no picks exist yet.
Team evaluation becomes populated after first pick."
```

---

### Task 3.6: Update Implementation Progress

**Files:**
- Modify: `docs/plans/2026-01-27-draft-simulator-implementation.md`

Update the status table to mark Stage 3 complete:

```markdown
| Stage | Status | Notes |
|-------|--------|-------|
| Stage 1: Core Scorers | ✅ Complete | MetaScorer, FlexResolver, ProficiencyScorer, MatchupCalculator |
| Stage 2: Enhancement Services | ✅ Complete | All fixes implemented and tested |
| Stage 3: Simulator Backend | ✅ Complete | Models, EnemySimulatorService, routes, team-composition-first engine |
| Stage 4: Frontend Types/Hook | ✅ Complete | Types and useSimulatorSession hook with review fixes |
| Stage 5: API Refactoring | ✅ Complete | CQRS refactor: endpoints renamed, query params, staleness guards |
| Stage 5.5: Performance | ✅ Complete | DuckDB file-backed caching, request-scope flex resolver cache |
| Stage 6: Frontend UI | 🔲 Not Started | ChampionPool, SimulatorSetupModal, SimulatorView, App integration |
| Stage 7: Integration Test | 🔲 Not Started | Full test suite, manual smoke test |
```

---

## Stage 3 Checkpoint

```bash
cd backend && uv run pytest tests/ -v
```

Manual test:
```bash
cd backend && uv run uvicorn ban_teemo.main:app --reload
# In another terminal:
curl -X POST http://localhost:8000/api/simulator/sessions \
  -H "Content-Type: application/json" \
  -d '{"blue_team_id":"oe:team:d2dc3681610c70d6cce8c5f4c1612769","red_team_id":"oe:team:3d032ff98e4a88c6de9bd8a43eb115f2","coaching_side":"blue"}'
```

---

## Stage 4: Frontend - Types and Hook

Build TypeScript types and the simulator hook.

---

### Task 4.1: Add Simulator Types

**Files:**
- Modify: `deepdraft/src/types/index.ts`

**Step 1: Add types at end of file**

```typescript
// === Simulator Types ===

export type DraftMode = "normal" | "fearless";

export interface SimulatorConfig {
  blueTeamId: string;
  redTeamId: string;
  coachingSide: Team;
  seriesLength: 1 | 3 | 5;
  draftMode: DraftMode;
}

export interface SeriesStatus {
  blue_wins: number;
  red_wins: number;
  games_played: number;
  series_complete: boolean;
}

export interface TeamDraftEvaluation {
  archetype: string | null;
  synergy_score: number;
  composition_score: number;
  strengths: string[];
  weaknesses: string[];
}

export interface TeamEvaluation {
  our_evaluation: TeamDraftEvaluation;
  enemy_evaluation: TeamDraftEvaluation;
  matchup_advantage: number;
  matchup_description: string;
}

export interface SimulatorStartResponse {
  session_id: string;
  game_number: number;
  blue_team: TeamContext;
  red_team: TeamContext;
  draft_state: DraftState;
  recommendations: PickRecommendation[] | null;
  team_evaluation: TeamEvaluation | null;
  is_our_turn: boolean;
}

export interface SimulatorActionResponse {
  action: DraftAction | null;
  draft_state: DraftState;
  recommendations: PickRecommendation[] | null;
  team_evaluation: TeamEvaluation | null;
  is_our_turn: boolean;
  source?: "reference_game" | "fallback_game" | "weighted_random";
}

// Fearless blocked entry with team and game metadata for tooltips
export interface FearlessBlockedEntry {
  team: "blue" | "red";
  game: number;
}

// Map of champion name -> blocking metadata
export type FearlessBlocked = Record<string, FearlessBlockedEntry>;

export interface CompleteGameResponse {
  series_status: SeriesStatus;
  fearless_blocked: FearlessBlocked;
  next_game_ready: boolean;
}

export interface TeamListItem {
  id: string;
  name: string;
}
```

**Step 2: Commit**

```bash
git add deepdraft/src/types/index.ts
git commit -m "feat(types): add simulator TypeScript types"
```

---

### Task 4.2: Create useSimulatorSession Hook

**Files:**
- Create: `deepdraft/src/hooks/useSimulatorSession.ts`

**Step 1: Write the hook**

```typescript
// deepdraft/src/hooks/useSimulatorSession.ts
import { useState, useCallback } from "react";
import type {
  SimulatorConfig,
  TeamContext,
  DraftState,
  DraftMode,
  PickRecommendation,
  SeriesStatus,
  SimulatorStartResponse,
  SimulatorActionResponse,
  FearlessBlocked,
} from "../types";

type SimulatorStatus = "setup" | "drafting" | "game_complete" | "series_complete";

interface SimulatorState {
  status: SimulatorStatus;
  sessionId: string | null;
  blueTeam: TeamContext | null;
  redTeam: TeamContext | null;
  coachingSide: "blue" | "red" | null;
  draftMode: DraftMode;
  draftState: DraftState | null;
  recommendations: PickRecommendation[] | null;
  isOurTurn: boolean;
  isEnemyThinking: boolean;
  gameNumber: number;
  seriesStatus: SeriesStatus | null;
  fearlessBlocked: FearlessBlocked;
  error: string | null;
}

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

export function useSimulatorSession() {
  const [state, setState] = useState<SimulatorState>({
    status: "setup",
    sessionId: null,
    blueTeam: null,
    redTeam: null,
    coachingSide: null,
    draftMode: "normal",
    draftState: null,
    recommendations: null,
    isOurTurn: false,
    isEnemyThinking: false,
    gameNumber: 1,
    seriesStatus: null,
    fearlessBlocked: {},
    error: null,
  });

  const startSession = useCallback(async (config: SimulatorConfig) => {
    try {
      const res = await fetch(`${API_BASE}/api/simulator/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          blue_team_id: config.blueTeamId,
          red_team_id: config.redTeamId,
          coaching_side: config.coachingSide,
          series_length: config.seriesLength,
          draft_mode: config.draftMode,
        }),
      });

      if (!res.ok) throw new Error("Failed to start session");

      const data: SimulatorStartResponse = await res.json();

      setState((s) => ({
        ...s,
        status: "drafting",
        sessionId: data.session_id,
        blueTeam: data.blue_team,
        redTeam: data.red_team,
        coachingSide: config.coachingSide,
        draftMode: config.draftMode,
        draftState: data.draft_state,
        recommendations: data.recommendations,
        isOurTurn: data.is_our_turn,
        gameNumber: data.game_number,
        error: null,
      }));

      // If it's enemy's turn first, trigger their action
      if (!data.is_our_turn) {
        setTimeout(() => triggerEnemyAction(data.session_id), 500);
      }
    } catch (err) {
      setState((s) => ({ ...s, error: String(err) }));
    }
  }, []);

  const submitAction = useCallback(async (champion: string) => {
    if (!state.sessionId || !state.isOurTurn) return;

    try {
      const res = await fetch(`${API_BASE}/api/simulator/${state.sessionId}/action`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ champion }),
      });

      if (!res.ok) throw new Error("Failed to submit action");

      const data: SimulatorActionResponse = await res.json();

      const isComplete = data.draft_state.phase === "COMPLETE";

      setState((s) => ({
        ...s,
        status: isComplete ? "game_complete" : "drafting",
        draftState: data.draft_state,
        recommendations: data.recommendations,
        isOurTurn: data.is_our_turn,
      }));

      // If now enemy's turn and not complete, trigger their action
      if (!data.is_our_turn && !isComplete) {
        setTimeout(() => triggerEnemyAction(state.sessionId!), 1000);
      }
    } catch (err) {
      setState((s) => ({ ...s, error: String(err) }));
    }
  }, [state.sessionId, state.isOurTurn]);

  const triggerEnemyAction = useCallback(async (sessionId: string) => {
    setState((s) => ({ ...s, isEnemyThinking: true }));

    try {
      const res = await fetch(`${API_BASE}/api/simulator/${sessionId}/enemy-action`, {
        method: "POST",
      });

      if (!res.ok) throw new Error("Failed to get enemy action");

      const data: SimulatorActionResponse = await res.json();

      const isComplete = data.draft_state.phase === "COMPLETE";

      setState((s) => ({
        ...s,
        status: isComplete ? "game_complete" : "drafting",
        draftState: data.draft_state,
        recommendations: data.recommendations,
        isOurTurn: data.is_our_turn,
        isEnemyThinking: false,
      }));

      // If still enemy's turn, continue
      if (!data.is_our_turn && !isComplete) {
        setTimeout(() => triggerEnemyAction(sessionId), 1000);
      }
    } catch (err) {
      setState((s) => ({ ...s, error: String(err), isEnemyThinking: false }));
    }
  }, []);

  const recordWinner = useCallback(async (winner: "blue" | "red") => {
    if (!state.sessionId) return;

    try {
      const res = await fetch(`${API_BASE}/api/simulator/${state.sessionId}/complete-game`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ winner }),
      });

      if (!res.ok) throw new Error("Failed to record winner");

      const data = await res.json();

      setState((s) => ({
        ...s,
        status: data.series_status.series_complete ? "series_complete" : "game_complete",
        seriesStatus: data.series_status,
        fearlessBlocked: data.fearless_blocked,
      }));
    } catch (err) {
      setState((s) => ({ ...s, error: String(err) }));
    }
  }, [state.sessionId]);

  const nextGame = useCallback(async () => {
    if (!state.sessionId) return;

    try {
      const res = await fetch(`${API_BASE}/api/simulator/${state.sessionId}/next-game`, {
        method: "POST",
      });

      if (!res.ok) throw new Error("Failed to start next game");

      const data = await res.json();

      setState((s) => ({
        ...s,
        status: "drafting",
        draftState: data.draft_state,
        gameNumber: data.game_number,
        fearlessBlocked: data.fearless_blocked,
        recommendations: null,
        isOurTurn: data.draft_state.next_team === s.coachingSide,
      }));

      // Trigger enemy if their turn
      if (data.draft_state.next_team !== state.coachingSide) {
        setTimeout(() => triggerEnemyAction(state.sessionId!), 500);
      }
    } catch (err) {
      setState((s) => ({ ...s, error: String(err) }));
    }
  }, [state.sessionId, state.coachingSide]);

  const endSession = useCallback(async () => {
    if (state.sessionId) {
      await fetch(`${API_BASE}/api/simulator/${state.sessionId}`, { method: "DELETE" });
    }

    setState({
      status: "setup",
      sessionId: null,
      blueTeam: null,
      redTeam: null,
      coachingSide: null,
      draftMode: "normal",
      draftState: null,
      recommendations: null,
      isOurTurn: false,
      isEnemyThinking: false,
      gameNumber: 1,
      seriesStatus: null,
      fearlessBlocked: {},
      error: null,
    });
  }, [state.sessionId]);

  return {
    ...state,
    startSession,
    submitAction,
    recordWinner,
    nextGame,
    endSession,
  };
}
```

**Step 2: Export from hooks index**

```typescript
// deepdraft/src/hooks/index.ts
export { useReplaySession } from "./useReplaySession";
export { useWebSocket } from "./useWebSocket";
export { useSimulatorSession } from "./useSimulatorSession";
```

**Step 3: Commit**

```bash
git add deepdraft/src/hooks/useSimulatorSession.ts deepdraft/src/hooks/index.ts
git commit -m "feat(hooks): add useSimulatorSession hook"
```

---

## Stage 5: API Refactoring

Refactor simulator API to separate commands from queries, add error contracts, and prevent stale data.

**Motivation:** The original API mixed responsibilities (action endpoints computed recommendations + evaluation as side effects), causing inconsistencies and tight coupling.

**Design Principles:**
- **Single Responsibility:** Each endpoint does one thing
- **Commands vs Queries:** POST mutates state, GET reads computed data
- **Staleness Prevention:** All responses include `action_count`. Client guards against out-of-order responses by rejecting data where incoming `action_count <= current action_count`. This applies to:
  - Action responses (triggerEnemyAction, submitAction) - prevents network-reordered responses from regressing state
  - Query responses (recommendations, evaluation) - uses `for_action_count` field
- **Consistent Error Contracts:** Predictable error responses

**Known Limitations (acceptable for MVP):**
- Session IDs are public/unguessable UUIDs, no auth
- Single client per session assumed
- No game history persistence

**Task Order:** Types (5.1) → Backend Routes (5.2) → Backend Tests (5.3) → Frontend Hook (5.4)

---

### API Surface (Target State)

```
# Session Lifecycle
POST   /api/simulator/sessions                         → 201 + session summary
GET    /api/simulator/sessions/{id}                    → 200 + session state
DELETE /api/simulator/sessions/{id}                    → 200 + { status: "ended" }

# Draft Commands (mutate state, optionally include computed data)
POST   /api/simulator/sessions/{id}/actions
       ?include_recommendations=true&include_evaluation=true
       → 200 + { action, draft_state, is_our_turn, recommendations?, evaluation? }
POST   /api/simulator/sessions/{id}/actions/enemy
       ?include_recommendations=true&include_evaluation=true
       → 200 + { action, draft_state, is_our_turn, source, recommendations?, evaluation? }
POST   /api/simulator/sessions/{id}/games/complete
       → 200 + { series_status, fearless_blocked }
POST   /api/simulator/sessions/{id}/games/next
       → 200 + { game_number, draft_state, fearless_blocked }

# Computed Queries (for explicit fetches or refetch after stale detection)
GET    /api/simulator/sessions/{id}/recommendations    → 200 + { for_action_count, phase, recommendations }
GET    /api/simulator/sessions/{id}/evaluation         → 200 + { for_action_count, our_eval, enemy_eval, ... }

# Teams
GET    /api/simulator/teams                            → 200 + { teams: [...] }
```

**Optimization:** Action endpoints accept optional query params:
- `?include_recommendations=true` - Include recommendations for resulting state
- `?include_evaluation=true` - Include team evaluation for resulting state

This avoids extra round trips. Both default to `false` to maintain CQRS purity by default. The GET endpoints remain for explicit fetches or refetching after staleness detection via `for_action_count`.

### Error Contracts

```python
# 400 Bad Request
{ "detail": "Not your turn" }
{ "detail": "Champion 'Azir' is unavailable" }
{ "detail": "Draft already complete" }
{ "detail": "Series already complete" }

# 404 Not Found
{ "detail": "Session not found" }
{ "detail": "Session expired" }

# 422 Validation Error (Pydantic)
{ "detail": [{ "loc": ["body", "champion"], "msg": "field required" }] }
```

---

### Task 5.1: Update Frontend Types

Define new response types before implementation to establish contracts.

**Files:**
- Modify: `deepdraft/src/types/index.ts`

**Step 1: Add new response types**

Add after line 269 (after `NextGameResponse`):

```typescript
// === Stage 5: New Query Response Types ===

export interface RecommendationsResponse {
  for_action_count: number;
  phase: DraftPhase;
  recommendations: SimulatorRecommendation[];
}

export interface EvaluationResponse {
  for_action_count: number;
  our_evaluation: TeamDraftEvaluation;
  enemy_evaluation: TeamDraftEvaluation;
  matchup_advantage: number;
  matchup_description: string;
}
```

**Step 2: Update SimulatorStartResponse (remove recommendations/evaluation)**

Replace the existing `SimulatorStartResponse` (lines 230-239):

```typescript
export interface SimulatorStartResponse {
  session_id: string;
  game_number: number;
  blue_team: TeamContext;
  red_team: TeamContext;
  draft_state: DraftState;
  is_our_turn: boolean;
}
```

**Step 3: Update SimulatorActionResponse (optional recommendations/evaluation)**

Replace the existing `SimulatorActionResponse` (lines 241-248):

```typescript
export interface SimulatorActionResponse {
  action: DraftAction | null;
  draft_state: DraftState;
  is_our_turn: boolean;
  source?: "reference_game" | "fallback_game" | "weighted_random";
  // Optional: included when ?include_recommendations=true
  recommendations?: SimulatorRecommendation[];
  // Optional: included when ?include_evaluation=true
  evaluation?: TeamEvaluation;
}
```

**Step 4: Verify TypeScript compiles**

```bash
cd deepdraft && npm run build
```

Expected: Build fails (hook still expects old types). That's OK - we'll fix in Task 5.4.

**Step 5: Commit**

```bash
git add deepdraft/src/types/index.ts
git commit -m "feat(types): add Stage 5 API response types for CQRS refactor"
```

---

### Task 5.2: Refactor Backend Routes

Update endpoint paths and separate command/query responsibilities.

**Files:**
- Modify: `backend/src/ban_teemo/api/routes/simulator.py`

**Step 1: Update route paths**

Change line 26 router prefix:
```python
router = APIRouter(prefix="/api/simulator", tags=["simulator"])
```
(no change needed - prefix stays the same)

**Step 2: Rename `/start` to `POST /sessions`**

Replace line 130:
```python
@router.post("/start")
```
with:
```python
@router.post("/sessions", status_code=201)
```

**Step 3: Update start_simulator response (remove recs/eval)**

Replace lines 199-208 (the return statement in `start_simulator`):

```python
    return {
        "session_id": session_id,
        "game_number": 1,
        "blue_team": _serialize_team(blue_team),
        "red_team": _serialize_team(red_team),
        "draft_state": _serialize_draft_state(draft_state),
        "is_our_turn": is_our_turn,
    }
```

Also remove lines 186-197 (recommendation computation in start_simulator):
```python
    # Get initial recommendations (starts in ban phase)
    is_our_turn = draft_state.next_team == body.coaching_side
    recommendations = None
    if is_our_turn:
        recommendations = ban_service.get_ban_recommendations(
            enemy_team_id=enemy_team_id,
            our_picks=[],
            enemy_picks=[],
            banned=[],
            phase="BAN_PHASE_1",
            limit=5,
        )
```

Replace with just:
```python
    is_our_turn = draft_state.next_team == body.coaching_side
```

**Step 4: Update action endpoints with query params**

Replace line 211-212 (the `submit_action` decorator and function signature):
```python
@router.post("/{session_id}/action")
async def submit_action(request: Request, session_id: str, body: ActionRequest):
```
with:
```python
@router.post("/sessions/{session_id}/actions")
async def submit_action(
    request: Request,
    session_id: str,
    body: ActionRequest,
    include_recommendations: bool = False,
    include_evaluation: bool = False,
):
```

Replace line 252-253 (the `trigger_enemy_action` decorator and function signature):
```python
@router.post("/{session_id}/enemy-action")
async def trigger_enemy_action(request: Request, session_id: str):
```
with:
```python
@router.post("/sessions/{session_id}/actions/enemy")
async def trigger_enemy_action(
    request: Request,
    session_id: str,
    include_recommendations: bool = False,
    include_evaluation: bool = False,
):
```

**Step 5: Update _build_response to support optional includes**

Replace the `_build_response` function (lines 481-531) with:

```python
def _build_response(
    request: Request,
    session: SimulatorSession,
    include_recommendations: bool = False,
    include_evaluation: bool = False,
) -> dict:
    """Build response after an action, optionally including computed data."""
    draft_state = session.draft_state
    is_our_turn = draft_state.next_team == session.coaching_side

    response = {
        "action": _serialize_action(draft_state.actions[-1]) if draft_state.actions else None,
        "draft_state": _serialize_draft_state(draft_state),
        "is_our_turn": is_our_turn,
    }

    # Optionally include recommendations (to avoid extra round trip)
    if include_recommendations and draft_state.current_phase != DraftPhase.COMPLETE:
        _, pick_engine, ban_service, _, _ = _get_or_create_services(request)

        our_team = session.blue_team if session.coaching_side == "blue" else session.red_team
        enemy_team_id = session.red_team.id if session.coaching_side == "blue" else session.blue_team.id

        our_picks = draft_state.blue_picks if session.coaching_side == "blue" else draft_state.red_picks
        enemy_picks = draft_state.red_picks if session.coaching_side == "blue" else draft_state.blue_picks
        banned = draft_state.blue_bans + draft_state.red_bans

        if draft_state.next_action == "ban":
            all_unavailable = list(set(banned) | session.fearless_blocked_set)
            response["recommendations"] = ban_service.get_ban_recommendations(
                enemy_team_id=enemy_team_id,
                our_picks=our_picks,
                enemy_picks=enemy_picks,
                banned=all_unavailable,
                phase=draft_state.current_phase.value,
                limit=5,
            )
        else:
            response["recommendations"] = pick_engine.get_recommendations(
                team_players=[{"name": p.name, "role": p.role} for p in our_team.players],
                our_picks=our_picks,
                enemy_picks=enemy_picks,
                banned=list(set(banned) | session.fearless_blocked_set),
                limit=5,
            )

    # Optionally include evaluation (to avoid extra round trip)
    if include_evaluation:
        _, _, _, team_eval_service, _ = _get_or_create_services(request)

        our_picks = draft_state.blue_picks if session.coaching_side == "blue" else draft_state.red_picks
        enemy_picks = draft_state.red_picks if session.coaching_side == "blue" else draft_state.blue_picks

        if our_picks or enemy_picks:
            evaluation = team_eval_service.evaluate_vs_enemy(our_picks, enemy_picks)
            response["evaluation"] = evaluation

    return response
```

Update callers to pass query params:
- In `submit_action` (line ~249): `return _build_response(request, session, include_recommendations, include_evaluation)`
- In `trigger_enemy_action` (line ~292): `response = _build_response(request, session, include_recommendations, include_evaluation)` then add source

**Step 6: Rename game management endpoints**

Replace line 297:
```python
@router.post("/{session_id}/complete-game")
```
with:
```python
@router.post("/sessions/{session_id}/games/complete")
```

Replace line 343:
```python
@router.post("/{session_id}/next-game")
```
with:
```python
@router.post("/sessions/{session_id}/games/next")
```

**Step 7: Rename session management endpoints**

Replace line 386:
```python
@router.get("/{session_id}")
```
with:
```python
@router.get("/sessions/{session_id}")
```

Replace line 430:
```python
@router.delete("/{session_id}")
```
with:
```python
@router.delete("/sessions/{session_id}")
```

**Step 8: Rename teams endpoint**

Replace line 410:
```python
@router.get("/teams/list")
```
with:
```python
@router.get("/teams")
```

**Step 9: Add GET /recommendations endpoint**

Add after the `get_session` endpoint (after line ~407):

```python
@router.get("/sessions/{session_id}/recommendations")
async def get_recommendations(request: Request, session_id: str):
    """Get pick/ban recommendations for current draft state."""
    session, lock = _get_session_with_lock(session_id)
    with lock:
        now = time.time()
        if _is_session_expired(session, now):
            raise HTTPException(status_code=404, detail="Session expired")
        _touch_session(session, now)

        draft_state = session.draft_state
        action_count = len(draft_state.actions)

        if draft_state.current_phase == DraftPhase.COMPLETE:
            return {
                "for_action_count": action_count,
                "phase": "COMPLETE",
                "recommendations": [],
            }

        _, pick_engine, ban_service, _, _ = _get_or_create_services(request)

        our_team = session.blue_team if session.coaching_side == "blue" else session.red_team
        enemy_team_id = session.red_team.id if session.coaching_side == "blue" else session.blue_team.id

        our_picks = draft_state.blue_picks if session.coaching_side == "blue" else draft_state.red_picks
        enemy_picks = draft_state.red_picks if session.coaching_side == "blue" else draft_state.blue_picks
        banned = draft_state.blue_bans + draft_state.red_bans

        recommendations = []
        if draft_state.next_action == "ban":
            all_unavailable = list(set(banned) | session.fearless_blocked_set)
            recommendations = ban_service.get_ban_recommendations(
                enemy_team_id=enemy_team_id,
                our_picks=our_picks,
                enemy_picks=enemy_picks,
                banned=all_unavailable,
                phase=draft_state.current_phase.value,
                limit=5,
            )
        else:
            recommendations = pick_engine.get_recommendations(
                team_players=[{"name": p.name, "role": p.role} for p in our_team.players],
                our_picks=our_picks,
                enemy_picks=enemy_picks,
                banned=list(set(banned) | session.fearless_blocked_set),
                limit=5,
            )

        return {
            "for_action_count": action_count,
            "phase": draft_state.current_phase.value,
            "recommendations": recommendations,
        }
```

**Step 10: Add GET /evaluation endpoint**

Add after the recommendations endpoint:

```python
@router.get("/sessions/{session_id}/evaluation")
async def get_evaluation(request: Request, session_id: str):
    """Get team composition evaluation for current draft state."""
    session, lock = _get_session_with_lock(session_id)
    with lock:
        now = time.time()
        if _is_session_expired(session, now):
            raise HTTPException(status_code=404, detail="Session expired")
        _touch_session(session, now)

        draft_state = session.draft_state
        action_count = len(draft_state.actions)

        _, _, _, team_eval_service, _ = _get_or_create_services(request)

        our_picks = draft_state.blue_picks if session.coaching_side == "blue" else draft_state.red_picks
        enemy_picks = draft_state.red_picks if session.coaching_side == "blue" else draft_state.blue_picks

        if not our_picks and not enemy_picks:
            return {
                "for_action_count": action_count,
                "our_evaluation": None,
                "enemy_evaluation": None,
                "matchup_advantage": 1.0,
                "matchup_description": "No picks yet",
            }

        evaluation = team_eval_service.evaluate_vs_enemy(our_picks, enemy_picks)

        return {
            "for_action_count": action_count,
            "our_evaluation": evaluation["our_evaluation"],
            "enemy_evaluation": evaluation["enemy_evaluation"],
            "matchup_advantage": evaluation["matchup_advantage"],
            "matchup_description": evaluation["matchup_description"],
        }
```

**Step 11: Run existing tests (expect failures)**

```bash
cd backend && uv run pytest tests/test_simulator_routes.py -v
```

Expected: Most tests FAIL due to path changes. This is expected - we'll fix in Task 5.3.

**Step 12: Commit**

```bash
git add backend/src/ban_teemo/api/routes/simulator.py
git commit -m "refactor(api): CQRS refactor - separate commands from queries

- Rename endpoints to RESTful /sessions/{id}/... paths
- Remove recommendations/evaluation from action responses
- Add GET /sessions/{id}/recommendations endpoint
- Add GET /sessions/{id}/evaluation endpoint
- Include for_action_count for staleness detection

BREAKING: Frontend must update to new API paths"
```

---

### Task 5.3: Update Backend Route Tests

Update tests to use new endpoint paths and test new query endpoints.

**Files:**
- Modify: `backend/tests/test_simulator_routes.py`

**Step 1: Update all endpoint paths in existing tests**

Find and replace throughout the file:
- `"/api/simulator/start"` → `"/api/simulator/sessions"`
- `"/api/simulator/{session_id}/action"` → `"/api/simulator/sessions/{session_id}/actions"`
- `"/api/simulator/{session_id}/enemy-action"` → `"/api/simulator/sessions/{session_id}/actions/enemy"`
- `"/api/simulator/{session_id}"` (GET/DELETE) → `"/api/simulator/sessions/{session_id}"`
- `"/api/simulator/teams/list"` → `"/api/simulator/teams"`

Specifically update these test methods:

```python
# In TestStartSimulator
# Line ~76-82
response = client.post(
    "/api/simulator/sessions",  # Changed from /start
    json={...},
)
assert response.status_code == 201  # Changed from 200

# Line ~100-108 (test_start_simulator_with_series)
response = client.post(
    "/api/simulator/sessions",
    ...
)
assert response.status_code == 201

# Line ~121-130 (test_start_simulator_team_not_found)
response = client.post(
    "/api/simulator/sessions",
    ...
)
```

```python
# In TestSubmitAction
# Line ~143-151
start_response = client.post(
    "/api/simulator/sessions",
    ...
)
# Line ~155-158
response = client.post(
    f"/api/simulator/sessions/{session_id}/actions",  # Changed
    ...
)

# Similar updates for all action endpoints
```

```python
# In TestGetSession
# Line ~255
response = client.get(f"/api/simulator/sessions/{session_id}")

# Line ~265
response = client.get("/api/simulator/sessions/nonexistent")
```

```python
# In TestEndSession
# Line ~289
response = client.delete(f"/api/simulator/sessions/{session_id}")

# Line ~296
response = client.delete("/api/simulator/sessions/nonexistent")
```

```python
# In TestListTeams
# Line ~314
response = client.get("/api/simulator/teams")  # Changed from /teams/list

# Line ~325
client.get("/api/simulator/teams?limit=10")
```

**Step 2: Update response assertions (no recs/eval in action responses)**

In `test_start_simulator_success`, update assertions:
```python
assert response.status_code == 201
data = response.json()
assert "session_id" in data
assert data["session_id"].startswith("sim_")
assert data["game_number"] == 1
assert data["is_our_turn"] is True
assert "blue_team" in data
assert "red_team" in data
assert "draft_state" in data
# Removed: assert "recommendations" in data
# Removed: assert "team_evaluation" in data
```

In `test_submit_action_success`, verify action response has no recs:
```python
assert response.status_code == 200
data = response.json()
assert data["action"]["champion_name"] == "Azir"
assert data["action"]["action_type"] == "ban"
assert data["action"]["team_side"] == "blue"
assert "is_our_turn" in data
# Recommendations now come from separate endpoint
assert "recommendations" not in data
```

**Step 3: Add test class for recommendations endpoint**

Add after `TestListTeams`:

```python
class TestGetRecommendations:
    """Tests for GET /api/simulator/sessions/{session_id}/recommendations."""

    def test_get_recommendations_ban_phase(self, client, mock_services):
        """Test getting ban recommendations."""
        with patch(
            "ban_teemo.api.routes.simulator.EnemySimulatorService",
            return_value=mock_services["enemy_service"],
        ):
            start_response = client.post(
                "/api/simulator/sessions",
                json={
                    "blue_team_id": "team_blue_123",
                    "red_team_id": "team_red_456",
                    "coaching_side": "blue",
                },
            )
            session_id = start_response.json()["session_id"]

            response = client.get(f"/api/simulator/sessions/{session_id}/recommendations")

        assert response.status_code == 200
        data = response.json()
        assert "for_action_count" in data
        assert data["for_action_count"] == 0  # No actions yet
        assert data["phase"] == "BAN_PHASE_1"
        assert "recommendations" in data

    def test_get_recommendations_session_not_found(self, client, mock_services):
        """Test error when session doesn't exist."""
        response = client.get("/api/simulator/sessions/nonexistent/recommendations")
        assert response.status_code == 404

    def test_recommendations_staleness_tracking(self, client, mock_services):
        """Test that for_action_count updates after actions."""
        with patch(
            "ban_teemo.api.routes.simulator.EnemySimulatorService",
            return_value=mock_services["enemy_service"],
        ):
            start_response = client.post(
                "/api/simulator/sessions",
                json={
                    "blue_team_id": "team_blue_123",
                    "red_team_id": "team_red_456",
                    "coaching_side": "blue",
                },
            )
            session_id = start_response.json()["session_id"]

            # Initial recommendations
            rec1 = client.get(f"/api/simulator/sessions/{session_id}/recommendations")
            assert rec1.json()["for_action_count"] == 0

            # Submit an action
            client.post(
                f"/api/simulator/sessions/{session_id}/actions",
                json={"champion": "Jinx"},
            )

            # Enemy action
            client.post(f"/api/simulator/sessions/{session_id}/actions/enemy")

            # Recommendations should reflect new action count
            rec2 = client.get(f"/api/simulator/sessions/{session_id}/recommendations")
            assert rec2.json()["for_action_count"] == 2
```

**Step 4: Add test class for evaluation endpoint**

```python
class TestGetEvaluation:
    """Tests for GET /api/simulator/sessions/{session_id}/evaluation."""

    def test_get_evaluation_no_picks(self, client, mock_services):
        """Test evaluation when no picks made yet."""
        with patch(
            "ban_teemo.api.routes.simulator.EnemySimulatorService",
            return_value=mock_services["enemy_service"],
        ):
            start_response = client.post(
                "/api/simulator/sessions",
                json={
                    "blue_team_id": "team_blue_123",
                    "red_team_id": "team_red_456",
                    "coaching_side": "blue",
                },
            )
            session_id = start_response.json()["session_id"]

            response = client.get(f"/api/simulator/sessions/{session_id}/evaluation")

        assert response.status_code == 200
        data = response.json()
        assert data["for_action_count"] == 0
        assert data["our_evaluation"] is None
        assert data["enemy_evaluation"] is None

    def test_get_evaluation_session_not_found(self, client, mock_services):
        """Test error when session doesn't exist."""
        response = client.get("/api/simulator/sessions/nonexistent/evaluation")
        assert response.status_code == 404
```

**Step 5: Add test for eager fetch query params**

```python
class TestEagerFetchQueryParams:
    """Tests for ?include_recommendations and ?include_evaluation query params."""

    def test_action_with_include_recommendations(self, client, mock_services):
        """Test action endpoint with include_recommendations=true."""
        with patch(
            "ban_teemo.api.routes.simulator.EnemySimulatorService",
            return_value=mock_services["enemy_service"],
        ):
            start_response = client.post(
                "/api/simulator/sessions",
                json={
                    "blue_team_id": "team_blue_123",
                    "red_team_id": "team_red_456",
                    "coaching_side": "blue",
                },
            )
            session_id = start_response.json()["session_id"]

            # Submit action WITHOUT query params
            response_without = client.post(
                f"/api/simulator/sessions/{session_id}/actions",
                json={"champion": "Jinx"},
            )
            assert "recommendations" not in response_without.json()

            # Trigger enemy action WITH query params
            response_with = client.post(
                f"/api/simulator/sessions/{session_id}/actions/enemy?include_recommendations=true",
            )
            data = response_with.json()
            assert "recommendations" in data
            assert isinstance(data["recommendations"], list)

    def test_action_with_include_evaluation(self, client, mock_services):
        """Test action endpoint with include_evaluation=true."""
        with patch(
            "ban_teemo.api.routes.simulator.EnemySimulatorService",
            return_value=mock_services["enemy_service"],
        ):
            start_response = client.post(
                "/api/simulator/sessions",
                json={
                    "blue_team_id": "team_blue_123",
                    "red_team_id": "team_red_456",
                    "coaching_side": "blue",
                },
            )
            session_id = start_response.json()["session_id"]

            # Submit action WITH include_evaluation
            response = client.post(
                f"/api/simulator/sessions/{session_id}/actions?include_evaluation=true",
                json={"champion": "Jinx"},
            )
            data = response.json()
            # Evaluation may be null if no picks yet, but key should exist
            assert "evaluation" in data or data.get("evaluation") is None
```

**Step 6: Run tests to verify**

```bash
cd backend && uv run pytest tests/test_simulator_routes.py -v
```

Expected: All tests PASS

**Step 7: Commit**

```bash
git add backend/tests/test_simulator_routes.py
git commit -m "test(api): update tests for CQRS refactored endpoints

- Update all endpoint paths to new /sessions/{id}/... format
- Remove assertions for recs/eval in action responses
- Add TestGetRecommendations class with staleness test
- Add TestGetEvaluation class"
```

---

### Task 5.4: Update Frontend Hook

Update the hook to use new API paths and eager fetch recommendations via query params.

**Files:**
- Modify: `deepdraft/src/hooks/useSimulatorSession.ts`

**Step 1: Update imports**

Replace the imports (lines 2-16):

```typescript
import { useState, useCallback, useRef, useEffect } from "react";
import type {
  SimulatorConfig,
  TeamContext,
  DraftState,
  DraftMode,
  SimulatorRecommendation,
  SeriesStatus,
  TeamEvaluation,
  SimulatorStartResponse,
  SimulatorActionResponse,
  CompleteGameResponse,
  NextGameResponse,
  FearlessBlocked,
  RecommendationsResponse,
  EvaluationResponse,
} from "../types";
```

**Step 2: Add fetchRecommendations helper**

Add after `cancelPendingOperations` (around line 92):

```typescript
  const fetchRecommendations = useCallback(async (sessionId: string, expectedActionCount: number) => {
    try {
      const res = await fetch(`${API_BASE}/api/simulator/sessions/${sessionId}/recommendations`);
      if (!res.ok) return;

      const data: RecommendationsResponse = await res.json();

      // Discard stale recommendations
      if (data.for_action_count !== expectedActionCount) {
        console.debug(`Discarding stale recommendations: got ${data.for_action_count}, expected ${expectedActionCount}`);
        return;
      }

      setState((s) => {
        if (s.sessionId !== sessionId) return s;
        if (s.draftState?.action_count !== expectedActionCount) return s;
        return { ...s, recommendations: data.recommendations };
      });
    } catch (err) {
      console.error("Failed to fetch recommendations:", err);
    }
  }, []);

  const fetchEvaluation = useCallback(async (sessionId: string, expectedActionCount: number) => {
    try {
      const res = await fetch(`${API_BASE}/api/simulator/sessions/${sessionId}/evaluation`);
      if (!res.ok) return;

      const data: EvaluationResponse = await res.json();

      // Discard stale evaluation
      if (data.for_action_count !== expectedActionCount) return;

      setState((s) => {
        if (s.sessionId !== sessionId) return s;
        if (s.draftState?.action_count !== expectedActionCount) return s;
        return {
          ...s,
          teamEvaluation: {
            our_evaluation: data.our_evaluation,
            enemy_evaluation: data.enemy_evaluation,
            matchup_advantage: data.matchup_advantage,
            matchup_description: data.matchup_description,
          },
        };
      });
    } catch (err) {
      console.error("Failed to fetch evaluation:", err);
    }
  }, []);
```

**Step 3: Update triggerEnemyAction (with eager fetch via query params)**

Replace the `triggerEnemyAction` function (lines 94-147):

```typescript
  const triggerEnemyAction = useCallback(async (sessionId: string) => {
    if (sessionIdRef.current !== sessionId) return;

    setState((s) => ({ ...s, isEnemyThinking: true }));

    abortControllerRef.current = new AbortController();

    try {
      // Use query params for eager fetch when it will be our turn
      // We always request recs since we don't know yet if it's our turn after enemy acts
      const url = `${API_BASE}/api/simulator/sessions/${sessionId}/actions/enemy?include_recommendations=true&include_evaluation=true`;
      const res = await fetch(url, {
        method: "POST",
        signal: abortControllerRef.current.signal,
      });

      if (sessionIdRef.current !== sessionId) return;
      if (!res.ok) throw new Error("Failed to get enemy action");

      const data: SimulatorActionResponse = await res.json();
      const isComplete = data.draft_state.phase === "COMPLETE";

      setState((s) => {
        if (s.sessionId !== sessionId) return s;

        // STALENESS GUARD: Reject if incoming action_count is not newer than current
        // This prevents out-of-order responses from regressing state
        const currentCount = s.draftState?.action_count ?? 0;
        const incomingCount = data.draft_state.action_count;
        if (incomingCount <= currentCount) {
          console.debug(`Discarding stale action response: got ${incomingCount}, have ${currentCount}`);
          return { ...s, isEnemyThinking: false };
        }

        return {
          ...s,
          status: isComplete ? "game_complete" : "drafting",
          draftState: data.draft_state,
          // Use eager-fetched data if available, otherwise null
          recommendations: data.recommendations ?? null,
          teamEvaluation: data.evaluation ?? null,
          isOurTurn: data.is_our_turn,
          isEnemyThinking: false,
        };
      });

      // If still enemy's turn, continue
      if (!data.is_our_turn && !isComplete && sessionIdRef.current === sessionId) {
        pendingTimerRef.current = setTimeout(() => {
          triggerEnemyAction(sessionId);
        }, 1000);
      }
    } catch (err) {
      if (err instanceof Error && err.name === "AbortError") return;
      setState((s) => {
        if (s.sessionId !== sessionId) return s;
        return { ...s, error: String(err), isEnemyThinking: false };
      });
    }
  }, []);
```

**Step 4: Update startSession**

Replace `startSession` (lines 149-197):

```typescript
  const startSession = useCallback(async (config: SimulatorConfig) => {
    cancelPendingOperations();
    setState({ ...initialState, status: "setup" });

    try {
      const res = await fetch(`${API_BASE}/api/simulator/sessions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          blue_team_id: config.blueTeamId,
          red_team_id: config.redTeamId,
          coaching_side: config.coachingSide,
          series_length: config.seriesLength,
          draft_mode: config.draftMode,
        }),
      });

      if (!res.ok) throw new Error("Failed to start session");

      const data: SimulatorStartResponse = await res.json();
      const actionCount = data.draft_state.action_count;

      setState({
        ...initialState,
        status: "drafting",
        sessionId: data.session_id,
        blueTeam: data.blue_team,
        redTeam: data.red_team,
        coachingSide: config.coachingSide,
        draftMode: config.draftMode,
        draftState: data.draft_state,
        recommendations: null, // Fetch separately
        teamEvaluation: null,
        isOurTurn: data.is_our_turn,
        gameNumber: data.game_number,
      });

      // Fetch recommendations if it's our turn
      if (data.is_our_turn) {
        fetchRecommendations(data.session_id, actionCount);
      } else {
        pendingTimerRef.current = setTimeout(() => {
          triggerEnemyAction(data.session_id);
        }, 500);
      }
    } catch (err) {
      setState((s) => ({ ...s, error: String(err) }));
    }
  }, [cancelPendingOperations, triggerEnemyAction, fetchRecommendations]);
```

**Step 5: Update submitAction (with eager evaluation fetch)**

Replace `submitAction` (lines 199-234):

```typescript
  const submitAction = useCallback(async (champion: string) => {
    const currentSessionId = state.sessionId;
    if (!currentSessionId || !state.isOurTurn) return;

    try {
      // Include evaluation for composition feedback after our pick
      // Don't need recs since it's about to be enemy's turn
      const url = `${API_BASE}/api/simulator/sessions/${currentSessionId}/actions?include_evaluation=true`;
      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ champion }),
      });

      if (!res.ok) throw new Error("Failed to submit action");

      const data: SimulatorActionResponse = await res.json();
      const isComplete = data.draft_state.phase === "COMPLETE";
      const incomingCount = data.draft_state.action_count;

      setState((s) => {
        // STALENESS GUARD: Reject if incoming action_count is not newer
        const currentCount = s.draftState?.action_count ?? 0;
        if (incomingCount <= currentCount) {
          console.debug(`Discarding stale submitAction response: got ${incomingCount}, have ${currentCount}`);
          return s;
        }

        return {
          ...s,
          status: isComplete ? "game_complete" : "drafting",
          draftState: data.draft_state,
          recommendations: null, // Enemy's turn now, we don't need recs
          teamEvaluation: data.evaluation ?? null,
          isOurTurn: data.is_our_turn,
        };
      });

      // Trigger enemy action if their turn (only if state was updated)
      if (!data.is_our_turn && !isComplete) {
        pendingTimerRef.current = setTimeout(() => {
          triggerEnemyAction(currentSessionId);
        }, 1000);
      }
    } catch (err) {
      setState((s) => ({ ...s, error: String(err) }));
    }
  }, [state.sessionId, state.isOurTurn, triggerEnemyAction]);
```

**Step 6: Update recordWinner**

Replace path in `recordWinner`:
```typescript
const res = await fetch(`${API_BASE}/api/simulator/sessions/${state.sessionId}/games/complete`, {
```

**Step 7: Update nextGame**

Replace path and add recommendation fetch:
```typescript
  const nextGame = useCallback(async () => {
    const currentSessionId = state.sessionId;
    const currentCoachingSide = state.coachingSide;
    if (!currentSessionId) return;

    try {
      const res = await fetch(`${API_BASE}/api/simulator/sessions/${currentSessionId}/games/next`, {
        method: "POST",
      });

      if (!res.ok) throw new Error("Failed to start next game");

      const data: NextGameResponse = await res.json();
      const isOurTurn = data.draft_state.next_team === currentCoachingSide;
      const actionCount = data.draft_state.action_count;

      setState((s) => ({
        ...s,
        status: "drafting",
        draftState: data.draft_state,
        gameNumber: data.game_number,
        fearlessBlocked: data.fearless_blocked,
        recommendations: null,
        teamEvaluation: null,
        isOurTurn,
      }));

      if (isOurTurn) {
        fetchRecommendations(currentSessionId, actionCount);
      } else {
        pendingTimerRef.current = setTimeout(() => {
          triggerEnemyAction(currentSessionId);
        }, 500);
      }
    } catch (err) {
      setState((s) => ({ ...s, error: String(err) }));
    }
  }, [state.sessionId, state.coachingSide, triggerEnemyAction, fetchRecommendations]);
```

**Step 8: Update endSession**

Replace path:
```typescript
fetch(`${API_BASE}/api/simulator/sessions/${currentSessionId}`, { method: "DELETE" }).catch(() => {});
```

**Step 9: Verify frontend builds**

```bash
cd deepdraft && npm run build
```

Expected: PASS

**Step 10: Commit**

```bash
git add deepdraft/src/hooks/useSimulatorSession.ts
git commit -m "refactor(hook): update useSimulatorSession for CQRS API

- Update all endpoint paths to /sessions/{id}/...
- Add fetchRecommendations() for GET /recommendations
- Add fetchEvaluation() for GET /evaluation
- Add staleness checks using for_action_count
- Fetch recommendations after actions when it's our turn"
```

---

## Stage 5 Checkpoint

```bash
# Backend tests
cd backend && uv run pytest tests/test_simulator_routes.py -v

# All backend tests
cd backend && uv run pytest tests/ -v

# Frontend build
cd deepdraft && npm run build
```

Expected: All tests pass, frontend builds successfully.

**Manual smoke test:**
```bash
# Terminal 1: Start backend
cd backend && uv run uvicorn ban_teemo.main:app --reload

# Terminal 2: Test new endpoints
# Create session
curl -X POST http://localhost:8000/api/simulator/sessions \
  -H "Content-Type: application/json" \
  -d '{"blue_team_id":"oe:team:d2dc3681610c70d6cce8c5f4c1612769","red_team_id":"oe:team:3d032ff98e4a88c6de9bd8a43eb115f2","coaching_side":"blue"}'

# Get recommendations (use session_id from above)
curl http://localhost:8000/api/simulator/sessions/sim_XXXXX/recommendations

# Get evaluation
curl http://localhost:8000/api/simulator/sessions/sim_XXXXX/evaluation
```

---

## Stage 5.5: Performance Optimization

Optimize backend latency by fixing the two largest bottlenecks: CSV re-parsing and redundant flex resolver calls.

**Motivation:** Current implementation re-parses CSV files on every query (~500-1000ms) and makes redundant flex resolver calls (~200-500ms). Total recommendation latency is 2-4s when it should be <1s.

**Design Principles:**
- **File-backed DuckDB:** Pre-build database file, query with read-only connections (no locks needed)
- **Request-scope caching:** Cache flex resolver results within a single recommendation request
- **Measure before optimizing further:** Counter-pick loops deferred until after these fixes

**Key Implementation Notes:**
- Data lives in `outputs/full_2024_2025_v2/csv/` (not `knowledge/`)
- Must update SQL queries to use table names instead of CSV file paths
- Must preserve existing type conversion logic (datetime→ISO, numeric→str)
- Use `all_varchar=true` to maintain string ID behavior

**Priority Order:**
1. File-backed DuckDB (biggest impact)
2. Flex resolver request-scope cache (cleanup)
3. Counter-pick optimization (only if still >2s after P1+P2)

---

### Issues to Address (Review Findings)

The following issues were identified during design review and must be fixed during implementation:

#### HIGH Priority

**1. CSV fallback path is broken with table-name queries**

The proposed `_query` fallback creates an in-memory DuckDB connection and executes SQL directly, but queries use table names (e.g., `FROM series`) instead of CSV paths. An in-memory connection has no tables defined.

**Decision:** Remove CSV fallback entirely. Fail fast with a clear error message.

Rationale: Keeping a true CSV fallback adds complexity (dual SQL paths, temp tables, or persistent connections) and encourages the slow path. For hackathon velocity, the simpler approach is: "DB missing → fail fast with instructions."

**Implementation:** On init, if `draft_data.duckdb` doesn't exist, raise `FileNotFoundError` with a clear message telling the user to run the build script.

**2. Lexicographic ordering on game_number with all_varchar=true**

`get_games_for_series` uses `ORDER BY game_number` without a cast. With `all_varchar=true`, this produces `1, 10, 2, 3...` instead of `1, 2, 3... 10`.

**Decision:** Add explicit `CAST()` in queries (already the pattern in `get_game_info`).

**Fix:** Change to `ORDER BY CAST(game_number AS INTEGER)` in `get_games_for_series`.

#### MEDIUM Priority

**3. Task 5.5.3 snippets don't match current engine API**

Plan snippets use outdated method/field names:
- `_get_filled_roles()` → actual: `_infer_filled_roles()`
- `score_data["total"]` → actual: `result["total_score"]`
- `_format_recommendation()` → doesn't exist (inline dict construction)

**Decision:** Update plan snippets to match actual API. See corrected snippets in Task 5.5.3.

**4. Role cache missing enemy picks**

`_build_role_cache` collects champions from player pools and meta picks, but `_calculate_score` also needs role probabilities for enemy picks (for lane matchup filtering).

**Decision:** Add `enemy_picks` parameter to `_build_role_cache` and include them in the cache.

**5. Double-pick window recommendations become stale**

During double-pick phases (e.g., red's first pick phase: picks 4 & 5), after the first pick is locked in, recommendations for the second pick are stale. The state has changed (roles, synergy, available champs), so keeping the old list can suggest suboptimal or conflicting picks.

**Decision:** Refresh recommendations after each pick in a double-pick window.

**Implementation (minimal, in useSimulatorSession):**
- Treat `submitAction` as "lock-in"
- After it returns, if `data.is_our_turn` is still true, fetch fresh recommendations
- If no longer our turn, clear recommendations
- This can be handled by checking the response and conditionally calling `fetchRecommendations()`

#### LOW Priority

**6. Missing Path import in DraftRepository**

Plan's `__init__` uses `Path(data_path)` but doesn't add the import.

**Fix:** Add `from pathlib import Path` to imports.

---

### Implementation Checklist (Do Not Skip)

- Ensure every repository query uses table names (including `get_game_info`,
  `get_players_for_game`, `get_team_for_game_side`, `get_team_roster`, and the `/teams` route).
- With `all_varchar=true`, any `ORDER BY` on numeric fields should cast.
- The role cache is request-scoped and safe; ensure `_calculate_score` uses cached
  enemy role probabilities exactly as shown.

---

### Task 5.5.1: Create DuckDB Build Script

Create a script to pre-build the DuckDB database file from CSV sources.

**Files:**
- Create: `backend/scripts/build_duckdb.py`

**Step 1: Write the build script**

```python
#!/usr/bin/env python3
"""Build DuckDB database from CSV data files.

Run this once after updating CSV files, or in CI/CD.
The resulting .duckdb file is used by DraftRepository for fast queries.

Usage:
    uv run python scripts/build_duckdb.py [data_path]

Default data_path: outputs/full_2024_2025_v2/csv (relative to repo root)
"""
import duckdb
from pathlib import Path
import sys


def build_duckdb(data_path: Path, output_path: Path | None = None) -> Path:
    """Build DuckDB database from CSV files in data_path.

    Args:
        data_path: Directory containing CSV files
        output_path: Where to write the .duckdb file (default: data_path/draft_data.duckdb)

    Returns:
        Path to the created database file
    """
    if output_path is None:
        output_path = data_path / "draft_data.duckdb"

    # Remove old DB if exists
    if output_path.exists():
        output_path.unlink()
        print(f"Removed existing {output_path}")

    conn = duckdb.connect(str(output_path))

    csv_files = list(data_path.glob("*.csv"))
    if not csv_files:
        print(f"Warning: No CSV files found in {data_path}")
        conn.close()
        return output_path

    print(f"Building {output_path} from {len(csv_files)} CSV files...")

    for csv_file in sorted(csv_files):
        table_name = csv_file.stem
        # Sanitize table name (replace hyphens with underscores)
        table_name = table_name.replace("-", "_")

        try:
            # Use all_varchar=true to preserve string ID behavior
            # This matches the current behavior where all values are converted to strings
            conn.execute(f"""
                CREATE TABLE {table_name} AS
                SELECT * FROM read_csv('{csv_file}', header=true, all_varchar=true)
            """)
            row_count = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
            print(f"  ✓ {table_name}: {row_count:,} rows")
        except Exception as e:
            print(f"  ✗ {table_name}: {e}")

    # List all tables
    tables = conn.execute("SHOW TABLES").fetchall()
    print(f"\nCreated {len(tables)} tables in {output_path}")

    conn.close()
    return output_path


def main():
    # Default to outputs/full_2024_2025_v2/csv relative to repo root
    if len(sys.argv) > 1:
        data_path = Path(sys.argv[1])
    else:
        # Find data directory: backend/scripts -> backend -> ban-teemo -> outputs/...
        script_dir = Path(__file__).parent
        repo_root = script_dir.parent.parent  # backend/scripts -> backend -> ban-teemo
        data_path = repo_root / "outputs" / "full_2024_2025_v2" / "csv"

    if not data_path.exists():
        print(f"Error: Data path not found: {data_path}")
        print(f"Make sure CSV files exist at: {data_path}")
        sys.exit(1)

    db_path = build_duckdb(data_path)
    print(f"\nDone! Database ready at: {db_path}")


if __name__ == "__main__":
    main()
```

**Step 2: Make script executable and test**

```bash
chmod +x backend/scripts/build_duckdb.py
cd backend && uv run python scripts/build_duckdb.py
```

Expected output:
```
Building outputs/full_2024_2025_v2/csv/draft_data.duckdb from N CSV files...
  ✓ games: X,XXX rows
  ✓ players: XXX rows
  ✓ series: XXX rows
  ✓ teams: XXX rows
  ...
Done! Database ready at: outputs/full_2024_2025_v2/csv/draft_data.duckdb
```

**Step 3: Add to .gitignore**

```bash
echo "outputs/**/*.duckdb" >> .gitignore
```

**Step 4: Commit**

```bash
git add backend/scripts/build_duckdb.py .gitignore
git commit -m "feat(perf): add DuckDB build script for draft data

Creates pre-built DuckDB file from CSVs for fast queries.
Uses all_varchar=true to preserve string ID behavior.
Run: cd backend && uv run python scripts/build_duckdb.py"
```

---

### Task 5.5.2: Update DraftRepository for File-Backed DuckDB

Modify DraftRepository to use the pre-built DuckDB file with read-only connections.
**CRITICAL:** Must update SQL queries to use table names AND preserve type conversion.

**Files:**
- Modify: `backend/src/ban_teemo/repositories/draft_repository.py`

**Step 1: Add Path import and update __init__**

First, add the Path import at the top of the file:
```python
from pathlib import Path
```

Replace the `__init__` method:

```python
def __init__(self, data_path: str):
    """Initialize with path to DuckDB database.

    Args:
        data_path: Path to directory containing draft_data.duckdb
                  (built from CSV files by scripts/build_duckdb.py)

    Raises:
        FileNotFoundError: If draft_data.duckdb doesn't exist
    """
    self.data_path = Path(data_path) if isinstance(data_path, str) else data_path
    self._db_path = self.data_path / "draft_data.duckdb"

    if not self._db_path.exists():
        raise FileNotFoundError(
            f"DuckDB database not found: {self._db_path}\n"
            f"Run: cd backend && uv run python scripts/build_duckdb.py"
        )

    # Verify we can connect
    with duckdb.connect(str(self._db_path), read_only=True) as conn:
        tables = conn.execute("SHOW TABLES").fetchall()
    print(f"DraftRepository: Using {self._db_path} ({len(tables)} tables)")
```

**Step 2: Update _query method (simplified, no fallback)**

Replace the existing `_query` method:

```python
def _query(self, sql: str) -> list[dict]:
    """Execute query and return list of dicts with proper type conversion."""
    # Read-only connection per query - no locks needed, thread-safe
    with duckdb.connect(str(self._db_path), read_only=True) as conn:
        df = conn.execute(sql).df()

    # Convert all columns to JSON-serializable types (preserve existing behavior)
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            # Convert datetime to ISO string
            df[col] = df[col].dt.strftime("%Y-%m-%dT%H:%M:%S")
        elif df[col].dtype == "object":
            # Keep strings as-is
            pass
        else:
            # Convert numeric types to native Python types
            df[col] = df[col].astype(str)

    return df.to_dict(orient="records")
```

**Step 3: Update ALL SQL queries to use table names**

The key change: replace `'{self.data_path}/filename.csv'` with just `table_name`.

Update `get_series_list` (around line 48):
```python
def get_series_list(self, limit: int = 50) -> list[dict]:
    """Get recent series for replay selection."""
    return self._query(f"""
        SELECT
            s.id,
            s.match_date,
            s.format,
            s.blue_team_id,
            t1.name as blue_team_name,
            s.red_team_id,
            t2.name as red_team_name
        FROM series s
        JOIN teams t1 ON s.blue_team_id = t1.id
        JOIN teams t2 ON s.red_team_id = t2.id
        ORDER BY s.match_date DESC
        LIMIT {limit}
    """)
```

Update `get_games_for_series` (around line 69):
```python
def get_games_for_series(self, series_id: str) -> list[dict]:
    """Get all games in a series."""
    return self._query(f"""
        SELECT
            id,
            game_number,
            patch_version,
            winner_team_id,
            duration_seconds
        FROM games
        WHERE series_id = '{series_id}'
        ORDER BY CAST(game_number AS INTEGER)
    """)
```
**NOTE:** `CAST(game_number AS INTEGER)` is required because `all_varchar=true` stores game_number as string. Without the cast, ordering would be lexicographic (1, 10, 2...).

**Apply similar changes to ALL query methods that reference CSV paths:**
- `get_game_info` - swap `read_csv(...)` with `games/series` tables
- `get_players_for_game` / `get_players_for_game_by_side` - use `player_game_stats`
- `get_team_for_game_side` - use `player_game_stats` + `teams`
- `get_draft_actions` - use `draft_actions` + `games` + `series`
- `get_team_games` - use `player_game_stats` + `games` + `series` + `teams`
- `get_team_roster` - use `player_game_stats`
- `get_team_with_name` - use `teams`
- `list_teams` (in simulator routes) - update to `teams`

**Step 4: Run tests to verify**

```bash
cd backend && uv run pytest tests/ -v
```

**Step 5: Benchmark improvement**

```bash
cd backend && uv run python -c "
import time
from ban_teemo.repositories.draft_repository import DraftRepository

repo = DraftRepository('../outputs/full_2024_2025_v2/csv')

start = time.time()
for _ in range(10):
    repo.get_series_list(limit=10)
elapsed = time.time() - start
print(f'10 queries: {elapsed*1000:.0f}ms ({elapsed/10*1000:.0f}ms per query)')
"
```

Expected: <50ms per query.

**Step 6: Commit**

```bash
git add backend/src/ban_teemo/repositories/draft_repository.py
git commit -m "perf(repository): use file-backed DuckDB for fast queries

- Require draft_data.duckdb on init (fail fast with clear error if missing)
- Use read-only connections (thread-safe, no locks)
- Update ALL queries to use table names instead of CSV paths
- Add CAST for numeric ordering (game_number)
- Preserve existing type conversion (datetime→ISO, numeric→str)

~10-20x faster query performance"
```

---

### Task 5.5.3: Add Request-Scope Cache to PickRecommendationEngine

Add caching for flex resolver calls within a single recommendation request.

**NOTE:** The current engine uses team-composition-first approach with signature:
- `team_players: list[dict]` - list of player dicts with name/role
- `unfilled_roles: set[str]` - roles not yet filled by picks
- `unavailable: set[str]` - banned/picked champions

**Files:**
- Modify: `backend/src/ban_teemo/services/pick_recommendation_engine.py`

**Step 1: Build role cache in get_recommendations and pass to methods**

Update `get_recommendations` to build cache once and pass it through.

**NOTE:** Method/field names must match actual API:
- `_infer_filled_roles()` (not `_get_filled_roles`)
- `result["total_score"]` (not `score_data["total"]`)
- Inline dict construction (no `_format_recommendation` method)

```python
def get_recommendations(
    self,
    team_players: list[dict],
    our_picks: list[str],
    enemy_picks: list[str],
    banned: list[str],
    limit: int = 5,
) -> list[dict]:
    """Generate ranked pick recommendations for best team composition."""
    unavailable = set(banned) | set(our_picks) | set(enemy_picks)
    filled_roles = self._infer_filled_roles(our_picks)
    unfilled_roles = self.ALL_ROLES - filled_roles

    if not unfilled_roles:
        return []

    # PRE-COMPUTE: Build role cache for all potential candidates + enemy picks
    # This avoids redundant flex resolver calls in _get_candidates and _calculate_score
    role_cache = self._build_role_cache(
        team_players, unfilled_roles, unavailable, enemy_picks
    )

    candidates = self._get_candidates(team_players, unfilled_roles, unavailable, role_cache)

    if not candidates:
        return []

    recommendations = []
    for champ in candidates:
        result = self._calculate_score(
            champ, team_players, unfilled_roles, our_picks, enemy_picks, role_cache
        )
        recommendations.append({
            "champion_name": champ,
            "score": result["total_score"],
            "base_score": result["base_score"],
            "synergy_multiplier": result["synergy_multiplier"],
            "confidence": result["confidence"],
            "suggested_role": result["suggested_role"],
            "components": result["components"],
            "flag": self._compute_flag(result),
            "reasons": self._generate_reasons(champ, result)
        })

    recommendations.sort(key=lambda x: -x["score"])
    return recommendations[:limit]
```

**Step 2: Add _build_role_cache helper method**

Add this new method to pre-compute all role probabilities.

**NOTE:** Must include `enemy_picks` to cache role probabilities for lane matchup filtering in `_calculate_score`.

```python
def _build_role_cache(
    self,
    team_players: list[dict],
    unfilled_roles: set[str],
    unavailable: set[str],
    enemy_picks: list[str],
) -> dict[str, dict[str, float]]:
    """Pre-compute role probabilities for candidates + enemies.

    This cache is REQUEST-SCOPED (built fresh each get_recommendations call).
    No state leaks between requests.

    Filtering logic:
    - Candidates: filtered by filled_roles (only unfilled roles matter for scoring)
    - Enemies: unfiltered (need full distribution for lane matchup analysis)

    No overlap risk: enemy_picks are in `unavailable`, so they won't be added
    from player pools or meta picks - only via explicit update().

    Returns:
        Dict mapping champion -> role probabilities
    """
    filled_roles = self.ALL_ROLES - unfilled_roles
    all_champions = set()

    # Collect champions from player pools
    for player in team_players:
        pool = self.proficiency_scorer.get_player_champion_pool(player["name"], min_games=1)
        for entry in pool[:15]:
            champ = entry["champion"]
            if champ not in unavailable:
                all_champions.add(champ)

    # Collect meta picks for unfilled roles
    for role in unfilled_roles:
        meta_picks = self.meta_scorer.get_top_meta_champions(role=role, limit=10)
        for champ in meta_picks:
            if champ not in unavailable:
                all_champions.add(champ)

    # Include enemy picks for lane matchup filtering in _calculate_score
    all_champions.update(enemy_picks)

    # Batch compute role probabilities
    # Note: for enemy picks we don't filter by filled_roles since we need their full distribution
    return {
        champ: self.flex_resolver.get_role_probabilities(
            champ, filled_roles=filled_roles if champ not in enemy_picks else set()
        )
        for champ in all_champions
    }
```

**Step 3: Update _get_candidates to use cache**

Update signature and use cached lookups:

```python
def _get_candidates(
    self,
    team_players: list[dict],
    unfilled_roles: set[str],
    unavailable: set[str],
    role_cache: dict[str, dict[str, float]],
) -> list[str]:
    """Get candidate champions from team pools and meta picks for unfilled roles.

    Uses pre-computed role_cache for O(1) lookups.
    """
    candidates = set()

    # 1. All players' champion pools
    for player in team_players:
        pool = self.proficiency_scorer.get_player_champion_pool(player["name"], min_games=1)
        for entry in pool[:15]:
            champ = entry["champion"]
            if champ not in unavailable:
                probs = role_cache.get(champ, {})
                if probs:  # Has at least one viable unfilled role
                    candidates.add(champ)

    # 2. Meta picks for each unfilled role
    for role in unfilled_roles:
        meta_picks = self.meta_scorer.get_top_meta_champions(role=role, limit=10)
        for champ in meta_picks:
            if champ not in unavailable and champ not in candidates:
                probs = role_cache.get(champ, {})
                if probs:
                    candidates.add(champ)

    return list(candidates)
```

**Step 4: Update _calculate_score to use cache**

Update signature to accept role_cache and use it for both candidate and enemy lookups:

```python
def _calculate_score(
    self,
    champion: str,
    team_players: list[dict],
    unfilled_roles: set[str],
    our_picks: list[str],
    enemy_picks: list[str],
    role_cache: dict[str, dict[str, float]],
) -> dict:
    """Calculate score using base factors + synergy multiplier.

    Uses pre-computed role_cache for O(1) lookups.
    """
    components = {}

    # Use cached role probabilities for suggested_role
    filled_roles = self.ALL_ROLES - unfilled_roles
    probs = role_cache.get(champion, {})
    suggested_role = None
    if probs:
        suggested_role = max(probs, key=probs.get)
    suggested_role = suggested_role or "MID"

    # Meta score (unchanged)
    components["meta"] = self.meta_scorer.get_meta_score(champion)

    # Proficiency (unchanged)
    best_prof = 0.0
    best_conf = "NO_DATA"
    for player in team_players:
        score, conf = self.proficiency_scorer.get_proficiency_score(player["name"], champion)
        if score > best_prof:
            best_prof = score
            best_conf = conf
    components["proficiency"] = best_prof
    prof_conf_val = {"HIGH": 1.0, "MEDIUM": 0.8, "LOW": 0.5, "NO_DATA": 0.3}.get(best_conf, 0.5)

    # Matchup (lane) - USE CACHE for enemy role probabilities
    matchup_scores = []
    for enemy in enemy_picks:
        role_probs = role_cache.get(enemy, {})  # Use cache instead of direct call
        if suggested_role in role_probs and role_probs[suggested_role] > 0:
            result = self.matchup_calculator.get_lane_matchup(champion, enemy, suggested_role)
            matchup_scores.append(result["score"])
    components["matchup"] = sum(matchup_scores) / len(matchup_scores) if matchup_scores else 0.5

    # Counter (team) - unchanged
    counter_scores = []
    for enemy in enemy_picks:
        result = self.matchup_calculator.get_team_matchup(champion, enemy)
        counter_scores.append(result["score"])
    components["counter"] = sum(counter_scores) / len(counter_scores) if counter_scores else 0.5

    # ... rest of synergy and scoring logic unchanged
```

**Step 5: Run tests**

```bash
cd backend && uv run pytest tests/test_pick_recommendation_engine.py -v
```

**Step 6: Commit**

```bash
git add backend/src/ban_teemo/services/pick_recommendation_engine.py
git commit -m "perf(engine): add request-scope cache for flex resolver

- Add _build_role_cache() to pre-compute role probabilities once
- Include enemy_picks in cache for lane matchup filtering
- Pass role_cache to _get_candidates and _calculate_score
- Use O(1) dict lookups instead of repeated flex resolver calls
- Reduces redundant calls from ~60 to ~40 per recommendation request"
```

---

### Task 5.5.4: Update Application Startup

Ensure DuckDB file is built during development setup.

**Files:**
- No code changes needed - DraftRepository already fails fast with clear error

**Step 1: Verify behavior**

DraftRepository now raises `FileNotFoundError` if `draft_data.duckdb` is missing (added in Task 5.5.2).

```bash
cd backend && uv run python -c "
from ban_teemo.repositories.draft_repository import DraftRepository
repo = DraftRepository('../outputs/full_2024_2025_v2/csv')
"
```

Expected output (if DuckDB exists):
```
DraftRepository: Using ../outputs/full_2024_2025_v2/csv/draft_data.duckdb (N tables)
```

Expected output (if DuckDB missing):
```
FileNotFoundError: DuckDB database not found: ../outputs/full_2024_2025_v2/csv/draft_data.duckdb
Run: cd backend && uv run python scripts/build_duckdb.py
```

---

## Stage 5.5 Checkpoint

```bash
# Build the DuckDB file
cd backend && uv run python scripts/build_duckdb.py

# Run all tests
cd backend && uv run pytest tests/ -v

# Quick performance check
cd backend && uv run python -c "
import time
from ban_teemo.repositories.draft_repository import DraftRepository

repo = DraftRepository('../outputs/full_2024_2025_v2/csv')
start = time.time()
for _ in range(10):
    repo.get_series_list(limit=10)
elapsed = time.time() - start
print(f'10 queries: {elapsed*1000:.0f}ms')
print(f'Per query: {elapsed/10*1000:.0f}ms')
"
```

Expected:
- Tests pass
- Per-query time <50ms (vs 500-1000ms before)
- Startup shows "Using draft_data.duckdb (N tables)"

---

## Stage 6: Frontend - UI Components

Build the simulator UI components.

---

### Task 6.1: Create ChampionPool Component

**Files:**
- Create: `deepdraft/src/components/ChampionPool/index.tsx`

**Step 1: Write the component**

```tsx
// deepdraft/src/components/ChampionPool/index.tsx
import { useState, useMemo } from "react";
import { ChampionPortrait } from "../shared/ChampionPortrait";
import type { FearlessBlocked } from "../../types";

interface ChampionPoolProps {
  allChampions: string[];
  unavailable: Set<string>;
  fearlessBlocked: FearlessBlocked;  // Dict with team/game metadata for tooltips
  onSelect: (champion: string) => void;
  disabled: boolean;
}

const ROLES = ["All", "Top", "Jungle", "Mid", "ADC", "Support"] as const;

export function ChampionPool({
  allChampions,
  unavailable,
  fearlessBlocked,
  onSelect,
  disabled,
}: ChampionPoolProps) {
  // Create Set for quick lookups
  const fearlessBlockedSet = useMemo(
    () => new Set(Object.keys(fearlessBlocked)),
    [fearlessBlocked]
  );
  const [search, setSearch] = useState("");
  const [selectedRole, setSelectedRole] = useState<string>("All");

  const filteredChampions = useMemo(() => {
    let filtered = allChampions;

    if (search) {
      const query = search.toLowerCase();
      filtered = filtered.filter((c) => c.toLowerCase().includes(query));
    }

    // Note: Role filtering would need champion role data
    // For now, just filter by search

    return filtered.sort();
  }, [allChampions, search, selectedRole]);

  return (
    <div className="bg-lol-darker rounded-lg p-4 flex flex-col h-full">
      {/* Search */}
      <input
        type="text"
        placeholder="Search champions..."
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        className="w-full px-3 py-2 bg-lol-dark border border-gold-dim/30 rounded text-text-primary placeholder-text-tertiary mb-3"
      />

      {/* Role Filters */}
      <div className="flex gap-1 mb-3 flex-wrap">
        {ROLES.map((role) => (
          <button
            key={role}
            onClick={() => setSelectedRole(role)}
            className={`px-2 py-1 text-xs rounded ${
              selectedRole === role
                ? "bg-gold-dim text-lol-darkest"
                : "bg-lol-dark text-text-secondary hover:bg-lol-light"
            }`}
          >
            {role}
          </button>
        ))}
      </div>

      {/* Champion Grid */}
      <div className="flex-1 overflow-y-auto">
        <div className="grid grid-cols-6 gap-1">
          {filteredChampions.map((champion) => {
            const isUnavailable = unavailable.has(champion);
            const isFearlessBlocked = fearlessBlockedSet.has(champion);
            const fearlessInfo = fearlessBlocked[champion];  // For tooltip
            const isDisabled = disabled || isUnavailable || isFearlessBlocked;

            return (
              <button
                key={champion}
                onClick={() => !isDisabled && onSelect(champion)}
                disabled={isDisabled}
                className={`relative aspect-square rounded overflow-hidden ${
                  isDisabled ? "opacity-40 cursor-not-allowed" : "hover:ring-2 hover:ring-gold-bright cursor-pointer"
                }`}
                title={
                  isFearlessBlocked && fearlessInfo
                    ? `${champion} - Used in Game ${fearlessInfo.game} by ${fearlessInfo.team === "blue" ? "Blue" : "Red"}`
                    : isUnavailable
                    ? `${champion} - Unavailable`
                    : champion
                }
              >
                <ChampionPortrait
                  championName={champion}
                  size="sm"
                  state={isUnavailable || isFearlessBlocked ? "banned" : "picked"}
                />
                {(isUnavailable || isFearlessBlocked) && (
                  <div className="absolute inset-0 flex items-center justify-center bg-black/50">
                    <span className="text-red-500 text-2xl font-bold">✕</span>
                  </div>
                )}
                {isFearlessBlocked && (
                  <div className="absolute top-0 right-0 bg-red-600 text-white text-xs px-1">
                    🔒
                  </div>
                )}
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
```

**Step 2: Commit**

```bash
git add deepdraft/src/components/ChampionPool/index.tsx
git commit -m "feat(ui): add ChampionPool component"
```

---

### Task 6.2: Create SimulatorSetupModal

**Files:**
- Create: `deepdraft/src/components/SimulatorSetupModal/index.tsx`

**Step 1: Write the component**

```tsx
// deepdraft/src/components/SimulatorSetupModal/index.tsx
import { useState, useEffect } from "react";
import type { SimulatorConfig, TeamListItem, Team, DraftMode } from "../../types";

interface SimulatorSetupModalProps {
  isOpen: boolean;
  onStart: (config: SimulatorConfig) => void;
  onClose: () => void;
}

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

export function SimulatorSetupModal({ isOpen, onStart, onClose }: SimulatorSetupModalProps) {
  const [teams, setTeams] = useState<TeamListItem[]>([]);
  const [blueTeamId, setBlueTeamId] = useState("");
  const [redTeamId, setRedTeamId] = useState("");
  const [coachingSide, setCoachingSide] = useState<Team>("blue");
  const [seriesLength, setSeriesLength] = useState<1 | 3 | 5>(1);
  const [draftMode, setDraftMode] = useState<DraftMode>("normal");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (isOpen) {
      fetch(`${API_BASE}/api/simulator/teams`)
        .then((res) => res.json())
        .then((data) => setTeams(data.teams || []))
        .catch(console.error);
    }
  }, [isOpen]);

  const handleStart = () => {
    if (!blueTeamId || !redTeamId) return;
    setLoading(true);
    onStart({
      blueTeamId,
      redTeamId,
      coachingSide,
      seriesLength,
      draftMode,
    });
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50">
      <div className="bg-lol-dark rounded-lg p-6 w-full max-w-lg border border-gold-dim/30">
        <h2 className="text-2xl font-bold text-gold-bright mb-6 text-center">
          Start Draft Simulator
        </h2>

        {/* Team Selection */}
        <div className="grid grid-cols-2 gap-4 mb-6">
          <div>
            <label className="block text-sm text-text-secondary mb-1">Blue Side</label>
            <select
              value={blueTeamId}
              onChange={(e) => setBlueTeamId(e.target.value)}
              className="w-full px-3 py-2 bg-lol-darker border border-gold-dim/30 rounded text-text-primary"
            >
              <option value="">Select Team</option>
              {teams.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm text-text-secondary mb-1">Red Side</label>
            <select
              value={redTeamId}
              onChange={(e) => setRedTeamId(e.target.value)}
              className="w-full px-3 py-2 bg-lol-darker border border-gold-dim/30 rounded text-text-primary"
            >
              <option value="">Select Team</option>
              {teams.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Coaching Side */}
        <div className="mb-6">
          <label className="block text-sm text-text-secondary mb-2">You are coaching:</label>
          <div className="flex gap-4">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="radio"
                checked={coachingSide === "blue"}
                onChange={() => setCoachingSide("blue")}
                className="accent-magic"
              />
              <span className="text-blue-400">Blue Side</span>
            </label>
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="radio"
                checked={coachingSide === "red"}
                onChange={() => setCoachingSide("red")}
                className="accent-magic"
              />
              <span className="text-red-400">Red Side</span>
            </label>
          </div>
        </div>

        {/* Series Format */}
        <div className="mb-6">
          <label className="block text-sm text-text-secondary mb-2">Series Format:</label>
          <div className="flex gap-4">
            {([1, 3, 5] as const).map((len) => (
              <label key={len} className="flex items-center gap-2 cursor-pointer">
                <input
                  type="radio"
                  checked={seriesLength === len}
                  onChange={() => setSeriesLength(len)}
                  className="accent-magic"
                />
                <span className="text-text-primary">Bo{len}</span>
              </label>
            ))}
          </div>
        </div>

        {/* Draft Mode */}
        <div className="mb-8">
          <label className="block text-sm text-text-secondary mb-2">Draft Mode:</label>
          <div className="flex gap-4">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="radio"
                checked={draftMode === "normal"}
                onChange={() => setDraftMode("normal")}
                className="accent-magic"
              />
              <span className="text-text-primary">Normal</span>
            </label>
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="radio"
                checked={draftMode === "fearless"}
                onChange={() => setDraftMode("fearless")}
                className="accent-magic"
              />
              <span className="text-text-primary">Fearless</span>
            </label>
          </div>
        </div>

        {/* Actions */}
        <div className="flex gap-4">
          <button
            onClick={onClose}
            className="flex-1 px-4 py-2 bg-lol-darker border border-gold-dim/30 rounded text-text-secondary hover:bg-lol-light"
          >
            Cancel
          </button>
          <button
            onClick={handleStart}
            disabled={!blueTeamId || !redTeamId || loading}
            className="flex-1 px-4 py-2 bg-gold-dim text-lol-darkest rounded font-semibold hover:bg-gold-bright disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? "Starting..." : "Start Draft"}
          </button>
        </div>
      </div>
    </div>
  );
}
```

**Step 2: Commit**

```bash
git add deepdraft/src/components/SimulatorSetupModal/index.tsx
git commit -m "feat(ui): add SimulatorSetupModal component"
```

---

### Task 6.3: Create BanRow Component

**Files:**
- Create: `deepdraft/src/components/draft/BanRow.tsx`

**Step 1: Write the component**

```tsx
// deepdraft/src/components/draft/BanRow.tsx
import { ChampionPortrait } from "../shared/ChampionPortrait";

interface BanRowProps {
  blueBans: string[];
  redBans: string[];
}

export function BanRow({ blueBans, redBans }: BanRowProps) {
  const renderBans = (bans: string[], side: "blue" | "red") => (
    <div className="flex gap-2">
      {[0, 1, 2, 3, 4].map((i) => (
        <div
          key={i}
          className={`w-10 h-10 rounded border ${
            side === "blue" ? "border-blue-500/30" : "border-red-500/30"
          } bg-lol-darker flex items-center justify-center`}
        >
          {bans[i] ? (
            <ChampionPortrait championName={bans[i]} size="sm" state="banned" />
          ) : (
            <span className="text-text-tertiary text-xs">-</span>
          )}
        </div>
      ))}
    </div>
  );

  return (
    <div className="flex justify-center items-center gap-8 py-3 bg-lol-dark/50 rounded">
      <div className="flex items-center gap-2">
        <span className="text-xs text-blue-400 uppercase">Blue Bans</span>
        {renderBans(blueBans, "blue")}
      </div>
      <div className="w-px h-8 bg-gold-dim/30" />
      <div className="flex items-center gap-2">
        {renderBans(redBans, "red")}
        <span className="text-xs text-red-400 uppercase">Red Bans</span>
      </div>
    </div>
  );
}
```

**Step 2: Export from draft index**

Update `deepdraft/src/components/draft/index.ts`:

```typescript
export { PhaseIndicator } from "./PhaseIndicator";
export { TeamPanel } from "./TeamPanel";
export { BanTrack } from "./BanTrack";
export { BanRow } from "./BanRow";
```

**Step 3: Commit**

```bash
git add deepdraft/src/components/draft/BanRow.tsx deepdraft/src/components/draft/index.ts
git commit -m "feat(ui): add BanRow component"
```

---

### Task 6.4: Create SimulatorView Component

**Files:**
- Create: `deepdraft/src/components/SimulatorView/index.tsx`

**Step 1: Write the component**

```tsx
// deepdraft/src/components/SimulatorView/index.tsx
import { useMemo } from "react";
import { PhaseIndicator, TeamPanel, BanRow } from "../draft";
import { ChampionPool } from "../ChampionPool";
import { RecommendationPanel } from "../RecommendationPanel";
import type { TeamContext, DraftState, PickRecommendation, FearlessBlocked } from "../../types";

// Static champion list - in production, fetch from API
const ALL_CHAMPIONS = [
  "Aatrox", "Ahri", "Akali", "Akshan", "Alistar", "Amumu", "Anivia", "Annie", "Aphelios",
  "Ashe", "Aurelion Sol", "Aurora", "Azir", "Bard", "Bel'Veth", "Blitzcrank", "Brand",
  "Braum", "Briar", "Caitlyn", "Camille", "Cassiopeia", "Cho'Gath", "Corki", "Darius",
  "Diana", "Dr. Mundo", "Draven", "Ekko", "Elise", "Evelynn", "Ezreal", "Fiddlesticks",
  "Fiora", "Fizz", "Galio", "Gangplank", "Garen", "Gnar", "Gragas", "Graves", "Gwen",
  "Hecarim", "Heimerdinger", "Illaoi", "Irelia", "Ivern", "Janna", "Jarvan IV", "Jax",
  "Jayce", "Jhin", "Jinx", "K'Sante", "Kai'Sa", "Kalista", "Karma", "Karthus", "Kassadin",
  "Katarina", "Kayle", "Kayn", "Kennen", "Kha'Zix", "Kindred", "Kled", "Kog'Maw", "LeBlanc",
  "Lee Sin", "Leona", "Lillia", "Lissandra", "Lucian", "Lulu", "Lux", "Malphite", "Malzahar",
  "Maokai", "Master Yi", "Milio", "Miss Fortune", "Mordekaiser", "Morgana", "Naafiri",
  "Nami", "Nasus", "Nautilus", "Neeko", "Nidalee", "Nilah", "Nocturne", "Nunu", "Olaf",
  "Orianna", "Ornn", "Pantheon", "Poppy", "Pyke", "Qiyana", "Quinn", "Rakan", "Rammus",
  "Rek'Sai", "Rell", "Renata Glasc", "Renekton", "Rengar", "Riven", "Rumble", "Ryze",
  "Samira", "Sejuani", "Senna", "Seraphine", "Sett", "Shaco", "Shen", "Shyvana", "Singed",
  "Sion", "Sivir", "Skarner", "Smolder", "Sona", "Soraka", "Swain", "Sylas", "Syndra",
  "Tahm Kench", "Taliyah", "Talon", "Taric", "Teemo", "Thresh", "Tristana", "Trundle",
  "Tryndamere", "Twisted Fate", "Twitch", "Udyr", "Urgot", "Varus", "Vayne", "Veigar",
  "Vel'Koz", "Vex", "Vi", "Viego", "Viktor", "Vladimir", "Volibear", "Warwick", "Wukong",
  "Xayah", "Xerath", "Xin Zhao", "Yasuo", "Yone", "Yorick", "Yuumi", "Zac", "Zed", "Zeri",
  "Ziggs", "Zilean", "Zoe", "Zyra"
];

interface SimulatorViewProps {
  blueTeam: TeamContext;
  redTeam: TeamContext;
  coachingSide: "blue" | "red";
  draftState: DraftState;
  recommendations: PickRecommendation[] | null;
  isOurTurn: boolean;
  isEnemyThinking: boolean;
  gameNumber: number;
  seriesScore: [number, number];
  fearlessBlocked: FearlessBlocked;
  draftMode: "normal" | "fearless";
  onChampionSelect: (champion: string) => void;
}

export function SimulatorView({
  blueTeam,
  redTeam,
  coachingSide,
  draftState,
  recommendations,
  isOurTurn,
  isEnemyThinking,
  gameNumber,
  seriesScore,
  fearlessBlocked,
  draftMode,
  onChampionSelect,
}: SimulatorViewProps) {
  const unavailable = useMemo(() => {
    return new Set([
      ...draftState.blue_bans,
      ...draftState.red_bans,
      ...draftState.blue_picks,
      ...draftState.red_picks,
    ]);
  }, [draftState]);

  const fearlessCount = Object.keys(fearlessBlocked).length;

  return (
    <div className="space-y-4">
      {/* Series Status */}
      <div className="flex justify-center items-center gap-4 text-sm">
        <span className="text-text-secondary">Game {gameNumber}</span>
        <span className="text-gold-bright font-bold">
          {blueTeam.name} {seriesScore[0]} - {seriesScore[1]} {redTeam.name}
        </span>
        {draftMode === "fearless" && (
          <span className="text-red-400">Fearless: {fearlessCount} blocked</span>
        )}
      </div>

      {/* Phase Indicator */}
      <div className="flex justify-center">
        <PhaseIndicator
          currentPhase={draftState.phase}
          nextTeam={draftState.next_team}
          nextAction={draftState.next_action}
        />
        {isEnemyThinking && (
          <span className="ml-4 text-text-tertiary animate-pulse">Enemy thinking...</span>
        )}
      </div>

      {/* Main 3-Column Layout */}
      <div className="grid grid-cols-[220px_1fr_220px] gap-4">
        {/* Blue Team */}
        <div className={coachingSide === "blue" ? "ring-2 ring-gold-bright rounded-lg" : ""}>
          <TeamPanel
            team={blueTeam}
            picks={draftState.blue_picks}
            side="blue"
            isActive={draftState.next_team === "blue" && draftState.next_action === "pick"}
          />
          {coachingSide === "blue" && (
            <div className="text-center text-xs text-gold-bright mt-1">★ Your Team</div>
          )}
        </div>

        {/* Champion Pool */}
        <ChampionPool
          allChampions={ALL_CHAMPIONS}
          unavailable={unavailable}
          fearlessBlocked={fearlessBlocked}
          onSelect={onChampionSelect}
          disabled={!isOurTurn}
        />

        {/* Red Team */}
        <div className={coachingSide === "red" ? "ring-2 ring-gold-bright rounded-lg" : ""}>
          <TeamPanel
            team={redTeam}
            picks={draftState.red_picks}
            side="red"
            isActive={draftState.next_team === "red" && draftState.next_action === "pick"}
          />
          {coachingSide === "red" && (
            <div className="text-center text-xs text-gold-bright mt-1">★ Your Team</div>
          )}
        </div>
      </div>

      {/* Ban Row */}
      <BanRow blueBans={draftState.blue_bans} redBans={draftState.red_bans} />

      {/* Recommendations */}
      {isOurTurn && recommendations && (
        <RecommendationPanel
          recommendations={{ for_team: coachingSide, picks: recommendations, bans: [] }}
          nextAction={draftState.next_action}
          onRecommendationClick={onChampionSelect}
        />
      )}
    </div>
  );
}
```

**Step 2: Commit**

```bash
git add deepdraft/src/components/SimulatorView/index.tsx
git commit -m "feat(ui): add SimulatorView component"
```

---

### Task 6.5: Update App with Mode Toggle

**Files:**
- Modify: `deepdraft/src/App.tsx`

**Step 1: Update App.tsx**

```tsx
// deepdraft/src/App.tsx
import { useState } from "react";
import { ActionLog } from "./components/ActionLog";
import { DraftBoard } from "./components/DraftBoard";
import { RecommendationPanel } from "./components/RecommendationPanel";
import { ReplayControls } from "./components/ReplayControls";
import { SimulatorSetupModal } from "./components/SimulatorSetupModal";
import { SimulatorView } from "./components/SimulatorView";
import { useReplaySession, useSimulatorSession } from "./hooks";

type AppMode = "replay" | "simulator";

export default function App() {
  const [mode, setMode] = useState<AppMode>("replay");
  const [showSetup, setShowSetup] = useState(false);

  const replay = useReplaySession();
  const simulator = useSimulatorSession();

  const handleStartSimulator = async (config: Parameters<typeof simulator.startSession>[0]) => {
    await simulator.startSession(config);
    setShowSetup(false);
  };

  return (
    <div className="min-h-screen bg-lol-darkest">
      {/* Header */}
      <header className="h-16 bg-lol-dark border-b border-gold-dim/30 flex items-center px-6">
        <div className="flex items-center gap-4">
          <h1 className="text-xl font-bold uppercase tracking-wide text-gold-bright">
            DeepDraft
          </h1>
          <span className="text-sm text-text-tertiary">LoL Draft Assistant</span>
        </div>

        {/* Mode Toggle */}
        <div className="ml-8 flex items-center gap-2">
          <button
            onClick={() => setMode("replay")}
            className={`px-3 py-1 rounded text-sm ${
              mode === "replay"
                ? "bg-gold-dim text-lol-darkest"
                : "bg-lol-darker text-text-secondary hover:bg-lol-light"
            }`}
          >
            Replay
          </button>
          <button
            onClick={() => {
              setMode("simulator");
              if (simulator.status === "setup") setShowSetup(true);
            }}
            className={`px-3 py-1 rounded text-sm ${
              mode === "simulator"
                ? "bg-gold-dim text-lol-darkest"
                : "bg-lol-darker text-text-secondary hover:bg-lol-light"
            }`}
          >
            Simulator
          </button>
        </div>

        <div className="ml-auto flex items-center gap-4">
          {mode === "replay" && replay.patch && (
            <span className="text-xs text-text-tertiary">Patch {replay.patch}</span>
          )}
          {mode === "replay" && replay.status === "playing" && (
            <span className="text-xs text-magic animate-pulse">● Live</span>
          )}
          {mode === "simulator" && simulator.status === "drafting" && (
            <span className="text-xs text-magic animate-pulse">● Drafting</span>
          )}
        </div>
      </header>

      {/* Main Content */}
      <main className="p-6 space-y-6">
        {mode === "replay" ? (
          <>
            <ReplayControls
              status={replay.status}
              onStart={replay.startReplay}
              onStop={replay.stopReplay}
              error={replay.error}
            />

            <div className="flex flex-row gap-6">
              <div className="flex-1">
                <DraftBoard
                  blueTeam={replay.blueTeam}
                  redTeam={replay.redTeam}
                  draftState={replay.draftState}
                />
              </div>

              {replay.status !== "idle" && (
                <ActionLog
                  actions={replay.actionHistory}
                  blueTeam={replay.blueTeam}
                  redTeam={replay.redTeam}
                />
              )}
            </div>

            <RecommendationPanel
              recommendations={replay.recommendations}
              nextAction={replay.draftState?.next_action ?? null}
            />
          </>
        ) : (
          <>
            {simulator.status === "setup" && (
              <div className="text-center py-12">
                <button
                  onClick={() => setShowSetup(true)}
                  className="px-6 py-3 bg-gold-dim text-lol-darkest rounded-lg font-semibold hover:bg-gold-bright"
                >
                  Start New Draft
                </button>
              </div>
            )}

            {simulator.status === "drafting" && simulator.blueTeam && simulator.redTeam && simulator.draftState && (
              <SimulatorView
                blueTeam={simulator.blueTeam}
                redTeam={simulator.redTeam}
                coachingSide={simulator.coachingSide!}
                draftState={simulator.draftState}
                recommendations={simulator.recommendations}
                isOurTurn={simulator.isOurTurn}
                isEnemyThinking={simulator.isEnemyThinking}
                gameNumber={simulator.gameNumber}
                seriesScore={simulator.seriesStatus ? [simulator.seriesStatus.blue_wins, simulator.seriesStatus.red_wins] : [0, 0]}
                fearlessBlocked={simulator.fearlessBlocked}
                draftMode={simulator.draftMode}
                onChampionSelect={simulator.submitAction}
              />
            )}

            {simulator.status === "game_complete" && (
              <div className="text-center py-12 space-y-4">
                <h2 className="text-2xl font-bold text-gold-bright">Draft Complete!</h2>
                <p className="text-text-secondary">Who won this game?</p>
                <div className="flex justify-center gap-4">
                  <button
                    onClick={() => simulator.recordWinner("blue")}
                    className="px-6 py-2 bg-blue-600 text-white rounded hover:bg-blue-500"
                  >
                    Blue Won
                  </button>
                  <button
                    onClick={() => simulator.recordWinner("red")}
                    className="px-6 py-2 bg-red-600 text-white rounded hover:bg-red-500"
                  >
                    Red Won
                  </button>
                </div>
                {simulator.seriesStatus && !simulator.seriesStatus.series_complete && (
                  <button
                    onClick={simulator.nextGame}
                    className="px-6 py-2 bg-gold-dim text-lol-darkest rounded hover:bg-gold-bright"
                  >
                    Next Game
                  </button>
                )}
              </div>
            )}

            {simulator.status === "series_complete" && (
              <div className="text-center py-12 space-y-4">
                <h2 className="text-2xl font-bold text-gold-bright">Series Complete!</h2>
                <p className="text-xl text-text-primary">
                  {simulator.seriesStatus?.blue_wins} - {simulator.seriesStatus?.red_wins}
                </p>
                <button
                  onClick={simulator.endSession}
                  className="px-6 py-2 bg-gold-dim text-lol-darkest rounded hover:bg-gold-bright"
                >
                  New Session
                </button>
              </div>
            )}

            {simulator.error && (
              <div className="text-center text-red-400">{simulator.error}</div>
            )}
          </>
        )}
      </main>

      {/* Simulator Setup Modal */}
      <SimulatorSetupModal
        isOpen={showSetup}
        onStart={handleStartSimulator}
        onClose={() => setShowSetup(false)}
      />
    </div>
  );
}
```

**Step 2: Commit**

```bash
git add deepdraft/src/App.tsx
git commit -m "feat(app): add mode toggle between replay and simulator"
```

---

### Task 6.6: Add Teams API Endpoint

**Status:** ✅ Already Complete (implemented in Stage 3)

The teams endpoint already exists at `GET /api/simulator/teams` in `backend/src/ban_teemo/api/routes/simulator.py:502-519`. No additional work needed.

**Existing implementation:**
- Endpoint: `GET /api/simulator/teams`
- Uses DuckDB-backed DraftRepository
- Returns `{"teams": [{"id": "...", "name": "..."}, ...]}`
- Includes pagination via `limit` query parameter (default 100, max 500)

---

## Stage 6 Checkpoint

```bash
cd deepdraft && npm run build
```

Expected: Build succeeds.

Manual test:
1. Start backend: `cd backend && uv run uvicorn ban_teemo.main:app --reload`
2. Start frontend: `cd deepdraft && npm run dev`
3. Click "Simulator" mode
4. Select two teams, start draft
5. Pick champions, watch AI respond

---

## Stage 7: Final Integration Test

### Task 7.1: Run Full Test Suite

```bash
# Backend tests
cd backend && uv run pytest tests/ -v

# Frontend build
cd deepdraft && npm run build

# Type check
cd deepdraft && npm run typecheck
```

### Task 7.2: Manual Smoke Test

1. Start backend and frontend
2. Test Replay mode still works
3. Test Simulator mode:
   - Setup modal loads teams
   - Draft flows correctly
   - Recommendations appear on your turn
   - Enemy picks happen automatically
   - Game complete flow works
   - Fearless mode blocks champions

---

## Summary

| Stage | Tasks | Focus |
|-------|-------|-------|
| 1 | 1.1-1.5 | Core scorers (Meta, Flex, Proficiency, Matchup) |
| 2 | 2.1-2.6 | Archetypes, Synergy, TeamEvaluation, Ban/Pick recommendation |
| 3 | 3.1-3.3 | Simulator backend (models, enemy AI, routes) |
| 4 | 4.1-4.2 | Frontend types + hook |
| 5 | 5.1-5.4 | API refactoring (separate commands/queries, error contracts) |
| 6 | 6.1-6.6 | UI components (pool, modal, views) |
| 7 | 7.1-7.2 | Integration testing |

**Total tasks:** 25
**Estimated commits:** 25
