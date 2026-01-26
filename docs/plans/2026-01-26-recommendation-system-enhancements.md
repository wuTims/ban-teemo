# Recommendation System Enhancements Implementation Plan

> **Status:** SUPERSEDED
> **Superseded By:** `2026-01-26-unified-recommendation-system.md`
> **Date:** 2026-01-26
>
> This plan has been merged into the unified recommendation system plan.
> Tasks from this plan are incorporated as **Stage 2: Enhancement Services** in the unified plan.

---

~~**For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.~~

**Goal:** Enhance the recommendation engine with archetype-based team composition scoring, wombo combo quality weighting, team draft evaluation, and ban recommendations.

**Architecture:** Add archetype counter matrix for rock-paper-scissors comp matchups. Enhance synergy scoring with partner quality ratings. Build cumulative team evaluation that tracks archetype alignment and synergy totals. Implement ban recommendation scoring based on target value, meta strength, and archetype counters.

**Tech Stack:** Python 3.14+, FastAPI, DuckDB, Pydantic, pytest

---

## Overview

This plan implements the recommendation system enhancements discussed:

1. **Archetype System** - 5 archetypes (engage, split, teamfight, protect, pick) with RPS counter matrix
2. **Wombo Combo Quality** - Use existing `rating` field (S/A/B/C) as synergy multiplier
3. **Team Draft Evaluation** - Cumulative team scoring with archetype detection
4. **Ban Recommendations** - Multi-factor ban priority scoring

## Prerequisites

- Existing `meta_stats.json` with counter-pick detection (completed)
- Existing `synergies.json` with `best_partners` ratings
- Existing `knowledge_base.json` with champion data

---

## Task 1: Create Archetype Counter Matrix

**Files:**
- Create: `knowledge/archetype_counters.json`

**Step 1: Create the archetype counters JSON file**

```json
{
  "metadata": {
    "version": "1.0.0",
    "generated_at": "2026-01-26",
    "description": "Rock-paper-scissors effectiveness matrix for team composition archetypes"
  },
  "archetypes": ["engage", "split", "teamfight", "protect", "pick"],
  "archetype_descriptions": {
    "engage": "Hard initiation, force fights on your terms (Malphite, Leona, Nautilus)",
    "split": "Side lane pressure, 1-3-1, avoid 5v5 (Fiora, Jax, Tryndamere)",
    "teamfight": "5v5 grouped fighting, wombo combos, AoE damage (Orianna, MF, Rumble)",
    "protect": "Keep carry alive, scale to late game, peel-focused (Lulu, Karma, Kog'Maw)",
    "pick": "Catch isolated targets, vision control, burst (Nidalee, Zoe, Thresh)"
  },
  "effectiveness_matrix": {
    "engage": {
      "vs_engage": 1.0,
      "vs_split": 1.2,
      "vs_teamfight": 1.2,
      "vs_protect": 0.8,
      "vs_pick": 0.8
    },
    "split": {
      "vs_engage": 0.8,
      "vs_split": 1.0,
      "vs_teamfight": 1.2,
      "vs_protect": 1.2,
      "vs_pick": 0.8
    },
    "teamfight": {
      "vs_engage": 0.8,
      "vs_split": 0.8,
      "vs_teamfight": 1.0,
      "vs_protect": 1.2,
      "vs_pick": 1.2
    },
    "protect": {
      "vs_engage": 1.2,
      "vs_split": 0.8,
      "vs_teamfight": 0.8,
      "vs_protect": 1.0,
      "vs_pick": 1.2
    },
    "pick": {
      "vs_engage": 1.2,
      "vs_split": 1.2,
      "vs_teamfight": 0.8,
      "vs_protect": 0.8,
      "vs_pick": 1.0
    }
  },
  "effectiveness_reasoning": {
    "engage_vs_split": "Engage can collapse on split pusher or force 4v5",
    "engage_vs_teamfight": "Engage disrupts teamfight setup before positioning",
    "engage_vs_protect": "Protect comp has tools to peel and disengage",
    "engage_vs_pick": "Engage wants to group, pick comp punishes grouping",
    "split_vs_teamfight": "Split forces bad fights or gives free objectives",
    "split_vs_protect": "Protect can't answer split pressure effectively",
    "split_vs_pick": "Pick comp can catch split pusher isolated",
    "teamfight_vs_protect": "Protect scales but teamfight has better early/mid 5v5",
    "teamfight_vs_pick": "Pick comp can't burst through grouped 5v5",
    "protect_vs_pick": "Protect has peel to save carry from picks"
  }
}
```

**Step 2: Verify file created correctly**

Run: `python3 -c "import json; d=json.load(open('knowledge/archetype_counters.json')); print('Archetypes:', d['archetypes']); print('Matrix keys:', list(d['effectiveness_matrix'].keys()))"`

Expected:
```
Archetypes: ['engage', 'split', 'teamfight', 'protect', 'pick']
Matrix keys: ['engage', 'split', 'teamfight', 'protect', 'pick']
```

**Step 3: Commit**

```bash
git add knowledge/archetype_counters.json
git commit -m "feat: add archetype counter matrix for team comp RPS system"
```

---

## Task 2: Add Champion Archetype Scores to Knowledge Base

**Files:**
- Modify: `scripts/build_computed_datasets.py`
- Create: `knowledge/champion_archetypes.json`

**Step 1: Write the failing test**

Create file: `backend/tests/test_archetype_scoring.py`

```python
"""Tests for champion archetype scoring."""
import json
from pathlib import Path

KNOWLEDGE_DIR = Path(__file__).parent.parent.parent.parent / "knowledge"


def test_champion_archetypes_file_exists():
    """Verify champion_archetypes.json exists."""
    path = KNOWLEDGE_DIR / "champion_archetypes.json"
    assert path.exists(), f"Missing {path}"


def test_champion_archetypes_structure():
    """Verify champion_archetypes.json has correct structure."""
    path = KNOWLEDGE_DIR / "champion_archetypes.json"
    data = json.load(open(path))

    assert "metadata" in data
    assert "champions" in data
    assert len(data["champions"]) >= 50, "Need at least 50 champions"

    # Check a known engage champion
    assert "Malphite" in data["champions"]
    malphite = data["champions"]["Malphite"]

    assert "primary" in malphite
    assert "secondary" in malphite or malphite.get("secondary") is None
    assert "scores" in malphite

    # Malphite should be engage primary
    assert malphite["primary"] == "engage"
    assert malphite["scores"]["engage"] >= 0.8


def test_archetype_scores_are_valid():
    """Verify all archetype scores are 0.0-1.0."""
    path = KNOWLEDGE_DIR / "champion_archetypes.json"
    data = json.load(open(path))

    valid_archetypes = {"engage", "split", "teamfight", "protect", "pick"}

    for champ_name, champ_data in data["champions"].items():
        # Primary must be valid
        assert champ_data["primary"] in valid_archetypes, f"{champ_name} has invalid primary"

        # Secondary can be None or valid
        if champ_data.get("secondary"):
            assert champ_data["secondary"] in valid_archetypes, f"{champ_name} has invalid secondary"

        # Scores must be 0.0-1.0
        for arch, score in champ_data["scores"].items():
            assert arch in valid_archetypes, f"{champ_name} has invalid archetype {arch}"
            assert 0.0 <= score <= 1.0, f"{champ_name}.{arch} score {score} out of range"
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_archetype_scoring.py -v`

Expected: FAIL with "Missing knowledge/champion_archetypes.json" or similar

**Step 3: Add build_champion_archetypes function to build script**

Add to `scripts/build_computed_datasets.py` after the `build_skill_transfers` function:

```python
def build_champion_archetypes(current_patch: str) -> dict:
    """Build champion_archetypes.json with archetype scores per champion.

    This generates initial scores based on champion classification and known patterns.
    Domain expert should review and adjust scores.
    """
    print("Building champion_archetypes.json...")

    knowledge_base = load_json(KNOWLEDGE_BASE_FILE)
    synergies = load_json(SYNERGIES_FILE)

    # Build synergy lookup for comp_archetypes hints
    champ_synergy_archetypes = defaultdict(set)
    for syn in synergies:
        archetypes = syn.get("comp_archetypes", [])
        for champ in syn.get("champions", []):
            for arch in archetypes:
                # Map old archetype names to new 5-archetype system
                arch_mapped = {
                    "dive": "engage",
                    "poke": "teamfight",  # Poke wants grouped fights at range
                    "splitpush": "split",
                }.get(arch, arch)
                if arch_mapped in ["engage", "split", "teamfight", "protect", "pick"]:
                    champ_synergy_archetypes[champ].add(arch_mapped)

    # Classification-based archetype hints
    class_archetypes = {
        # Tanks/Vanguards -> Engage
        ("Tank", "Vanguard"): {"engage": 0.9, "teamfight": 0.6},
        ("Tank", "Warden"): {"protect": 0.8, "teamfight": 0.5},
        # Fighters -> Split or Engage
        ("Fighter", "Juggernaut"): {"split": 0.6, "teamfight": 0.5},
        ("Fighter", "Diver"): {"engage": 0.7, "pick": 0.5},
        ("Fighter", "Skirmisher"): {"split": 0.8, "pick": 0.4},
        # Assassins -> Pick
        ("Assassin", None): {"pick": 0.9, "split": 0.4},
        ("Assassin", "Assassin"): {"pick": 0.9, "split": 0.4},
        # Mages
        ("Mage", "Artillery"): {"teamfight": 0.8, "pick": 0.5},
        ("Mage", "Battlemage"): {"teamfight": 0.7, "engage": 0.4},
        ("Mage", "Burst"): {"pick": 0.7, "teamfight": 0.5},
        # Marksmen -> Teamfight or Protect
        ("Marksman", None): {"teamfight": 0.6, "protect": 0.5},
        ("Marksman", "Marksman"): {"teamfight": 0.6, "protect": 0.5},
        # Supports
        ("Controller", "Enchanter"): {"protect": 0.9, "teamfight": 0.5},
        ("Controller", "Catcher"): {"pick": 0.8, "engage": 0.5},
        ("Specialist", None): {"split": 0.5, "teamfight": 0.5},
    }

    # Known overrides for specific champions (domain expert knowledge)
    overrides = {
        # Engage champions
        "Malphite": {"primary": "engage", "secondary": "teamfight", "scores": {"engage": 0.95, "teamfight": 0.8, "protect": 0.2, "split": 0.3, "pick": 0.2}},
        "Leona": {"primary": "engage", "secondary": "pick", "scores": {"engage": 0.9, "pick": 0.6, "teamfight": 0.5, "protect": 0.3, "split": 0.1}},
        "Nautilus": {"primary": "engage", "secondary": "pick", "scores": {"engage": 0.85, "pick": 0.7, "teamfight": 0.5, "protect": 0.4, "split": 0.1}},
        "Alistar": {"primary": "engage", "secondary": "protect", "scores": {"engage": 0.85, "protect": 0.6, "teamfight": 0.5, "pick": 0.3, "split": 0.1}},
        "Rakan": {"primary": "engage", "secondary": "protect", "scores": {"engage": 0.8, "protect": 0.7, "teamfight": 0.6, "pick": 0.4, "split": 0.1}},

        # Split champions
        "Fiora": {"primary": "split", "secondary": None, "scores": {"split": 0.95, "pick": 0.4, "teamfight": 0.2, "engage": 0.2, "protect": 0.1}},
        "Jax": {"primary": "split", "secondary": "teamfight", "scores": {"split": 0.9, "teamfight": 0.5, "engage": 0.4, "pick": 0.3, "protect": 0.1}},
        "Tryndamere": {"primary": "split", "secondary": None, "scores": {"split": 0.95, "teamfight": 0.3, "pick": 0.3, "engage": 0.2, "protect": 0.1}},
        "Camille": {"primary": "split", "secondary": "pick", "scores": {"split": 0.8, "pick": 0.7, "engage": 0.5, "teamfight": 0.4, "protect": 0.1}},

        # Teamfight champions
        "Orianna": {"primary": "teamfight", "secondary": "protect", "scores": {"teamfight": 0.95, "protect": 0.7, "pick": 0.4, "engage": 0.3, "split": 0.1}},
        "Rumble": {"primary": "teamfight", "secondary": "engage", "scores": {"teamfight": 0.9, "engage": 0.5, "split": 0.4, "pick": 0.3, "protect": 0.2}},
        "Miss Fortune": {"primary": "teamfight", "secondary": None, "scores": {"teamfight": 0.9, "protect": 0.4, "pick": 0.3, "engage": 0.2, "split": 0.1}},
        "Kennen": {"primary": "teamfight", "secondary": "engage", "scores": {"teamfight": 0.85, "engage": 0.7, "split": 0.5, "pick": 0.3, "protect": 0.2}},
        "Azir": {"primary": "teamfight", "secondary": "split", "scores": {"teamfight": 0.85, "split": 0.6, "protect": 0.5, "engage": 0.4, "pick": 0.3}},

        # Protect champions
        "Lulu": {"primary": "protect", "secondary": "teamfight", "scores": {"protect": 0.95, "teamfight": 0.6, "pick": 0.3, "engage": 0.2, "split": 0.1}},
        "Karma": {"primary": "protect", "secondary": "teamfight", "scores": {"protect": 0.8, "teamfight": 0.6, "pick": 0.4, "engage": 0.3, "split": 0.2}},
        "Janna": {"primary": "protect", "secondary": None, "scores": {"protect": 0.95, "teamfight": 0.5, "pick": 0.2, "engage": 0.1, "split": 0.1}},
        "Kog'Maw": {"primary": "protect", "secondary": "teamfight", "scores": {"protect": 0.8, "teamfight": 0.7, "split": 0.3, "pick": 0.2, "engage": 0.1}},

        # Pick champions
        "Zoe": {"primary": "pick", "secondary": "teamfight", "scores": {"pick": 0.9, "teamfight": 0.5, "split": 0.3, "protect": 0.2, "engage": 0.1}},
        "Nidalee": {"primary": "pick", "secondary": None, "scores": {"pick": 0.85, "split": 0.4, "teamfight": 0.3, "engage": 0.2, "protect": 0.1}},
        "Thresh": {"primary": "pick", "secondary": "engage", "scores": {"pick": 0.8, "engage": 0.7, "protect": 0.6, "teamfight": 0.5, "split": 0.1}},
        "Blitzcrank": {"primary": "pick", "secondary": "engage", "scores": {"pick": 0.9, "engage": 0.6, "teamfight": 0.3, "protect": 0.2, "split": 0.1}},
        "LeBlanc": {"primary": "pick", "secondary": "split", "scores": {"pick": 0.85, "split": 0.5, "teamfight": 0.4, "engage": 0.2, "protect": 0.1}},

        # Flex/hybrid champions
        "Nocturne": {"primary": "pick", "secondary": "engage", "scores": {"pick": 0.85, "engage": 0.7, "split": 0.5, "teamfight": 0.4, "protect": 0.1}},
        "Jarvan IV": {"primary": "engage", "secondary": "teamfight", "scores": {"engage": 0.8, "teamfight": 0.7, "pick": 0.5, "split": 0.3, "protect": 0.2}},
        "Gragas": {"primary": "engage", "secondary": "pick", "scores": {"engage": 0.75, "pick": 0.6, "teamfight": 0.6, "split": 0.4, "protect": 0.3}},
    }

    champions = {}

    for champ_name, champ_data in knowledge_base.get("champions", {}).items():
        # Start with override if exists
        if champ_name in overrides:
            champions[champ_name] = overrides[champ_name]
            continue

        # Otherwise, generate from classification
        primary_class = champ_data.get("classification", {}).get("primary_class")
        subclass = champ_data.get("classification", {}).get("subclass")

        # Default scores
        scores = {"engage": 0.3, "split": 0.3, "teamfight": 0.3, "protect": 0.3, "pick": 0.3}

        # Apply class-based hints
        class_key = (primary_class, subclass)
        if class_key in class_archetypes:
            for arch, score in class_archetypes[class_key].items():
                scores[arch] = max(scores[arch], score)

        # Also try with None subclass
        class_key_none = (primary_class, None)
        if class_key_none in class_archetypes:
            for arch, score in class_archetypes[class_key_none].items():
                scores[arch] = max(scores[arch], score)

        # Apply synergy-based hints
        for arch in champ_synergy_archetypes.get(champ_name, []):
            scores[arch] = max(scores[arch], 0.6)

        # Determine primary and secondary
        sorted_archs = sorted(scores.items(), key=lambda x: -x[1])
        primary = sorted_archs[0][0]
        secondary = sorted_archs[1][0] if sorted_archs[1][1] >= 0.5 else None

        champions[champ_name] = {
            "primary": primary,
            "secondary": secondary,
            "scores": {k: round(v, 2) for k, v in scores.items()}
        }

    result = {
        "metadata": {
            "generated_at": datetime.now().isoformat(),
            "current_patch": current_patch,
            "champions_count": len(champions),
            "note": "Auto-generated with domain expert overrides. Review and adjust scores as needed."
        },
        "champions": dict(sorted(champions.items()))
    }

    save_json(result, OUTPUT_DIR / "champion_archetypes.json")
    return result
```

