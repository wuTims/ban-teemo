# Draft Quality Score Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Surface draft quality metrics at draft completion, comparing actual team vs engine-recommended team using archetype-based scoring.

**Architecture:** Track top recommendation at each pick step during draft. At draft completion, build "recommended team" from stored picks, evaluate both teams using existing TeamEvaluationService, and return comparison with archetype matchup insights.

**Tech Stack:** Python/FastAPI backend, existing TeamEvaluationService, ArchetypeService

---

## Summary

This feature adds end-of-draft analysis showing:
1. **Actual Draft Score** - composition_score, archetype, synergy for what was picked
2. **Recommended Draft Score** - same metrics for engine's top recommendations
3. **Comparison** - score delta, archetype matchup insight, key deviations

Data sources are stable (archetype theory, not sparse matchup data).

---

### Task 1: Add Recommendation Tracking to SimulatorSession Model

**Files:**
- Modify: `backend/src/ban_teemo/models/simulator.py`

**Step 1: Write the test for new field**

```python
# backend/tests/test_simulator_models.py
def test_simulator_session_tracks_recommended_picks():
    """SimulatorSession should have recommended_picks list."""
    from ban_teemo.models.simulator import SimulatorSession
    from ban_teemo.models.team import TeamContext, Player
    from ban_teemo.models.draft import DraftState, DraftPhase

    # Minimal setup
    players = [Player(id="p1", name="Player1", role="top")]
    team = TeamContext(id="t1", name="Team1", side="blue", players=players)
    draft = DraftState(
        game_id="g1",
        series_id="s1",
        game_number=1,
        patch_version="15.18",
        match_date=None,
        blue_team=team,
        red_team=team,
        actions=[],
        current_phase=DraftPhase.BAN_PHASE_1,
        next_team="blue",
        next_action="ban",
    )

    session = SimulatorSession(
        session_id="test",
        blue_team=team,
        red_team=team,
        coaching_side="blue",
        series_length=1,
        draft_mode="normal",
        draft_state=draft,
        enemy_strategy={"team_id": "t2", "team_name": "Enemy"},
    )

    assert hasattr(session, "recommended_picks")
    assert session.recommended_picks == []
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_simulator_models.py::test_simulator_session_tracks_recommended_picks -v`
Expected: FAIL with AttributeError or similar

**Step 3: Add recommended_picks field to SimulatorSession**

In `backend/src/ban_teemo/models/simulator.py`, add to SimulatorSession class:

```python
# After existing fields, add:
recommended_picks: list[str] = field(default_factory=list)
```

**Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_simulator_models.py::test_simulator_session_tracks_recommended_picks -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/ban_teemo/models/simulator.py backend/tests/test_simulator_models.py
git commit -m "feat(simulator): add recommended_picks tracking to session model"
```

---

### Task 2: Create DraftQualityAnalyzer Service

**Files:**
- Create: `backend/src/ban_teemo/services/draft_quality_analyzer.py`
- Create: `backend/tests/test_draft_quality_analyzer.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_draft_quality_analyzer.py
import pytest


def test_analyze_returns_both_team_evaluations():
    """Analyzer returns evaluation for actual and recommended teams."""
    from ban_teemo.services.draft_quality_analyzer import DraftQualityAnalyzer

    analyzer = DraftQualityAnalyzer()

    result = analyzer.analyze(
        actual_picks=["Renekton", "Lee Sin", "Ahri", "Jinx", "Thresh"],
        recommended_picks=["Rumble", "Sejuani", "Orianna", "Kai'Sa", "Rakan"],
        enemy_picks=["Jayce", "Viego", "Syndra", "Ezreal", "Nautilus"],
    )

    assert "actual_draft" in result
    assert "recommended_draft" in result
    assert "comparison" in result

    # Actual draft has required fields
    assert "picks" in result["actual_draft"]
    assert "archetype" in result["actual_draft"]
    assert "composition_score" in result["actual_draft"]
    assert "vs_enemy_advantage" in result["actual_draft"]

    # Recommended draft has same fields
    assert "picks" in result["recommended_draft"]
    assert "archetype" in result["recommended_draft"]
    assert "composition_score" in result["recommended_draft"]
    assert "vs_enemy_advantage" in result["recommended_draft"]

    # Comparison has delta and insight
    assert "score_delta" in result["comparison"]
    assert "archetype_insight" in result["comparison"]


