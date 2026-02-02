# Smart Enemy Simulator Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make the enemy simulator use scoring/recommendation logic to make intelligent draft decisions, filtered to champions in their historical pool.

**Architecture:** Modify `EnemySimulatorService.generate_action()` to use `BanRecommendationService` and `PickRecommendationEngine` to get recommendations, then filter to champions that overlap with the enemy's historical champion pool (from `champion_weights`). Select randomly from top 3 overlapping recommendations.

**Tech Stack:** Python, pytest, FastAPI, existing scoring services

---

## Task 1: Add Recommendation Services to EnemySimulatorService

**Files:**
- Modify: `backend/src/ban_teemo/services/enemy_simulator_service.py:12-18`

**Step 1: Add imports and update constructor**

Add the recommendation service imports and update `__init__` to accept optional service instances (for dependency injection in tests).

```python
"""Generates enemy picks/bans from historical data."""

import random
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from ban_teemo.models.simulator import EnemyStrategy
from ban_teemo.models.draft import DraftAction
from ban_teemo.repositories.draft_repository import DraftRepository

if TYPE_CHECKING:
    from ban_teemo.services.ban_recommendation_service import BanRecommendationService
    from ban_teemo.services.pick_recommendation_engine import PickRecommendationEngine


class EnemySimulatorService:
    """Generates enemy picks/bans from historical data."""

    def __init__(
        self,
        database_path: Optional[str] = None,
        ban_service: Optional["BanRecommendationService"] = None,
        pick_engine: Optional["PickRecommendationEngine"] = None,
    ):
        if database_path is None:
            database_path = str(Path(__file__).parents[4] / "data" / "draft_data.duckdb")
        self.repo = DraftRepository(database_path)

        # Lazy-load recommendation services if not provided
        self._ban_service = ban_service
        self._pick_engine = pick_engine

    @property
    def ban_service(self) -> "BanRecommendationService":
        """Lazy-load ban recommendation service."""
        if self._ban_service is None:
            from ban_teemo.services.ban_recommendation_service import BanRecommendationService
            self._ban_service = BanRecommendationService(
                draft_repository=self.repo,
                simulator_mode=True,
            )
        return self._ban_service

    @property
    def pick_engine(self) -> "PickRecommendationEngine":
        """Lazy-load pick recommendation engine."""
        if self._pick_engine is None:
            from ban_teemo.services.pick_recommendation_engine import PickRecommendationEngine
            self._pick_engine = PickRecommendationEngine(simulator_mode=True)
        return self._pick_engine
```

**Step 2: Verify module imports work**

Run: `cd /workspaces/web-dev-playground/ban-teemo/backend && uv run python -c "from ban_teemo.services.enemy_simulator_service import EnemySimulatorService; print('OK')"`
Expected: OK

**Step 3: Commit**

```bash
git add backend/src/ban_teemo/services/enemy_simulator_service.py
git commit -m "feat(simulator): add recommendation services to EnemySimulatorService"
```

---

## Task 2: Add Draft Context to EnemyStrategy Model

**Files:**
- Modify: `backend/src/ban_teemo/models/simulator.py:12-22`

**Step 1: Add fields to EnemyStrategy for draft context**

The enemy needs to know draft state context to use recommendation services. Add fields for team info and roster.

```python
@dataclass
class EnemyStrategy:
    """Enemy team's draft strategy based on historical data."""

    reference_game_id: str
    draft_script: list[DraftAction]
    fallback_game_ids: list[str]
    champion_weights: dict[str, float]
    # Maps game_id -> team_side for filtering fallback actions correctly
    game_team_sides: dict[str, str] = field(default_factory=dict)
    current_script_index: int = 0

    # Team context for smart recommendations
    team_id: str = ""
    team_name: str = ""
    players: list[dict] = field(default_factory=list)  # List of {"name": str, "role": str}

    @property
    def champion_pool(self) -> set[str]:
        """Set of champions in the enemy's historical pool."""
        return set(self.champion_weights.keys())
```

**Step 2: Run existing tests to ensure no regression**

Run: `cd /workspaces/web-dev-playground/ban-teemo/backend && uv run pytest tests/test_enemy_simulator_service.py -v`
Expected: All tests pass

**Step 3: Commit**

```bash
git add backend/src/ban_teemo/models/simulator.py
git commit -m "feat(simulator): add team context fields to EnemyStrategy"
```

