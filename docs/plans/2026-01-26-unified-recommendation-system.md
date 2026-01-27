# Unified Recommendation System Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build the complete recommendation engine with scoring, team evaluation, coach mode, and contextual UI.

**Reference:** See `docs/recommendation-service-overview.md` for formulas, concepts, and data architecture.

**Tech Stack:** Python 3.14+, FastAPI, Pydantic dataclasses, TypeScript/React, WebSocket

---

## Review Corrections (2026-01-27)

The following corrections were made based on code review:

### 1. Matchup Win Rate Direction (Critical)
**Problem:** Original plan incorrectly stated that `counters[champ][vs_lane][role][enemy].win_rate` was the enemy's win rate and needed inversion.

**Actual data:** The win_rate is from the FIRST key's perspective (our champion). `counters[Maokai][vs_lane][JUNGLE][Sejuani].win_rate = 0.739` means Maokai wins 73.9%.

**Fix:** Use win_rate directly for direct lookups. Only invert when doing reverse lookups (looking up `counters[enemy][...][us]`).

### 2. Role Naming Standardization (High)
**Problem:** Plan used `JNG` but actual data uses `JUNGLE`.

**Canonical roles:** `TOP`, `JUNGLE`, `MID`, `ADC`, `SUP`

**Fix:** All `VALID_ROLES` constants updated to use `JUNGLE`.

### 3. Counter vs Matchup Separation (Medium)
**Problem:** Counter score was just copying matchup score, double-weighting the same signal.

**Fix:**
- `matchup` (0.25 weight) → Uses `vs_lane` data (lane-specific matchups)
- `counter` (0.15 weight) → Uses `vs_team` data (team-level matchups)

### 4. Matchup Confidence (Medium)
**Problem:** Sample size and data confidence from `matchup_stats.json` were ignored.

**Fix:** `get_lane_matchup()` now returns `{score, confidence, games, data_source}` instead of just a float.

### 5. Candidate Generation Fallback (Low)
**Problem:** Unknown players returned empty candidate list.

**Fix:** Added `get_top_meta_champions()` fallback when player pool is sparse.

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
│  PickRecommendationEngine (base score × synergy multiplier)                      │
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

Synergy acts as a **multiplier** on the base score, not an additive component. This prevents
synergy from "rescuing" weak picks—it can only amplify or dampen already-viable champions.

```python
# Step 1: Calculate base score from core factors
base_score = (
    meta_score        * 0.25 +   # MetaScorer - is this champion strong right now?
    proficiency_score * 0.35 +   # ProficiencyScorer - can this player execute?
    matchup_score     * 0.25 +   # MatchupCalculator.vs_lane - does this champion win LANE?
    counter_score     * 0.15     # MatchupCalculator.vs_team - does this champion counter TEAM?
)

# Step 2: Apply synergy as a multiplier (±15% swing)
# synergy_score is 0.0-1.0, so (synergy - 0.5) ranges from -0.5 to +0.5
# Multiplied by 0.3 gives a range of -0.15 to +0.15
synergy_multiplier = 1.0 + (synergy_score - 0.5) * 0.3

# Step 3: Final score
final_score = base_score * synergy_multiplier
```

**Multiplier examples:**
- S-tier synergy (1.0) → 1.15x multiplier (15% boost)
- No synergy (0.5) → 1.0x (neutral)
- Anti-synergy (0.0) → 0.85x multiplier (15% penalty)

**Why multiplicative?** A champion with 0.3 base score and perfect synergy gets 0.3 × 1.15 = 0.345.
A champion with 0.7 base score and no synergy gets 0.7 × 1.0 = 0.7. Synergy enhances good picks,
not compensates for bad ones.

## Prerequisites

- [x] `knowledge/meta_stats.json` - champion meta statistics (has pre-computed `meta_score` field)
- [x] `knowledge/matchup_stats.json` - champion counter data (uses `counters` key with hierarchical structure)
- [x] `knowledge/player_proficiency.json` - player performance data (uses `proficiencies` key)
- [x] `knowledge/synergies.json` - curated synergies with S/A/B/C ratings (array format)
- [x] `knowledge/champion_synergies.json` - computed statistical synergies (nested format with `synergy_score`)
- [x] `knowledge/flex_champions.json` - champion role distributions (uses `flex_picks` key)
- [x] `knowledge/player_roles.json` - player role mappings (uses `players` key)
- [ ] `knowledge/champion_archetypes.json` - champion archetype scores (Task 2.1)
- [ ] `knowledge/archetype_counters.json` - RPS effectiveness matrix (Task 2.1)