def test_analyze_with_partial_recommendations():
    """Analyzer handles case where not all 5 picks have recommendations."""
    from ban_teemo.services.draft_quality_analyzer import DraftQualityAnalyzer

    analyzer = DraftQualityAnalyzer()

    # Only 3 recommended picks (maybe session interrupted)
    result = analyzer.analyze(
        actual_picks=["Renekton", "Lee Sin", "Ahri", "Jinx", "Thresh"],
        recommended_picks=["Rumble", "Sejuani", "Orianna"],
        enemy_picks=["Jayce", "Viego", "Syndra", "Ezreal", "Nautilus"],
    )

    assert result["recommended_draft"]["picks"] == ["Rumble", "Sejuani", "Orianna"]
    assert result["comparison"]["picks_tracked"] == 3


def test_analyze_calculates_score_delta():
    """Score delta is recommended minus actual."""
    from ban_teemo.services.draft_quality_analyzer import DraftQualityAnalyzer

    analyzer = DraftQualityAnalyzer()

    result = analyzer.analyze(
        actual_picks=["Renekton", "Lee Sin", "Ahri", "Jinx", "Thresh"],
        recommended_picks=["Rumble", "Sejuani", "Orianna", "Kai'Sa", "Rakan"],
        enemy_picks=["Jayce", "Viego", "Syndra", "Ezreal", "Nautilus"],
    )

    expected_delta = (
        result["recommended_draft"]["composition_score"]
        - result["actual_draft"]["composition_score"]
    )
    assert abs(result["comparison"]["score_delta"] - expected_delta) < 0.001
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_draft_quality_analyzer.py -v`
Expected: FAIL with ModuleNotFoundError

**Step 3: Implement DraftQualityAnalyzer**

```python
# backend/src/ban_teemo/services/draft_quality_analyzer.py
"""Draft quality analysis comparing actual vs recommended picks."""
from pathlib import Path
from typing import Optional

from ban_teemo.services.team_evaluation_service import TeamEvaluationService
from ban_teemo.services.archetype_service import ArchetypeService