---

## Task 3: Update initialize_enemy_strategy to Populate Team Context

**Files:**
- Modify: `backend/src/ban_teemo/services/enemy_simulator_service.py` (the `initialize_enemy_strategy` method)

**Step 1: Update method to accept team context and populate EnemyStrategy fields**

Modify `initialize_enemy_strategy` to look up roster and populate the new fields.

```python
def initialize_enemy_strategy(self, enemy_team_id: str) -> EnemyStrategy:
    """Load reference game, fallbacks, and champion weights."""
    games = self.repo.get_team_games(enemy_team_id, limit=20)
    if not games:
        raise ValueError(f"No games found for team {enemy_team_id}")

    reference = random.choice(games)
    fallbacks = [g for g in games if g["game_id"] != reference["game_id"]]

    # Load draft actions for reference game
    draft_actions_raw = self.repo.get_draft_actions(reference["game_id"])

    # Convert dict results to DraftAction if needed
    draft_actions = []
    for a in draft_actions_raw:
        if isinstance(a, DraftAction):
            draft_actions.append(a)
        else:
            draft_actions.append(
                DraftAction(
                    sequence=int(a["sequence"]),
                    action_type=a["action_type"],
                    team_side=a["team_side"],
                    champion_id=a["champion_id"],
                    champion_name=a["champion_name"],
                )
            )

    # Determine which side the enemy team was on in this game
    team_side = reference.get("team_side")
    if not team_side:
        # Fallback: check if team is blue_team_id
        if reference.get("blue_team_id") == enemy_team_id:
            team_side = "blue"
        else:
            team_side = "red"

    # Filter to enemy team's actions only
    enemy_actions = [a for a in draft_actions if a.team_side == team_side]

    # Build champion weights from all games
    weights = self._build_champion_weights(enemy_team_id, games)

    # Build game_id -> team_side mapping for all games (needed for fallback filtering)
    game_team_sides = {}
    for game in games:
        game_side = game.get("team_side")
        if not game_side:
            if game.get("blue_team_id") == enemy_team_id:
                game_side = "blue"
            else:
                game_side = "red"
        game_team_sides[game["game_id"]] = game_side

    # Load team info and roster for smart recommendations
    team_info = self.repo.get_team_with_name(enemy_team_id)
    team_name = team_info["name"] if team_info else ""

    roster = self.repo.get_team_roster(enemy_team_id)
    players = [
        {"name": p["player_name"], "role": p["role"]}
        for p in roster
    ] if roster else []

    return EnemyStrategy(
        reference_game_id=reference["game_id"],
        draft_script=enemy_actions,
        fallback_game_ids=[g["game_id"] for g in fallbacks],
        champion_weights=weights,
        game_team_sides=game_team_sides,
        team_id=enemy_team_id,
        team_name=team_name,
        players=players,
    )
```

**Step 2: Run existing tests**

Run: `cd /workspaces/web-dev-playground/ban-teemo/backend && uv run pytest tests/test_enemy_simulator_service.py -v`
Expected: All tests pass

**Step 3: Commit**

```bash
git add backend/src/ban_teemo/services/enemy_simulator_service.py
git commit -m "feat(simulator): populate team context in initialize_enemy_strategy"
```

---

## Task 4: Write Tests for Smart Enemy Action Generation

**Files:**
- Modify: `backend/tests/test_enemy_simulator_service.py`

**Step 1: Add test for ban recommendation filtering**

