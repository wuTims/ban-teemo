# Draft Simulator Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build an interactive draft simulator with AI-controlled opponents, powered by a real recommendation engine.

**Architecture:** Stages 1-3 build the recommendation engine (scorers → services → engine). Stage 4 adds simulator backend (enemy AI, session management). Stage 5 builds the simulator frontend (champion pool, 3-column layout).

**Tech Stack:** Python 3.14+, FastAPI, Pydantic, TypeScript, React, Tailwind CSS

**Reference:**
- `docs/plans/2026-01-27-draft-simulator-design.md` - Design document
- `docs/plans/2026-01-26-unified-recommendation-system.md` - Scoring formulas and data schemas

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

Build synergy scoring and team evaluation.

---

### Task 2.1: Create SynergyService

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

### Task 2.2: Create PickRecommendationEngine

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
    fearless_blocked: set[str] = field(default_factory=set)

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
        # Step 1: Try reference script
        for action in strategy.draft_script:
            if action.sequence == sequence and action.champion_name not in unavailable:
                return action.champion_name, "reference_game"

        # Step 2: Try fallback games
        for fallback_id in strategy.fallback_game_ids:
            actions = self.repo.get_draft_actions(fallback_id)
            for action in actions:
                if action.sequence == sequence and action.champion_name not in unavailable:
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
from ban_teemo.services.draft_service import DraftService
from ban_teemo.repositories.draft_repository import DraftRepository


router = APIRouter(prefix="/api/simulator", tags=["simulator"])

# In-memory session storage
_sessions: dict[str, SimulatorSession] = {}
_enemy_service: Optional[EnemySimulatorService] = None
_recommendation_engine: Optional[PickRecommendationEngine] = None
_draft_service: Optional[DraftService] = None
_repository: Optional[DraftRepository] = None