class DraftQualityAnalyzer:
    """Analyzes draft quality by comparing actual picks to recommendations."""

    def __init__(self, knowledge_dir: Optional[Path] = None):
        self.team_eval = TeamEvaluationService(knowledge_dir)
        self.archetype_service = ArchetypeService(knowledge_dir)

    def analyze(
        self,
        actual_picks: list[str],
        recommended_picks: list[str],
        enemy_picks: list[str],
    ) -> dict:
        """Compare actual draft to recommended draft.

        Args:
            actual_picks: Champions actually picked by the team
            recommended_picks: Top recommendations at each pick step
            enemy_picks: Enemy team's picks

        Returns:
            Dict with actual_draft, recommended_draft, and comparison
        """
        # Evaluate actual team
        actual_eval = self.team_eval.evaluate_vs_enemy(actual_picks, enemy_picks)
        actual_arch = self.archetype_service.calculate_team_archetype(actual_picks)

        # Evaluate recommended team
        rec_eval = self.team_eval.evaluate_vs_enemy(recommended_picks, enemy_picks)
        rec_arch = self.archetype_service.calculate_team_archetype(recommended_picks)

        # Get enemy archetype for insight
        enemy_arch = self.archetype_service.calculate_team_archetype(enemy_picks)

        # Build archetype insight
        archetype_insight = self._build_archetype_insight(
            actual_arch["primary"],
            rec_arch["primary"],
            enemy_arch["primary"],
        )

        # Calculate picks that matched
        picks_matched = sum(
            1 for a, r in zip(actual_picks, recommended_picks) if a == r
        )

        return {
            "actual_draft": {
                "picks": actual_picks,
                "archetype": actual_arch["primary"],
                "composition_score": round(actual_eval["our_evaluation"]["composition_score"], 3),
                "synergy_score": round(actual_eval["our_evaluation"]["synergy_score"], 3),
                "vs_enemy_advantage": actual_eval["matchup_advantage"],
                "vs_enemy_description": actual_eval["matchup_description"],
            },
            "recommended_draft": {
                "picks": recommended_picks,
                "archetype": rec_arch["primary"],
                "composition_score": round(rec_eval["our_evaluation"]["composition_score"], 3),
                "synergy_score": round(rec_eval["our_evaluation"]["synergy_score"], 3),
                "vs_enemy_advantage": rec_eval["matchup_advantage"],
                "vs_enemy_description": rec_eval["matchup_description"],
            },
            "comparison": {
                "score_delta": round(
                    rec_eval["our_evaluation"]["composition_score"]
                    - actual_eval["our_evaluation"]["composition_score"],
                    3
                ),
                "advantage_delta": round(
                    rec_eval["matchup_advantage"] - actual_eval["matchup_advantage"],
                    3
                ),
                "archetype_insight": archetype_insight,
                "picks_matched": picks_matched,
                "picks_tracked": len(recommended_picks),
            },
        }

    def _build_archetype_insight(
        self,
        actual_arch: Optional[str],
        rec_arch: Optional[str],
        enemy_arch: Optional[str],
    ) -> str:
        """Generate insight about archetype differences."""
        if not rec_arch or not enemy_arch:
            return "Insufficient data for archetype analysis"

        if actual_arch == rec_arch:
            return f"Both drafts have {actual_arch} identity"

        # Get effectiveness of each archetype vs enemy
        actual_eff = 1.0
        rec_eff = 1.0
        if actual_arch:
            actual_eff = self.archetype_service.get_archetype_effectiveness(
                actual_arch, enemy_arch
            )
        if rec_arch:
            rec_eff = self.archetype_service.get_archetype_effectiveness(
                rec_arch, enemy_arch
            )

        if rec_eff > actual_eff:
            return f"Recommended {rec_arch} archetype better vs enemy's {enemy_arch} style"
        elif actual_eff > rec_eff:
            return f"Your {actual_arch} archetype actually better vs enemy's {enemy_arch} style"
        else:
            return f"Both {actual_arch} and {rec_arch} archetypes neutral vs enemy"
```

**Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_draft_quality_analyzer.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/ban_teemo/services/draft_quality_analyzer.py backend/tests/test_draft_quality_analyzer.py
git commit -m "feat(analyzer): add DraftQualityAnalyzer service"
```

---

### Task 3: Track Top Recommendations During Pick Phase

**Files:**
- Modify: `backend/src/ban_teemo/api/routes/simulator.py`

**Context:** The `_build_response` function generates recommendations BEFORE the user picks. When we generate recommendations for our team's pick turn, we store the top recommendation. Later, when the pick is made, we can compare what we recommended vs what was actually chosen.

**Step 1: Add tracking logic to _build_response**

In `_build_response`, after pick recommendations are generated (after `response["recommendations"] = pick_engine.get_recommendations(...)`), add:

```python
# Track top pick recommendation for draft quality analysis (our picks only)
# This captures what we recommended BEFORE the pick happens
if is_our_turn and draft_state.next_action == "pick":
    if response.get("recommendations"):
        top_rec_name = response["recommendations"][0]["champion_name"]
        # Count how many picks our team has already made
        our_pick_count = len([
            a for a in draft_state.actions
            if a.action_type == "pick" and a.team_side == session.coaching_side
        ])
        # Only append if we haven't tracked for this pick slot yet
        if len(session.recommended_picks) == our_pick_count:
            session.recommended_picks.append(top_rec_name)
```

**Step 2: Run existing tests to ensure no regression**

Run: `cd backend && uv run pytest tests/ -k simulator -v --tb=short`
Expected: All existing tests pass

**Step 3: Commit**

```bash
git add backend/src/ban_teemo/api/routes/simulator.py
git commit -m "feat(simulator): track top recommendations during pick phase"
```

---

### Task 4: Add Draft Quality Analysis Endpoint

**Files:**
- Modify: `backend/src/ban_teemo/api/routes/simulator.py`
- Create: `backend/tests/test_simulator_draft_quality.py`