**Step 4: Register the new dataset builder**

Add to the `DATASETS` dict in `build_computed_datasets.py`:

```python
DATASETS = {
    "patch_info": build_patch_info,
    "role_baselines": build_role_baselines,
    "meta_stats": build_meta_stats,
    "flex_champions": build_flex_champions,
    "player_proficiency": build_player_proficiency,
    "champion_synergies": build_champion_synergies,
    "matchup_stats": build_matchup_stats,
    "skill_transfers": build_skill_transfers,
    "champion_archetypes": build_champion_archetypes,  # Add this line
}
```

And add to the build order list:

```python
order = [
    "patch_info",
    "role_baselines",
    "meta_stats",
    "flex_champions",
    "player_proficiency",
    "champion_synergies",
    "matchup_stats",
    "skill_transfers",
    "champion_archetypes",  # Add this line
]
```

**Step 5: Run the builder**

Run: `python scripts/build_computed_datasets.py --dataset champion_archetypes --current-patch 15.18`

Expected: `Saved: knowledge/champion_archetypes.json`

**Step 6: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_archetype_scoring.py -v`

Expected: All tests PASS

**Step 7: Commit**

```bash
git add scripts/build_computed_datasets.py knowledge/champion_archetypes.json backend/tests/test_archetype_scoring.py
git commit -m "feat: add champion archetype scoring system"
```

---

## Task 3: Create Archetype Scoring Service

**Files:**
- Create: `backend/src/ban_teemo/services/archetype_service.py`
- Create: `backend/tests/test_archetype_service.py`

**Step 1: Write the failing test**

Create file: `backend/tests/test_archetype_service.py`

```python
"""Tests for archetype scoring service."""
import pytest
from ban_teemo.services.archetype_service import ArchetypeService


@pytest.fixture
def service():
    return ArchetypeService()


def test_get_champion_archetypes(service):
    """Test getting champion archetype scores."""
    result = service.get_champion_archetypes("Malphite")

    assert result is not None
    assert result["primary"] == "engage"
    assert result["scores"]["engage"] >= 0.8


def test_get_champion_archetypes_unknown(service):
    """Test unknown champion returns default scores."""
    result = service.get_champion_archetypes("NonexistentChampion")

    assert result is not None
    assert result["primary"] is not None
    assert all(0.0 <= s <= 1.0 for s in result["scores"].values())


def test_calculate_team_archetype(service):
    """Test calculating team archetype from picks."""
    picks = ["Malphite", "Nocturne", "Orianna"]

    result = service.calculate_team_archetype(picks)

    assert "primary" in result
    assert "secondary" in result
    assert "scores" in result
    assert "alignment" in result
    # With Malphite + Nocturne + Orianna, should lean engage/teamfight
    assert result["primary"] in ["engage", "teamfight"]


def test_calculate_team_archetype_empty(service):
    """Test empty picks returns neutral scores."""
    result = service.calculate_team_archetype([])

    assert result["primary"] is None
    assert all(s == 0.0 for s in result["scores"].values())


def test_get_archetype_effectiveness(service):
    """Test getting archetype matchup effectiveness."""
    # Engage beats teamfight
    effectiveness = service.get_archetype_effectiveness("engage", "teamfight")
    assert effectiveness > 1.0

    # Protect beats engage
    effectiveness = service.get_archetype_effectiveness("protect", "engage")
    assert effectiveness > 1.0

    # Mirror matchup is neutral
    effectiveness = service.get_archetype_effectiveness("engage", "engage")
    assert effectiveness == 1.0


def test_calculate_comp_advantage(service):
    """Test calculating comp advantage between two teams."""
    our_picks = ["Malphite", "Nocturne", "Orianna", "Jinx", "Thresh"]
    enemy_picks = ["Fiora", "Lee Sin", "Azir", "Ezreal", "Karma"]

    result = service.calculate_comp_advantage(our_picks, enemy_picks)

    assert "our_archetype" in result
    assert "enemy_archetype" in result
    assert "effectiveness" in result
    assert isinstance(result["effectiveness"], float)
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_archetype_service.py -v`

Expected: FAIL with "ModuleNotFoundError: No module named 'ban_teemo.services.archetype_service'"

**Step 3: Write minimal implementation**

Create file: `backend/src/ban_teemo/services/archetype_service.py`

```python
"""Service for calculating team composition archetypes and matchups."""
import json
from pathlib import Path
from typing import Optional


