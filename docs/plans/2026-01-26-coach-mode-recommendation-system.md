# Coach Mode Recommendation System Implementation Plan

> **Status:** SUPERSEDED
> **Superseded By:** `2026-01-26-unified-recommendation-system.md`
> **Date:** 2026-01-26
>
> This plan has been merged into the unified recommendation system plan.
> Tasks from this plan are incorporated as **Stage 4: Coach Mode** and **Stage 5: Frontend** in the unified plan.

---

~~**For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.~~

**Goal:** Implement a coach-mode recommendation system where users select a team and receive contextual recommendations only for that team, including enemy threat analysis with role-grouped pools and priority-ranked ban targets.

**Architecture:** Add team selection to session start. Create EnemyPoolService that computes likely enemy picks per role based on player proficiency + meta + draft context. Extend Recommendations model with team_evaluation and enemy_analysis. Update WebSocket to only send recommendations when it's the coached team's turn, and enemy analysis when it's not.

**Tech Stack:** Python 3.14+, FastAPI, Pydantic dataclasses, TypeScript/React, WebSocket

---

## Overview

This plan implements Coach Mode with three key features:

1. **Team Selection** - User selects which team they're coaching at session start
2. **Enemy Pool Analysis** - Role-grouped + priority-ranked view of enemy's likely picks
3. **Contextual Recommendations** - Show pick/ban recs on our turn, enemy analysis on their turn

## Data Flow

```
Session Start
    ↓
User selects "coaching_team: blue"
    ↓
Each Draft Action:
    ├─ If next_team == coaching_team:
    │     → Send: pick/ban recommendations + team evaluation
    └─ If next_team == enemy_team:
          → Send: enemy pool analysis + threat rankings
```

## Prerequisites

- Existing `player_proficiency.json` with per-player champion stats
- Existing `meta_stats.json` with champion meta tiers
- Existing `flex_champions.json` with role distributions
- Existing `player_roles.json` with player role mappings
- Existing WebSocket replay infrastructure

---

## Task 1: Extend Recommendations Model with Team Evaluation and Enemy Analysis

**Files:**
- Modify: `backend/src/ban_teemo/models/recommendations.py`

**Step 1: Read the current file**

Read the file to understand current structure.

**Step 2: Add new dataclasses**

Add these dataclasses to `backend/src/ban_teemo/models/recommendations.py`:

```python
"""Recommendation models for draft suggestions."""

from dataclasses import dataclass, field


@dataclass
class PickRecommendation:
    """A recommended champion pick."""

    champion_name: str
    confidence: float  # 0.0 - 1.0
    flag: str | None = None  # "SURPRISE_PICK", "LOW_CONFIDENCE", None
    reasons: list[str] = field(default_factory=list)


@dataclass
class BanRecommendation:
    """A recommended champion ban."""

    champion_name: str
    priority: float  # 0.0 - 1.0
    target_player: str | None = None  # Who we're targeting with this ban
    reasons: list[str] = field(default_factory=list)


@dataclass
class ArchetypeScore:
    """Team archetype analysis."""

    primary: str | None  # "engage", "split", "teamfight", "protect", "pick"
    secondary: str | None
    scores: dict[str, float] = field(default_factory=dict)
    alignment: float = 0.0  # How focused the comp is


@dataclass
class TeamEvaluation:
    """Evaluation of a team's draft so far."""

    archetype: ArchetypeScore
    composition_score: float  # 0.0 - 1.0
    synergy_score: float  # 0.0 - 1.0
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)


@dataclass
class EnemyCandidate:
    """A likely enemy pick candidate."""

    champion_name: str
    player_name: str
    role: str  # TOP, JNG, MID, ADC, SUP
    threat_score: float  # 0.0 - 1.0
    proficiency_score: float  # Player's skill on this champ
    meta_score: float  # Champion's meta strength
    reasons: list[str] = field(default_factory=list)


@dataclass
class EnemyRolePool:
    """Enemy candidates for a specific role."""

    role: str  # TOP, JNG, MID, ADC, SUP
    player_name: str
    is_filled: bool  # Already picked for this role
    candidates: list[EnemyCandidate] = field(default_factory=list)


@dataclass
class EnemyAnalysis:
    """Analysis of enemy team's likely picks."""

    role_pools: list[EnemyRolePool] = field(default_factory=list)
    top_threats: list[EnemyCandidate] = field(default_factory=list)  # Priority-ranked
    archetype_tendency: str | None = None  # Detected comp direction


@dataclass
class Recommendations:
    """Collection of recommendations for a team."""

    for_team: str  # "blue" or "red"
    phase: str  # "our_turn" or "enemy_turn"
    picks: list[PickRecommendation] = field(default_factory=list)
    bans: list[BanRecommendation] = field(default_factory=list)
    team_evaluation: TeamEvaluation | None = None
    enemy_analysis: EnemyAnalysis | None = None
```

**Step 3: Verify syntax**

Run: `cd backend && python -c "from ban_teemo.models.recommendations import Recommendations, EnemyAnalysis; print('OK')"`

Expected: `OK`

**Step 4: Commit**

```bash
git add backend/src/ban_teemo/models/recommendations.py
git commit -m "feat(models): extend recommendations with team evaluation and enemy analysis"
```

---

## Task 2: Create Enemy Pool Service

**Files:**
- Create: `backend/src/ban_teemo/services/enemy_pool_service.py`
- Create: `backend/tests/test_enemy_pool_service.py`

**Step 1: Write the failing test**

Create file: `backend/tests/test_enemy_pool_service.py`