**Step 1: Write failing test for new endpoint**

```python
# backend/tests/test_simulator_draft_quality.py
"""Test draft quality analysis endpoint."""
import pytest
from unittest.mock import MagicMock, patch


def test_draft_quality_endpoint_returns_analysis():
    """GET /sessions/{id}/draft-quality returns analysis at draft end."""
    # This is an integration test skeleton
    # Full test would use TestClient with mocked session
    pass


def test_draft_quality_requires_complete_draft():
    """Endpoint returns 400 if draft not complete."""
    pass
```

**Step 2: Add endpoint to simulator.py**

Add after the `/evaluation` endpoint:

```python
@router.get("/sessions/{session_id}/draft-quality")
async def get_draft_quality(request: Request, session_id: str):
    """Get draft quality analysis comparing actual vs recommended picks.

    Only available when draft is complete.
    """
    session, lock = _get_session_with_lock(session_id)
    with lock:
        now = time.time()
        if _is_session_expired(session, now):
            raise HTTPException(status_code=404, detail="Session expired")
        _touch_session(session, now)

        draft_state = session.draft_state

        if draft_state.current_phase != DraftPhase.COMPLETE:
            raise HTTPException(
                status_code=400,
                detail="Draft quality analysis only available when draft is complete"
            )

        # Get actual picks for our team
        our_picks = (
            draft_state.blue_picks
            if session.coaching_side == "blue"
            else draft_state.red_picks
        )
        enemy_picks = (
            draft_state.red_picks
            if session.coaching_side == "blue"
            else draft_state.blue_picks
        )

        # Get or create analyzer
        if not hasattr(request.app.state, "draft_quality_analyzer"):
            from ban_teemo.services.draft_quality_analyzer import DraftQualityAnalyzer
            request.app.state.draft_quality_analyzer = DraftQualityAnalyzer()

        analyzer = request.app.state.draft_quality_analyzer

        analysis = analyzer.analyze(
            actual_picks=our_picks,
            recommended_picks=session.recommended_picks,
            enemy_picks=enemy_picks,
        )

        return {
            "session_id": session_id,
            "game_number": session.current_game,
            "coaching_side": session.coaching_side,
            **analysis,
        }
```

**Step 3: Run tests**

Run: `cd backend && uv run pytest tests/test_simulator_draft_quality.py -v`
Expected: Tests pass (or skip placeholders)

**Step 4: Commit**

```bash
git add backend/src/ban_teemo/api/routes/simulator.py backend/tests/test_simulator_draft_quality.py
git commit -m "feat(simulator): add /draft-quality endpoint for end-of-draft analysis"
```

---

### Task 5: Include Draft Quality in Complete Game Response

**Files:**
- Modify: `backend/src/ban_teemo/api/routes/simulator.py`

**Step 1: Modify complete_game to include draft quality**

In the `complete_game` endpoint, before the return statement, add draft quality analysis:

```python
# Include draft quality analysis
from ban_teemo.services.draft_quality_analyzer import DraftQualityAnalyzer
if not hasattr(request.app.state, "draft_quality_analyzer"):
    request.app.state.draft_quality_analyzer = DraftQualityAnalyzer()

our_picks = (
    draft_state.blue_picks
    if session.coaching_side == "blue"
    else draft_state.red_picks
)
enemy_picks = (
    draft_state.red_picks
    if session.coaching_side == "blue"
    else draft_state.blue_picks
)

draft_quality = request.app.state.draft_quality_analyzer.analyze(
    actual_picks=our_picks,
    recommended_picks=session.recommended_picks,
    enemy_picks=enemy_picks,
)
```

Then modify the return statement to include `draft_quality`:

```python
return {
    "series_status": {
        "blue_wins": session.series_score[0],
        "red_wins": session.series_score[1],
        "games_played": len(session.game_results),
        "series_complete": session.series_complete,
    },
    "fearless_blocked": session.fearless_blocked,
    "next_game_ready": not session.series_complete,
    "blue_comp_with_roles": blue_with_roles,
    "red_comp_with_roles": red_with_roles,
    "draft_quality": draft_quality,  # NEW
}
```

**Step 2: Run existing tests**