class ArchetypeService:
    """Handles archetype scoring and team composition analysis."""

    VALID_ARCHETYPES = {"engage", "split", "teamfight", "protect", "pick"}
    DEFAULT_SCORES = {"engage": 0.3, "split": 0.3, "teamfight": 0.3, "protect": 0.3, "pick": 0.3}

    def __init__(self, knowledge_dir: Optional[Path] = None):
        if knowledge_dir is None:
            knowledge_dir = Path(__file__).parent.parent.parent.parent.parent / "knowledge"

        self.knowledge_dir = knowledge_dir
        self._champion_archetypes: dict = {}
        self._archetype_counters: dict = {}
        self._load_data()

    def _load_data(self):
        """Load archetype data from knowledge files."""
        # Load champion archetypes
        champ_path = self.knowledge_dir / "champion_archetypes.json"
        if champ_path.exists():
            with open(champ_path) as f:
                data = json.load(f)
                self._champion_archetypes = data.get("champions", {})

        # Load archetype counters
        counter_path = self.knowledge_dir / "archetype_counters.json"
        if counter_path.exists():
            with open(counter_path) as f:
                data = json.load(f)
                self._archetype_counters = data.get("effectiveness_matrix", {})

    def get_champion_archetypes(self, champion_name: str) -> dict:
        """Get archetype scores for a champion.

        Returns:
            dict with keys: primary, secondary, scores
        """
        if champion_name in self._champion_archetypes:
            return self._champion_archetypes[champion_name]

        # Return default for unknown champions
        sorted_default = sorted(self.DEFAULT_SCORES.items(), key=lambda x: -x[1])
        return {
            "primary": sorted_default[0][0],
            "secondary": None,
            "scores": self.DEFAULT_SCORES.copy()
        }

    def calculate_team_archetype(self, picks: list[str]) -> dict:
        """Calculate cumulative team archetype from picks.

        Args:
            picks: List of champion names picked by team

        Returns:
            dict with keys: primary, secondary, scores, alignment
        """
        if not picks:
            return {
                "primary": None,
                "secondary": None,
                "scores": {arch: 0.0 for arch in self.VALID_ARCHETYPES},
                "alignment": 0.0
            }

        # Sum archetype scores from all picks
        cumulative = {arch: 0.0 for arch in self.VALID_ARCHETYPES}

        for champ in picks:
            champ_data = self.get_champion_archetypes(champ)
            for arch, score in champ_data["scores"].items():
                cumulative[arch] += score

        # Normalize by number of picks
        normalized = {arch: score / len(picks) for arch, score in cumulative.items()}

        # Determine primary and secondary
        sorted_archs = sorted(normalized.items(), key=lambda x: -x[1])
        primary = sorted_archs[0][0]
        secondary = sorted_archs[1][0] if sorted_archs[1][1] >= 0.4 else None

        # Calculate alignment (how focused is the team on primary archetype)
        alignment = sorted_archs[0][1] / sum(normalized.values()) if sum(normalized.values()) > 0 else 0

        return {
            "primary": primary,
            "secondary": secondary,
            "scores": {k: round(v, 3) for k, v in normalized.items()},
            "alignment": round(alignment, 3)
        }

    def get_archetype_effectiveness(self, our_archetype: str, enemy_archetype: str) -> float:
        """Get effectiveness multiplier for archetype matchup.

        Args:
            our_archetype: Our team's primary archetype
            enemy_archetype: Enemy team's primary archetype

        Returns:
            float multiplier (1.0 = neutral, >1.0 = advantage, <1.0 = disadvantage)
        """
        if our_archetype not in self._archetype_counters:
            return 1.0

        key = f"vs_{enemy_archetype}"
        return self._archetype_counters[our_archetype].get(key, 1.0)

    def calculate_comp_advantage(self, our_picks: list[str], enemy_picks: list[str]) -> dict:
        """Calculate composition advantage between two teams.

        Args:
            our_picks: Our team's champion picks
            enemy_picks: Enemy team's champion picks

        Returns:
            dict with our_archetype, enemy_archetype, effectiveness
        """
        our_archetype = self.calculate_team_archetype(our_picks)
        enemy_archetype = self.calculate_team_archetype(enemy_picks)

        effectiveness = 1.0
        if our_archetype["primary"] and enemy_archetype["primary"]:
            effectiveness = self.get_archetype_effectiveness(
                our_archetype["primary"],
                enemy_archetype["primary"]
            )

        return {
            "our_archetype": our_archetype,
            "enemy_archetype": enemy_archetype,
            "effectiveness": effectiveness
        }
```

**Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_archetype_service.py -v`

Expected: All tests PASS

**Step 5: Commit**

```bash
git add backend/src/ban_teemo/services/archetype_service.py backend/tests/test_archetype_service.py
git commit -m "feat: add archetype scoring service"
```

---

## Task 4: Create Synergy Scoring Service with Rating Multipliers

**Files:**
- Create: `backend/src/ban_teemo/services/synergy_service.py`
- Create: `backend/tests/test_synergy_service.py`

**Step 1: Write the failing test**

Create file: `backend/tests/test_synergy_service.py`

```python
"""Tests for synergy scoring service."""
import pytest
from ban_teemo.services.synergy_service import SynergyService


@pytest.fixture
def service():
    return SynergyService()


def test_get_partner_rating_multiplier(service):
    """Test rating to multiplier conversion."""
    assert service.get_rating_multiplier("S") == 1.0
    assert service.get_rating_multiplier("A") == 0.8
    assert service.get_rating_multiplier("B") == 0.6
    assert service.get_rating_multiplier("C") == 0.4
    assert service.get_rating_multiplier(None) == 0.5  # Default


def test_get_synergy_score_basic(service):
    """Test basic synergy score lookup."""
    # Yasuo + Malphite should have high synergy (S-tier partner)
    score = service.get_synergy_score("Yasuo", "Malphite")
    assert score >= 0.8, "Yasuo + Malphite should have high synergy"


def test_get_synergy_score_no_synergy(service):
    """Test champions with no special synergy."""
    # Random pair with no curated synergy
    score = service.get_synergy_score("Teemo", "Soraka")
    # Should return statistical synergy or neutral
    assert 0.0 <= score <= 1.0


def test_calculate_team_synergy(service):
    """Test calculating total team synergy."""
    picks = ["Yasuo", "Malphite", "Orianna"]

    result = service.calculate_team_synergy(picks)

    assert "total_score" in result
    assert "pair_count" in result
    assert "synergy_pairs" in result
    assert result["total_score"] >= 0.0


def test_get_best_synergy_partners(service):
    """Test finding best synergy partners for a champion."""
    partners = service.get_best_synergy_partners("Yasuo", limit=5)

    assert len(partners) <= 5
    # Malphite should be in top partners for Yasuo
    partner_names = [p["champion"] for p in partners]
    assert "Malphite" in partner_names or "Diana" in partner_names
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_synergy_service.py -v`

Expected: FAIL with "ModuleNotFoundError: No module named 'ban_teemo.services.synergy_service'"

**Step 3: Write minimal implementation**

Create file: `backend/src/ban_teemo/services/synergy_service.py`