---

## Data Schema Reference

> **Important:** The actual data schemas below were verified against the knowledge files. Implementations must use these exact structures.

### meta_stats.json

```json
{
  "metadata": { "generated_at": "...", "current_patch": "15.18", ... },
  "champions": {
    "Azir": {
      "presence": 0.392,        // pick_rate + ban_rate
      "win_rate": 0.543,
      "meta_tier": "A",         // S/A/B/C/D
      "meta_score": 0.73,       // Pre-computed, use directly (0.0-1.0)
      "sample_sufficient": true,
      "flags": []               // e.g., ["counter_pick_inflated"]
    }
  }
}
```

**Usage:** Use pre-computed `meta_score` directly rather than recalculating.

### matchup_stats.json

```json
{
  "metadata": { ... },
  "counters": {
    "Corki": {                              // Champion whose matchups we're looking up
      "vs_lane": {
        "MID": {                            // Role (uppercase: TOP, JUNGLE, MID, ADC, SUP)
          "Azir": {                         // Enemy champion
            "games": 32,
            "win_rate": 0.562,              // Corki's WR when facing Azir (OUR perspective)
            "confidence": "HIGH"            // HIGH/MEDIUM/LOW
          }
        }
      },
      "vs_team": {
        "Sejuani": { "games": 61, "win_rate": 0.574 }  // Corki's WR when Sejuani on enemy team
      }
    }
  }
}
```