```python
"""Tests for enemy pool analysis service."""

import pytest
from ban_teemo.services.enemy_pool_service import EnemyPoolService
from ban_teemo.models.team import Player, TeamContext


@pytest.fixture
def service():
    return EnemyPoolService()


@pytest.fixture
def enemy_team():
    """Sample enemy team with 5 players."""
    return TeamContext(
        id="t1",
        name="T1",
        side="red",
        players=[
            Player(id="p1", name="Zeus", role="TOP"),
            Player(id="p2", name="Oner", role="JNG"),
            Player(id="p3", name="Faker", role="MID"),
            Player(id="p4", name="Gumayusi", role="ADC"),
            Player(id="p5", name="Keria", role="SUP"),
        ],
    )


def test_get_player_champion_pool(service, enemy_team):
    """Test getting a player's champion pool."""
    # Faker should have champions in his pool
    pool = service.get_player_champion_pool("Faker", "MID")

    assert len(pool) > 0
    # Each entry should have required fields
    for candidate in pool:
        assert candidate.champion_name
        assert candidate.role == "MID"
        assert 0.0 <= candidate.proficiency_score <= 1.0


def test_analyze_enemy_team(service, enemy_team):
    """Test full enemy team analysis."""
    banned = ["Azir", "Aurora"]
    picked = []

    analysis = service.analyze_enemy_team(
        enemy_team=enemy_team,
        banned_champions=banned,
        enemy_picks=[],
        our_picks=[],
    )

    # Should have 5 role pools
    assert len(analysis.role_pools) == 5

    # Should have top threats
    assert len(analysis.top_threats) > 0
    assert analysis.top_threats[0].threat_score >= analysis.top_threats[-1].threat_score

    # Banned champions should not appear
    all_candidates = [c.champion_name for rp in analysis.role_pools for c in rp.candidates]
    assert "Azir" not in all_candidates
    assert "Aurora" not in all_candidates


def test_role_pool_marked_filled(service, enemy_team):
    """Test that picked roles are marked as filled."""
    # Enemy already picked Rumble for TOP
    analysis = service.analyze_enemy_team(
        enemy_team=enemy_team,
        banned_champions=[],
        enemy_picks=["Rumble"],
        our_picks=[],
    )

    # Find TOP role pool
    top_pool = next((rp for rp in analysis.role_pools if rp.role == "TOP"), None)
    assert top_pool is not None
    assert top_pool.is_filled is True
    assert len(top_pool.candidates) == 0  # No more candidates needed


def test_threat_score_includes_meta(service, enemy_team):
    """Test that threat score factors in meta strength."""
    analysis = service.analyze_enemy_team(
        enemy_team=enemy_team,
        banned_champions=[],
        enemy_picks=[],
        our_picks=[],
    )

    # Top threats should have meta_score populated
    for threat in analysis.top_threats[:3]:
        assert threat.meta_score > 0
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_enemy_pool_service.py -v`

Expected: FAIL with "ModuleNotFoundError: No module named 'ban_teemo.services.enemy_pool_service'"

**Step 3: Write minimal implementation**

Create file: `backend/src/ban_teemo/services/enemy_pool_service.py`