```python
"""Service for calculating champion synergy scores."""
import json
from pathlib import Path
from typing import Optional
from collections import defaultdict


class SynergyService:
    """Handles synergy scoring between champions."""

    RATING_MULTIPLIERS = {
        "S": 1.0,
        "A": 0.8,
        "B": 0.6,
        "C": 0.4,
    }
    DEFAULT_MULTIPLIER = 0.5

    def __init__(self, knowledge_dir: Optional[Path] = None):
        if knowledge_dir is None:
            knowledge_dir = Path(__file__).parent.parent.parent.parent.parent / "knowledge"

        self.knowledge_dir = knowledge_dir
        self._curated_synergies: list = []
        self._statistical_synergies: dict = {}
        self._partner_ratings: dict = defaultdict(dict)  # champ -> partner -> rating
        self._load_data()

    def _load_data(self):
        """Load synergy data from knowledge files."""
        # Load curated synergies
        synergies_path = self.knowledge_dir / "synergies.json"
        if synergies_path.exists():
            with open(synergies_path) as f:
                self._curated_synergies = json.load(f)
            self._build_partner_ratings()

        # Load statistical synergies
        stats_path = self.knowledge_dir / "champion_synergies.json"
        if stats_path.exists():
            with open(stats_path) as f:
                data = json.load(f)
                self._statistical_synergies = data.get("synergies", {})

    def _build_partner_ratings(self):
        """Build lookup for partner ratings from curated synergies."""
        for syn in self._curated_synergies:
            # Handle ability_requirement type with best_partners
            if syn.get("type") == "ability_requirement":
                main_champs = syn.get("champions", [])
                best_partners = syn.get("best_partners", [])

                for main_champ in main_champs:
                    for partner in best_partners:
                        partner_name = partner.get("champion")
                        rating = partner.get("rating", "A")
                        if partner_name:
                            self._partner_ratings[main_champ][partner_name] = rating

            # Handle ability_combo with direct champion pairs
            elif syn.get("type") == "ability_combo":
                champs = syn.get("champions", [])
                strength = syn.get("strength", "A")

                if len(champs) >= 2:
                    # Both champions get each other as partners
                    self._partner_ratings[champs[0]][champs[1]] = strength
                    self._partner_ratings[champs[1]][champs[0]] = strength

    def get_rating_multiplier(self, rating: Optional[str]) -> float:
        """Convert rating (S/A/B/C) to multiplier."""
        if rating is None:
            return self.DEFAULT_MULTIPLIER
        return self.RATING_MULTIPLIERS.get(rating.upper(), self.DEFAULT_MULTIPLIER)

    def get_synergy_score(self, champ_a: str, champ_b: str) -> float:
        """Get synergy score between two champions.

        Combines curated partner ratings with statistical synergy data.

        Returns:
            float score 0.0-1.0
        """
        # Check for curated partner rating
        curated_rating = None
        if champ_a in self._partner_ratings and champ_b in self._partner_ratings[champ_a]:
            curated_rating = self._partner_ratings[champ_a][champ_b]
        elif champ_b in self._partner_ratings and champ_a in self._partner_ratings[champ_b]:
            curated_rating = self._partner_ratings[champ_b][champ_a]

        if curated_rating:
            # Use curated rating as multiplier on base synergy
            base_score = 0.85  # High base for curated synergies
            return base_score * self.get_rating_multiplier(curated_rating)

        # Fall back to statistical synergy
        if champ_a in self._statistical_synergies:
            if champ_b in self._statistical_synergies[champ_a]:
                return self._statistical_synergies[champ_a][champ_b].get("synergy_score", 0.5)

        if champ_b in self._statistical_synergies:
            if champ_a in self._statistical_synergies[champ_b]:
                return self._statistical_synergies[champ_b][champ_a].get("synergy_score", 0.5)

        # No data - return neutral
        return 0.5

    def calculate_team_synergy(self, picks: list[str]) -> dict:
        """Calculate total team synergy from all pick pairs.

        Args:
            picks: List of champion names

        Returns:
            dict with total_score, pair_count, synergy_pairs
        """
        if len(picks) < 2:
            return {
                "total_score": 0.0,
                "pair_count": 0,
                "synergy_pairs": []
            }

        pairs = []
        total_score = 0.0

        for i, champ_a in enumerate(picks):
            for champ_b in picks[i + 1:]:
                score = self.get_synergy_score(champ_a, champ_b)
                total_score += score
                if score > 0.6:  # Only track notable synergies
                    pairs.append({
                        "champions": [champ_a, champ_b],
                        "score": round(score, 3)
                    })

        pair_count = len(picks) * (len(picks) - 1) // 2
        avg_score = total_score / pair_count if pair_count > 0 else 0.0

        return {
            "total_score": round(avg_score, 3),
            "pair_count": pair_count,
            "synergy_pairs": sorted(pairs, key=lambda x: -x["score"])
        }

    def get_best_synergy_partners(self, champion: str, limit: int = 5) -> list[dict]:
        """Find best synergy partners for a champion.

        Args:
            champion: Champion name to find partners for
            limit: Max partners to return

        Returns:
            List of dicts with champion, score, rating
        """
        partners = []

        # Check curated partners
        if champion in self._partner_ratings:
            for partner, rating in self._partner_ratings[champion].items():
                partners.append({
                    "champion": partner,
                    "score": 0.85 * self.get_rating_multiplier(rating),
                    "rating": rating,
                    "source": "curated"
                })

        # Check statistical synergies
        if champion in self._statistical_synergies:
            for partner, data in self._statistical_synergies[champion].items():
                # Skip if already in curated
                if any(p["champion"] == partner for p in partners):
                    continue

                score = data.get("synergy_score", 0.5)
                if score > 0.55:  # Only include positive synergies
                    partners.append({
                        "champion": partner,
                        "score": score,
                        "rating": None,
                        "source": "statistical"
                    })

        # Sort by score and limit
        return sorted(partners, key=lambda x: -x["score"])[:limit]
```

**Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_synergy_service.py -v`

Expected: All tests PASS

**Step 5: Commit**

```bash
git add backend/src/ban_teemo/services/synergy_service.py backend/tests/test_synergy_service.py
git commit -m "feat: add synergy scoring service with rating multipliers"
```

---

## Task 5: Create Team Draft Evaluation Service

**Files:**
- Create: `backend/src/ban_teemo/services/team_evaluation_service.py`
- Create: `backend/tests/test_team_evaluation_service.py`

**Step 1: Write the failing test**

Create file: `backend/tests/test_team_evaluation_service.py`

```python
"""Tests for team draft evaluation service."""
import pytest
from ban_teemo.services.team_evaluation_service import TeamEvaluationService


@pytest.fixture
def service():
    return TeamEvaluationService()


def test_evaluate_team_draft(service):
    """Test full team draft evaluation."""
    picks = ["Malphite", "Nocturne", "Orianna", "Jinx", "Thresh"]

    result = service.evaluate_team_draft(picks)

    assert "archetype" in result
    assert "synergy" in result
    assert "composition_score" in result
    assert "role_coverage" in result
    assert "strengths" in result
    assert "weaknesses" in result


def test_evaluate_partial_draft(service):
    """Test evaluation with partial draft."""
    picks = ["Malphite", "Nocturne"]

    result = service.evaluate_team_draft(picks)

    assert result["role_coverage"]["filled"] == 2
    assert result["role_coverage"]["missing"] == 3
    assert "composition_score" in result


def test_evaluate_empty_draft(service):
    """Test evaluation with no picks."""
    result = service.evaluate_team_draft([])

    assert result["composition_score"] == 0.0
    assert result["role_coverage"]["filled"] == 0


def test_get_composition_score(service):
    """Test composition score calculation."""
    # Good comp: engage + teamfight + ADC
    good_picks = ["Malphite", "Orianna", "Jinx", "Lulu", "Thresh"]
    good_score = service.evaluate_team_draft(good_picks)["composition_score"]

    # Random comp: no synergy
    random_picks = ["Teemo", "Shaco", "Ryze", "Draven", "Pyke"]
    random_score = service.evaluate_team_draft(random_picks)["composition_score"]

    # Good comp should score higher
    assert good_score > random_score


def test_evaluate_vs_enemy(service):
    """Test evaluation against enemy team."""
    our_picks = ["Malphite", "Nocturne", "Orianna", "Jinx", "Thresh"]
    enemy_picks = ["Fiora", "Lee Sin", "Azir", "Ezreal", "Karma"]

    result = service.evaluate_vs_enemy(our_picks, enemy_picks)

    assert "our_evaluation" in result
    assert "enemy_evaluation" in result
    assert "matchup_advantage" in result
    assert isinstance(result["matchup_advantage"], float)
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_team_evaluation_service.py -v`

Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write minimal implementation**

Create file: `backend/src/ban_teemo/services/team_evaluation_service.py`

```python
"""Service for evaluating team draft compositions."""
from typing import Optional
from pathlib import Path

from ban_teemo.services.archetype_service import ArchetypeService
from ban_teemo.services.synergy_service import SynergyService


