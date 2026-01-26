# Unified Recommendation System Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build the complete recommendation engine with scoring, team evaluation, coach mode, and contextual UI.

**Reference:** See `docs/recommendation-service-overview.md` for formulas, concepts, and data architecture.

**Tech Stack:** Python 3.14+, FastAPI, Pydantic dataclasses, TypeScript/React, WebSocket

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              DATA LAYER (exists)                                 │
│  knowledge/*.json: meta_stats, matchup_stats, player_proficiency, synergies,    │
│                    champion_archetypes, archetype_counters, flex_champions      │
└─────────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         STAGE 1: CORE SCORERS                                    │
│  MetaScorer, ProficiencyScorer, MatchupCalculator, FlexResolver                  │
└─────────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                       STAGE 2: ENHANCEMENT SERVICES                              │
│  ArchetypeService, SynergyService, TeamEvaluationService, BanRecommendationSvc   │
└─────────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                       STAGE 3: RECOMMENDATION ENGINE                             │
│  PickRecommendationEngine (combines all scores with weights + confidence)        │
└─────────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          STAGE 4: COACH MODE                                     │
│  EnemyPoolService, turn-based logic, session management                          │
└─────────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          STAGE 5: FRONTEND                                       │
│  Types, EnemyAnalysisPanel, contextual panels, team selector                     │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## Scoring Formula (Final)

```python
score = (
    meta_score        * 0.15 +   # MetaScorer
    proficiency_score * 0.25 +   # ProficiencyScorer (with confidence)
    matchup_score     * 0.15 +   # MatchupCalculator (× FlexResolver confidence)
    synergy_score     * 0.20 +   # SynergyService (S/A/B/C multipliers)
    counter_score     * 0.10 +   # CounterCalculator
    archetype_fit     * 0.15     # ArchetypeService
)
```

## Prerequisites

- [x] `knowledge/meta_stats.json` - champion meta statistics
- [x] `knowledge/matchup_stats.json` - champion matchup data
- [x] `knowledge/player_proficiency.json` - player performance data
- [x] `knowledge/synergies.json` - curated synergies with S/A/B/C ratings
- [x] `knowledge/flex_champions.json` - champion role distributions
- [x] `knowledge/player_roles.json` - player role mappings
- [ ] `knowledge/champion_archetypes.json` - champion archetype scores (Task 2.1)
- [ ] `knowledge/archetype_counters.json` - RPS effectiveness matrix (Task 2.1)

---

## Stage 1: Core Scorers

**Checkpoint:** After Stage 1, basic scoring components work independently.

### Task 1.1: Create MetaScorer

**Files:**
- Create: `backend/src/ban_teemo/services/scorers/meta_scorer.py`
- Create: `backend/tests/test_meta_scorer.py`

**Test first:**

```python
"""Tests for meta scorer."""
import pytest
from ban_teemo.services.scorers.meta_scorer import MetaScorer


@pytest.fixture
def scorer():
    return MetaScorer()


def test_get_meta_score_high_presence(scorer):
    """S-tier champion should have high meta score."""
    # Aurora is typically high presence
    score = scorer.get_meta_score("Aurora")
    assert 0.7 <= score <= 1.0


def test_get_meta_score_low_presence(scorer):
    """Low presence champion should have lower score."""
    score = scorer.get_meta_score("Teemo")
    assert 0.0 <= score <= 0.6


def test_get_meta_score_unknown(scorer):
    """Unknown champion returns neutral score."""
    score = scorer.get_meta_score("NonexistentChamp")
    assert score == 0.5


def test_get_meta_tier(scorer):
    """Test meta tier retrieval."""
    tier = scorer.get_meta_tier("Aurora")
    assert tier in ["S", "A", "B", "C", "D", None]
```

**Implementation:**

```python
"""Meta strength scorer based on pick/ban presence and win rate."""
import json
from pathlib import Path
from typing import Optional


class MetaScorer:
    """Scores champions based on current meta strength."""

    def __init__(self, knowledge_dir: Optional[Path] = None):
        if knowledge_dir is None:
            knowledge_dir = Path(__file__).parent.parent.parent.parent.parent.parent / "knowledge"
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
        """Get meta strength score for a champion.

        Score based on presence (pick+ban rate) and win rate.

        Returns:
            float 0.0-1.0 where higher = stronger meta pick
        """
        if champion_name not in self._meta_stats:
            return 0.5  # Neutral for unknown

        data = self._meta_stats[champion_name]
        presence = data.get("presence", 0)
        win_rate = data.get("win_rate", 0.5)

        # Presence contributes 60%, win rate deviation contributes 40%
        presence_score = min(1.0, presence)  # Cap at 100%
        win_rate_score = (win_rate - 0.45) * 2.5  # Normalize around 50%
        win_rate_score = max(0.0, min(1.0, win_rate_score + 0.5))

        return round(presence_score * 0.6 + win_rate_score * 0.4, 3)

    def get_meta_tier(self, champion_name: str) -> Optional[str]:
        """Get meta tier (S/A/B/C/D) for a champion."""
        if champion_name not in self._meta_stats:
            return None
        return self._meta_stats[champion_name].get("meta_tier")
```

**Verify:** `cd backend && uv run pytest tests/test_meta_scorer.py -v`

**Commit:** `git add backend/src/ban_teemo/services/scorers/ backend/tests/test_meta_scorer.py && git commit -m "feat(scorers): add MetaScorer service"`

---

### Task 1.2: Create FlexResolver

**Files:**
- Create: `backend/src/ban_teemo/services/scorers/flex_resolver.py`
- Create: `backend/tests/test_flex_resolver.py`

**Test first:**

```python
"""Tests for flex pick role resolution."""
import pytest
from ban_teemo.services.scorers.flex_resolver import FlexResolver


@pytest.fixture
def resolver():
    return FlexResolver()


def test_get_role_probabilities_flex(resolver):
    """Flex champion should have multiple roles with probabilities."""
    probs = resolver.get_role_probabilities("Aurora")

    assert isinstance(probs, dict)
    assert sum(probs.values()) == pytest.approx(1.0, abs=0.01)
    # Aurora is typically MID/TOP flex
    assert "MID" in probs or "TOP" in probs


def test_get_role_probabilities_single_role(resolver):
    """Single-role champion should have high probability for one role."""
    probs = resolver.get_role_probabilities("Jinx")

    # Jinx is ADC only
    assert probs.get("ADC", 0) >= 0.9


def test_resolve_with_filled_roles(resolver):
    """Should adjust probabilities when roles are filled."""
    # If MID is filled, Aurora should be 100% TOP
    probs = resolver.get_role_probabilities(
        "Aurora",
        filled_roles={"MID"}
    )

    if "TOP" in probs:
        assert probs["TOP"] >= 0.9


def test_get_matchup_confidence(resolver):
    """Test matchup confidence based on role certainty."""
    # Known single-role champion = high confidence
    conf = resolver.get_matchup_confidence("Jinx", target_role="ADC")
    assert conf >= 0.9

    # Flex champion = lower confidence
    conf = resolver.get_matchup_confidence("Aurora", target_role="MID")
    assert 0.5 <= conf <= 0.95
```

**Implementation:**

```python
"""Flex pick role resolution with probability estimation."""
import json
from pathlib import Path
from typing import Optional


class FlexResolver:
    """Resolves flex pick role probabilities."""

    VALID_ROLES = {"TOP", "JNG", "MID", "ADC", "SUP"}

    def __init__(self, knowledge_dir: Optional[Path] = None):
        if knowledge_dir is None:
            knowledge_dir = Path(__file__).parent.parent.parent.parent.parent.parent / "knowledge"
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
        self,
        champion_name: str,
        filled_roles: Optional[set[str]] = None
    ) -> dict[str, float]:
        """Get role probability distribution for a champion.

        Args:
            champion_name: Champion to resolve
            filled_roles: Roles already filled (excluded from distribution)

        Returns:
            dict mapping role -> probability (sums to 1.0)
        """
        filled = filled_roles or set()

        if champion_name not in self._flex_data:
            # Unknown champion - assume even distribution across unfilled roles
            available = self.VALID_ROLES - filled
            if not available:
                return {}
            prob = 1.0 / len(available)
            return {role: prob for role in available}

        data = self._flex_data[champion_name]

        # Get base probabilities
        probs = {}
        for role in self.VALID_ROLES:
            if role not in filled:
                probs[role] = data.get(role, 0)

        # Normalize to sum to 1.0
        total = sum(probs.values())
        if total > 0:
            probs = {role: p / total for role, p in probs.items()}
        elif probs:
            # All zeros - distribute evenly
            prob = 1.0 / len(probs)
            probs = {role: prob for role in probs}

        return probs

    def get_matchup_confidence(
        self,
        champion_name: str,
        target_role: str,
        filled_roles: Optional[set[str]] = None
    ) -> float:
        """Get confidence level for a matchup given role uncertainty.

        Args:
            champion_name: Champion in question
            target_role: The role we're assuming
            filled_roles: Roles already filled

        Returns:
            float 0.0-1.0 confidence level
        """
        probs = self.get_role_probabilities(champion_name, filled_roles)
        return probs.get(target_role, 0.0)

    def is_flex_pick(self, champion_name: str) -> bool:
        """Check if champion is a flex pick (plays multiple roles)."""
        if champion_name not in self._flex_data:
            return False
        return self._flex_data[champion_name].get("is_flex", False)
```

**Verify:** `cd backend && uv run pytest tests/test_flex_resolver.py -v`

**Commit:** `git commit -m "feat(scorers): add FlexResolver service"`

---

### Task 1.3: Create ProficiencyScorer

**Files:**
- Create: `backend/src/ban_teemo/services/scorers/proficiency_scorer.py`
- Create: `backend/tests/test_proficiency_scorer.py`

**Test first:**

```python
"""Tests for player proficiency scoring."""
import pytest
from ban_teemo.services.scorers.proficiency_scorer import ProficiencyScorer


@pytest.fixture
def scorer():
    return ProficiencyScorer()


def test_get_proficiency_score(scorer):
    """Test basic proficiency lookup."""
    # Use a known pro player
    score, confidence = scorer.get_proficiency_score("Faker", "Azir")

    assert 0.0 <= score <= 1.0
    assert confidence in ["HIGH", "MEDIUM", "LOW", "NO_DATA"]


def test_get_proficiency_unknown_player(scorer):
    """Unknown player returns neutral score with NO_DATA."""
    score, confidence = scorer.get_proficiency_score("UnknownPlayer123", "Azir")

    assert score == 0.5
    assert confidence == "NO_DATA"


def test_get_proficiency_unknown_champion(scorer):
    """Known player, unknown champion returns NO_DATA."""
    score, confidence = scorer.get_proficiency_score("Faker", "NonexistentChamp")

    assert confidence == "NO_DATA"


def test_confidence_levels(scorer):
    """Test confidence thresholds."""
    # HIGH = 8+ games, MEDIUM = 4-7, LOW = 1-3, NO_DATA = 0
    games_to_conf = scorer.games_to_confidence(10)
    assert games_to_conf == "HIGH"

    games_to_conf = scorer.games_to_confidence(5)
    assert games_to_conf == "MEDIUM"

    games_to_conf = scorer.games_to_confidence(2)
    assert games_to_conf == "LOW"

    games_to_conf = scorer.games_to_confidence(0)
    assert games_to_conf == "NO_DATA"
```

**Implementation:**

```python
"""Player proficiency scoring with confidence tracking."""
import json
from pathlib import Path
from typing import Optional


class ProficiencyScorer:
    """Scores player proficiency on champions with confidence levels."""

    CONFIDENCE_THRESHOLDS = {
        "HIGH": 8,
        "MEDIUM": 4,
        "LOW": 1,
    }

    def __init__(self, knowledge_dir: Optional[Path] = None):
        if knowledge_dir is None:
            knowledge_dir = Path(__file__).parent.parent.parent.parent.parent.parent / "knowledge"
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

    def get_proficiency_score(
        self,
        player_name: str,
        champion_name: str
    ) -> tuple[float, str]:
        """Get proficiency score and confidence for player-champion pair.

        Args:
            player_name: Player's in-game name
            champion_name: Champion name

        Returns:
            tuple of (score 0.0-1.0, confidence level)
        """
        if player_name not in self._proficiency_data:
            return 0.5, "NO_DATA"

        player_data = self._proficiency_data[player_name]

        if champion_name not in player_data:
            return 0.5, "NO_DATA"

        champ_data = player_data[champion_name]

        # Get raw values
        games = champ_data.get("games_raw", champ_data.get("games_weighted", 0))
        win_rate = champ_data.get("win_rate_weighted", champ_data.get("win_rate", 0.5))

        # Calculate score from win rate and games
        games_factor = min(1.0, games / 10)  # Cap at 10 games
        score = win_rate * 0.6 + games_factor * 0.4

        # Determine confidence
        confidence = self.games_to_confidence(games)

        return round(score, 3), confidence

    def games_to_confidence(self, games: int) -> str:
        """Convert game count to confidence level."""
        if games >= self.CONFIDENCE_THRESHOLDS["HIGH"]:
            return "HIGH"
        elif games >= self.CONFIDENCE_THRESHOLDS["MEDIUM"]:
            return "MEDIUM"
        elif games >= self.CONFIDENCE_THRESHOLDS["LOW"]:
            return "LOW"
        else:
            return "NO_DATA"

    def get_player_champion_pool(
        self,
        player_name: str,
        min_games: int = 1
    ) -> list[dict]:
        """Get a player's champion pool sorted by proficiency.

        Returns list of {champion, score, games, confidence}
        """
        if player_name not in self._proficiency_data:
            return []

        pool = []
        for champ, data in self._proficiency_data[player_name].items():
            games = data.get("games_raw", 0)
            if games >= min_games:
                score, conf = self.get_proficiency_score(player_name, champ)
                pool.append({
                    "champion": champ,
                    "score": score,
                    "games": games,
                    "confidence": conf
                })

        return sorted(pool, key=lambda x: -x["score"])
```

**Verify:** `cd backend && uv run pytest tests/test_proficiency_scorer.py -v`

**Commit:** `git commit -m "feat(scorers): add ProficiencyScorer service"`

---

### Task 1.4: Create MatchupCalculator

**Files:**
- Create: `backend/src/ban_teemo/services/scorers/matchup_calculator.py`
- Create: `backend/tests/test_matchup_calculator.py`

**Test first:**

```python
"""Tests for matchup calculation."""
import pytest
from ban_teemo.services.scorers.matchup_calculator import MatchupCalculator


@pytest.fixture
def calculator():
    return MatchupCalculator()


def test_get_lane_matchup(calculator):
    """Test lane matchup lookup."""
    score = calculator.get_lane_matchup("Syndra", "Azir", "MID")
    assert 0.0 <= score <= 1.0


def test_get_team_matchup(calculator):
    """Test team-level matchup (regardless of lane)."""
    score = calculator.get_team_matchup("Syndra", "Azir")
    assert 0.0 <= score <= 1.0


def test_get_matchup_with_flex_uncertainty(calculator):
    """Test matchup calculation with flex pick uncertainty."""
    # Aurora could be MID or TOP
    role_probs = {"MID": 0.7, "TOP": 0.3}

    result = calculator.get_weighted_matchup(
        our_champion="Syndra",
        our_role="MID",
        enemy_champion="Aurora",
        enemy_role_probs=role_probs
    )

    assert "score" in result
    assert "confidence" in result
    assert 0.0 <= result["score"] <= 1.0
    assert 0.0 <= result["confidence"] <= 1.0


def test_matchup_unknown_returns_neutral(calculator):
    """Unknown matchup returns 0.5."""
    score = calculator.get_lane_matchup("FakeChamp1", "FakeChamp2", "MID")
    assert score == 0.5
```

**Implementation:**

```python
"""Matchup calculation with flex pick uncertainty handling."""
import json
from pathlib import Path
from typing import Optional


class MatchupCalculator:
    """Calculates matchup scores between champions."""

    def __init__(self, knowledge_dir: Optional[Path] = None):
        if knowledge_dir is None:
            knowledge_dir = Path(__file__).parent.parent.parent.parent.parent.parent / "knowledge"
        self.knowledge_dir = knowledge_dir
        self._matchup_stats: dict = {}
        self._load_data()

    def _load_data(self):
        """Load matchup statistics."""
        matchup_path = self.knowledge_dir / "matchup_stats.json"
        if matchup_path.exists():
            with open(matchup_path) as f:
                data = json.load(f)
                self._matchup_stats = data.get("matchups", {})

    def get_lane_matchup(
        self,
        our_champion: str,
        enemy_champion: str,
        role: str
    ) -> float:
        """Get lane-specific matchup score.

        Args:
            our_champion: Our champion
            enemy_champion: Enemy champion
            role: Lane role (TOP, MID, etc.)

        Returns:
            float 0.0-1.0 (0.5 = neutral, >0.5 = favorable)
        """
        key = f"{our_champion}_vs_{enemy_champion}"

        if key not in self._matchup_stats:
            return 0.5

        matchup = self._matchup_stats[key]
        role_data = matchup.get("by_role", {}).get(role, {})

        if not role_data:
            # Fall back to overall matchup
            return matchup.get("win_rate", 0.5)

        return role_data.get("win_rate", 0.5)

    def get_team_matchup(
        self,
        our_champion: str,
        enemy_champion: str
    ) -> float:
        """Get team-level matchup (game outcome when both are in game).

        Returns:
            float 0.0-1.0 win rate when both champions are in game
        """
        key = f"{our_champion}_vs_{enemy_champion}"

        if key not in self._matchup_stats:
            return 0.5

        return self._matchup_stats[key].get("team_win_rate", 0.5)

    def get_weighted_matchup(
        self,
        our_champion: str,
        our_role: str,
        enemy_champion: str,
        enemy_role_probs: dict[str, float]
    ) -> dict:
        """Calculate matchup with flex pick uncertainty.

        Weights lane matchup by role probability, falls back to team matchup.

        Args:
            our_champion: Our champion
            our_role: Our role
            enemy_champion: Enemy champion
            enemy_role_probs: dict mapping role -> probability

        Returns:
            dict with score and confidence
        """
        if not enemy_role_probs:
            return {"score": 0.5, "confidence": 0.0}

        # Check if enemy is in our lane
        enemy_in_our_lane_prob = enemy_role_probs.get(our_role, 0)

        if enemy_in_our_lane_prob > 0:
            # Calculate lane matchup
            lane_score = self.get_lane_matchup(our_champion, enemy_champion, our_role)
            # Use team matchup for when enemy is elsewhere
            team_score = self.get_team_matchup(our_champion, enemy_champion)

            # Weight by probability
            score = (
                lane_score * enemy_in_our_lane_prob +
                team_score * (1 - enemy_in_our_lane_prob)
            )
            confidence = enemy_in_our_lane_prob
        else:
            # Enemy not in our lane - use team matchup
            score = self.get_team_matchup(our_champion, enemy_champion)
            confidence = 1.0  # Confident they're NOT in our lane

        return {
            "score": round(score, 3),
            "confidence": round(confidence, 3)
        }
```

**Verify:** `cd backend && uv run pytest tests/test_matchup_calculator.py -v`

**Commit:** `git commit -m "feat(scorers): add MatchupCalculator service"`

---

### Task 1.5: Create Scorers Package Init

**Files:**
- Create: `backend/src/ban_teemo/services/scorers/__init__.py`

```python
"""Core scoring components for recommendation engine."""
from ban_teemo.services.scorers.meta_scorer import MetaScorer
from ban_teemo.services.scorers.flex_resolver import FlexResolver
from ban_teemo.services.scorers.proficiency_scorer import ProficiencyScorer
from ban_teemo.services.scorers.matchup_calculator import MatchupCalculator

__all__ = [
    "MetaScorer",
    "FlexResolver",
    "ProficiencyScorer",
    "MatchupCalculator",
]
```

**Verify:** `cd backend && python -c "from ban_teemo.services.scorers import MetaScorer, FlexResolver; print('OK')"`

**Commit:** `git commit -m "feat(scorers): add scorers package init"`

---

## Stage 1 Checkpoint

After completing Stage 1, verify all core scorers work:

```bash
cd backend && uv run pytest tests/test_meta_scorer.py tests/test_flex_resolver.py tests/test_proficiency_scorer.py tests/test_matchup_calculator.py -v
```

**Expected:** All tests pass. Core scoring infrastructure ready.

---

## Stage 2: Enhancement Services

**Checkpoint:** After Stage 2, team evaluation and archetype system work.

### Task 2.1: Create Archetype Data Files

**Files:**
- Create: `knowledge/archetype_counters.json`
- Add to: `scripts/build_computed_datasets.py`
- Generate: `knowledge/champion_archetypes.json`

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
  }
}
```

**Step 2: Run build script for champion_archetypes**

Add `build_champion_archetypes` function to build script (see Enhancement plan Task 2 for full implementation).

Run: `python scripts/build_computed_datasets.py --dataset champion_archetypes`

**Verify:** `ls -la knowledge/champion_archetypes.json knowledge/archetype_counters.json`

**Commit:** `git commit -m "feat(data): add archetype counter matrix and champion archetypes"`

---

### Task 2.2: Create ArchetypeService

**Files:**
- Create: `backend/src/ban_teemo/services/archetype_service.py`
- Create: `backend/tests/test_archetype_service.py`

See Enhancement plan Task 3 for full test and implementation.

**Key methods:**
- `get_champion_archetypes(champion)` → {primary, secondary, scores}
- `calculate_team_archetype(picks)` → {primary, secondary, scores, alignment}
- `get_archetype_effectiveness(our, enemy)` → float multiplier
- `calculate_comp_advantage(our_picks, enemy_picks)` → dict

**Commit:** `git commit -m "feat(services): add ArchetypeService"`

---

### Task 2.3: Create SynergyService

**Files:**
- Create: `backend/src/ban_teemo/services/synergy_service.py`
- Create: `backend/tests/test_synergy_service.py`

See Enhancement plan Task 4 for full test and implementation.

**Key methods:**
- `get_rating_multiplier(rating)` → S=1.0, A=0.8, B=0.6, C=0.4
- `get_synergy_score(champ_a, champ_b)` → float 0.0-1.0
- `calculate_team_synergy(picks)` → {total_score, pair_count, synergy_pairs}
- `get_best_synergy_partners(champion)` → list of partners

**Commit:** `git commit -m "feat(services): add SynergyService with rating multipliers"`

---

### Task 2.4: Create TeamEvaluationService

**Files:**
- Create: `backend/src/ban_teemo/services/team_evaluation_service.py`
- Create: `backend/tests/test_team_evaluation_service.py`

See Enhancement plan Task 5 for full test and implementation.

**Key methods:**
- `evaluate_team_draft(picks)` → {archetype, synergy, composition_score, strengths, weaknesses}
- `evaluate_vs_enemy(our_picks, enemy_picks)` → {our_evaluation, enemy_evaluation, matchup_advantage}

**Commit:** `git commit -m "feat(services): add TeamEvaluationService"`

---

### Task 2.5: Create BanRecommendationService

**Files:**
- Create: `backend/src/ban_teemo/services/ban_recommendation_service.py`
- Create: `backend/tests/test_ban_recommendation_service.py`

See Enhancement plan Task 6 for full test and implementation.

**Key methods:**
- `get_ban_recommendations(enemy_team_id, our_picks, enemy_picks, banned, phase)` → list
- `calculate_ban_priority(champion, enemy_team_id, our_archetype, enemy_archetype)` → float

**Commit:** `git commit -m "feat(services): add BanRecommendationService"`

---

## Stage 2 Checkpoint

After completing Stage 2, verify enhancement services:

```bash
cd backend && uv run pytest tests/test_archetype_service.py tests/test_synergy_service.py tests/test_team_evaluation_service.py tests/test_ban_recommendation_service.py -v
```

**Expected:** All tests pass. Team evaluation and archetype system ready.

---

## Stage 3: Recommendation Engine

**Checkpoint:** After Stage 3, the complete pick recommendation engine works.

### Task 3.1: Create PickRecommendationEngine

**Files:**
- Create: `backend/src/ban_teemo/services/pick_recommendation_engine.py`
- Create: `backend/tests/test_pick_recommendation_engine.py`

**Test first:**

```python
"""Tests for pick recommendation engine."""
import pytest
from ban_teemo.services.pick_recommendation_engine import PickRecommendationEngine


@pytest.fixture
def engine():
    return PickRecommendationEngine()


def test_get_pick_recommendations(engine):
    """Test generating pick recommendations."""
    recommendations = engine.get_recommendations(
        player_name="Faker",
        player_role="MID",
        our_picks=["Malphite"],
        enemy_picks=["Fiora"],
        banned=["Aurora", "Yone"],
        limit=5
    )

    assert len(recommendations) <= 5
    for rec in recommendations:
        assert "champion_name" in rec
        assert "score" in rec
        assert "confidence" in rec
        assert 0.0 <= rec["score"] <= 1.0


def test_recommendations_exclude_unavailable(engine):
    """Banned and picked champions excluded."""
    recommendations = engine.get_recommendations(
        player_name="Faker",
        player_role="MID",
        our_picks=["Orianna"],
        enemy_picks=["Azir"],
        banned=["Aurora", "Syndra"],
        limit=10
    )

    names = {r["champion_name"] for r in recommendations}
    assert "Orianna" not in names
    assert "Azir" not in names
    assert "Aurora" not in names
    assert "Syndra" not in names


def test_recommendations_include_score_breakdown(engine):
    """Each recommendation includes score components."""
    recommendations = engine.get_recommendations(
        player_name="Faker",
        player_role="MID",
        our_picks=[],
        enemy_picks=[],
        banned=[],
        limit=3
    )

    for rec in recommendations:
        assert "components" in rec
        components = rec["components"]
        assert "meta" in components
        assert "proficiency" in components
        assert "synergy" in components
        assert "archetype_fit" in components


def test_surprise_pick_detection(engine):
    """Low-game champions flagged as surprise picks when contextually strong."""
    # This tests the surprise pick logic
    recommendations = engine.get_recommendations(
        player_name="Faker",
        player_role="MID",
        our_picks=["Nocturne"],  # Creates Orianna synergy
        enemy_picks=["Azir"],  # Orianna counters
        banned=[],
        limit=10
    )

    # Check if any recommendations have SURPRISE_PICK flag
    flags = [r.get("flag") for r in recommendations]
    # At least verify flag field exists
    assert all(f in [None, "SURPRISE_PICK", "LOW_CONFIDENCE"] for f in flags)
```

**Implementation:**

```python
"""Pick recommendation engine combining all scoring components."""
from typing import Optional
from pathlib import Path

from ban_teemo.services.scorers import MetaScorer, FlexResolver, ProficiencyScorer, MatchupCalculator
from ban_teemo.services.archetype_service import ArchetypeService
from ban_teemo.services.synergy_service import SynergyService


class PickRecommendationEngine:
    """Generates pick recommendations using weighted multi-factor scoring."""

    # Scoring weights
    WEIGHTS = {
        "meta": 0.15,
        "proficiency": 0.25,
        "matchup": 0.15,
        "synergy": 0.20,
        "counter": 0.10,
        "archetype_fit": 0.15,
    }

    # Confidence thresholds
    SURPRISE_PICK_THRESHOLD = 0.65
    LOW_CONFIDENCE_THRESHOLD = 0.65

    def __init__(self, knowledge_dir: Optional[Path] = None):
        self.meta_scorer = MetaScorer(knowledge_dir)
        self.flex_resolver = FlexResolver(knowledge_dir)
        self.proficiency_scorer = ProficiencyScorer(knowledge_dir)
        self.matchup_calculator = MatchupCalculator(knowledge_dir)
        self.archetype_service = ArchetypeService(knowledge_dir)
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
        """Generate ranked pick recommendations.

        Args:
            player_name: Player making the pick
            player_role: Role being picked for
            our_picks: Champions our team has picked
            enemy_picks: Champions enemy has picked
            banned: All banned champions
            limit: Max recommendations to return

        Returns:
            List of recommendations sorted by score
        """
        unavailable = set(banned) | set(our_picks) | set(enemy_picks)

        # Get team archetype for fit scoring
        team_archetype = self.archetype_service.calculate_team_archetype(our_picks)

        # Get candidate champions (from player pool + meta)
        candidates = self._get_candidates(player_name, player_role, unavailable)

        recommendations = []

        for champ in candidates:
            score_result = self._calculate_champion_score(
                champion=champ,
                player_name=player_name,
                player_role=player_role,
                our_picks=our_picks,
                enemy_picks=enemy_picks,
                team_archetype=team_archetype
            )

            recommendations.append({
                "champion_name": champ,
                "score": score_result["total_score"],
                "confidence": score_result["confidence"],
                "flag": score_result["flag"],
                "components": score_result["components"],
                "reasons": self._generate_reasons(champ, score_result)
            })

        # Sort by score
        recommendations.sort(key=lambda x: -x["score"])
        return recommendations[:limit]

    def _get_candidates(
        self,
        player_name: str,
        role: str,
        unavailable: set[str]
    ) -> list[str]:
        """Get candidate champions to consider."""
        candidates = set()

        # Add player's champion pool
        pool = self.proficiency_scorer.get_player_champion_pool(player_name, min_games=1)
        for entry in pool[:20]:
            if entry["champion"] not in unavailable:
                candidates.add(entry["champion"])

        # Add meta picks for the role
        # (would need role filtering in meta_stats)

        return list(candidates)

    def _calculate_champion_score(
        self,
        champion: str,
        player_name: str,
        player_role: str,
        our_picks: list[str],
        enemy_picks: list[str],
        team_archetype: dict
    ) -> dict:
        """Calculate weighted score for a champion."""
        components = {}
        confidences = {}

        # Meta score
        components["meta"] = self.meta_scorer.get_meta_score(champion)
        confidences["meta"] = 1.0  # Always confident in meta data

        # Proficiency score
        prof_score, prof_conf = self.proficiency_scorer.get_proficiency_score(
            player_name, champion
        )
        components["proficiency"] = prof_score
        confidences["proficiency"] = {"HIGH": 1.0, "MEDIUM": 0.8, "LOW": 0.5, "NO_DATA": 0.3}.get(prof_conf, 0.5)

        # Matchup score (aggregate across enemy picks)
        matchup_score, matchup_conf = self._calculate_matchup_aggregate(
            champion, player_role, enemy_picks
        )
        components["matchup"] = matchup_score
        confidences["matchup"] = matchup_conf

        # Synergy score
        synergy_result = self.synergy_service.calculate_team_synergy(our_picks + [champion])
        components["synergy"] = synergy_result["total_score"]
        confidences["synergy"] = 1.0

        # Counter score (simplified - same as matchup for now)
        components["counter"] = matchup_score
        confidences["counter"] = matchup_conf

        # Archetype fit
        champ_archetypes = self.archetype_service.get_champion_archetypes(champion)
        primary_archetype = team_archetype.get("primary")
        if primary_archetype:
            components["archetype_fit"] = champ_archetypes["scores"].get(primary_archetype, 0.3)
        else:
            components["archetype_fit"] = 0.5
        confidences["archetype_fit"] = 1.0

        # Calculate weighted total with confidence penalties
        total = 0.0
        weight_sum = 0.0

        for component, weight in self.WEIGHTS.items():
            conf = confidences.get(component, 1.0)
            effective_weight = weight * conf
            total += components.get(component, 0.5) * effective_weight
            weight_sum += effective_weight

        total_score = total / weight_sum if weight_sum > 0 else 0.5

        # Overall confidence
        overall_conf = sum(confidences.values()) / len(confidences)

        # Determine flag
        flag = None
        if confidences["proficiency"] < 0.5:
            # Low proficiency confidence
            contextual_strength = (components["meta"] + components["synergy"] + components["matchup"]) / 3
            if contextual_strength >= self.SURPRISE_PICK_THRESHOLD:
                flag = "SURPRISE_PICK"
            elif contextual_strength < self.LOW_CONFIDENCE_THRESHOLD:
                flag = "LOW_CONFIDENCE"

        return {
            "total_score": round(total_score, 3),
            "confidence": round(overall_conf, 3),
            "flag": flag,
            "components": {k: round(v, 3) for k, v in components.items()}
        }

    def _calculate_matchup_aggregate(
        self,
        our_champion: str,
        our_role: str,
        enemy_picks: list[str]
    ) -> tuple[float, float]:
        """Calculate aggregate matchup score across all enemy picks."""
        if not enemy_picks:
            return 0.5, 1.0

        scores = []
        confidences = []

        for enemy in enemy_picks:
            # Get enemy role probabilities
            role_probs = self.flex_resolver.get_role_probabilities(enemy)

            result = self.matchup_calculator.get_weighted_matchup(
                our_champion=our_champion,
                our_role=our_role,
                enemy_champion=enemy,
                enemy_role_probs=role_probs
            )

            scores.append(result["score"])
            confidences.append(result["confidence"])

        avg_score = sum(scores) / len(scores)
        avg_conf = sum(confidences) / len(confidences)

        return avg_score, avg_conf

    def _generate_reasons(self, champion: str, score_result: dict) -> list[str]:
        """Generate human-readable reasons for recommendation."""
        reasons = []
        components = score_result["components"]

        if components.get("meta", 0) >= 0.7:
            tier = self.meta_scorer.get_meta_tier(champion)
            reasons.append(f"{tier or 'High'}-tier meta pick")

        if components.get("proficiency", 0) >= 0.7:
            reasons.append("Strong player proficiency")

        if components.get("synergy", 0) >= 0.65:
            reasons.append("Good team synergy")

        if components.get("archetype_fit", 0) >= 0.7:
            reasons.append("Fits team composition direction")

        if components.get("matchup", 0) >= 0.55:
            reasons.append("Favorable matchups")

        if score_result["flag"] == "SURPRISE_PICK":
            reasons.append("Contextually strong despite low games")

        return reasons if reasons else ["Solid overall pick"]
```

**Verify:** `cd backend && uv run pytest tests/test_pick_recommendation_engine.py -v`

**Commit:** `git commit -m "feat(engine): add PickRecommendationEngine"`

---

### Task 3.2: Update Recommendation Models

**Files:**
- Modify: `backend/src/ban_teemo/models/recommendations.py`

Add the full model structure from Coach Mode plan Task 1. Key dataclasses:
- `PickRecommendation`
- `BanRecommendation`
- `ArchetypeScore`
- `TeamEvaluation`
- `EnemyCandidate`
- `EnemyRolePool`
- `EnemyAnalysis`
- `Recommendations`

**Commit:** `git commit -m "feat(models): extend recommendations with full model structure"`

---

## Stage 3 Checkpoint

After completing Stage 3, verify the recommendation engine:

```bash
cd backend && uv run pytest tests/test_pick_recommendation_engine.py -v
```

**Expected:** All tests pass. Complete pick recommendation engine ready.

---

## Stage 4: Coach Mode

**Checkpoint:** After Stage 4, coach mode with turn-based logic works.

### Task 4.1: Create EnemyPoolService

**Files:**
- Create: `backend/src/ban_teemo/services/enemy_pool_service.py`
- Create: `backend/tests/test_enemy_pool_service.py`

See Coach Mode plan Task 2 for full test and implementation.

**Key methods:**
- `get_player_champion_pool(player_name, role, exclude, limit)` → list[EnemyCandidate]
- `analyze_enemy_team(enemy_team, banned, enemy_picks, our_picks)` → EnemyAnalysis

**Commit:** `git commit -m "feat(services): add EnemyPoolService"`

---

### Task 4.2: Update DraftService with Coach Mode

**Files:**
- Modify: `backend/src/ban_teemo/services/draft_service.py`
- Create: `backend/tests/test_draft_service_coach_mode.py`

See Coach Mode plan Task 3 for full test and implementation.

**Key changes:**
- Add `coaching_team` parameter to `get_recommendations`
- Determine `is_our_turn` based on `next_team == coaching_team`
- Return pick/ban recommendations on our turn
- Return enemy analysis on enemy turn
- Always include team evaluation

**Commit:** `git commit -m "feat(services): add coach mode to DraftService"`

---

### Task 4.3: Update WebSocket Protocol

**Files:**
- Modify: `backend/src/ban_teemo/services/replay_manager.py`
- Modify: `backend/src/ban_teemo/api/websockets/replay_ws.py`

See Coach Mode plan Task 4 for full implementation.

**Key changes:**
- Add `coaching_team` to `ReplaySession`
- Update `_serialize_recommendations` for new model fields
- Pass `coaching_team` to `get_recommendations`

**Commit:** `git commit -m "feat(ws): update WebSocket for coach mode"`

---

## Stage 4 Checkpoint

After completing Stage 4, verify coach mode:

```bash
cd backend && uv run pytest tests/test_enemy_pool_service.py tests/test_draft_service_coach_mode.py -v
```

**Expected:** All tests pass. Coach mode backend ready.

---

## Stage 5: Frontend

**Checkpoint:** After Stage 5, the full UI works with coach mode.

### Task 5.1: Update TypeScript Types

**Files:**
- Modify: `deepdraft/src/types/index.ts`

See Coach Mode plan Task 5. Add:
- `ArchetypeScore`
- `TeamEvaluation`
- `EnemyCandidate`
- `EnemyRolePool`
- `EnemyAnalysis`
- Update `Recommendations` interface

**Commit:** `git commit -m "feat(types): add TypeScript types for coach mode"`

---

### Task 5.2: Create EnemyAnalysisPanel

**Files:**
- Create: `deepdraft/src/components/EnemyAnalysisPanel/index.tsx`

See Coach Mode plan Task 6 for full implementation.

**Commit:** `git commit -m "feat(ui): add EnemyAnalysisPanel component"`

---

### Task 5.3: Update App with Contextual Panels

**Files:**
- Modify: `deepdraft/src/App.tsx`
- Modify: `deepdraft/src/hooks/useReplaySession.ts`

See Coach Mode plan Tasks 7-8 for full implementation.

**Key changes:**
- Show `RecommendationPanel` when `phase === "our_turn"`
- Show `EnemyAnalysisPanel` when `phase === "enemy_turn"`
- Always show `TeamEvaluationBar`
- Add team selector to `ReplayControls`

**Commit:** `git commit -m "feat(ui): add contextual panels and team selector"`

---

## Stage 5 Checkpoint

After completing Stage 5, verify frontend builds:

```bash
cd deepdraft && npm run build
```

**Expected:** Build succeeds. Full UI ready.

---

## Final Integration Test

### Task 6.1: Run Full Test Suite

```bash
# Backend tests
cd backend && uv run pytest tests/ -v

# Frontend build
cd deepdraft && npm run build

# Linting
cd backend && uv run ruff check src/
```

### Task 6.2: Manual Integration Test

1. Start backend: `cd backend && uv run uvicorn ban_teemo.main:app --reload`
2. Start frontend: `cd deepdraft && npm run dev`
3. Select "Coach Blue Team"
4. Start a replay
5. Verify:
   - Blue's turn → RecommendationPanel with picks/bans
   - Red's turn → EnemyAnalysisPanel with threat rankings
   - Team evaluation bar always visible
   - Recommendations include score breakdowns

---

## Summary

| Stage | Tasks | Focus |
|-------|-------|-------|
| 1 | 1.1-1.5 | Core scorers (Meta, Flex, Proficiency, Matchup) |
| 2 | 2.1-2.5 | Enhancement services (Archetype, Synergy, TeamEval, Ban) |
| 3 | 3.1-3.2 | Recommendation engine (combines all scores) |
| 4 | 4.1-4.3 | Coach mode (EnemyPool, turn logic, WebSocket) |
| 5 | 5.1-5.3 | Frontend (types, panels, contextual UI) |
| 6 | 6.1-6.2 | Integration testing |

**Total tasks:** 18
**Estimated commits:** 18

Each stage has a checkpoint to verify progress before continuing.