```python
"""Service for analyzing enemy team's likely champion picks."""

import json
from pathlib import Path
from typing import Optional

from ban_teemo.models.recommendations import (
    EnemyAnalysis,
    EnemyCandidate,
    EnemyRolePool,
)
from ban_teemo.models.team import TeamContext


class EnemyPoolService:
    """Analyzes enemy team's likely picks based on player pools and meta."""

    ROLE_MAP = {
        "TOP": "top",
        "JNG": "jungle",
        "JUNGLE": "jungle",
        "MID": "mid",
        "ADC": "bot",
        "BOT": "bot",
        "SUP": "support",
        "SUPPORT": "support",
    }

    def __init__(self, knowledge_dir: Optional[Path] = None):
        if knowledge_dir is None:
            knowledge_dir = Path(__file__).parent.parent.parent.parent.parent / "knowledge"

        self.knowledge_dir = knowledge_dir
        self._player_proficiency: dict = {}
        self._meta_stats: dict = {}
        self._player_roles: dict = {}
        self._flex_champions: dict = {}
        self._load_data()

    def _load_data(self):
        """Load knowledge files."""
        # Player proficiency
        prof_path = self.knowledge_dir / "player_proficiency.json"
        if prof_path.exists():
            with open(prof_path) as f:
                data = json.load(f)
                self._player_proficiency = data.get("proficiencies", {})

        # Meta stats
        meta_path = self.knowledge_dir / "meta_stats.json"
        if meta_path.exists():
            with open(meta_path) as f:
                data = json.load(f)
                self._meta_stats = data.get("champions", {})

        # Player roles
        roles_path = self.knowledge_dir / "player_roles.json"
        if roles_path.exists():
            with open(roles_path) as f:
                data = json.load(f)
                self._player_roles = data.get("players", {})

        # Flex champions
        flex_path = self.knowledge_dir / "flex_champions.json"
        if flex_path.exists():
            with open(flex_path) as f:
                data = json.load(f)
                self._flex_champions = data.get("flex_picks", {})

    def get_player_champion_pool(
        self,
        player_name: str,
        role: str,
        exclude_champions: set[str] | None = None,
        limit: int = 5,
    ) -> list[EnemyCandidate]:
        """Get a player's likely champion picks for their role.

        Args:
            player_name: Player's in-game name
            role: Role to get champions for (TOP, JNG, MID, ADC, SUP)
            exclude_champions: Champions to exclude (banned/picked)
            limit: Max candidates to return

        Returns:
            List of EnemyCandidate sorted by proficiency
        """
        exclude = exclude_champions or set()
        candidates = []

        # Get player's champion data
        player_data = self._player_proficiency.get(player_name, {})

        for champ_name, prof_data in player_data.items():
            if champ_name in exclude:
                continue

            # Check if champion plays this role
            flex_data = self._flex_champions.get(champ_name, {})
            role_prob = flex_data.get(role.upper(), 0)

            # Skip if champion doesn't play this role significantly
            if role_prob < 0.1:
                continue

            # Get meta score
            meta_data = self._meta_stats.get(champ_name, {})
            meta_score = meta_data.get("meta_score", 0.5)

            # Calculate proficiency score (normalized)
            win_rate = prof_data.get("win_rate_weighted", prof_data.get("win_rate", 0.5))
            games = prof_data.get("games_weighted", 0)
            confidence = prof_data.get("confidence", "LOW")

            # Proficiency based on games + win rate
            games_factor = min(1.0, games / 10)  # Cap at 10 games
            prof_score = (win_rate * 0.6 + games_factor * 0.4)

            # Build reasons
            reasons = []
            if confidence == "HIGH":
                reasons.append(f"High confidence ({prof_data.get('games_raw', 0)} games)")
            if win_rate >= 0.6:
                reasons.append(f"Strong win rate ({win_rate:.0%})")
            if meta_score >= 0.7:
                reasons.append(f"Meta pick ({meta_data.get('meta_tier', 'B')}-tier)")

            # Calculate threat score (proficiency + meta combined)
            threat_score = (prof_score * 0.6 + meta_score * 0.4)

            candidates.append(
                EnemyCandidate(
                    champion_name=champ_name,
                    player_name=player_name,
                    role=role.upper(),
                    threat_score=round(threat_score, 3),
                    proficiency_score=round(prof_score, 3),
                    meta_score=round(meta_score, 3),
                    reasons=reasons,
                )
            )

        # Sort by threat score and limit
        candidates.sort(key=lambda x: -x.threat_score)
        return candidates[:limit]

    def analyze_enemy_team(
        self,
        enemy_team: TeamContext,
        banned_champions: list[str],
        enemy_picks: list[str],
        our_picks: list[str],
    ) -> EnemyAnalysis:
        """Analyze enemy team's likely remaining picks.

        Args:
            enemy_team: Enemy team context with players
            banned_champions: All banned champions
            enemy_picks: Champions enemy has already picked
            our_picks: Champions our team has picked

        Returns:
            EnemyAnalysis with role pools and top threats
        """
        unavailable = set(banned_champions) | set(enemy_picks) | set(our_picks)

        # Map players to roles
        role_to_player: dict[str, str] = {}
        for player in enemy_team.players:
            role_upper = player.role.upper()
            if role_upper in ("JNG", "JUNGLE"):
                role_upper = "JNG"
            elif role_upper in ("SUP", "SUPPORT"):
                role_upper = "SUP"
            elif role_upper in ("ADC", "BOT"):
                role_upper = "ADC"
            role_to_player[role_upper] = player.name

        # Determine which roles are filled (simplified: assume picks fill in order)
        # In reality, we'd need role detection from the picked champions
        filled_roles = self._detect_filled_roles(enemy_picks, enemy_team)

        role_pools = []
        all_candidates = []

        for role in ["TOP", "JNG", "MID", "ADC", "SUP"]:
            player_name = role_to_player.get(role, "Unknown")
            is_filled = role in filled_roles

            if is_filled:
                role_pools.append(
                    EnemyRolePool(
                        role=role,
                        player_name=player_name,
                        is_filled=True,
                        candidates=[],
                    )
                )
            else:
                candidates = self.get_player_champion_pool(
                    player_name=player_name,
                    role=role,
                    exclude_champions=unavailable,
                    limit=5,
                )
                role_pools.append(
                    EnemyRolePool(
                        role=role,
                        player_name=player_name,
                        is_filled=False,
                        candidates=candidates,
                    )
                )
                all_candidates.extend(candidates)

        # Sort all candidates by threat score for top threats
        all_candidates.sort(key=lambda x: -x.threat_score)
        top_threats = all_candidates[:10]

        # Detect archetype tendency from picks so far
        archetype_tendency = self._detect_archetype_tendency(enemy_picks)

        return EnemyAnalysis(
            role_pools=role_pools,
            top_threats=top_threats,
            archetype_tendency=archetype_tendency,
        )

    def _detect_filled_roles(
        self,
        picks: list[str],
        team: TeamContext,
    ) -> set[str]:
        """Detect which roles have been filled based on picks.

        Uses champion role data and pick count heuristics.
        """
        filled = set()

        for champ in picks:
            flex_data = self._flex_champions.get(champ, {})

            # Find the most likely role for this champion
            best_role = None
            best_prob = 0

            for role in ["TOP", "JNG", "MID", "ADC", "SUP"]:
                prob = flex_data.get(role, 0)
                if prob > best_prob and role not in filled:
                    best_prob = prob
                    best_role = role

            if best_role:
                filled.add(best_role)

        return filled

    def _detect_archetype_tendency(self, picks: list[str]) -> str | None:
        """Detect emerging archetype from picks."""
        if not picks:
            return None

        # Simplified: would integrate with ArchetypeService
        # For now return None
        return None
```

**Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_enemy_pool_service.py -v`

Expected: Most tests PASS. Some may fail if player data doesn't exist - that's OK for now.

**Step 5: Commit**

```bash
git add backend/src/ban_teemo/services/enemy_pool_service.py backend/tests/test_enemy_pool_service.py
git commit -m "feat(services): add enemy pool analysis service"
```

---

## Task 3: Update Draft Service with Coach Mode Logic

**Files:**
- Modify: `backend/src/ban_teemo/services/draft_service.py`

**Step 1: Write test for coach mode**

Add to existing tests or create: `backend/tests/test_draft_service_coach_mode.py`

```python
"""Tests for draft service coach mode."""

import pytest
from datetime import datetime
from ban_teemo.services.draft_service import DraftService
from ban_teemo.models.draft import DraftState, DraftPhase, DraftAction
from ban_teemo.models.team import Player, TeamContext


@pytest.fixture
def service():
    return DraftService(data_path="outputs/full_2024_2025_v2/csv")