class TeamEvaluationService:
    """Evaluates team composition quality and matchups."""

    # Expected roles in a team
    ROLES = ["TOP", "JUNGLE", "MID", "ADC", "SUPPORT"]

    def __init__(self, knowledge_dir: Optional[Path] = None):
        self.archetype_service = ArchetypeService(knowledge_dir)
        self.synergy_service = SynergyService(knowledge_dir)

    def evaluate_team_draft(self, picks: list[str]) -> dict:
        """Evaluate a team's draft composition.

        Args:
            picks: List of champion names (up to 5)

        Returns:
            dict with archetype, synergy, composition_score, role_coverage, strengths, weaknesses
        """
        if not picks:
            return {
                "archetype": {
                    "primary": None,
                    "secondary": None,
                    "scores": {},
                    "alignment": 0.0
                },
                "synergy": {
                    "total_score": 0.0,
                    "pair_count": 0,
                    "synergy_pairs": []
                },
                "composition_score": 0.0,
                "role_coverage": {
                    "filled": 0,
                    "missing": 5,
                    "roles": []
                },
                "strengths": [],
                "weaknesses": ["No picks yet"]
            }

        # Calculate archetype
        archetype = self.archetype_service.calculate_team_archetype(picks)

        # Calculate synergy
        synergy = self.synergy_service.calculate_team_synergy(picks)

        # Role coverage (simplified - would need champion role data for accuracy)
        role_coverage = {
            "filled": len(picks),
            "missing": max(0, 5 - len(picks)),
            "roles": []  # Would populate with detected roles
        }

        # Calculate composition score
        composition_score = self._calculate_composition_score(
            archetype, synergy, role_coverage, len(picks)
        )

        # Identify strengths and weaknesses
        strengths, weaknesses = self._identify_strengths_weaknesses(
            archetype, synergy, picks
        )

        return {
            "archetype": archetype,
            "synergy": synergy,
            "composition_score": round(composition_score, 3),
            "role_coverage": role_coverage,
            "strengths": strengths,
            "weaknesses": weaknesses
        }

    def _calculate_composition_score(
        self,
        archetype: dict,
        synergy: dict,
        role_coverage: dict,
        pick_count: int
    ) -> float:
        """Calculate overall composition score (0.0-1.0)."""
        if pick_count == 0:
            return 0.0

        # Archetype alignment score (how focused is the comp)
        archetype_score = archetype.get("alignment", 0.3) * 0.8 + 0.2

        # Synergy score
        synergy_score = synergy.get("total_score", 0.5)

        # Coverage score (penalize incomplete drafts)
        coverage_score = pick_count / 5.0

        # Weighted combination
        score = (
            archetype_score * 0.35 +
            synergy_score * 0.40 +
            coverage_score * 0.25
        )

        return min(1.0, max(0.0, score))

    def _identify_strengths_weaknesses(
        self,
        archetype: dict,
        synergy: dict,
        picks: list[str]
    ) -> tuple[list[str], list[str]]:
        """Identify composition strengths and weaknesses."""
        strengths = []
        weaknesses = []

        # Archetype-based
        primary = archetype.get("primary")
        alignment = archetype.get("alignment", 0)

        if alignment >= 0.4:
            archetype_descriptions = {
                "engage": "Strong initiation and pick potential",
                "split": "Excellent side lane pressure",
                "teamfight": "Powerful 5v5 team fighting",
                "protect": "Great carry protection and scaling",
                "pick": "High catch and assassination threat"
            }
            if primary in archetype_descriptions:
                strengths.append(archetype_descriptions[primary])
        else:
            weaknesses.append("No clear composition identity")

        # Synergy-based
        if synergy.get("total_score", 0) >= 0.65:
            strengths.append("High internal synergy between picks")
        elif synergy.get("total_score", 0) <= 0.45:
            weaknesses.append("Limited synergy between champions")

        # Notable synergy pairs
        notable_pairs = [p for p in synergy.get("synergy_pairs", []) if p["score"] >= 0.7]
        if notable_pairs:
            pair = notable_pairs[0]
            strengths.append(f"Strong combo: {pair['champions'][0]} + {pair['champions'][1]}")

        return strengths, weaknesses

    def evaluate_vs_enemy(self, our_picks: list[str], enemy_picks: list[str]) -> dict:
        """Evaluate our draft against enemy draft.

        Args:
            our_picks: Our team's picks
            enemy_picks: Enemy team's picks

        Returns:
            dict with our_evaluation, enemy_evaluation, matchup_advantage
        """
        our_eval = self.evaluate_team_draft(our_picks)
        enemy_eval = self.evaluate_team_draft(enemy_picks)

        # Calculate archetype matchup advantage
        comp_advantage = self.archetype_service.calculate_comp_advantage(
            our_picks, enemy_picks
        )

        return {
            "our_evaluation": our_eval,
            "enemy_evaluation": enemy_eval,
            "matchup_advantage": comp_advantage["effectiveness"]
        }
```

**Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_team_evaluation_service.py -v`

Expected: All tests PASS

**Step 5: Commit**

```bash
git add backend/src/ban_teemo/services/team_evaluation_service.py backend/tests/test_team_evaluation_service.py
git commit -m "feat: add team draft evaluation service"
```

---

## Task 6: Create Ban Recommendation Service

**Files:**
- Create: `backend/src/ban_teemo/services/ban_recommendation_service.py`
- Create: `backend/tests/test_ban_recommendation_service.py`

**Step 1: Write the failing test**

Create file: `backend/tests/test_ban_recommendation_service.py`

```python
"""Tests for ban recommendation service."""
import pytest
from ban_teemo.services.ban_recommendation_service import BanRecommendationService


@pytest.fixture
def service():
    return BanRecommendationService()


def test_get_ban_recommendations(service):
    """Test generating ban recommendations."""
    enemy_team_id = "123"  # Would be real team ID
    our_picks = []
    enemy_picks = []
    banned = []

    recommendations = service.get_ban_recommendations(
        enemy_team_id=enemy_team_id,
        our_picks=our_picks,
        enemy_picks=enemy_picks,
        already_banned=banned,
        phase=1,
        limit=3
    )

    assert len(recommendations) <= 3
    for rec in recommendations:
        assert "champion_name" in rec
        assert "priority" in rec
        assert 0.0 <= rec["priority"] <= 1.0
        assert "reasons" in rec


def test_ban_recommendations_exclude_banned(service):
    """Test that already banned champions are excluded."""
    recommendations = service.get_ban_recommendations(
        enemy_team_id="123",
        our_picks=[],
        enemy_picks=[],
        already_banned=["Aurora", "Yone", "Yasuo"],
        phase=1,
        limit=5
    )

    banned_names = {"Aurora", "Yone", "Yasuo"}
    for rec in recommendations:
        assert rec["champion_name"] not in banned_names


def test_ban_recommendations_exclude_picked(service):
    """Test that already picked champions are excluded."""
    recommendations = service.get_ban_recommendations(
        enemy_team_id="123",
        our_picks=["Jinx"],
        enemy_picks=["Azir"],
        already_banned=[],
        phase=2,
        limit=5
    )

    picked_names = {"Jinx", "Azir"}
    for rec in recommendations:
        assert rec["champion_name"] not in picked_names


def test_ban_priority_calculation(service):
    """Test ban priority factors."""
    # High meta champion should have higher priority than low meta
    high_meta_priority = service.calculate_ban_priority(
        champion="Aurora",  # Assuming high meta presence
        enemy_team_id="123",
        our_archetype="engage",
        enemy_archetype=None
    )

    # Priority should be valid range
    assert 0.0 <= high_meta_priority <= 1.0
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_ban_recommendation_service.py -v`

Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write minimal implementation**