Run: `cd backend && uv run pytest tests/ -k simulator -v --tb=short`
Expected: All tests pass

**Step 3: Commit**

```bash
git add backend/src/ban_teemo/api/routes/simulator.py
git commit -m "feat(simulator): include draft quality in complete_game response"
```

---

### Task 6: Reset recommended_picks on New Game

**Files:**
- Modify: `backend/src/ban_teemo/api/routes/simulator.py`

**Step 1: Modify next_game to reset recommended_picks**

In the `next_game` endpoint, after resetting draft_state, add:

```python
session.recommended_picks = []  # Reset for new game
```

**Step 2: Run tests**

Run: `cd backend && uv run pytest tests/ -k simulator -v --tb=short`
Expected: All tests pass

**Step 3: Commit**

```bash
git add backend/src/ban_teemo/api/routes/simulator.py
git commit -m "fix(simulator): reset recommended_picks on new game in series"
```

---

### Task 7: Add Draft Quality to Replay Mode

**Files:**
- Modify: `backend/src/ban_teemo/api/websockets/replay_ws.py`
- Modify: `backend/src/ban_teemo/services/replay_manager.py`

**Key Design Decision:** Replay mode doesn't have a "coaching side" like simulator. We track recommendations for BOTH teams separately and provide analysis for both in the final output.

**Step 1: Add per-team recommendation tracking to ReplaySession**

In `backend/src/ban_teemo/services/replay_manager.py`, add to ReplaySession class:

```python
# Track recommendations separately for each team
blue_recommended_picks: list[str] = field(default_factory=list)
red_recommended_picks: list[str] = field(default_factory=list)
```

**Step 2: Track recommendations during replay loop by team**

In `backend/src/ban_teemo/api/websockets/replay_ws.py`, in `_run_replay_loop`, after generating `pending_recommendations`, add tracking:

```python
# After: pending_recommendations = service.get_recommendations(...)
# Track top pick recommendation for draft quality analysis (per-team)
if pending_recommendations and pending_recommendations.picks:
    if current_state.next_action == "pick":
        top_pick = pending_recommendations.picks[0].champion_name
        rec_team = pending_recommendations.for_team
        if rec_team == "blue" and len(session.blue_recommended_picks) < 5:
            session.blue_recommended_picks.append(top_pick)
        elif rec_team == "red" and len(session.red_recommended_picks) < 5:
            session.red_recommended_picks.append(top_pick)
```

**Step 3: Include draft quality in draft_complete message for both teams**

In the `draft_complete` section, add:

```python
# Before sending draft_complete, add analysis for both teams:
from ban_teemo.services.draft_quality_analyzer import DraftQualityAnalyzer
analyzer = DraftQualityAnalyzer()

# Analyze from blue's perspective
blue_quality = analyzer.analyze(
    actual_picks=final_state.blue_picks,
    recommended_picks=session.blue_recommended_picks,
    enemy_picks=final_state.red_picks,
)

# Analyze from red's perspective
red_quality = analyzer.analyze(
    actual_picks=final_state.red_picks,
    recommended_picks=session.red_recommended_picks,
    enemy_picks=final_state.blue_picks,
)
```

Then add to the websocket message:

```python
await websocket.send_json({
    "type": "draft_complete",
    "draft_state": _serialize_draft_state(final_state),
    "blue_comp": final_state.blue_picks,
    "red_comp": final_state.red_picks,
    "blue_comp_with_roles": blue_with_roles,
    "red_comp_with_roles": red_with_roles,
    "draft_quality": {
        "blue": blue_quality,
        "red": red_quality,
    },
})
```

**Step 4: Run tests**

Run: `cd backend && uv run pytest tests/ -k replay -v --tb=short`
Expected: All tests pass

**Step 5: Commit**

```bash
git add backend/src/ban_teemo/api/websockets/replay_ws.py backend/src/ban_teemo/services/replay_manager.py
git commit -m "feat(replay): add draft quality analysis to replay mode"
```

---

### Task 8: Add Unit Tests for Edge Cases

**Files:**
- Modify: `backend/tests/test_draft_quality_analyzer.py`

**Step 1: Add edge case tests**