@pytest.fixture
def sample_draft_state():
    """Create a sample draft state."""
    return DraftState(
        game_id="test-game",
        series_id="test-series",
        game_number=1,
        patch_version="15.18",
        match_date=datetime.now(),
        blue_team=TeamContext(
            id="blue-team",
            name="G2",
            side="blue",
            players=[
                Player(id="p1", name="BrokenBlade", role="TOP"),
                Player(id="p2", name="Yike", role="JNG"),
                Player(id="p3", name="Caps", role="MID"),
                Player(id="p4", name="Hans sama", role="ADC"),
                Player(id="p5", name="Mikyx", role="SUP"),
            ],
        ),
        red_team=TeamContext(
            id="red-team",
            name="T1",
            side="red",
            players=[
                Player(id="p6", name="Zeus", role="TOP"),
                Player(id="p7", name="Oner", role="JNG"),
                Player(id="p8", name="Faker", role="MID"),
                Player(id="p9", name="Gumayusi", role="ADC"),
                Player(id="p10", name="Keria", role="SUP"),
            ],
        ),
        actions=[],
        current_phase=DraftPhase.BAN_PHASE_1,
        next_team="blue",
        next_action="ban",
    )


def test_get_recommendations_our_turn(service, sample_draft_state):
    """Test recommendations when it's our turn."""
    # Coaching blue, it's blue's turn
    recs = service.get_recommendations(
        draft_state=sample_draft_state,
        for_team="blue",
        coaching_team="blue",
    )

    assert recs.phase == "our_turn"
    assert recs.for_team == "blue"
    # Should have ban recommendations (ban phase)
    assert len(recs.bans) > 0 or len(recs.picks) > 0


def test_get_recommendations_enemy_turn(service, sample_draft_state):
    """Test recommendations when it's enemy turn."""
    # Coaching blue, but it's red's turn
    sample_draft_state.next_team = "red"

    recs = service.get_recommendations(
        draft_state=sample_draft_state,
        for_team="blue",
        coaching_team="blue",
    )

    assert recs.phase == "enemy_turn"
    assert recs.for_team == "blue"
    # Should have enemy analysis
    assert recs.enemy_analysis is not None
    assert len(recs.enemy_analysis.role_pools) == 5


def test_get_recommendations_includes_team_eval(service, sample_draft_state):
    """Test that recommendations include team evaluation."""
    # Add some picks first
    sample_draft_state.actions = [
        DraftAction(1, "ban", "blue", "1", "Azir"),
        DraftAction(2, "ban", "red", "2", "Aurora"),
        DraftAction(3, "ban", "blue", "3", "Yone"),
        DraftAction(4, "ban", "red", "4", "Yasuo"),
        DraftAction(5, "ban", "blue", "5", "Rumble"),
        DraftAction(6, "ban", "red", "6", "Kalista"),
        DraftAction(7, "pick", "blue", "7", "Orianna"),
        DraftAction(8, "pick", "red", "8", "Nautilus"),
    ]
    sample_draft_state.current_phase = DraftPhase.PICK_PHASE_1
    sample_draft_state.next_team = "red"

    recs = service.get_recommendations(
        draft_state=sample_draft_state,
        for_team="blue",
        coaching_team="blue",
    )

    # Should have team evaluation
    assert recs.team_evaluation is not None
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_draft_service_coach_mode.py -v`

Expected: FAIL (coaching_team parameter doesn't exist yet)

**Step 3: Update draft_service.py**

Replace contents of `backend/src/ban_teemo/services/draft_service.py`:

```python
"""Draft business logic service with coach mode support."""

from ban_teemo.models.draft import DraftAction, DraftPhase, DraftState
from ban_teemo.models.recommendations import (
    ArchetypeScore,
    BanRecommendation,
    EnemyAnalysis,
    PickRecommendation,
    Recommendations,
    TeamEvaluation,
)
from ban_teemo.services.enemy_pool_service import EnemyPoolService