Create file: `backend/src/ban_teemo/services/ban_recommendation_service.py`

```python
"""Service for generating ban recommendations."""
import json
from pathlib import Path
from typing import Optional


class BanRecommendationService:
    """Generates intelligent ban recommendations."""

    # Ban priority weights
    WEIGHTS = {
        "meta_strength": 0.30,
        "player_proficiency": 0.25,
        "archetype_counter": 0.20,
        "flex_value": 0.15,
        "matchup_threat": 0.10,
    }

    def __init__(self, knowledge_dir: Optional[Path] = None):
        if knowledge_dir is None:
            knowledge_dir = Path(__file__).parent.parent.parent.parent.parent / "knowledge"

        self.knowledge_dir = knowledge_dir
        self._meta_stats: dict = {}
        self._player_proficiency: dict = {}
        self._archetype_counters: dict = {}
        self._flex_champions: dict = {}
        self._load_data()

    def _load_data(self):
        """Load knowledge files for ban recommendations."""
        # Meta stats
        meta_path = self.knowledge_dir / "meta_stats.json"
        if meta_path.exists():
            with open(meta_path) as f:
                data = json.load(f)
                self._meta_stats = data.get("champions", {})

        # Player proficiency
        prof_path = self.knowledge_dir / "player_proficiency.json"
        if prof_path.exists():
            with open(prof_path) as f:
                data = json.load(f)
                self._player_proficiency = data.get("proficiencies", {})

        # Archetype counters
        arch_path = self.knowledge_dir / "archetype_counters.json"
        if arch_path.exists():
            with open(arch_path) as f:
                data = json.load(f)
                self._archetype_counters = data.get("effectiveness_matrix", {})

        # Flex champions
        flex_path = self.knowledge_dir / "flex_champions.json"
        if flex_path.exists():
            with open(flex_path) as f:
                data = json.load(f)
                self._flex_champions = data.get("flex_picks", {})

    def get_ban_recommendations(
        self,
        enemy_team_id: str,
        our_picks: list[str],
        enemy_picks: list[str],
        already_banned: list[str],
        phase: int = 1,
        limit: int = 3
    ) -> list[dict]:
        """Generate ban recommendations.

        Args:
            enemy_team_id: ID of enemy team (for player targeting)
            our_picks: Champions our team has picked
            enemy_picks: Champions enemy team has picked
            already_banned: Champions already banned
            phase: Ban phase (1 or 2)
            limit: Max recommendations to return

        Returns:
            List of ban recommendations with champion_name, priority, reasons
        """
        unavailable = set(already_banned) | set(our_picks) | set(enemy_picks)

        # Get all available champions to consider
        candidates = []

        for champ_name, meta_data in self._meta_stats.items():
            if champ_name in unavailable:
                continue

            priority = self.calculate_ban_priority(
                champion=champ_name,
                enemy_team_id=enemy_team_id,
                our_archetype=self._detect_archetype(our_picks),
                enemy_archetype=self._detect_archetype(enemy_picks)
            )

            reasons = self._generate_ban_reasons(
                champ_name, meta_data, enemy_team_id, phase
            )

            candidates.append({
                "champion_name": champ_name,
                "priority": round(priority, 3),
                "reasons": reasons,
                "target_player": None  # Would be populated with player targeting
            })

        # Sort by priority and return top N
        candidates.sort(key=lambda x: -x["priority"])
        return candidates[:limit]

    def calculate_ban_priority(
        self,
        champion: str,
        enemy_team_id: str,
        our_archetype: Optional[str],
        enemy_archetype: Optional[str]
    ) -> float:
        """Calculate ban priority score for a champion.

        Args:
            champion: Champion name
            enemy_team_id: Enemy team ID
            our_archetype: Our team's primary archetype
            enemy_archetype: Enemy team's emerging archetype

        Returns:
            float priority 0.0-1.0
        """
        meta_data = self._meta_stats.get(champion, {})

        # Meta strength (presence + win rate)
        presence = meta_data.get("presence", 0)
        win_rate = meta_data.get("win_rate", 0.5)
        meta_score = (presence * 0.6 + (win_rate - 0.45) * 2) * 0.5
        meta_score = min(1.0, max(0.0, meta_score))

        # Flex value (higher for flex picks)
        flex_data = self._flex_champions.get(champion, {})
        is_flex = flex_data.get("is_flex", False)
        flex_score = 0.8 if is_flex else 0.3

        # Archetype counter (ban what enables enemy archetype)
        archetype_score = 0.5
        if enemy_archetype and our_archetype:
            # If champion enables enemy's archetype that counters ours, high value
            counter_key = f"vs_{our_archetype}"
            enemy_effectiveness = self._archetype_counters.get(enemy_archetype, {}).get(counter_key, 1.0)
            if enemy_effectiveness > 1.0:
                archetype_score = 0.8  # Enemy archetype counters us, ban enablers

        # Player proficiency (placeholder - would need team roster)
        proficiency_score = 0.5

        # Matchup threat (placeholder)
        matchup_score = 0.5

        # Weighted combination
        priority = (
            meta_score * self.WEIGHTS["meta_strength"] +
            proficiency_score * self.WEIGHTS["player_proficiency"] +
            archetype_score * self.WEIGHTS["archetype_counter"] +
            flex_score * self.WEIGHTS["flex_value"] +
            matchup_score * self.WEIGHTS["matchup_threat"]
        )

        return min(1.0, max(0.0, priority))

    def _detect_archetype(self, picks: list[str]) -> Optional[str]:
        """Detect primary archetype from picks (simplified)."""
        if not picks:
            return None
        # Would use ArchetypeService for full detection
        return None

    def _generate_ban_reasons(
        self,
        champion: str,
        meta_data: dict,
        enemy_team_id: str,
        phase: int
    ) -> list[str]:
        """Generate human-readable ban reasons."""
        reasons = []

        presence = meta_data.get("presence", 0)
        win_rate = meta_data.get("win_rate", 0.5)
        tier = meta_data.get("meta_tier")

        if tier == "S":
            reasons.append(f"S-tier meta pick ({presence:.0%} presence)")
        elif tier == "A":
            reasons.append(f"A-tier meta pick ({presence:.0%} presence)")

        if win_rate >= 0.55:
            reasons.append(f"High win rate ({win_rate:.0%})")

        flex_data = self._flex_champions.get(champion, {})
        if flex_data.get("is_flex"):
            reasons.append("Flex pick - removes multiple options")

        # Counter-pick flag
        if meta_data.get("pick_context", {}).get("is_counter_pick_dependent"):
            reasons.append("Often used as counter-pick")

        return reasons if reasons else ["Meta consideration"]
```

**Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_ban_recommendation_service.py -v`

Expected: All tests PASS

**Step 5: Commit**

```bash
git add backend/src/ban_teemo/services/ban_recommendation_service.py backend/tests/test_ban_recommendation_service.py
git commit -m "feat: add ban recommendation service"
```

---

## Task 7: Integrate Services into Draft Service

**Files:**
- Modify: `backend/src/ban_teemo/services/draft_service.py`
- Create: `backend/tests/test_draft_service_integration.py`

**Step 1: Write the failing test**

Create file: `backend/tests/test_draft_service_integration.py`

```python
"""Integration tests for draft service with new scoring services."""
import pytest
from ban_teemo.services.draft_service import DraftService
from ban_teemo.models.draft import DraftState, DraftPhase


@pytest.fixture
def service():
    return DraftService()