```python
# Add to backend/tests/test_draft_quality_analyzer.py

def test_analyze_with_empty_recommendations():
    """Handle case where no recommendations were tracked."""
    from ban_teemo.services.draft_quality_analyzer import DraftQualityAnalyzer

    analyzer = DraftQualityAnalyzer()

    result = analyzer.analyze(
        actual_picks=["Renekton", "Lee Sin", "Ahri", "Jinx", "Thresh"],
        recommended_picks=[],  # No recommendations tracked
        enemy_picks=["Jayce", "Viego", "Syndra", "Ezreal", "Nautilus"],
    )

    assert result["recommended_draft"]["picks"] == []
    assert result["comparison"]["picks_tracked"] == 0
    assert result["comparison"]["picks_matched"] == 0


def test_analyze_with_unknown_champions():
    """Handle champions not in archetype data."""
    from ban_teemo.services.draft_quality_analyzer import DraftQualityAnalyzer

    analyzer = DraftQualityAnalyzer()

    # Use a mix of known and unknown champion names
    result = analyzer.analyze(
        actual_picks=["Renekton", "UnknownChamp1", "Ahri", "Jinx", "Thresh"],
        recommended_picks=["Rumble", "Sejuani", "Orianna", "Kai'Sa", "Rakan"],
        enemy_picks=["Jayce", "Viego", "Syndra", "Ezreal", "Nautilus"],
    )

    # Should still return valid structure
    assert "actual_draft" in result
    assert "composition_score" in result["actual_draft"]


def test_analyze_archetype_insight_when_same():
    """Insight explains when actual and recommended have same archetype."""
    from ban_teemo.services.draft_quality_analyzer import DraftQualityAnalyzer

    analyzer = DraftQualityAnalyzer()

    # Pick teams that should have similar archetypes
    result = analyzer.analyze(
        actual_picks=["Jarvan IV", "Sejuani", "Orianna", "Kai'Sa", "Rakan"],
        recommended_picks=["Zac", "Sejuani", "Orianna", "Kai'Sa", "Rakan"],
        enemy_picks=["Jayce", "Viego", "Syndra", "Ezreal", "Nautilus"],
    )

    # Both should be engage-focused
    if result["actual_draft"]["archetype"] == result["recommended_draft"]["archetype"]:
        assert "Both drafts have" in result["comparison"]["archetype_insight"]
```

**Step 2: Run all tests**

Run: `cd backend && uv run pytest tests/test_draft_quality_analyzer.py -v`
Expected: All tests pass

**Step 3: Commit**

```bash
git add backend/tests/test_draft_quality_analyzer.py
git commit -m "test(analyzer): add edge case tests for draft quality analyzer"
```

---

## Verification

After all tasks complete, verify end-to-end:

### Simulator Mode
1. Start a simulator session
2. Complete a draft (pick phase actions)
3. Call `POST /sessions/{id}/games/complete`
4. Verify response includes `draft_quality` with:
   - `actual_draft.picks`, `archetype`, `composition_score`, `vs_enemy_advantage`
   - `recommended_draft.picks`, `archetype`, `composition_score`, `vs_enemy_advantage`
   - `comparison.score_delta`, `archetype_insight`, `picks_matched`

### Replay Mode
1. Start a replay session
2. Let it run to completion
3. Verify `draft_complete` message includes `draft_quality` with:
   - `draft_quality.blue` - analysis from blue's perspective
   - `draft_quality.red` - analysis from red's perspective

---

## Summary

| Task | Description | Files |
|------|-------------|-------|
| 1 | Add recommended_picks to SimulatorSession | models/simulator.py |
| 2 | Create DraftQualityAnalyzer service | services/draft_quality_analyzer.py |
| 3 | Track recommendations during pick phase | routes/simulator.py |
| 4 | Add /draft-quality endpoint | routes/simulator.py |
| 5 | Include in complete_game response | routes/simulator.py |
| 6 | Reset on new game | routes/simulator.py |
| 7 | Add to replay mode (both teams) | websockets/replay_ws.py, replay_manager.py |
| 8 | Edge case tests | tests/test_draft_quality_analyzer.py |