class DraftService:
    """Core business logic for draft state and recommendations."""

    def __init__(self, data_path: str):
        """Initialize the draft service.

        Args:
            data_path: Path to CSV data directory (for future analytics)
        """
        self.data_path = data_path
        self.enemy_pool_service = EnemyPoolService()

    def compute_phase(self, action_count: int) -> DraftPhase:
        """Compute draft phase from action count.

        Args:
            action_count: Number of actions completed (0-20)

        Returns:
            The current draft phase
        """
        if action_count >= 20:
            return DraftPhase.COMPLETE
        elif action_count < 6:
            return DraftPhase.BAN_PHASE_1
        elif action_count < 12:
            return DraftPhase.PICK_PHASE_1
        elif action_count < 16:
            return DraftPhase.BAN_PHASE_2
        else:
            return DraftPhase.PICK_PHASE_2

    def build_draft_state_at(
        self,
        base_state: DraftState,
        actions: list[DraftAction],
        up_to_index: int,
    ) -> DraftState:
        """Build draft state after N actions have occurred.

        Args:
            base_state: Initial draft state with team info
            actions: All draft actions for the game
            up_to_index: Include actions 0 through up_to_index-1

        Returns:
            New DraftState with actions applied
        """
        actions_so_far = actions[:up_to_index]
        phase = self.compute_phase(len(actions_so_far))

        if up_to_index >= len(actions):
            next_team = None
            next_action = None
        else:
            next_act = actions[up_to_index]
            next_team = next_act.team_side
            next_action = next_act.action_type

        return DraftState(
            game_id=base_state.game_id,
            series_id=base_state.series_id,
            game_number=base_state.game_number,
            patch_version=base_state.patch_version,
            match_date=base_state.match_date,
            blue_team=base_state.blue_team,
            red_team=base_state.red_team,
            actions=actions_so_far,
            current_phase=phase,
            next_team=next_team,
            next_action=next_action,
        )

    def get_recommendations(
        self,
        draft_state: DraftState,
        for_team: str,
        coaching_team: str | None = None,
    ) -> Recommendations:
        """Generate recommendations for a team in coach mode.

        Args:
            draft_state: Current state of the draft
            for_team: Which team to generate recommendations for
            coaching_team: The team being coached (determines our_turn vs enemy_turn)

        Returns:
            Recommendations with context-appropriate content
        """
        if coaching_team is None:
            coaching_team = for_team

        if draft_state.current_phase == DraftPhase.COMPLETE:
            return Recommendations(
                for_team=for_team,
                phase="complete",
                picks=[],
                bans=[],
            )

        # Determine if it's our turn or enemy's turn
        is_our_turn = draft_state.next_team == coaching_team

        # Get team contexts
        if coaching_team == "blue":
            our_team = draft_state.blue_team
            enemy_team = draft_state.red_team
            our_picks = draft_state.blue_picks
            enemy_picks = draft_state.red_picks
        else:
            our_team = draft_state.red_team
            enemy_team = draft_state.blue_team
            our_picks = draft_state.red_picks
            enemy_picks = draft_state.blue_picks

        all_bans = draft_state.blue_bans + draft_state.red_bans

        # Always compute team evaluation
        team_eval = self._compute_team_evaluation(our_picks)

        if is_our_turn:
            # Our turn: provide pick/ban recommendations
            return self._build_our_turn_recommendations(
                draft_state=draft_state,
                for_team=for_team,
                team_eval=team_eval,
                all_bans=all_bans,
                our_picks=our_picks,
                enemy_picks=enemy_picks,
            )
        else:
            # Enemy turn: provide enemy analysis
            enemy_analysis = self.enemy_pool_service.analyze_enemy_team(
                enemy_team=enemy_team,
                banned_champions=all_bans,
                enemy_picks=enemy_picks,
                our_picks=our_picks,
            )

            return Recommendations(
                for_team=for_team,
                phase="enemy_turn",
                picks=[],
                bans=[],
                team_evaluation=team_eval,
                enemy_analysis=enemy_analysis,
            )

    def _build_our_turn_recommendations(
        self,
        draft_state: DraftState,
        for_team: str,
        team_eval: TeamEvaluation,
        all_bans: list[str],
        our_picks: list[str],
        enemy_picks: list[str],
    ) -> Recommendations:
        """Build recommendations for when it's our turn."""
        unavailable = set(all_bans + our_picks + enemy_picks)

        if draft_state.next_action == "pick":
            picks = self._generate_pick_recommendations(unavailable)
            return Recommendations(
                for_team=for_team,
                phase="our_turn",
                picks=picks,
                bans=[],
                team_evaluation=team_eval,
                enemy_analysis=None,
            )
        else:
            bans = self._generate_ban_recommendations(unavailable)
            return Recommendations(
                for_team=for_team,
                phase="our_turn",
                picks=[],
                bans=bans,
                team_evaluation=team_eval,
                enemy_analysis=None,
            )

    def _compute_team_evaluation(self, picks: list[str]) -> TeamEvaluation:
        """Compute team evaluation from current picks."""
        if not picks:
            return TeamEvaluation(
                archetype=ArchetypeScore(
                    primary=None,
                    secondary=None,
                    scores={},
                    alignment=0.0,
                ),
                composition_score=0.0,
                synergy_score=0.0,
                strengths=[],
                weaknesses=["No picks yet"],
            )

        # Simplified evaluation - would integrate with archetype/synergy services
        return TeamEvaluation(
            archetype=ArchetypeScore(
                primary="teamfight",  # Placeholder
                secondary=None,
                scores={"teamfight": 0.6, "engage": 0.3},
                alignment=0.5,
            ),
            composition_score=0.5,
            synergy_score=0.5,
            strengths=[f"Draft in progress ({len(picks)} picks)"],
            weaknesses=[],
        )

    def _generate_pick_recommendations(
        self,
        unavailable: set[str],
    ) -> list[PickRecommendation]:
        """Generate pick recommendations (stub)."""
        # Stub - would use meta_stats + proficiency
        candidates = ["Azir", "Vi", "Aurora", "Orianna", "Jinx"]
        picks = []

        for i, champ in enumerate(candidates):
            if champ not in unavailable:
                picks.append(
                    PickRecommendation(
                        champion_name=champ,
                        confidence=0.8 - (i * 0.1),
                        flag="SURPRISE_PICK" if i == 2 else None,
                        reasons=["Meta pick", "TODO: Real analytics"],
                    )
                )

        return picks[:3]

    def _generate_ban_recommendations(
        self,
        unavailable: set[str],
    ) -> list[BanRecommendation]:
        """Generate ban recommendations (stub)."""
        candidates = ["Rumble", "Kalista", "Rell", "Aurora", "Yone"]
        bans = []

        for i, champ in enumerate(candidates):
            if champ not in unavailable:
                bans.append(
                    BanRecommendation(
                        champion_name=champ,
                        priority=0.85 - (i * 0.05),
                        target_player=None,
                        reasons=["High presence", "TODO: Real analytics"],
                    )
                )

        return bans[:3]
```

**Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_draft_service_coach_mode.py -v`

Expected: All tests PASS

**Step 5: Commit**

```bash
git add backend/src/ban_teemo/services/draft_service.py backend/tests/test_draft_service_coach_mode.py
git commit -m "feat(services): add coach mode to draft service with enemy analysis"
```

---

## Task 4: Update WebSocket Protocol for Coach Mode

**Files:**
- Modify: `backend/src/ban_teemo/api/websockets/replay_ws.py`
- Modify: `backend/src/ban_teemo/services/replay_manager.py`

**Step 1: Update ReplaySession to track coaching_team**