def get_services(data_path: str):
    """Initialize services lazily."""
    global _enemy_service, _recommendation_engine, _draft_service, _repository
    if _enemy_service is None:
        _enemy_service = EnemySimulatorService(data_path)
        _recommendation_engine = PickRecommendationEngine()
        _draft_service = DraftService(data_path)
        _repository = DraftRepository(data_path)
    return _enemy_service, _recommendation_engine, _draft_service, _repository


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
    enemy_service, rec_engine, draft_service, repo = get_services(data_path)

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

    # Get initial recommendations
    is_our_turn = draft_state.next_team == request.coaching_side
    recommendations = None
    if is_our_turn:
        our_team = blue_team if request.coaching_side == "blue" else red_team
        player = our_team.players[0] if our_team.players else None
        if player:
            recommendations = rec_engine.get_recommendations(
                player_name=player.name,
                player_role=player.role,
                our_picks=[],
                enemy_picks=[],
                banned=[],
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
    enemy_service, _, _, _ = get_services(app.state.data_path)

    # Get unavailable champions
    unavailable = set(
        draft_state.blue_bans + draft_state.red_bans +
        draft_state.blue_picks + draft_state.red_picks
    ) | session.fearless_blocked

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

    # Fearless blocking
    if session.draft_mode == "fearless":
        session.fearless_blocked.update(draft_state.blue_picks)
        session.fearless_blocked.update(draft_state.red_picks)

    return {
        "series_status": {
            "blue_wins": session.series_score[0],
            "red_wins": session.series_score[1],
            "games_played": len(session.game_results),
            "series_complete": session.series_complete
        },
        "fearless_blocked": list(session.fearless_blocked),
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
    enemy_service, _, _, _ = get_services(app.state.data_path)

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
        "fearless_blocked": list(session.fearless_blocked)
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
        "fearless_blocked": list(session.fearless_blocked)
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
    draft_state = session.draft_state
    is_our_turn = draft_state.next_team == session.coaching_side

    recommendations = None
    if is_our_turn and draft_state.current_phase != DraftPhase.COMPLETE:
        from ban_teemo.main import app
        _, rec_engine, _, _ = get_services(app.state.data_path)

        our_team = session.blue_team if session.coaching_side == "blue" else session.red_team
        our_picks = draft_state.blue_picks if session.coaching_side == "blue" else draft_state.red_picks
        enemy_picks = draft_state.red_picks if session.coaching_side == "blue" else draft_state.blue_picks
        banned = draft_state.blue_bans + draft_state.red_bans

        # Get player for current pick
        pick_index = len(our_picks)
        player = our_team.players[pick_index] if pick_index < len(our_team.players) else our_team.players[0]

        if player:
            recommendations = rec_engine.get_recommendations(
                player_name=player.name,
                player_role=player.role,
                our_picks=our_picks,
                enemy_picks=enemy_picks,
                banned=list(set(banned) | session.fearless_blocked),
                limit=5
            )

    return {
        "action": _serialize_action(draft_state.actions[-1]) if draft_state.actions else None,
        "draft_state": _serialize_draft_state(draft_state),
        "recommendations": recommendations,
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

## Stage 3 Checkpoint

```bash
cd backend && uv run pytest tests/ -v
```

Manual test:
```bash
cd backend && uv run uvicorn ban_teemo.main:app --reload
# In another terminal:
curl -X POST http://localhost:8000/api/simulator/start \
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

export interface SimulatorStartResponse {
  session_id: string;
  game_number: number;
  blue_team: TeamContext;
  red_team: TeamContext;
  draft_state: DraftState;
  recommendations: PickRecommendation[] | null;
  is_our_turn: boolean;
}

export interface SimulatorActionResponse {
  action: DraftAction | null;
  draft_state: DraftState;
  recommendations: PickRecommendation[] | null;
  is_our_turn: boolean;
  source?: "reference_game" | "fallback_game" | "weighted_random";
}

export interface CompleteGameResponse {
  series_status: SeriesStatus;
  fearless_blocked: string[];
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
  PickRecommendation,
  SeriesStatus,
  SimulatorStartResponse,
  SimulatorActionResponse,
} from "../types";

type SimulatorStatus = "setup" | "drafting" | "game_complete" | "series_complete";

interface SimulatorState {
  status: SimulatorStatus;
  sessionId: string | null;
  blueTeam: TeamContext | null;
  redTeam: TeamContext | null;
  coachingSide: "blue" | "red" | null;
  draftState: DraftState | null;
  recommendations: PickRecommendation[] | null;
  isOurTurn: boolean;
  isEnemyThinking: boolean;
  gameNumber: number;
  seriesStatus: SeriesStatus | null;
  fearlessBlocked: string[];
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
    draftState: null,
    recommendations: null,
    isOurTurn: false,
    isEnemyThinking: false,
    gameNumber: 1,
    seriesStatus: null,
    fearlessBlocked: [],
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
      draftState: null,
      recommendations: null,
      isOurTurn: false,
      isEnemyThinking: false,
      gameNumber: 1,
      seriesStatus: null,
      fearlessBlocked: [],
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

## Stage 5: Frontend - UI Components

Build the simulator UI components.

---

### Task 5.1: Create ChampionPool Component

**Files:**
- Create: `deepdraft/src/components/ChampionPool/index.tsx`

**Step 1: Write the component**

```tsx
// deepdraft/src/components/ChampionPool/index.tsx
import { useState, useMemo } from "react";
import { ChampionPortrait } from "../shared/ChampionPortrait";

interface ChampionPoolProps {
  allChampions: string[];
  unavailable: Set<string>;
  fearlessBlocked: Set<string>;
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
            const isFearlessBlocked = fearlessBlocked.has(champion);
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
                  isFearlessBlocked
                    ? `${champion} - Blocked (Fearless)`
                    : isUnavailable
                    ? `${champion} - Unavailable`
                    : champion
                }
              >
                <ChampionPortrait
                  championName={champion}
                  size="sm"
                  state={isUnavailable || isFearlessBlocked ? "banned" : "available"}
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

### Task 5.2: Create SimulatorSetupModal

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
      fetch(`${API_BASE}/api/teams`)
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

### Task 5.3: Create BanRow Component

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
            <ChampionPortrait championName={bans[i]} size="xs" state="banned" />
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

### Task 5.4: Create SimulatorView Component

**Files:**
- Create: `deepdraft/src/components/SimulatorView/index.tsx`

**Step 1: Write the component**

```tsx
// deepdraft/src/components/SimulatorView/index.tsx
import { useMemo } from "react";
import { PhaseIndicator, TeamPanel, BanRow } from "../draft";
import { ChampionPool } from "../ChampionPool";
import { RecommendationPanel } from "../RecommendationPanel";
import type { TeamContext, DraftState, PickRecommendation } from "../../types";

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
  fearlessBlocked: string[];
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

  const fearlessSet = useMemo(() => new Set(fearlessBlocked), [fearlessBlocked]);

  return (
    <div className="space-y-4">
      {/* Series Status */}
      <div className="flex justify-center items-center gap-4 text-sm">
        <span className="text-text-secondary">Game {gameNumber}</span>
        <span className="text-gold-bright font-bold">
          {blueTeam.name} {seriesScore[0]} - {seriesScore[1]} {redTeam.name}
        </span>
        {draftMode === "fearless" && (
          <span className="text-red-400">Fearless: {fearlessBlocked.length} blocked</span>
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
          fearlessBlocked={fearlessSet}
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

### Task 5.5: Update App with Mode Toggle

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
                draftMode="normal"
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

### Task 5.6: Add Teams API Endpoint

**Files:**
- Modify: `backend/src/ban_teemo/api/routes/replay.py`

**Step 1: Add teams endpoint**

Add to replay.py:

```python
@router.get("/teams")
async def list_teams():
    """List all available teams for simulator selection."""
    from ban_teemo.main import app
    repo = DraftRepository(app.state.data_path)

    teams = repo.get_all_teams()
    return {
        "teams": [{"id": t["id"], "name": t["name"]} for t in teams]
    }
```

**Step 2: Add get_all_teams to repository**

Add to `backend/src/ban_teemo/repositories/draft_repository.py`:

```python
def get_all_teams(self) -> list[dict]:
    """Get all unique teams from the database."""
    query = """
        SELECT DISTINCT id, name
        FROM read_csv_auto(?)
        ORDER BY name
    """
    teams_path = f"{self.data_path}/teams.csv"
    result = self.conn.execute(query, [teams_path]).fetchall()
    return [{"id": row[0], "name": row[1]} for row in result]
```

**Step 3: Commit**

```bash
git add backend/src/ban_teemo/api/routes/replay.py backend/src/ban_teemo/repositories/draft_repository.py
git commit -m "feat(api): add teams list endpoint for simulator"
```

---

## Stage 5 Checkpoint

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

## Final Integration Test

### Task 6.1: Run Full Test Suite

```bash
# Backend tests
cd backend && uv run pytest tests/ -v

# Frontend build
cd deepdraft && npm run build

# Type check
cd deepdraft && npm run typecheck
```

### Task 6.2: Manual Smoke Test

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
| 2 | 2.1-2.2 | Synergy service + Recommendation engine |
| 3 | 3.1-3.3 | Simulator backend (models, enemy AI, routes) |
| 4 | 4.1-4.2 | Frontend types + hook |
| 5 | 5.1-5.6 | UI components (pool, modal, views) |
| 6 | 6.1-6.2 | Integration testing |

**Total tasks:** 17
**Estimated commits:** 17