**Usage:** `counters[our_champ][vs_lane][ROLE][enemy]` gives OUR win rate against enemy. Use directly (no inversion needed).
When looking up reverse (enemy's data about us), invert: `1.0 - counters[enemy][vs_lane][ROLE][us]`.

### player_proficiency.json

```json
{
  "metadata": { ... },
  "proficiencies": {
    "Faker": {
      "Azir": {
        "games_raw": 36,
        "games_weighted": 12.2,             // Recency-weighted
        "win_rate": 0.75,
        "win_rate_weighted": 0.779,
        "kda_normalized": -0.02,            // Relative to role average
        "kp_normalized": -0.49,
        "confidence": "HIGH",               // HIGH (8+), MEDIUM (4-7), LOW (1-3)
        "last_patch": "15.14"
      }
    }
  }
}
```

### synergies.json (Curated)

```json
[
  {
    "id": "orianna_nocturne",
    "champions": ["Orianna", "Nocturne"],
    "strength": "S",                        // S/A/B/C rating
    "type": "ability_combo",
    "description": "Ball delivery via Nocturne ult"
  },
  {
    "id": "yasuo_knockup",
    "champions": ["Yasuo"],
    "partner_requirement": "knockup",
    "best_partners": [
      { "champion": "Malphite", "rating": "S" },
      { "champion": "Diana", "rating": "A" }
    ]
  }
]
```

**Usage:** Check `strength` field for direct pairs, or `best_partners[].rating` for requirement-based synergies.

### champion_synergies.json (Statistical)

```json
{
  "metadata": { ... },
  "synergies": {
    "Aatrox": {
      "Maokai": {
        "games_together": 30,
        "win_rate_together": 0.567,
        "expected_win_rate": 0.485,
        "synergy_delta": 0.081,             // Actual - expected
        "synergy_score": 0.581              // Normalized 0.0-1.0 (0.5 = neutral)
      }
    }
  }
}
```

**Usage:** Use `synergy_score` directly. Curated synergies take priority over statistical.

### flex_champions.json

```json
{
  "metadata": { ... },
  "flex_picks": {
    "Aurora": {
      "MID": 0.696,                         // Role probability
      "TOP": 0.304,
      "is_flex": true,
      "games_total": 414
    },
    "Jinx": {
      "ADC": 1.0,
      "is_flex": false
    }
  }
}
```

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
    """High-tier champion should have high meta score."""
    # Azir has meta_score=0.73 in current data
    score = scorer.get_meta_score("Azir")
    assert 0.7 <= score <= 1.0


def test_get_meta_score_low_presence(scorer):
    """Low presence champion should have lower score."""
    # Aphelios has meta_score=0.312 in current data
    score = scorer.get_meta_score("Aphelios")
    assert 0.0 <= score <= 0.5


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
    # First champion should have high meta score
    if top:
        assert scorer.get_meta_score(top[0]) >= 0.6
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

        Uses pre-computed meta_score from knowledge data (already normalized 0.0-1.0).
        The meta_score is computed during data generation using presence and win rate.

        Returns:
            float 0.0-1.0 where higher = stronger meta pick
        """
        if champion_name not in self._meta_stats:
            return 0.5  # Neutral for unknown

        # Use pre-computed meta_score from knowledge file
        return self._meta_stats[champion_name].get("meta_score", 0.5)

    def get_meta_tier(self, champion_name: str) -> Optional[str]:
        """Get meta tier (S/A/B/C/D) for a champion."""
        if champion_name not in self._meta_stats:
            return None
        return self._meta_stats[champion_name].get("meta_tier")

    def get_top_meta_champions(
        self,
        role: Optional[str] = None,
        limit: int = 10
    ) -> list[str]:
        """Get top meta champions, optionally filtered by role.

        Args:
            role: Optional role filter (TOP, JUNGLE, MID, ADC, SUP)
            limit: Max champions to return

        Returns:
            List of champion names sorted by meta_score descending
        """
        # Note: Role filtering requires flex_champions.json data
        # For now, return top meta picks regardless of role
        ranked = sorted(
            self._meta_stats.items(),
            key=lambda x: x[1].get("meta_score", 0),
            reverse=True
        )
        return [name for name, _ in ranked[:limit]]
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

    VALID_ROLES = {"TOP", "JUNGLE", "MID", "ADC", "SUP"}

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

        # Use pre-computed confidence if available, else calculate
        confidence = champ_data.get("confidence") or self.games_to_confidence(int(games))

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


def test_get_lane_matchup_direct_lookup(calculator):
    """Test lane matchup with direct data lookup.

    Data structure: counters[our_champ][vs_lane][ROLE][enemy] = OUR win_rate
    Example: counters[Maokai][vs_lane][JUNGLE][Sejuani] = 0.739 means Maokai wins 73.9%
    """
    result = calculator.get_lane_matchup("Maokai", "Sejuani", "JUNGLE")
    # Maokai has 73.9% WR vs Sejuani - should be favorable
    assert result["score"] >= 0.7
    assert result["confidence"] in ["HIGH", "MEDIUM", "LOW", "NO_DATA"]
    assert result["games"] >= 0


def test_get_lane_matchup_reverse_lookup(calculator):
    """When we only have enemy's data about us, invert it.

    If counters[Maokai][vs_lane][JUNGLE][Sejuani] = 0.739 (Maokai's WR),
    then get_lane_matchup("Sejuani", "Maokai", "JUNGLE") should invert to ~0.261
    """
    result = calculator.get_lane_matchup("Sejuani", "Maokai", "JUNGLE")
    # Sejuani loses to Maokai (inverse of 0.739)
    assert result["score"] <= 0.35
    assert result["data_source"] == "reverse_lookup"


def test_get_team_matchup(calculator):
    """Test team-level matchup (regardless of lane).

    Data: counters[Maokai][vs_team][Sejuani] = 0.706 means Maokai wins 70.6%
    when Sejuani is on the enemy team.
    """
    result = calculator.get_team_matchup("Maokai", "Sejuani")
    assert result["score"] >= 0.65
    assert 0.0 <= result["score"] <= 1.0


def test_get_matchup_with_flex_uncertainty(calculator):
    """Test matchup calculation with flex pick uncertainty."""
    role_probs = {"MID": 0.7, "TOP": 0.3}

    result = calculator.get_weighted_matchup(
        our_champion="Azir",
        our_role="MID",
        enemy_champion="Aurora",
        enemy_role_probs=role_probs
    )

    assert "score" in result
    assert "confidence" in result
    assert 0.0 <= result["score"] <= 1.0
    assert 0.0 <= result["confidence"] <= 1.0


def test_matchup_unknown_returns_neutral_with_no_data(calculator):
    """Unknown matchup returns 0.5 with NO_DATA confidence."""
    result = calculator.get_lane_matchup("FakeChamp1", "FakeChamp2", "MID")
    assert result["score"] == 0.5
    assert result["confidence"] == "NO_DATA"
    assert result["games"] == 0
```

**Implementation:**

```python
"""Matchup calculation with flex pick uncertainty handling."""
import json
from pathlib import Path
from typing import Optional


class MatchupCalculator:
    """Calculates matchup scores between champions.

    Uses matchup_stats.json which has a "counters" key with hierarchical structure:
    {
      "counters": {
        "ChampionA": {
          "vs_lane": { "ROLE": { "EnemyChamp": { "games": N, "win_rate": 0.XX } } },
          "vs_team": { "EnemyChamp": { "games": N, "win_rate": 0.XX } }
        }
      }
    }

    IMPORTANT: Win rates are from the perspective of ChampionA (the first key).
    counters[Maokai][vs_lane][JUNGLE][Sejuani].win_rate = 0.739 means MAOKAI wins 73.9%.
    """

    def __init__(self, knowledge_dir: Optional[Path] = None):
        if knowledge_dir is None:
            knowledge_dir = Path(__file__).parent.parent.parent.parent.parent.parent / "knowledge"
        self.knowledge_dir = knowledge_dir
        self._counters: dict = {}
        self._load_data()

    def _load_data(self):
        """Load matchup statistics from counters format."""
        matchup_path = self.knowledge_dir / "matchup_stats.json"
        if matchup_path.exists():
            with open(matchup_path) as f:
                data = json.load(f)
                self._counters = data.get("counters", {})

    def get_lane_matchup(
        self,
        our_champion: str,
        enemy_champion: str,
        role: str
    ) -> dict:
        """Get lane-specific matchup score with confidence.

        Args:
            our_champion: Our champion
            enemy_champion: Enemy champion
            role: Lane role (TOP, JUNGLE, MID, ADC, SUP)

        Returns:
            dict with score (0.0-1.0), confidence, games, data_source
        """
        role_upper = role.upper()

        # Direct lookup: counters[our_champ][vs_lane][role][enemy] = OUR win_rate
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

        # Reverse lookup: counters[enemy][vs_lane][role][us] = ENEMY's win_rate
        # We must INVERT this to get our perspective
        if enemy_champion in self._counters:
            vs_lane = self._counters[enemy_champion].get("vs_lane", {})
            role_data = vs_lane.get(role_upper, {})
            if our_champion in role_data:
                matchup = role_data[our_champion]
                enemy_wr = matchup.get("win_rate", 0.5)
                return {
                    "score": round(1.0 - enemy_wr, 3),  # Invert for our perspective
                    "confidence": matchup.get("confidence", "MEDIUM"),
                    "games": matchup.get("games", 0),
                    "data_source": "reverse_lookup"
                }

        # No data available
        return {
            "score": 0.5,
            "confidence": "NO_DATA",
            "games": 0,
            "data_source": "none"
        }

    def get_team_matchup(
        self,
        our_champion: str,
        enemy_champion: str
    ) -> dict:
        """Get team-level matchup (game outcome when both are in game).

        Returns:
            dict with score (0.0-1.0), games, data_source
        """
        # Direct lookup: counters[our_champ][vs_team][enemy] = OUR win_rate
        if our_champion in self._counters:
            vs_team = self._counters[our_champion].get("vs_team", {})
            if enemy_champion in vs_team:
                matchup = vs_team[enemy_champion]
                return {
                    "score": matchup.get("win_rate", 0.5),
                    "games": matchup.get("games", 0),
                    "data_source": "direct_lookup"
                }

        # Reverse lookup: counters[enemy][vs_team][us] = ENEMY's win_rate
        if enemy_champion in self._counters:
            vs_team = self._counters[enemy_champion].get("vs_team", {})
            if our_champion in vs_team:
                matchup = vs_team[our_champion]
                enemy_wr = matchup.get("win_rate", 0.5)
                return {
                    "score": round(1.0 - enemy_wr, 3),  # Invert for our perspective
                    "games": matchup.get("games", 0),
                    "data_source": "reverse_lookup"
                }

        return {
            "score": 0.5,
            "games": 0,
            "data_source": "none"
        }

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
            our_role: Our role (TOP, JUNGLE, MID, ADC, SUP)
            enemy_champion: Enemy champion
            enemy_role_probs: dict mapping role -> probability

        Returns:
            dict with score, confidence, and breakdown
        """
        if not enemy_role_probs:
            return {"score": 0.5, "confidence": 0.0, "data_source": "none"}

        # Check if enemy is in our lane
        enemy_in_our_lane_prob = enemy_role_probs.get(our_role, 0)

        if enemy_in_our_lane_prob > 0:
            # Calculate lane matchup
            lane_result = self.get_lane_matchup(our_champion, enemy_champion, our_role)
            lane_score = lane_result["score"]

            # Use team matchup for when enemy is elsewhere
            team_result = self.get_team_matchup(our_champion, enemy_champion)
            team_score = team_result["score"]

            # Weight by probability
            score = (
                lane_score * enemy_in_our_lane_prob +
                team_score * (1 - enemy_in_our_lane_prob)
            )

            # Confidence accounts for both role certainty and data quality
            data_confidence = 1.0 if lane_result["confidence"] != "NO_DATA" else 0.5
            confidence = enemy_in_our_lane_prob * data_confidence
        else:
            # Enemy not in our lane - use team matchup only
            team_result = self.get_team_matchup(our_champion, enemy_champion)
            score = team_result["score"]
            confidence = 1.0 if team_result["data_source"] != "none" else 0.5

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

**Data Sources:**
This service uses TWO different synergy files:
1. `synergies.json` - Curated mechanical synergies (array format with `strength: "S/A/B/C"`)
2. `champion_synergies.json` - Computed statistical synergies (nested format with `synergy_score: 0.0-1.0`)

**Test first:**

```python
"""Tests for synergy service."""
import pytest
from ban_teemo.services.synergy_service import SynergyService


@pytest.fixture
def service():
    return SynergyService()


def test_get_rating_multiplier(service):
    """Test rating to multiplier conversion."""
    assert service.get_rating_multiplier("S") == 1.0
    assert service.get_rating_multiplier("A") == 0.8
    assert service.get_rating_multiplier("B") == 0.6
    assert service.get_rating_multiplier("C") == 0.4


def test_get_synergy_score_curated(service):
    """Curated synergy (Orianna+Nocturne) should return high score."""
    score = service.get_synergy_score("Orianna", "Nocturne")
    # S-tier curated synergy should be 0.85 × 1.0 = 0.85
    assert score >= 0.8


def test_get_synergy_score_statistical(service):
    """Statistical synergy falls back to champion_synergies.json."""
    # Use a pair that exists in statistical data but not curated
    score = service.get_synergy_score("Aatrox", "Maokai")
    assert 0.0 <= score <= 1.0


def test_get_synergy_score_unknown(service):
    """Unknown pair returns neutral 0.5."""
    score = service.get_synergy_score("FakeChamp1", "FakeChamp2")
    assert score == 0.5


def test_calculate_team_synergy(service):
    """Test team synergy aggregation."""
    result = service.calculate_team_synergy(["Orianna", "Nocturne", "Malphite"])

    assert "total_score" in result
    assert "pair_count" in result
    assert "synergy_pairs" in result
    assert 0.0 <= result["total_score"] <= 1.0


def test_get_best_synergy_partners(service):
    """Test finding best partners for a champion."""
    partners = service.get_best_synergy_partners("Orianna", limit=5)

    assert len(partners) <= 5
    for p in partners:
        assert "champion" in p
        assert "score" in p
```

**Implementation:**

```python
"""Synergy scoring with curated ratings and statistical fallback."""
import json
from pathlib import Path
from typing import Optional


class SynergyService:
    """Scores champion synergies using curated data with statistical fallback.

    Uses two data sources:
    1. synergies.json - Curated mechanical synergies (array with "strength" ratings)
    2. champion_synergies.json - Statistical synergies (nested with "synergy_score")

    Curated synergies take priority; statistical used as fallback.
    """

    RATING_MULTIPLIERS = {
        "S": 1.0,
        "A": 0.8,
        "B": 0.6,
        "C": 0.4,
    }

    BASE_CURATED_SCORE = 0.85  # Curated synergies start at this base

    def __init__(self, knowledge_dir: Optional[Path] = None):
        if knowledge_dir is None:
            knowledge_dir = Path(__file__).parent.parent.parent.parent.parent.parent / "knowledge"
        self.knowledge_dir = knowledge_dir
        self._curated_synergies: dict[tuple[str, str], str] = {}  # (ChampA, ChampB) -> rating
        self._stat_synergies: dict = {}  # ChampA -> {ChampB -> data}
        self._load_data()

    def _load_data(self):
        """Load both curated and statistical synergy data."""
        # Load curated synergies (array format)
        curated_path = self.knowledge_dir / "synergies.json"
        if curated_path.exists():
            with open(curated_path) as f:
                synergies = json.load(f)
                for syn in synergies:
                    champs = syn.get("champions", [])
                    strength = syn.get("strength", "C")

                    # Handle partner_requirement synergies (like Yasuo knockup)
                    if syn.get("partner_requirement"):
                        for partner in syn.get("best_partners", []):
                            partner_champ = partner.get("champion")
                            partner_rating = partner.get("rating", strength)
                            if partner_champ and len(champs) >= 1:
                                key = tuple(sorted([champs[0], partner_champ]))
                                self._curated_synergies[key] = partner_rating

                    # Handle direct champion pair synergies
                    if len(champs) >= 2:
                        key = tuple(sorted(champs[:2]))
                        self._curated_synergies[key] = strength

        # Load statistical synergies (nested format)
        stats_path = self.knowledge_dir / "champion_synergies.json"
        if stats_path.exists():
            with open(stats_path) as f:
                data = json.load(f)
                self._stat_synergies = data.get("synergies", {})

    def get_rating_multiplier(self, rating: str) -> float:
        """Convert S/A/B/C rating to multiplier."""
        return self.RATING_MULTIPLIERS.get(rating.upper(), 0.4)

    def get_synergy_score(self, champ_a: str, champ_b: str) -> float:
        """Get synergy score between two champions.

        Priority: curated synergies > statistical synergies > neutral

        Returns:
            float 0.0-1.0 where higher = stronger synergy
        """
        key = tuple(sorted([champ_a, champ_b]))

        # Check curated synergies first
        if key in self._curated_synergies:
            rating = self._curated_synergies[key]
            multiplier = self.get_rating_multiplier(rating)
            return round(self.BASE_CURATED_SCORE * multiplier, 3)

        # Fall back to statistical synergies
        if champ_a in self._stat_synergies:
            if champ_b in self._stat_synergies[champ_a]:
                return self._stat_synergies[champ_a][champ_b].get("synergy_score", 0.5)

        if champ_b in self._stat_synergies:
            if champ_a in self._stat_synergies[champ_b]:
                return self._stat_synergies[champ_b][champ_a].get("synergy_score", 0.5)

        return 0.5  # Neutral for unknown pairs

    def calculate_team_synergy(self, picks: list[str]) -> dict:
        """Calculate aggregate synergy for a team composition.

        Args:
            picks: List of champion names on the team

        Returns:
            dict with total_score, pair_count, and synergy_pairs details
        """
        if len(picks) < 2:
            return {"total_score": 0.5, "pair_count": 0, "synergy_pairs": []}

        synergy_pairs = []
        scores = []

        # Calculate all pairwise synergies
        for i, champ_a in enumerate(picks):
            for champ_b in picks[i + 1:]:
                score = self.get_synergy_score(champ_a, champ_b)
                scores.append(score)
                if score != 0.5:  # Only track non-neutral
                    synergy_pairs.append({
                        "champions": [champ_a, champ_b],
                        "score": score
                    })

        # Sort pairs by score descending
        synergy_pairs.sort(key=lambda x: -x["score"])

        total_score = sum(scores) / len(scores) if scores else 0.5

        return {
            "total_score": round(total_score, 3),
            "pair_count": len(scores),
            "synergy_pairs": synergy_pairs[:5]  # Top 5 notable pairs
        }

    def get_best_synergy_partners(
        self,
        champion: str,
        limit: int = 10
    ) -> list[dict]:
        """Get best synergy partners for a champion.

        Returns list of {champion, score, source} sorted by score.
        """
        partners = []

        # Check curated synergies
        for key, rating in self._curated_synergies.items():
            if champion in key:
                partner = key[0] if key[1] == champion else key[1]
                score = self.BASE_CURATED_SCORE * self.get_rating_multiplier(rating)
                partners.append({
                    "champion": partner,
                    "score": round(score, 3),
                    "source": "curated",
                    "rating": rating
                })

        # Check statistical synergies
        if champion in self._stat_synergies:
            for partner, data in self._stat_synergies[champion].items():
                score = data.get("synergy_score", 0.5)
                if score > 0.55:  # Only include positive synergies
                    # Skip if already in curated
                    if not any(p["champion"] == partner for p in partners):
                        partners.append({
                            "champion": partner,
                            "score": score,
                            "source": "statistical"
                        })

        # Sort by score and return top N
        partners.sort(key=lambda x: -x["score"])
        return partners[:limit]
```

**Key methods:**
- `get_rating_multiplier(rating)` → S=1.0, A=0.8, B=0.6, C=0.4
- `get_synergy_score(champ_a, champ_b)` → float 0.0-1.0
- `calculate_team_synergy(picks)` → {total_score, pair_count, synergy_pairs}
- `get_best_synergy_partners(champion)` → list of partners

**Note:** The `total_score` from `calculate_team_synergy()` feeds into the recommendation
engine's synergy multiplier: `multiplier = 1.0 + (total_score - 0.5) * 0.3`

**Verify:** `cd backend && uv run pytest tests/test_synergy_service.py -v`

**Commit:** `git commit -m "feat(services): add SynergyService with dual data sources"`

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
    """Each recommendation includes base score, synergy multiplier, and components."""
    recommendations = engine.get_recommendations(
        player_name="Faker",
        player_role="MID",
        our_picks=[],
        enemy_picks=[],
        banned=[],
        limit=3
    )

    for rec in recommendations:
        # Check multiplicative scoring structure
        assert "base_score" in rec
        assert "synergy_multiplier" in rec
        assert 0.85 <= rec["synergy_multiplier"] <= 1.15  # ±15% range

        # Check components
        assert "components" in rec
        components = rec["components"]
        assert "meta" in components
        assert "proficiency" in components
        assert "matchup" in components
        assert "counter" in components
        assert "synergy" in components  # Stored for display


def test_matchup_and_counter_use_different_data(engine):
    """Matchup (vs_lane) and counter (vs_team) should use different data sources.

    This ensures we're not double-counting the same matchup signal.
    """
    # With enemy picks, matchup and counter can differ
    recommendations = engine.get_recommendations(
        player_name="Faker",
        player_role="MID",
        our_picks=[],
        enemy_picks=["Maokai", "Sejuani"],  # Full team for team-level data
        banned=[],
        limit=5
    )

    # At least verify both components exist and are scored
    for rec in recommendations:
        components = rec["components"]
        assert "matchup" in components
        assert "counter" in components
        # Both should be valid scores
        assert 0.0 <= components["matchup"] <= 1.0
        assert 0.0 <= components["counter"] <= 1.0


def test_synergy_multiplier_effect(engine):
    """Synergy should amplify good picks, not rescue bad ones."""
    # Get recommendations with teammates that have known synergies
    recs_with_synergy = engine.get_recommendations(
        player_name="Faker",
        player_role="MID",
        our_picks=["Nocturne", "Jarvan IV"],  # Engage/dive comp
        enemy_picks=[],
        banned=[],
        limit=10
    )

    # Verify multiplier is applied correctly
    for rec in recs_with_synergy:
        base = rec["base_score"]
        multiplier = rec["synergy_multiplier"]
        final = rec["score"]
        # Final should equal base × multiplier (within rounding)
        assert abs(final - (base * multiplier)) < 0.01


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
    """Generates pick recommendations using weighted multi-factor scoring.

    Synergy is applied as a multiplier on the base score, not an additive component.
    This prevents synergy from "rescuing" weak picks.
    """

    # Base score weights (must sum to 1.0)
    BASE_WEIGHTS = {
        "meta": 0.25,        # Is this champion strong in the current meta?
        "proficiency": 0.35, # Can this player execute on this champion?
        "matchup": 0.25,     # Does this champion win its lane matchups?
        "counter": 0.15,     # Does this champion counter enemy team comp?
    }

    # Synergy multiplier range: ±15% swing
    SYNERGY_MULTIPLIER_RANGE = 0.3  # (synergy - 0.5) * this value

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
        """Get candidate champions to consider.

        Sources (in priority order):
        1. Player's champion pool from proficiency data
        2. Meta picks for the role (fallback for unknown players)
        """
        candidates = set()

        # Add player's champion pool
        pool = self.proficiency_scorer.get_player_champion_pool(player_name, min_games=1)
        for entry in pool[:20]:
            if entry["champion"] not in unavailable:
                candidates.add(entry["champion"])

        # Fallback: Add meta picks for unknown players or sparse pools
        if len(candidates) < 5:
            meta_picks = self.meta_scorer.get_top_meta_champions(role=role, limit=15)
            for champ in meta_picks:
                if champ not in unavailable:
                    candidates.add(champ)
                if len(candidates) >= 10:
                    break

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
        """Calculate score using base factors + synergy multiplier.

        Base score = weighted sum of meta, proficiency, matchup, counter
        Final score = base_score × synergy_multiplier
        """
        components = {}
        confidences = {}

        # === BASE SCORE COMPONENTS ===

        # Meta score
        components["meta"] = self.meta_scorer.get_meta_score(champion)
        confidences["meta"] = 1.0  # Always confident in meta data

        # Proficiency score
        prof_score, prof_conf = self.proficiency_scorer.get_proficiency_score(
            player_name, champion
        )
        components["proficiency"] = prof_score
        confidences["proficiency"] = {"HIGH": 1.0, "MEDIUM": 0.8, "LOW": 0.5, "NO_DATA": 0.3}.get(prof_conf, 0.5)

        # Matchup score (lane matchups against enemy laners)
        matchup_score, matchup_conf = self._calculate_lane_matchup_aggregate(
            champion, player_role, enemy_picks
        )
        components["matchup"] = matchup_score
        confidences["matchup"] = matchup_conf

        # Counter score (team-level matchups using vs_team data)
        # This answers: "How well does this champion perform against the enemy TEAM?"
        counter_score, counter_conf = self._calculate_team_counter_aggregate(
            champion, enemy_picks
        )
        components["counter"] = counter_score
        confidences["counter"] = counter_conf

        # === SYNERGY MULTIPLIER (not in base score) ===

        synergy_result = self.synergy_service.calculate_team_synergy(our_picks + [champion])
        synergy_score = synergy_result["total_score"]
        components["synergy"] = synergy_score  # Store for display, but not in base calc

        # Calculate synergy multiplier: 0.85x to 1.15x
        synergy_multiplier = 1.0 + (synergy_score - 0.5) * self.SYNERGY_MULTIPLIER_RANGE
        components["synergy_multiplier"] = synergy_multiplier

        # === CALCULATE BASE SCORE ===

        base_total = 0.0
        weight_sum = 0.0

        for component, weight in self.BASE_WEIGHTS.items():
            conf = confidences.get(component, 1.0)
            effective_weight = weight * conf
            base_total += components.get(component, 0.5) * effective_weight
            weight_sum += effective_weight

        base_score = base_total / weight_sum if weight_sum > 0 else 0.5
        components["base_score"] = base_score

        # === APPLY SYNERGY MULTIPLIER ===

        total_score = base_score * synergy_multiplier

        # Overall confidence (from base components only)
        base_confidences = [confidences[k] for k in self.BASE_WEIGHTS.keys()]
        overall_conf = sum(base_confidences) / len(base_confidences)

        # Determine flag
        flag = None
        if confidences["proficiency"] < 0.5:
            # Low proficiency confidence - check if contextually strong
            contextual_strength = (components["meta"] + components["matchup"]) / 2
            if contextual_strength >= self.SURPRISE_PICK_THRESHOLD:
                flag = "SURPRISE_PICK"
            elif contextual_strength < self.LOW_CONFIDENCE_THRESHOLD:
                flag = "LOW_CONFIDENCE"

        return {
            "total_score": round(total_score, 3),
            "base_score": round(base_score, 3),
            "synergy_multiplier": round(synergy_multiplier, 3),
            "confidence": round(overall_conf, 3),
            "flag": flag,
            "components": {k: round(v, 3) for k, v in components.items()}
        }

    def _calculate_lane_matchup_aggregate(
        self,
        our_champion: str,
        our_role: str,
        enemy_picks: list[str]
    ) -> tuple[float, float]:
        """Calculate aggregate LANE matchup score (vs_lane data).

        This answers: "How well does this champion lane against enemy laners?"
        Uses flex resolution to weight matchups by role probability.
        """
        if not enemy_picks:
            return 0.5, 1.0

        scores = []
        confidences = []

        for enemy in enemy_picks:
            # Get enemy role probabilities for flex handling
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

    def _calculate_team_counter_aggregate(
        self,
        our_champion: str,
        enemy_picks: list[str]
    ) -> tuple[float, float]:
        """Calculate aggregate TEAM counter score (vs_team data).

        This answers: "How well does this champion perform against the enemy TEAM?"
        Uses vs_team matchup data which tracks win rates regardless of role.
        """
        if not enemy_picks:
            return 0.5, 1.0

        scores = []
        data_found = 0

        for enemy in enemy_picks:
            result = self.matchup_calculator.get_team_matchup(our_champion, enemy)
            scores.append(result["score"])
            if result.get("data_source") != "none":
                data_found += 1

        avg_score = sum(scores) / len(scores)
        # Confidence based on how much data we found
        confidence = data_found / len(enemy_picks) if enemy_picks else 0.5

        return avg_score, confidence

    def _generate_reasons(self, champion: str, score_result: dict) -> list[str]:
        """Generate human-readable reasons for recommendation."""
        reasons = []
        components = score_result["components"]

        if components.get("meta", 0) >= 0.7:
            tier = self.meta_scorer.get_meta_tier(champion)
            reasons.append(f"{tier or 'High'}-tier meta pick")

        if components.get("proficiency", 0) >= 0.7:
            reasons.append("Strong player proficiency")

        if components.get("matchup", 0) >= 0.55:
            reasons.append("Favorable matchups")

        # Synergy multiplier feedback
        multiplier = score_result.get("synergy_multiplier", 1.0)
        if multiplier >= 1.10:
            reasons.append("Strong team synergy (+10% or more)")
        elif multiplier <= 0.90:
            reasons.append("Warning: poor team synergy")

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