Read and modify `backend/src/ban_teemo/services/replay_manager.py` to add `coaching_team: str` field to `ReplaySession`.

Add to `ReplaySession` dataclass:

```python
coaching_team: str = "blue"  # Which team user is coaching
```

**Step 2: Update WebSocket serialization**

Modify `backend/src/ban_teemo/api/websockets/replay_ws.py`:

Add new serialization function after `_serialize_recommendations`:

```python
def _serialize_recommendations(recs: Recommendations | None) -> dict | None:
    """Serialize Recommendations to JSON-compatible dict."""
    if not recs:
        return None

    result = {
        "for_team": recs.for_team,
        "phase": recs.phase,
        "picks": [
            {
                "champion_name": p.champion_name,
                "confidence": p.confidence,
                "flag": p.flag,
                "reasons": p.reasons,
            }
            for p in recs.picks
        ],
        "bans": [
            {
                "champion_name": b.champion_name,
                "priority": b.priority,
                "target_player": b.target_player,
                "reasons": b.reasons,
            }
            for b in recs.bans
        ],
    }

    if recs.team_evaluation:
        result["team_evaluation"] = {
            "archetype": {
                "primary": recs.team_evaluation.archetype.primary,
                "secondary": recs.team_evaluation.archetype.secondary,
                "scores": recs.team_evaluation.archetype.scores,
                "alignment": recs.team_evaluation.archetype.alignment,
            },
            "composition_score": recs.team_evaluation.composition_score,
            "synergy_score": recs.team_evaluation.synergy_score,
            "strengths": recs.team_evaluation.strengths,
            "weaknesses": recs.team_evaluation.weaknesses,
        }

    if recs.enemy_analysis:
        result["enemy_analysis"] = {
            "role_pools": [
                {
                    "role": rp.role,
                    "player_name": rp.player_name,
                    "is_filled": rp.is_filled,
                    "candidates": [
                        {
                            "champion_name": c.champion_name,
                            "player_name": c.player_name,
                            "role": c.role,
                            "threat_score": c.threat_score,
                            "proficiency_score": c.proficiency_score,
                            "meta_score": c.meta_score,
                            "reasons": c.reasons,
                        }
                        for c in rp.candidates
                    ],
                }
                for rp in recs.enemy_analysis.role_pools
            ],
            "top_threats": [
                {
                    "champion_name": t.champion_name,
                    "player_name": t.player_name,
                    "role": t.role,
                    "threat_score": t.threat_score,
                    "reasons": t.reasons,
                }
                for t in recs.enemy_analysis.top_threats
            ],
            "archetype_tendency": recs.enemy_analysis.archetype_tendency,
        }

    return result
```

**Step 3: Update replay loop to pass coaching_team**

In `_run_replay_loop`, update the `get_recommendations` call:

```python
recommendations = service.get_recommendations(
    current_state,
    for_team=session.coaching_team,
    coaching_team=session.coaching_team,
)
```

**Step 4: Verify by running the server**

Run: `cd backend && uv run python -c "from ban_teemo.api.websockets.replay_ws import _serialize_recommendations; print('OK')"`

Expected: `OK`

**Step 5: Commit**

```bash
git add backend/src/ban_teemo/api/websockets/replay_ws.py backend/src/ban_teemo/services/replay_manager.py
git commit -m "feat(ws): update websocket protocol for coach mode with enemy analysis"
```

---

## Task 5: Update Frontend Types

**Files:**
- Modify: `deepdraft/src/types/index.ts`

**Step 1: Add new TypeScript types**

Add to `deepdraft/src/types/index.ts`:

```typescript
// === Team Evaluation ===
export interface ArchetypeScore {
  primary: string | null;
  secondary: string | null;
  scores: Record<string, number>;
  alignment: number;
}

export interface TeamEvaluation {
  archetype: ArchetypeScore;
  composition_score: number;
  synergy_score: number;
  strengths: string[];
  weaknesses: string[];
}

// === Enemy Analysis ===
export interface EnemyCandidate {
  champion_name: string;
  player_name: string;
  role: string;
  threat_score: number;
  proficiency_score: number;
  meta_score: number;
  reasons: string[];
}

export interface EnemyRolePool {
  role: string;
  player_name: string;
  is_filled: boolean;
  candidates: EnemyCandidate[];
}

export interface EnemyAnalysis {
  role_pools: EnemyRolePool[];
  top_threats: EnemyCandidate[];
  archetype_tendency: string | null;
}

// Update existing Recommendations interface
export interface Recommendations {
  for_team: Team;
  phase: "our_turn" | "enemy_turn" | "complete";
  picks: PickRecommendation[];
  bans: BanRecommendation[];
  team_evaluation?: TeamEvaluation;
  enemy_analysis?: EnemyAnalysis;
}
```

**Step 2: Verify TypeScript compiles**

Run: `cd deepdraft && npm run build`

Expected: Build succeeds (or only unrelated errors)

**Step 3: Commit**

```bash
git add deepdraft/src/types/index.ts
git commit -m "feat(types): add TypeScript types for team evaluation and enemy analysis"
```

---

## Task 6: Create Enemy Analysis Panel Component

**Files:**
- Create: `deepdraft/src/components/EnemyAnalysisPanel/index.tsx`

**Step 1: Create the component**

Create file: `deepdraft/src/components/EnemyAnalysisPanel/index.tsx`