def test_get_recommendations_returns_team_evaluation(service):
    """Test that recommendations include team evaluation."""
    # Create a mock draft state
    draft_state = create_mock_draft_state(
        blue_picks=["Malphite", "Nocturne"],
        red_picks=["Fiora"],
        phase=DraftPhase.PICK_PHASE_1
    )

    recommendations = service.get_recommendations(draft_state, for_team="blue")

    assert "team_evaluation" in recommendations
    assert "archetype" in recommendations["team_evaluation"]
    assert "composition_score" in recommendations["team_evaluation"]


def test_get_recommendations_includes_archetype_advantage(service):
    """Test that recommendations include archetype matchup info."""
    draft_state = create_mock_draft_state(
        blue_picks=["Malphite", "Orianna", "Jinx"],
        red_picks=["Fiora", "Lee Sin", "Azir"],
        phase=DraftPhase.PICK_PHASE_2
    )

    recommendations = service.get_recommendations(draft_state, for_team="blue")

    assert "matchup_advantage" in recommendations


def test_get_ban_recommendations(service):
    """Test ban recommendations during ban phase."""
    draft_state = create_mock_draft_state(
        blue_picks=[],
        red_picks=[],
        blue_bans=["Aurora"],
        red_bans=["Yone"],
        phase=DraftPhase.BAN_PHASE_1
    )

    recommendations = service.get_recommendations(draft_state, for_team="blue")

    assert "bans" in recommendations
    assert len(recommendations["bans"]) > 0


def create_mock_draft_state(
    blue_picks=None,
    red_picks=None,
    blue_bans=None,
    red_bans=None,
    phase=DraftPhase.BAN_PHASE_1
) -> DraftState:
    """Create a mock draft state for testing."""
    from ban_teemo.models.draft import DraftState, TeamContext

    return DraftState(
        game_id="test-game",
        series_id="test-series",
        patch="15.18",
        blue_team=TeamContext(id="blue-team", name="Blue Team", side="blue", players=[]),
        red_team=TeamContext(id="red-team", name="Red Team", side="red", players=[]),
        actions=[],
        current_phase=phase,
        blue_bans=blue_bans or [],
        red_bans=red_bans or [],
        blue_picks=blue_picks or [],
        red_picks=red_picks or [],
        next_action_team="blue",
        next_action_type="ban"
    )
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_draft_service_integration.py -v`

Expected: FAIL (recommendations missing new fields)

**Step 3: Update draft_service.py to integrate new services**

Modify `backend/src/ban_teemo/services/draft_service.py`:

```python
"""Draft service with integrated recommendation scoring."""
from typing import Optional
from ban_teemo.models.draft import DraftState, DraftPhase
from ban_teemo.models.recommendations import Recommendations, PickRecommendation, BanRecommendation
from ban_teemo.services.archetype_service import ArchetypeService
from ban_teemo.services.synergy_service import SynergyService
from ban_teemo.services.team_evaluation_service import TeamEvaluationService
from ban_teemo.services.ban_recommendation_service import BanRecommendationService


class DraftService:
    """Core draft logic with integrated scoring services."""

    def __init__(self):
        self.archetype_service = ArchetypeService()
        self.synergy_service = SynergyService()
        self.team_evaluation_service = TeamEvaluationService()
        self.ban_recommendation_service = BanRecommendationService()

    def compute_phase(self, action_count: int) -> DraftPhase:
        """Determine current draft phase from action count."""
        if action_count < 6:
            return DraftPhase.BAN_PHASE_1
        elif action_count < 12:
            return DraftPhase.PICK_PHASE_1
        elif action_count < 16:
            return DraftPhase.BAN_PHASE_2
        elif action_count < 20:
            return DraftPhase.PICK_PHASE_2
        else:
            return DraftPhase.COMPLETE

    def get_recommendations(
        self,
        draft_state: DraftState,
        for_team: str
    ) -> dict:
        """Generate recommendations for a team.

        Args:
            draft_state: Current draft state
            for_team: "blue" or "red"

        Returns:
            dict with picks, bans, team_evaluation, matchup_advantage
        """
        # Get team's picks and enemy's picks
        if for_team == "blue":
            our_picks = draft_state.blue_picks
            enemy_picks = draft_state.red_picks
            our_bans = draft_state.blue_bans
            enemy_bans = draft_state.red_bans
            enemy_team_id = draft_state.red_team.id if draft_state.red_team else ""
        else:
            our_picks = draft_state.red_picks
            enemy_picks = draft_state.blue_picks
            our_bans = draft_state.red_bans
            enemy_bans = draft_state.blue_bans
            enemy_team_id = draft_state.blue_team.id if draft_state.blue_team else ""

        all_banned = our_bans + enemy_bans

        # Team evaluation
        team_eval = self.team_evaluation_service.evaluate_team_draft(our_picks)

        # Matchup advantage
        matchup = self.team_evaluation_service.evaluate_vs_enemy(our_picks, enemy_picks)

        # Generate recommendations based on phase
        phase = draft_state.current_phase

        result = {
            "team_evaluation": team_eval,
            "matchup_advantage": matchup["matchup_advantage"],
            "picks": [],
            "bans": []
        }

        if phase in [DraftPhase.BAN_PHASE_1, DraftPhase.BAN_PHASE_2]:
            # Ban phase - generate ban recommendations
            ban_phase = 1 if phase == DraftPhase.BAN_PHASE_1 else 2
            result["bans"] = self.ban_recommendation_service.get_ban_recommendations(
                enemy_team_id=enemy_team_id,
                our_picks=our_picks,
                enemy_picks=enemy_picks,
                already_banned=all_banned,
                phase=ban_phase,
                limit=3
            )
        else:
            # Pick phase - generate pick recommendations
            result["picks"] = self._generate_pick_recommendations(
                our_picks=our_picks,
                enemy_picks=enemy_picks,
                banned=all_banned,
                team_eval=team_eval
            )

        return result

    def _generate_pick_recommendations(
        self,
        our_picks: list[str],
        enemy_picks: list[str],
        banned: list[str],
        team_eval: dict
    ) -> list[dict]:
        """Generate pick recommendations (simplified for now)."""
        # This would integrate meta_stats, proficiency, matchups, etc.
        # For now, return empty - to be expanded in future tasks
        return []
```

**Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_draft_service_integration.py -v`

Expected: All tests PASS

**Step 5: Commit**

```bash
git add backend/src/ban_teemo/services/draft_service.py backend/tests/test_draft_service_integration.py
git commit -m "feat: integrate scoring services into draft service"
```

---

## Task 8: Run Full Test Suite and Verify

**Step 1: Run all backend tests**

Run: `cd backend && uv run pytest tests/ -v`

Expected: All tests PASS

**Step 2: Run linting**

Run: `cd backend && uv run ruff check src/`

Expected: No errors (or fix any that appear)

**Step 3: Verify all knowledge files exist**

Run: `ls -la knowledge/*.json | head -20`

Expected: All knowledge files present including new ones

**Step 4: Final commit**

```bash
git add -A
git commit -m "chore: final cleanup and verification"
```

---

## Summary

This plan implements:

1. **Archetype Counter Matrix** (`archetype_counters.json`) - RPS system for team comp matchups
2. **Champion Archetype Scores** (`champion_archetypes.json`) - Per-champion archetype classification
3. **Archetype Service** - Calculate team archetypes and matchup effectiveness
4. **Synergy Service** - Use S/A/B/C ratings as quality multipliers
5. **Team Evaluation Service** - Cumulative team scoring with archetype + synergy
6. **Ban Recommendation Service** - Multi-factor ban priority scoring
7. **Draft Service Integration** - Wire all services together

Total estimated tasks: 8
Total estimated commits: 8