```python
def test_generate_smart_ban_uses_recommendations_filtered_by_pool(service, mock_repository):
    """Smart ban should use recommendation service filtered to champion pool."""
    # Force game1 as reference
    with patch("random.choice", return_value=mock_repository.get_team_games.return_value[0]):
        strategy = service.initialize_enemy_strategy("oe:team:test")

    # Add team context for recommendations
    strategy.team_id = "oe:team:test"
    strategy.team_name = "Test Team"
    strategy.players = [{"name": "Player1", "role": "mid"}]

    # Mock ban service to return recommendations
    mock_ban_service = MagicMock()
    mock_ban_service.get_ban_recommendations.return_value = [
        {"champion_name": "Azir", "priority": 0.9},  # In pool (from game1)
        {"champion_name": "NotInPool", "priority": 0.85},  # Not in pool
        {"champion_name": "Kai'Sa", "priority": 0.8},  # In pool (from game1)
    ]
    service._ban_service = mock_ban_service

    # Generate smart ban action
    champion, source = service.generate_smart_action(
        strategy=strategy,
        action_type="ban",
        our_picks=[],
        enemy_picks=[],
        banned=[],
        unavailable=set(),
    )

    # Should pick from pool champions that are in top recommendations
    assert champion in strategy.champion_pool
    assert source == "smart_recommendation"


def test_generate_smart_pick_uses_recommendations_filtered_by_pool(service, mock_repository):
    """Smart pick should use recommendation service filtered to champion pool."""
    with patch("random.choice", return_value=mock_repository.get_team_games.return_value[0]):
        strategy = service.initialize_enemy_strategy("oe:team:test")

    strategy.team_id = "oe:team:test"
    strategy.team_name = "Test Team"
    strategy.players = [{"name": "Player1", "role": "mid"}]

    # Mock pick engine to return recommendations
    mock_pick_engine = MagicMock()
    mock_pick_engine.get_recommendations.return_value = [
        {"champion_name": "Kai'Sa", "score": 0.9, "suggested_role": "bot"},  # In pool
        {"champion_name": "NotInPool", "score": 0.85, "suggested_role": "mid"},
        {"champion_name": "Varus", "score": 0.8, "suggested_role": "bot"},  # In pool (from game2)
    ]
    service._pick_engine = mock_pick_engine

    champion, source = service.generate_smart_action(
        strategy=strategy,
        action_type="pick",
        our_picks=[],
        enemy_picks=[],
        banned=[],
        unavailable=set(),
    )

    assert champion in strategy.champion_pool
    assert source == "smart_recommendation"


def test_generate_smart_action_falls_back_when_no_pool_overlap(service, mock_repository):
    """Should fall back to legacy behavior when no recommendations overlap with pool."""
    with patch("random.choice", return_value=mock_repository.get_team_games.return_value[0]):
        strategy = service.initialize_enemy_strategy("oe:team:test")

    strategy.players = [{"name": "Player1", "role": "mid"}]

    # Mock ban service with no pool overlap
    mock_ban_service = MagicMock()
    mock_ban_service.get_ban_recommendations.return_value = [
        {"champion_name": "NotInPool1", "priority": 0.9},
        {"champion_name": "NotInPool2", "priority": 0.85},
    ]
    service._ban_service = mock_ban_service

    champion, source = service.generate_smart_action(
        strategy=strategy,
        action_type="ban",
        our_picks=[],
        enemy_picks=[],
        banned=[],
        unavailable=set(),
    )

    # Should fall back to legacy generation
    assert champion is not None
    assert source in ["reference_game", "fallback_game", "weighted_random"]
```

**Step 2: Run test to verify it fails (TDD)**