```tsx
// deepdraft/src/components/EnemyAnalysisPanel/index.tsx
import type { EnemyAnalysis, EnemyCandidate, EnemyRolePool } from "../../types";
import { ChampionPortrait } from "../shared/ChampionPortrait";

interface EnemyAnalysisPanelProps {
  analysis: EnemyAnalysis | null;
  enemyTeamName: string;
}

export function EnemyAnalysisPanel({
  analysis,
  enemyTeamName,
}: EnemyAnalysisPanelProps) {
  if (!analysis) {
    return (
      <div className="bg-lol-dark rounded-lg p-6">
        <div className="text-center text-text-tertiary py-8">
          Waiting for enemy analysis...
        </div>
      </div>
    );
  }

  return (
    <div className="bg-lol-dark rounded-lg p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h2 className="font-semibold text-lg uppercase tracking-wide text-gold-bright">
          Enemy Analysis
        </h2>
        <span className="text-sm font-semibold uppercase px-2 py-1 rounded bg-red-team/20 text-red-team">
          {enemyTeamName}'s Turn
        </span>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left: Top Threats */}
        <div>
          <h3 className="text-sm font-semibold text-text-secondary mb-3 uppercase tracking-wide">
            Top Threats to Ban
          </h3>
          <div className="space-y-2">
            {analysis.top_threats.slice(0, 5).map((threat, idx) => (
              <ThreatRow key={threat.champion_name} threat={threat} rank={idx + 1} />
            ))}
          </div>
        </div>

        {/* Right: Role Pools */}
        <div>
          <h3 className="text-sm font-semibold text-text-secondary mb-3 uppercase tracking-wide">
            Likely Picks by Role
          </h3>
          <div className="space-y-3">
            {analysis.role_pools.map((pool) => (
              <RolePoolRow key={pool.role} pool={pool} />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function ThreatRow({ threat, rank }: { threat: EnemyCandidate; rank: number }) {
  const threatPercent = Math.round(threat.threat_score * 100);

  return (
    <div className="flex items-center gap-3 p-2 rounded bg-lol-darkest/50">
      <span className="text-gold-bright font-bold w-5">{rank}.</span>
      <ChampionPortrait
        championName={threat.champion_name}
        size="sm"
      />
      <div className="flex-1">
        <div className="flex items-center gap-2">
          <span className="font-medium text-text-primary">
            {threat.champion_name}
          </span>
          <span className="text-xs text-text-tertiary">
            ({threat.player_name} - {threat.role})
          </span>
        </div>
        <div className="flex items-center gap-2 mt-0.5">
          <div className="flex-1 h-1.5 bg-lol-darkest rounded-full overflow-hidden">
            <div
              className="h-full bg-red-team rounded-full"
              style={{ width: `${threatPercent}%` }}
            />
          </div>
          <span className="text-xs text-red-team font-medium">
            {threatPercent}%
          </span>
        </div>
      </div>
    </div>
  );
}

function RolePoolRow({ pool }: { pool: EnemyRolePool }) {
  if (pool.is_filled) {
    return (
      <div className="flex items-center gap-3 p-2 rounded bg-lol-darkest/30 opacity-50">
        <span className="w-12 text-xs font-semibold text-text-tertiary uppercase">
          {pool.role}
        </span>
        <span className="text-sm text-text-tertiary italic">
          Already picked
        </span>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-3 p-2 rounded bg-lol-darkest/50">
      <span className="w-12 text-xs font-semibold text-gold-dim uppercase">
        {pool.role}
      </span>
      <span className="text-xs text-text-tertiary mr-2">
        {pool.player_name}:
      </span>
      <div className="flex gap-1">
        {pool.candidates.slice(0, 4).map((c) => (
          <ChampionPortrait
            key={c.champion_name}
            championName={c.champion_name}
            size="xs"
            title={`${c.champion_name} (${Math.round(c.threat_score * 100)}%)`}
          />
        ))}
      </div>
    </div>
  );
}
```

**Step 2: Export the component**

Create or update `deepdraft/src/components/EnemyAnalysisPanel/index.ts` if needed.

**Step 3: Verify component compiles**

Run: `cd deepdraft && npm run build`

Expected: Build succeeds

**Step 4: Commit**

```bash
git add deepdraft/src/components/EnemyAnalysisPanel/
git commit -m "feat(ui): add EnemyAnalysisPanel component"
```

---

## Task 7: Update App to Show Contextual Panels

**Files:**
- Modify: `deepdraft/src/App.tsx`

**Step 1: Import and use EnemyAnalysisPanel**

Update `deepdraft/src/App.tsx`:

```tsx
// deepdraft/src/App.tsx
import { ActionLog } from "./components/ActionLog";
import { DraftBoard } from "./components/DraftBoard";
import { EnemyAnalysisPanel } from "./components/EnemyAnalysisPanel";
import { RecommendationPanel } from "./components/RecommendationPanel";
import { ReplayControls } from "./components/ReplayControls";
import { useReplaySession } from "./hooks";

export default function App() {
  const {
    status,
    blueTeam,
    redTeam,
    draftState,
    recommendations,
    actionHistory,
    patch,
    error,
    startReplay,
    stopReplay,
    coachingTeam, // Add this to hook
  } = useReplaySession();

  // Determine which panel to show
  const isOurTurn = recommendations?.phase === "our_turn";
  const isEnemyTurn = recommendations?.phase === "enemy_turn";
  const enemyTeamName = coachingTeam === "blue" ? redTeam?.name : blueTeam?.name;

  return (
    <div className="min-h-screen bg-lol-darkest">
      {/* Header */}
      <header className="h-16 bg-lol-dark border-b border-gold-dim/30 flex items-center px-6">
        <div className="flex items-center gap-4">
          <h1 className="text-xl font-bold uppercase tracking-wide text-gold-bright">
            DeepDraft
          </h1>
          <span className="text-sm text-text-tertiary">
            LoL Draft Assistant
          </span>
        </div>

        <div className="ml-auto flex items-center gap-4">
          {coachingTeam && (
            <span className={`
              text-xs font-semibold uppercase px-2 py-1 rounded
              ${coachingTeam === "blue" ? "bg-blue-team/20 text-blue-team" : "bg-red-team/20 text-red-team"}
            `}>
              Coaching {coachingTeam === "blue" ? blueTeam?.name : redTeam?.name}
            </span>
          )}
          {patch && (
            <span className="text-xs text-text-tertiary">
              Patch {patch}
            </span>
          )}
          {status === "playing" && (
            <span className="text-xs text-magic animate-pulse">
              ● Live
            </span>
          )}
        </div>
      </header>

      {/* Main Content */}
      <main className="p-6 space-y-6">
        {/* Replay Controls */}
        <ReplayControls
          status={status}
          onStart={startReplay}
          onStop={stopReplay}
          error={error}
        />

        {/* Draft Board + Action Log */}
        <div className="flex flex-row gap-6">
          <div className="flex-1">
            <DraftBoard
              blueTeam={blueTeam}
              redTeam={redTeam}
              draftState={draftState}
            />
          </div>

          {status !== "idle" && (
            <ActionLog
              actions={actionHistory}
              blueTeam={blueTeam}
              redTeam={redTeam}
            />
          )}
        </div>

        {/* Contextual Panel: Our Turn vs Enemy Turn */}
        {isOurTurn && (
          <RecommendationPanel
            recommendations={recommendations}
            nextAction={draftState?.next_action ?? null}
          />
        )}

        {isEnemyTurn && (
          <EnemyAnalysisPanel
            analysis={recommendations?.enemy_analysis ?? null}
            enemyTeamName={enemyTeamName ?? "Enemy"}
          />
        )}

        {/* Team Evaluation (always visible when draft started) */}
        {recommendations?.team_evaluation && (
          <TeamEvaluationBar evaluation={recommendations.team_evaluation} />
        )}
      </main>
    </div>
  );
}

// Simple team evaluation bar component
function TeamEvaluationBar({ evaluation }: { evaluation: TeamEvaluation }) {
  return (
    <div className="bg-lol-dark rounded-lg p-4 flex items-center gap-6">
      <div>
        <span className="text-xs text-text-tertiary uppercase">Comp Score</span>
        <div className="text-lg font-bold text-gold-bright">
          {Math.round(evaluation.composition_score * 100)}%
        </div>
      </div>
      <div>
        <span className="text-xs text-text-tertiary uppercase">Archetype</span>
        <div className="text-lg font-semibold text-text-primary capitalize">
          {evaluation.archetype.primary ?? "—"}
        </div>
      </div>
      {evaluation.strengths.length > 0 && (
        <div className="flex-1">
          <span className="text-xs text-text-tertiary uppercase">Strengths</span>
          <div className="text-sm text-text-secondary">
            {evaluation.strengths.join(" • ")}
          </div>
        </div>
      )}
    </div>
  );
}

// Add import for TeamEvaluation type at top
import type { TeamEvaluation } from "./types";
```

**Step 2: Update useReplaySession hook to expose coachingTeam**

This requires adding `coachingTeam` state to the hook and exposing it.

**Step 3: Verify frontend builds**

Run: `cd deepdraft && npm run build`

Expected: Build succeeds (may need to fix import issues)

**Step 4: Commit**

```bash
git add deepdraft/src/App.tsx
git commit -m "feat(ui): show contextual panels based on turn (our turn vs enemy turn)"
```

---

## Task 8: Add Team Selection to Session Start

**Files:**
- Modify: `deepdraft/src/hooks/useReplaySession.ts`
- Modify: `deepdraft/src/components/ReplayControls/index.tsx`

**Step 1: Update hook to track and set coaching team**

Add to the hook:
- `coachingTeam` state (default "blue")
- `setCoachingTeam` function
- Pass to API when starting session

**Step 2: Update ReplayControls to allow team selection**

Add a team selector before the Start button:

```tsx
<select
  value={coachingTeam}
  onChange={(e) => setCoachingTeam(e.target.value as "blue" | "red")}
  className="bg-lol-darkest text-text-primary px-3 py-2 rounded"
>
  <option value="blue">Coach Blue Team</option>
  <option value="red">Coach Red Team</option>
</select>
```

**Step 3: Test the flow**

Run: `cd deepdraft && npm run dev`

Verify: Can select team before starting replay

**Step 4: Commit**

```bash
git add deepdraft/src/hooks/useReplaySession.ts deepdraft/src/components/ReplayControls/
git commit -m "feat(ui): add team selection for coach mode"
```

---

## Task 9: Run Full Integration Test

**Step 1: Start backend**

Run: `cd backend && uv run uvicorn ban_teemo.main:app --reload`

**Step 2: Start frontend**

Run: `cd deepdraft && npm run dev`

**Step 3: Test coach mode flow**

1. Select "Coach Blue Team"
2. Start a replay
3. Verify: When it's Blue's turn → see RecommendationPanel
4. Verify: When it's Red's turn → see EnemyAnalysisPanel
5. Verify: Team evaluation bar always visible

**Step 4: Run all tests**

Run: `cd backend && uv run pytest tests/ -v`

Expected: All tests PASS

**Step 5: Final commit**

```bash
git add -A
git commit -m "feat: complete coach mode recommendation system"
```

---

## Summary

This plan implements:

1. **Extended Models** - TeamEvaluation, EnemyAnalysis, EnemyCandidate, EnemyRolePool
2. **Enemy Pool Service** - Analyzes enemy's likely picks by player proficiency + meta
3. **Coach Mode Logic** - Different recommendations for our turn vs enemy turn
4. **Updated WebSocket** - Serializes new data structures, tracks coaching_team
5. **Frontend Types** - TypeScript types matching backend models
6. **Enemy Analysis Panel** - Role-grouped pools + priority-ranked threats
7. **Contextual App** - Shows appropriate panel based on whose turn it is
8. **Team Selection** - User picks which team to coach at session start

Total estimated tasks: 9
Total estimated commits: 9