Run: `cd /workspaces/web-dev-playground/ban-teemo/backend && uv run pytest tests/test_enemy_simulator_service.py::test_generate_smart_ban_uses_recommendations_filtered_by_pool -v`
Expected: FAIL with AttributeError (generate_smart_action doesn't exist)

**Step 3: Commit test**

```bash
git add backend/tests/test_enemy_simulator_service.py
git commit -m "test(simulator): add tests for smart enemy action generation"
```

---

## Task 5: Implement generate_smart_action Method

**Files:**
- Modify: `backend/src/ban_teemo/services/enemy_simulator_service.py`

**Step 1: Add the generate_smart_action method**

Add this method after `generate_action`:

```python
def generate_smart_action(
    self,
    strategy: EnemyStrategy,
    action_type: str,  # "ban" or "pick"
    our_picks: list[str],
    enemy_picks: list[str],
    banned: list[str],
    unavailable: set[str],
) -> tuple[str, str]:
    """Generate enemy action using recommendation services filtered by champion pool.

    Uses the same scoring logic as user recommendations, but filtered to champions
    the enemy team has historically played. Selects randomly from top 3 overlapping
    recommendations for variety.

    Falls back to legacy generate_action if no recommendations overlap with pool.

    Args:
        strategy: Enemy's draft strategy with champion pool
        action_type: "ban" or "pick"
        our_picks: Enemy's picks so far (from their perspective)
        enemy_picks: User's picks (enemy to them)
        banned: All banned champions
        unavailable: Set of unavailable champions (picked, banned, fearless)

    Returns:
        Tuple of (champion_name, source) where source indicates selection method
    """
    pool = strategy.champion_pool - unavailable

    if not pool:
        # No champions in pool available, fall back to legacy
        return self.generate_action(strategy, sequence=1, unavailable=unavailable)

    if action_type == "ban":
        recommendations = self._get_smart_ban_recommendations(
            strategy, our_picks, enemy_picks, banned
        )
    else:
        recommendations = self._get_smart_pick_recommendations(
            strategy, our_picks, enemy_picks, banned
        )

    # Filter recommendations to champions in pool and available
    pool_recommendations = [
        r for r in recommendations
        if r["champion_name"] in pool
    ]

    if not pool_recommendations:
        # No overlap with pool, fall back to legacy generation
        # Calculate sequence based on action count
        sequence = len(banned) + len(our_picks) + len(enemy_picks) + 1
        return self.generate_action(strategy, sequence=sequence, unavailable=unavailable)

    # Select randomly from top 3 for variety (avoid being too predictable)
    top_n = min(3, len(pool_recommendations))
    selected = random.choice(pool_recommendations[:top_n])

    return selected["champion_name"], "smart_recommendation"

def _get_smart_ban_recommendations(
    self,
    strategy: EnemyStrategy,
    our_picks: list[str],
    enemy_picks: list[str],
    banned: list[str],
) -> list[dict]:
    """Get ban recommendations from enemy's perspective."""
    # Determine phase based on ban count
    ban_count = len(banned)
    phase = "BAN_PHASE_1" if ban_count < 6 else "BAN_PHASE_2"

    # Get recommendations - note: from enemy's perspective:
    # - "our_picks" = enemy team's picks (the simulator's team)
    # - "enemy_picks" = user's team's picks (enemy to the simulator)
    # - enemy_team_id = user's team (who enemy wants to target)
    # But we don't have user's team_id easily, so we pass empty and rely on meta
    return self.ban_service.get_ban_recommendations(
        enemy_team_id="",  # Will use global meta bans
        our_picks=our_picks,
        enemy_picks=enemy_picks,
        banned=banned,
        phase=phase,
        enemy_players=None,  # Will use global meta
        limit=10,
    )

def _get_smart_pick_recommendations(
    self,
    strategy: EnemyStrategy,
    our_picks: list[str],
    enemy_picks: list[str],
    banned: list[str],
) -> list[dict]:
    """Get pick recommendations from enemy's perspective."""
    return self.pick_engine.get_recommendations(
        team_players=strategy.players,
        our_picks=our_picks,
        enemy_picks=enemy_picks,
        banned=banned,
        limit=10,
    )
```

**Step 2: Run tests**

Run: `cd /workspaces/web-dev-playground/ban-teemo/backend && uv run pytest tests/test_enemy_simulator_service.py -v`
Expected: All tests pass

**Step 3: Commit**

```bash
git add backend/src/ban_teemo/services/enemy_simulator_service.py
git commit -m "feat(simulator): implement generate_smart_action with pool filtering"
```

---

## Task 6: Update trigger_enemy_action Route to Use Smart Actions

**Files:**
- Modify: `backend/src/ban_teemo/api/routes/simulator.py:279-326`

**Step 1: Update the route to call generate_smart_action**

The route needs to pass draft context to enable smart recommendations.

```python
@router.post("/sessions/{session_id}/actions/enemy")
async def trigger_enemy_action(
    request: Request,
    session_id: str,
    include_recommendations: bool = False,
    include_evaluation: bool = False,
):
    """Triggers enemy pick/ban generation."""
    session, lock = _get_session_with_lock(session_id)
    with lock:
        now = time.time()
        if _is_session_expired(session, now):
            raise HTTPException(status_code=404, detail="Session expired")
        _touch_session(session, now)

        draft_state = session.draft_state

        if draft_state.next_team == session.coaching_side:
            raise HTTPException(status_code=400, detail="Not enemy's turn")

        enemy_service, _, _, _, _ = _get_or_create_services(request)

        # Get unavailable champions
        unavailable = set(
            draft_state.blue_bans + draft_state.red_bans +
            draft_state.blue_picks + draft_state.red_picks
        ) | session.fearless_blocked_set

        # Determine picks from enemy's perspective
        enemy_side = session.enemy_side
        if enemy_side == "blue":
            enemy_picks = list(draft_state.blue_picks)  # Enemy's picks
            our_picks = list(draft_state.red_picks)      # User's picks (enemy to them)
        else:
            enemy_picks = list(draft_state.red_picks)
            our_picks = list(draft_state.blue_picks)

        banned = list(draft_state.blue_bans + draft_state.red_bans)

        # Generate smart enemy action using recommendation services
        champion, source = enemy_service.generate_smart_action(
            strategy=session.enemy_strategy,
            action_type=draft_state.next_action,
            our_picks=enemy_picks,  # Enemy's own picks
            enemy_picks=our_picks,   # User's picks (enemy to them)
            banned=banned,
            unavailable=unavailable,
        )

        action = DraftAction(
            sequence=len(draft_state.actions) + 1,
            action_type=draft_state.next_action,
            team_side=draft_state.next_team,
            champion_id=champion.lower().replace(" ", ""),
            champion_name=champion,
        )

        _apply_action(session, action)

        response = _build_response(request, session, include_recommendations, include_evaluation)
        response["source"] = source
        return response
```

**Step 2: Run integration test**

Run: `cd /workspaces/web-dev-playground/ban-teemo/backend && uv run pytest tests/test_simulator_routes.py -v -k enemy`
Expected: Tests pass (if tests exist) or no errors on import

**Step 3: Commit**

```bash
git add backend/src/ban_teemo/api/routes/simulator.py
git commit -m "feat(simulator): use smart enemy actions in API route"
```

---

## Task 7: Add Integration Tests for Smart Enemy in API

**Files:**
- Modify: `backend/tests/test_simulator_routes.py` (or create if doesn't exist)

**Step 1: Check if test file exists and add integration test**

First check if the file exists, then add appropriate tests.

```python
# Add to existing test file or create new one

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

# ... existing imports and fixtures ...

def test_enemy_action_uses_smart_recommendations(client, mock_services):
    """Enemy actions should use smart recommendations filtered by pool."""
    # Create session
    response = client.post("/api/simulator/sessions", json={
        "blue_team_id": "test_blue",
        "red_team_id": "test_red",
        "coaching_side": "blue",
    })
    session_id = response.json()["session_id"]

    # Submit user's first ban
    client.post(f"/api/simulator/sessions/{session_id}/actions", json={
        "champion": "Azir"
    })

    # Trigger enemy action
    response = client.post(f"/api/simulator/sessions/{session_id}/actions/enemy")
    data = response.json()

    # Should have a source indicating the selection method
    assert "source" in data
    assert data["source"] in ["smart_recommendation", "reference_game", "fallback_game", "weighted_random"]
```

**Step 2: Run test**

Run: `cd /workspaces/web-dev-playground/ban-teemo/backend && uv run pytest tests/test_simulator_routes.py -v -k smart` (if exists)
Expected: Test passes

**Step 3: Commit**

```bash
git add backend/tests/
git commit -m "test(simulator): add integration test for smart enemy actions"
```

---

## Task 8: Final Verification and Cleanup

**Step 1: Run full test suite**

Run: `cd /workspaces/web-dev-playground/ban-teemo/backend && uv run pytest tests/ -v --tb=short`
Expected: All tests pass

**Step 2: Manual testing with actual API**

Start the server and test manually:
```bash
cd /workspaces/web-dev-playground/ban-teemo/backend
uv run uvicorn ban_teemo.api.main:app --reload
```

Then test with curl or the frontend to verify enemy actions are smarter.

**Step 3: Final commit**

```bash
git add -A
git commit -m "feat(simulator): complete smart enemy action implementation

Enemy simulator now uses the same scoring/recommendation logic as user guidance:
- BanRecommendationService for ban decisions
- PickRecommendationEngine for pick decisions
- Filtered to champions in enemy's historical pool
- Selects randomly from top 3 overlapping recommendations for variety
- Falls back to legacy script-based approach when no overlap"
```

---

## Summary

This implementation:
1. Adds recommendation services to `EnemySimulatorService` via lazy loading
2. Extends `EnemyStrategy` model with team context (ID, name, players)
3. Populates team context during strategy initialization
4. Implements `generate_smart_action()` that:
   - Gets recommendations from ban/pick services
   - Filters to champions in the enemy's historical pool
   - Selects randomly from top 3 for variety
   - Falls back to legacy generation if no overlap
5. Updates the API route to use smart actions
6. Maintains backward compatibility (legacy `generate_action` still works)
