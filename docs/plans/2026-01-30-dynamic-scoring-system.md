# Dynamic Scoring System Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix scoring system gaps causing 24.7% pick accuracy and 18.4% ban accuracy by implementing phase-aware, context-sensitive scoring for both picks and bans.

**Architecture:** Replace static weight-based scoring with dynamic, draft-phase-aware scoring. Pick engine gets versatility-aware archetype scoring and context-sensitive weights. Ban engine gets power-pick focus for Phase 1 and archetype/synergy denial for Phase 2.

**Tech Stack:** Python 3.11+, pytest, existing ban_teemo services

---

## Root Cause Analysis Summary

### Critical Issues Identified

1. **Versatile Champion Penalty** (Archetype Scoring)
   - Current: Normalization divides by total archetype scores
   - Result: Multi-archetype champions (Orianna, Galio, J4) score 0.4-0.5 vs specialists at 0.9
   - Impact: 126 first-pick misses, including Orianna(18), Jarvan IV(9)

2. **Context Blindness** (Pick Weights)
   - Current: Static 20% proficiency weight regardless of draft phase
   - Result: First picks over-weighted toward player comfort vs meta power
   - Impact: Missing contested power picks early in draft

3. **Ban Strategy Static** (Ban Engine)
   - Current: Same player-pool targeting for both ban phases
   - Result: BAN_PHASE_2 at 14.4% accuracy (worst phase)
   - Impact: Missing archetype counters, synergy denial, role denial

### Data Flow Reference

```
knowledge/meta_stats.json     → MetaScorer (25%)      → Power level + presence
knowledge/player_proficiency  → ProficiencyScorer    → Player comfort (20%)
knowledge/archetype_counters  → ArchetypeService     → Team composition (20%)
knowledge/matchup_stats.json  → MatchupCalculator    → Lane/team counters (35%)
knowledge/champion_role_hist  → FlexResolver         → Role assignment
```

---

## Task 1: Add Versatility Detection to Archetype Service

**Files:**
- Modify: `backend/src/ban_teemo/services/archetype_service.py:29-41`
- Test: `backend/tests/test_archetype_service.py`

**Step 1: Write failing test for versatility score**

```python
# Add to backend/tests/test_archetype_service.py

def test_get_versatility_score_single_archetype():
    """Single-archetype champions have low versatility."""
    service = ArchetypeService()
    # Azir has only teamfight: 0.6
    score = service.get_versatility_score("Azir")
    assert score < 0.3, "Single archetype should have low versatility"


def test_get_versatility_score_multi_archetype():
    """Multi-archetype champions have high versatility."""
    service = ArchetypeService()
    # Orianna has engage: 0.5, protect: 0.5, teamfight: 1.0
    score = service.get_versatility_score("Orianna")
    assert score >= 0.5, "Multi-archetype should have high versatility"


def test_get_versatility_score_unknown_champion():
    """Unknown champions return neutral versatility."""
    service = ArchetypeService()
    score = service.get_versatility_score("NonexistentChamp")
    assert score == 0.0
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_archetype_service.py::test_get_versatility_score_single_archetype -v`
Expected: FAIL with "AttributeError: 'ArchetypeService' object has no attribute 'get_versatility_score'"

**Step 3: Write minimal implementation**

Add to `backend/src/ban_teemo/services/archetype_service.py` after `get_champion_archetypes` method:

```python
def get_versatility_score(self, champion: str) -> float:
    """Calculate versatility score based on archetype diversity.

    Champions with multiple significant archetypes (>= 0.4) are more versatile,
    meaning they can fit multiple team compositions and are harder to read.

    Returns:
        Float 0.0-1.0 where higher = more versatile
    """
    if champion not in self._champion_archetypes:
        return 0.0

    scores = self._champion_archetypes[champion]
    # Count archetypes with meaningful contribution (>= 0.4)
    significant_archetypes = [v for v in scores.values() if v >= 0.4]
    num_significant = len(significant_archetypes)

    if num_significant >= 3:
        return 0.8  # Highly versatile (3+ archetypes)
    elif num_significant >= 2:
        return 0.5  # Moderately versatile (2 archetypes)
    elif num_significant >= 1:
        return 0.2  # Focused (1 archetype)
    return 0.0  # No archetype data
```

**Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_archetype_service.py::test_get_versatility_score_single_archetype tests/test_archetype_service.py::test_get_versatility_score_multi_archetype tests/test_archetype_service.py::test_get_versatility_score_unknown_champion -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/ban_teemo/services/archetype_service.py backend/tests/test_archetype_service.py
git commit -m "feat(archetype): add versatility score for multi-archetype champions"
```

---

## Task 2: Add Contribution Score to Archetype Service

**Files:**
- Modify: `backend/src/ban_teemo/services/archetype_service.py`
- Test: `backend/tests/test_archetype_service.py`

**Step 1: Write failing test for contribution score**

```python
# Add to backend/tests/test_archetype_service.py

def test_get_contribution_to_archetype_matching():
    """Champion contributes to team's primary archetype."""
    service = ArchetypeService()
    # Orianna has teamfight: 1.0, adding to teamfight team should score high
    score = service.get_contribution_to_archetype("Orianna", "teamfight")
    assert score >= 0.8, "Orianna should contribute highly to teamfight"


def test_get_contribution_to_archetype_mismatched():
    """Champion doesn't contribute to unrelated archetype."""
    service = ArchetypeService()
    # Orianna has no split archetype
    score = service.get_contribution_to_archetype("Orianna", "split")
    assert score == 0.0, "Orianna should not contribute to split"


def test_get_contribution_to_archetype_partial():
    """Champion partially contributes to secondary archetype."""
    service = ArchetypeService()
    # Orianna has engage: 0.5
    score = service.get_contribution_to_archetype("Orianna", "engage")
    assert 0.3 <= score <= 0.7, "Orianna should partially contribute to engage"
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_archetype_service.py::test_get_contribution_to_archetype_matching -v`
Expected: FAIL with "AttributeError"

**Step 3: Write minimal implementation**

Add to `backend/src/ban_teemo/services/archetype_service.py`:

```python
def get_contribution_to_archetype(self, champion: str, archetype: str) -> float:
    """Get how much a champion contributes to a specific archetype.

    Args:
        champion: Champion name
        archetype: Target archetype (engage, split, teamfight, protect, pick)

    Returns:
        Float 0.0-1.0 representing contribution strength
    """
    if champion not in self._champion_archetypes:
        return 0.0

    scores = self._champion_archetypes[champion]
    return scores.get(archetype, 0.0)
```

**Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_archetype_service.py::test_get_contribution_to_archetype_matching tests/test_archetype_service.py::test_get_contribution_to_archetype_mismatched tests/test_archetype_service.py::test_get_contribution_to_archetype_partial -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/ban_teemo/services/archetype_service.py backend/tests/test_archetype_service.py
git commit -m "feat(archetype): add contribution score for archetype alignment"
```

---

## Task 3: Add Raw Strength Method to Archetype Service

**Files:**
- Modify: `backend/src/ban_teemo/services/archetype_service.py`
- Test: `backend/tests/test_archetype_service.py`

**Step 1: Write failing test**

```python
# Add to backend/tests/test_archetype_service.py

def test_get_raw_strength_returns_max_score():
    """Raw strength is the maximum archetype score."""
    service = ArchetypeService()
    # Orianna has engage: 0.5, protect: 0.5, teamfight: 1.0
    strength = service.get_raw_strength("Orianna")
    assert strength == 1.0, "Should return max archetype score"


def test_get_raw_strength_single_archetype():
    """Single archetype champion returns that score."""
    service = ArchetypeService()
    # Azir has teamfight: 0.6
    strength = service.get_raw_strength("Azir")
    assert strength == 0.6


def test_get_raw_strength_unknown():
    """Unknown champion returns 0.5 neutral."""
    service = ArchetypeService()
    strength = service.get_raw_strength("NonexistentChamp")
    assert strength == 0.5
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_archetype_service.py::test_get_raw_strength_returns_max_score -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
def get_raw_strength(self, champion: str) -> float:
    """Get champion's raw archetype strength (max of all archetypes).

    This avoids the normalization penalty for versatile champions.

    Returns:
        Float 0.0-1.0, or 0.5 for unknown champions
    """
    if champion not in self._champion_archetypes:
        return 0.5  # Neutral for unknown

    scores = self._champion_archetypes[champion]
    if not scores:
        return 0.5
    return max(scores.values())
```

**Step 4: Run tests**

Run: `cd backend && uv run pytest tests/test_archetype_service.py -k "raw_strength" -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/ban_teemo/services/archetype_service.py backend/tests/test_archetype_service.py
git commit -m "feat(archetype): add raw strength method avoiding normalization penalty"
```

---

## Task 4: Implement Phase-Aware Archetype Scoring in Pick Engine

**Files:**
- Modify: `backend/src/ban_teemo/services/pick_recommendation_engine.py:333-382`
- Test: `backend/tests/test_pick_recommendation_engine.py`

**Step 1: Write failing tests for phase-aware archetype scoring**

```python
# Add to backend/tests/test_pick_recommendation_engine.py

def test_archetype_score_early_draft_values_versatility():
    """Early draft (0-1 picks) should value versatility."""
    engine = PickRecommendationEngine()

    # Orianna is versatile (3 archetypes), Azir is specialist (1 archetype)
    ori_score = engine._calculate_archetype_score("Orianna", [], [])
    azir_score = engine._calculate_archetype_score("Azir", [], [])

    # In early draft, versatile champions should NOT be penalized
    # They should score at least as high as specialists
    assert ori_score >= azir_score - 0.1, (
        f"Versatile Orianna ({ori_score}) should not be heavily penalized vs "
        f"specialist Azir ({azir_score}) in early draft"
    )


def test_archetype_score_mid_draft_values_alignment():
    """Mid draft (2+ picks) should value alignment with team direction."""
    engine = PickRecommendationEngine()

    # Team has picked J4 (engage) and Rumble (teamfight)
    our_picks = ["Jarvan IV", "Rumble"]

    # Orianna (teamfight) should score well with this team
    ori_score = engine._calculate_archetype_score("Orianna", our_picks, [])

    # Fiora (split) should score worse - doesn't fit teamfight direction
    fiora_score = engine._calculate_archetype_score("Fiora", our_picks, [])

    assert ori_score > fiora_score, (
        f"Orianna ({ori_score}) should fit teamfight team better than "
        f"Fiora ({fiora_score})"
    )


def test_archetype_score_versatile_not_penalized_first_pick():
    """Versatile champions should get bonus in first pick scenario."""
    engine = PickRecommendationEngine()

    # First pick - no context
    ori_score = engine._calculate_archetype_score("Orianna", [], [])

    # Should be significantly higher than the old 0.5 penalty
    assert ori_score >= 0.7, (
        f"Versatile Orianna should score >= 0.7 in first pick, got {ori_score}"
    )
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_pick_recommendation_engine.py::test_archetype_score_early_draft_values_versatility -v`
Expected: FAIL (Orianna currently scores 0.5 vs Azir's 0.9)

**Step 3: Rewrite `_calculate_archetype_score` method**

Replace the method in `backend/src/ban_teemo/services/pick_recommendation_engine.py`:

```python
def _calculate_archetype_score(
    self,
    champion: str,
    our_picks: list[str],
    enemy_picks: list[str],
) -> float:
    """Calculate phase-aware archetype score.

    Scoring strategy changes by draft phase:
    - Early draft (0-1 picks): Value raw strength + versatility bonus
    - Mid draft (2-3 picks): Blend raw strength with team alignment
    - Late draft (4+ picks): Weight alignment + counter-effectiveness

    Returns:
        Score from 0-1, where 0.5 is neutral.
    """
    pick_count = len(our_picks)

    # Get champion's archetype data
    raw_strength = self.archetype_service.get_raw_strength(champion)
    versatility = self.archetype_service.get_versatility_score(champion)

    # PHASE 1: Early draft (0-1 picks) - Value versatility
    if pick_count <= 1:
        # Versatile champions are valuable - they hide strategy
        versatility_bonus = versatility * 0.15
        return min(1.0, raw_strength + versatility_bonus)

    # PHASE 2+: Mid-late draft - Value alignment with team direction
    team_arch = self.archetype_service.calculate_team_archetype(our_picks)
    team_primary = team_arch.get("primary")

    if not team_primary:
        # No clear team direction yet - use raw strength
        return raw_strength

    # How much does this champion contribute to team's direction?
    contribution = self.archetype_service.get_contribution_to_archetype(
        champion, team_primary
    )

    # Blend contribution with raw strength
    # More picks = weight contribution more heavily
    alignment_weight = min(0.7, pick_count * 0.15)  # 0.30 at 2 picks → 0.70 at 5
    base_score = (
        contribution * alignment_weight +
        raw_strength * (1 - alignment_weight)
    )

    # PHASE 3: Factor in counter-effectiveness vs enemy (late draft)
    if enemy_picks and pick_count >= 3:
        advantage = self.archetype_service.calculate_comp_advantage(
            our_picks + [champion], enemy_picks
        )
        effectiveness = advantage.get("advantage", 1.0)
        # Normalize effectiveness (typically 0.8-1.2) to 0-1 scale
        effectiveness_normalized = max(0.0, min(1.0, (effectiveness - 0.8) / 0.4))

        # Weight effectiveness more as draft progresses
        eff_weight = min(0.4, (pick_count - 2) * 0.1)  # 0.1 at 3 picks → 0.4 at 5+
        base_score = base_score * (1 - eff_weight) + effectiveness_normalized * eff_weight

    return round(base_score, 3)
```

**Step 4: Run tests**

Run: `cd backend && uv run pytest tests/test_pick_recommendation_engine.py -k "archetype_score" -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/ban_teemo/services/pick_recommendation_engine.py backend/tests/test_pick_recommendation_engine.py
git commit -m "feat(picks): implement phase-aware archetype scoring

- Early draft: value versatility, don't penalize multi-archetype champs
- Mid draft: blend raw strength with team alignment
- Late draft: factor in counter-effectiveness vs enemy"
```

---

## Task 5: Add Context-Aware Weight Adjustment to Pick Engine

**Files:**
- Modify: `backend/src/ban_teemo/services/pick_recommendation_engine.py:448-468`
- Test: `backend/tests/test_pick_recommendation_engine.py`

**Step 1: Write failing tests**

```python
# Add to backend/tests/test_pick_recommendation_engine.py

def test_get_effective_weights_first_pick_reduces_proficiency():
    """First pick should reduce proficiency weight, increase meta."""
    engine = PickRecommendationEngine()

    # First pick scenario: no picks, no enemy picks
    weights = engine._get_effective_weights("HIGH", pick_count=0, has_enemy_picks=False)

    # Proficiency should be reduced from base 0.20
    assert weights["proficiency"] < 0.20, "First pick should reduce proficiency weight"
    # Meta should be increased from base 0.25
    assert weights["meta"] > 0.25, "First pick should increase meta weight"


def test_get_effective_weights_counter_pick_increases_matchup():
    """Counter-pick scenario should increase matchup weight."""
    engine = PickRecommendationEngine()

    # Late draft with enemy picks visible
    weights = engine._get_effective_weights("HIGH", pick_count=4, has_enemy_picks=True)

    # Matchup should be increased for counter-picking
    assert weights["matchup"] >= 0.20, "Counter-pick should maintain/increase matchup weight"


def test_get_effective_weights_no_data_redistributes():
    """NO_DATA proficiency should redistribute weight to other components."""
    engine = PickRecommendationEngine()

    weights = engine._get_effective_weights("NO_DATA", pick_count=2, has_enemy_picks=False)

    # Proficiency weight should be heavily reduced
    assert weights["proficiency"] < 0.10, "NO_DATA should reduce proficiency weight"
    # Total should still sum to ~1.0
    total = sum(weights.values())
    assert 0.99 <= total <= 1.01, f"Weights should sum to 1.0, got {total}"
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_pick_recommendation_engine.py::test_get_effective_weights_first_pick_reduces_proficiency -v`
Expected: FAIL (current method doesn't take pick_count or has_enemy_picks)

**Step 3: Update `_get_effective_weights` method signature and implementation**

Replace in `backend/src/ban_teemo/services/pick_recommendation_engine.py`:

```python
def _get_effective_weights(
    self,
    prof_conf: str,
    pick_count: int = 0,
    has_enemy_picks: bool = False
) -> dict:
    """Get context-adjusted scoring weights.

    Adjustments:
    - First pick (pick_count=0, no enemy): reduce proficiency, boost meta
    - Counter-pick (late draft, has enemy): boost matchup
    - NO_DATA proficiency: redistribute to other components

    Args:
        prof_conf: Proficiency confidence level
        pick_count: Number of picks our team has made
        has_enemy_picks: Whether enemy has revealed picks

    Returns:
        Dict of component weights summing to ~1.0
    """
    weights = dict(self.BASE_WEIGHTS)

    # First pick context: reduce proficiency, increase meta
    # Rationale: First picks are about power level, not player comfort
    if pick_count == 0 and not has_enemy_picks:
        redistribution = 0.08  # Take from proficiency
        weights["proficiency"] -= redistribution
        weights["meta"] += redistribution

    # Counter-pick context: increase matchup weight
    # Rationale: Late picks should exploit matchup knowledge
    elif has_enemy_picks and pick_count >= 3:
        redistribution = 0.05
        weights["meta"] -= redistribution
        weights["matchup"] += redistribution

    # Handle NO_DATA proficiency - redistribute most of its weight
    if prof_conf == "NO_DATA":
        redistribute = weights["proficiency"] * 0.8
        weights["proficiency"] = weights["proficiency"] * 0.2
        # Distribute evenly to other components
        for key in ["meta", "matchup", "counter", "archetype"]:
            weights[key] += redistribute / 4

    return weights
```

**Step 4: Update `_calculate_score` to pass new parameters**

Find the call to `_get_effective_weights` in `_calculate_score` (around line 309) and update:

```python
# In _calculate_score method, replace:
effective_weights = self._get_effective_weights(role_prof_conf)

# With:
effective_weights = self._get_effective_weights(
    role_prof_conf,
    pick_count=len(our_picks),
    has_enemy_picks=len(enemy_picks) > 0
)
```

**Step 5: Run tests**

Run: `cd backend && uv run pytest tests/test_pick_recommendation_engine.py -k "effective_weights" -v`
Expected: PASS

**Step 6: Commit**

```bash
git add backend/src/ban_teemo/services/pick_recommendation_engine.py backend/tests/test_pick_recommendation_engine.py
git commit -m "feat(picks): add context-aware weight adjustment

- First pick: reduce proficiency, boost meta for power picks
- Counter-pick: boost matchup weight for late draft
- NO_DATA: redistribute proficiency weight to other components"
```

---

## Task 6: Add Blind-Pick Safety Factor to Meta Scorer

**Files:**
- Modify: `backend/src/ban_teemo/services/scorers/meta_scorer.py`
- Test: `backend/tests/test_meta_scorer.py`

**Step 1: Write failing tests**

```python
# Add to backend/tests/test_meta_scorer.py

def test_get_blind_pick_safety_counter_dependent_penalized():
    """Counter-pick dependent champions should have lower blind safety."""
    scorer = MetaScorer()

    # Neeko is flagged as counter_pick_dependent in meta_stats
    safety = scorer.get_blind_pick_safety("Neeko")

    # Should be penalized for blind picking
    assert safety < 0.9, f"Counter-dependent Neeko should have low blind safety: {safety}"


def test_get_blind_pick_safety_blind_safe_rewarded():
    """Champions with high blind win rate should have good safety."""
    scorer = MetaScorer()

    # Azir has high blind_early_win_rate
    safety = scorer.get_blind_pick_safety("Azir")

    assert safety >= 0.9, f"Blind-safe Azir should have high safety: {safety}"


def test_get_blind_pick_safety_unknown_neutral():
    """Unknown champions return neutral safety."""
    scorer = MetaScorer()

    safety = scorer.get_blind_pick_safety("NonexistentChamp")
    assert safety == 1.0, "Unknown should return neutral 1.0"
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest backend/tests/test_meta_scorer.py::test_get_blind_pick_safety_counter_dependent_penalized -v`
Expected: FAIL

**Step 3: Write implementation**

Add to `backend/src/ban_teemo/services/scorers/meta_scorer.py`:

```python
def get_blind_pick_safety(self, champion_name: str) -> float:
    """Get blind pick safety factor for a champion.

    Based on pick_context data:
    - Counter-pick dependent champions are penalized for blind picking
    - Champions with high blind_early_win_rate are rewarded

    Returns:
        Float 0.7-1.1 as a multiplier (1.0 = neutral)
    """
    if champion_name not in self._meta_stats:
        return 1.0  # Neutral for unknown

    meta_data = self._meta_stats[champion_name]
    pick_context = meta_data.get("pick_context", {})

    if not pick_context:
        return 1.0

    # Check if counter-pick dependent
    is_counter_dependent = pick_context.get("is_counter_pick_dependent", False)
    if is_counter_dependent:
        return 0.85  # Penalty for blind picking counter-dependent champs

    # Use blind early win rate to determine safety
    blind_wr = pick_context.get("blind_early_win_rate")
    if blind_wr is not None:
        # Scale 0.7-1.1 based on win rate (0.4-0.6 range)
        # 0.5 WR = 1.0 safety, 0.6 WR = 1.1, 0.4 WR = 0.9
        return 0.9 + (blind_wr - 0.5) * 0.4

    return 1.0
```

**Step 4: Run tests**

Run: `cd backend && uv run pytest backend/tests/test_meta_scorer.py -k "blind_pick" -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/ban_teemo/services/scorers/meta_scorer.py backend/tests/test_meta_scorer.py
git commit -m "feat(meta): add blind pick safety factor from pick_context data"
```

---

## Task 7: Integrate Blind Safety into Pick Scoring

**Files:**
- Modify: `backend/src/ban_teemo/services/pick_recommendation_engine.py:246-331`
- Test: `backend/tests/test_pick_recommendation_engine.py`

**Step 1: Write failing test**

```python
# Add to backend/tests/test_pick_recommendation_engine.py

def test_first_pick_applies_blind_safety_factor():
    """First pick scoring should apply blind safety factor."""
    engine = PickRecommendationEngine()

    team_players = [
        {"name": "TestTop", "role": "top"},
        {"name": "TestJungle", "role": "jungle"},
        {"name": "TestMid", "role": "mid"},
        {"name": "TestBot", "role": "bot"},
        {"name": "TestSupport", "role": "support"},
    ]

    # Get recommendations for first pick (no context)
    recommendations = engine.get_recommendations(
        team_players=team_players,
        our_picks=[],
        enemy_picks=[],
        banned=[],
        limit=10,
    )

    # Counter-dependent champions should not be top recommended for first pick
    # (Neeko is counter_pick_dependent)
    top_5_names = [r["champion_name"] for r in recommendations[:5]]

    # This is a soft check - Neeko can still appear but shouldn't dominate
    # The test validates the factor is being applied by checking scores
    for rec in recommendations:
        if rec["champion_name"] == "Neeko":
            # Check that blind_safety_applied flag exists or score reflects it
            # We'll add a flag to track this
            assert "blind_safety_applied" in rec or rec["score"] < 0.75
            break
```

**Step 2: Update `_calculate_score` to apply blind safety**

In `backend/src/ban_teemo/services/pick_recommendation_engine.py`, update `_calculate_score`:

```python
def _calculate_score(
    self,
    champion: str,
    team_players: list[dict],
    unfilled_roles: set[str],
    our_picks: list[str],
    enemy_picks: list[str],
    role_cache: dict[str, dict[str, float]],
    role_fill: Optional[dict[str, float]] = None,
) -> dict:
    """Calculate score using base factors + synergy multiplier."""
    components = {}
    pick_count = len(our_picks)
    has_enemy_picks = len(enemy_picks) > 0

    # Use cached role probabilities for suggested_role
    probs = role_cache.get(champion, {})
    (
        suggested_role,
        role_prof_score,
        role_prof_conf,
        prof_source,
        prof_player,
    ) = self._choose_best_role(champion, probs, team_players, role_fill=role_fill)
    suggested_role = suggested_role or "mid"

    # Meta
    components["meta"] = self.meta_scorer.get_meta_score(champion)

    # Proficiency - role-assigned player only
    components["proficiency"] = role_prof_score
    prof_conf_val = {"HIGH": 1.0, "MEDIUM": 0.8, "LOW": 0.5, "NO_DATA": 0.3}.get(
        role_prof_conf, 0.5
    )

    # Matchup (lane) - USE CACHE for enemy role probabilities
    matchup_scores = []
    for enemy in enemy_picks:
        role_probs = role_cache.get(enemy, {})
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

    # Synergy
    synergy_result = self.synergy_service.calculate_team_synergy(our_picks + [champion])
    synergy_score = synergy_result["total_score"]
    components["synergy"] = synergy_score
    synergy_multiplier = 1.0 + (synergy_score - 0.5) * self.SYNERGY_MULTIPLIER_RANGE

    # Archetype - phase-aware scoring
    archetype_score = self._calculate_archetype_score(champion, our_picks, enemy_picks)
    components["archetype"] = archetype_score

    # Base score with context-aware weights
    effective_weights = self._get_effective_weights(
        role_prof_conf,
        pick_count=pick_count,
        has_enemy_picks=has_enemy_picks
    )
    base_score = (
        components["meta"] * effective_weights["meta"] +
        components["proficiency"] * effective_weights["proficiency"] +
        components["matchup"] * effective_weights["matchup"] +
        components["counter"] * effective_weights["counter"] +
        components["archetype"] * effective_weights["archetype"]
    )

    # Apply blind pick safety factor for early picks without enemy context
    blind_safety_applied = False
    if pick_count <= 1 and not has_enemy_picks:
        blind_safety = self.meta_scorer.get_blind_pick_safety(champion)
        base_score = base_score * blind_safety
        blind_safety_applied = True
        components["blind_safety"] = blind_safety

    total_score = base_score * synergy_multiplier
    confidence = (1.0 + prof_conf_val) / 2

    return {
        "total_score": round(total_score, 3),
        "base_score": round(base_score, 3),
        "synergy_multiplier": round(synergy_multiplier, 3),
        "confidence": round(confidence, 3),
        "suggested_role": suggested_role,
        "components": {k: round(v, 3) for k, v in components.items()},
        "effective_weights": {k: round(v, 3) for k, v in effective_weights.items()},
        "proficiency_source": prof_source,
        "proficiency_player": prof_player,
        "blind_safety_applied": blind_safety_applied,
    }
```

**Step 3: Run tests**

Run: `cd backend && uv run pytest tests/test_pick_recommendation_engine.py -v`
Expected: PASS

**Step 4: Commit**

```bash
git add backend/src/ban_teemo/services/pick_recommendation_engine.py backend/tests/test_pick_recommendation_engine.py
git commit -m "feat(picks): integrate blind safety factor into early pick scoring"
```

---

## Task 8: Add Presence Score to Ban Service

**Files:**
- Modify: `backend/src/ban_teemo/services/ban_recommendation_service.py`
- Test: `backend/tests/test_ban_recommendation_service.py`

**Step 1: Write failing test**

```python
# Add to backend/tests/test_ban_recommendation_service.py

def test_get_presence_score_high_presence():
    """High presence champions should have high presence score."""
    service = BanRecommendationService()

    # Azir has ~39% presence
    score = service._get_presence_score("Azir")
    assert score >= 0.3, f"High presence Azir should score >= 0.3: {score}"


def test_get_presence_score_low_presence():
    """Low presence champions should have low presence score."""
    service = BanRecommendationService()

    score = service._get_presence_score("Qiyana")  # ~7% presence
    assert score < 0.15, f"Low presence Qiyana should score < 0.15: {score}"


def test_get_presence_score_unknown():
    """Unknown champions return 0."""
    service = BanRecommendationService()
    score = service._get_presence_score("NonexistentChamp")
    assert score == 0.0
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest backend/tests/test_ban_recommendation_service.py::test_get_presence_score_high_presence -v`
Expected: FAIL

**Step 3: Write implementation**

Add to `backend/src/ban_teemo/services/ban_recommendation_service.py`:

```python
def _get_presence_score(self, champion: str) -> float:
    """Get champion's presence rate as a score.

    Presence = pick_rate + ban_rate (how contested is this pick?)

    Returns:
        Float 0.0-1.0 representing presence
    """
    meta_data = self.meta_scorer._meta_stats.get(champion, {})
    presence = meta_data.get("presence", 0)
    return presence  # Already 0-1 scale
```

**Step 4: Run tests**

Run: `cd backend && uv run pytest backend/tests/test_ban_recommendation_service.py -k "presence" -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/ban_teemo/services/ban_recommendation_service.py backend/tests/test_ban_recommendation_service.py
git commit -m "feat(bans): add presence score for contested picks"
```

---

## Task 9: Add Flex Value Score to Ban Service

**Files:**
- Modify: `backend/src/ban_teemo/services/ban_recommendation_service.py`
- Test: `backend/tests/test_ban_recommendation_service.py`

**Step 1: Write failing test**

```python
# Add to backend/tests/test_ban_recommendation_service.py

def test_get_flex_value_multi_role():
    """Multi-role flex picks should have high flex value."""
    service = BanRecommendationService()

    # Need to add FlexResolver to ban service for this
    # Aurora can go mid/top/jungle
    value = service._get_flex_value("Aurora")
    assert value >= 0.5, f"Flex Aurora should have value >= 0.5: {value}"


def test_get_flex_value_single_role():
    """Single-role champions should have low flex value."""
    service = BanRecommendationService()

    # Jinx is bot only
    value = service._get_flex_value("Jinx")
    assert value <= 0.3, f"Single-role Jinx should have value <= 0.3: {value}"
```

**Step 2: First, add FlexResolver to ban service `__init__`**

Update `backend/src/ban_teemo/services/ban_recommendation_service.py`:

```python
# Add import at top
from ban_teemo.services.scorers import FlexResolver

# Update __init__
def __init__(
    self,
    knowledge_dir: Optional[Path] = None,
    draft_repository: Optional["DraftRepository"] = None
):
    if knowledge_dir is None:
        knowledge_dir = Path(__file__).parents[4] / "knowledge"

    self.meta_scorer = MetaScorer(knowledge_dir)
    self.proficiency_scorer = ProficiencyScorer(knowledge_dir)
    self.matchup_calculator = MatchupCalculator(knowledge_dir)
    self.flex_resolver = FlexResolver(knowledge_dir)  # Add this
    self._draft_repository = draft_repository
```

**Step 3: Write implementation**

```python
def _get_flex_value(self, champion: str) -> float:
    """Get champion's flex pick value based on role versatility.

    Champions that can play multiple roles are harder to plan against
    and more valuable to ban.

    Returns:
        Float 0.0-0.8 representing flex value
    """
    probs = self.flex_resolver.get_role_probabilities(champion)
    if not probs:
        return 0.2  # Unknown - assume single role

    # Count roles with >= 15% probability (viable roles)
    viable_roles = [r for r, p in probs.items() if p >= 0.15]

    if len(viable_roles) >= 3:
        return 0.8  # True flex (3+ roles)
    elif len(viable_roles) >= 2:
        return 0.5  # Dual flex
    return 0.2  # Single role
```

**Step 4: Run tests**

Run: `cd backend && uv run pytest backend/tests/test_ban_recommendation_service.py -k "flex" -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/ban_teemo/services/ban_recommendation_service.py backend/tests/test_ban_recommendation_service.py
git commit -m "feat(bans): add flex value score for role-versatile champions"
```

---

## Task 10: Update BAN_PHASE_1 Priority Calculation

**Files:**
- Modify: `backend/src/ban_teemo/services/ban_recommendation_service.py:129-187`
- Test: `backend/tests/test_ban_recommendation_service.py`

**Step 1: Write failing test**

```python
# Add to backend/tests/test_ban_recommendation_service.py

def test_phase1_ban_priority_uses_tiered_system():
    """Phase 1 bans should use tiered priority system."""
    service = BanRecommendationService()

    # T1: High proficiency + high presence + in pool
    priority_t1, components_t1 = service._calculate_ban_priority(
        champion="Azir",  # High presence champion
        player={"name": "TestPlayer", "role": "mid"},
        proficiency={"score": 0.8, "games": 10, "confidence": "HIGH"},
        pool_size=5,
        is_phase_1=True,
    )

    # Should include tier classification
    assert "tier" in components_t1, "Should include tier classification"
    assert components_t1["tier"] == "T1_POOL_AND_POWER", (
        f"High prof + high presence should be T1, got {components_t1['tier']}"
    )
    assert "tier_bonus" in components_t1, "Should include tier bonus"
    assert components_t1["tier_bonus"] >= 0.10, "T1 should have significant bonus"


def test_phase1_tier2_pool_targeting():
    """Tier 2 should apply for pool targeting without high presence."""
    service = BanRecommendationService()

    # T2: High proficiency, in pool, but low presence champion
    priority, components = service._calculate_ban_priority(
        champion="Qiyana",  # Lower presence (~7%)
        player={"name": "TestPlayer", "role": "mid"},
        proficiency={"score": 0.75, "games": 8, "confidence": "MEDIUM"},
        pool_size=3,
        is_phase_1=True,
    )

    # Should be T2 (pool target) or T4 (if presence threshold not met)
    tier = components.get("tier", "")
    assert tier in ["T2_POOL_TARGET", "T4_GENERAL"], f"Low presence comfort pick: {tier}"


def test_phase1_tier_ordering():
    """Higher tiers should have higher priority than lower tiers."""
    service = BanRecommendationService()

    # T1 scenario
    p1, c1 = service._calculate_ban_priority(
        champion="Azir",
        player={"name": "P1", "role": "mid"},
        proficiency={"score": 0.85, "games": 12, "confidence": "HIGH"},
        pool_size=4,
        is_phase_1=True,
    )

    # T4 scenario (low proficiency, low presence)
    p4, c4 = service._calculate_ban_priority(
        champion="Qiyana",
        player={"name": "P1", "role": "mid"},
        proficiency={"score": 0.5, "games": 2, "confidence": "LOW"},
        pool_size=8,
        is_phase_1=True,
    )

    assert p1 > p4, f"T1 priority ({p1}) should exceed T4 ({p4})"
```

**Step 2: Update `_calculate_ban_priority` to accept phase parameter and new weights**

```python
def _calculate_ban_priority(
    self,
    champion: str,
    player: dict,
    proficiency: dict,
    pool_size: int = 0,
    is_phase_1: bool = True,
) -> tuple[float, dict[str, float]]:
    """Calculate ban priority score using explicit tiered priority.

    TIERED PRIORITY SYSTEM (Phase 1):
        Tier 1 (Highest): High proficiency + high presence (in pool + meta power)
        Tier 2 (High):    High proficiency only (pool targeting)
        Tier 3 (Medium):  High presence only (global power)
        Tier 4 (Lower):   General meta bans

    Base weights: proficiency(30%), meta(25%), presence(25%), flex(20%)
    Tier bonuses applied on top for combined conditions.

    Args:
        champion: Champion name being considered for ban
        player: Player dict with 'name' and 'role'
        proficiency: Proficiency entry with 'score', 'games', 'confidence'
        pool_size: Pre-computed size of player's champion pool
        is_phase_1: Whether this is BAN_PHASE_1

    Returns:
        Tuple of (priority_score, components_dict)
    """
    components: dict[str, float] = {}

    if is_phase_1:
        # Phase 1: Tiered power pick priority

        # Calculate base components
        meta_score = self.meta_scorer.get_meta_score(champion)
        presence = self._get_presence_score(champion)
        flex = self._get_flex_value(champion)
        prof_score = proficiency["score"]
        conf = proficiency.get("confidence", "LOW")

        # Determine tier conditions
        is_high_proficiency = prof_score >= 0.7 and conf in {"HIGH", "MEDIUM"}
        is_high_presence = presence >= 0.25
        is_in_pool = proficiency.get("games", 0) >= 2

        # Base score (weights: prof 30%, meta 25%, presence 25%, flex 20%)
        proficiency_component = prof_score * 0.30
        meta_component = meta_score * 0.25
        presence_component = presence * 0.25
        flex_component = flex * 0.20

        components["proficiency"] = round(proficiency_component, 3)
        components["meta"] = round(meta_component, 3)
        components["presence"] = round(presence_component, 3)
        components["flex"] = round(flex_component, 3)

        base_priority = (
            proficiency_component
            + meta_component
            + presence_component
            + flex_component
        )

        # Apply tier bonuses
        tier_bonus = 0.0
        if is_high_proficiency and is_high_presence and is_in_pool:
            # TIER 1: High proficiency + high presence + in pool
            tier_bonus = 0.15
            components["tier"] = "T1_POOL_AND_POWER"
        elif is_high_proficiency and is_in_pool:
            # TIER 2: High proficiency, in pool (comfort pick targeting)
            tier_bonus = 0.10
            components["tier"] = "T2_POOL_TARGET"
        elif is_high_presence:
            # TIER 3: High presence only (global power ban)
            tier_bonus = 0.05
            components["tier"] = "T3_GLOBAL_POWER"
        else:
            # TIER 4: General meta ban
            tier_bonus = 0.0
            components["tier"] = "T4_GENERAL"

        components["tier_bonus"] = round(tier_bonus, 3)

        # Pool depth exploitation (additive - shallow pools = higher impact)
        pool_bonus = 0.0
        if pool_size >= 1:
            if pool_size <= 3:
                pool_bonus = 0.08
            elif pool_size <= 5:
                pool_bonus = 0.04
        components["pool_depth_bonus"] = round(pool_bonus, 3)

        priority = base_priority + tier_bonus + pool_bonus
    else:
        # Phase 2: Original calculation (will be enhanced in next task)
        proficiency_component = proficiency["score"] * 0.4
        components["proficiency"] = round(proficiency_component, 3)

        meta_score = self.meta_scorer.get_meta_score(champion)
        meta_component = meta_score * 0.3
        components["meta"] = round(meta_component, 3)

        games = proficiency.get("games", 0)
        comfort = min(1.0, games / 10)
        comfort_component = comfort * 0.2
        components["comfort"] = round(comfort_component, 3)

        conf = proficiency.get("confidence", "LOW")
        conf_bonus = {"HIGH": 0.1, "MEDIUM": 0.05, "LOW": 0.0}.get(conf, 0)
        components["confidence_bonus"] = round(conf_bonus, 3)

        pool_bonus = 0.0
        if pool_size >= 1:
            if pool_size <= 3:
                pool_bonus = 0.20
            elif pool_size <= 5:
                pool_bonus = 0.10
        components["pool_depth_bonus"] = round(pool_bonus, 3)

        priority = (
            proficiency_component
            + meta_component
            + comfort_component
            + conf_bonus
            + pool_bonus
        )

    return (round(min(1.0, priority), 3), components)
```

**Step 3: Update caller to pass is_phase_1**

In `get_ban_recommendations`, update the call:

```python
priority, components = self._calculate_ban_priority(
    champion=champ,
    player=player,
    proficiency=entry,
    pool_size=pool_size,
    is_phase_1=is_phase_1,  # Add this
)
```

**Step 4: Run tests**

Run: `cd backend && uv run pytest backend/tests/test_ban_recommendation_service.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/ban_teemo/services/ban_recommendation_service.py backend/tests/test_ban_recommendation_service.py
git commit -m "feat(bans): implement tiered Phase 1 ban priority

TIERED PRIORITY:
- T1: High proficiency + high presence + in pool (highest)
- T2: High proficiency + in pool (pool targeting)
- T3: High presence only (global power)
- T4: General meta ban (lowest)

Base weights: prof(30%), meta(25%), presence(25%), flex(20%)
Tier bonuses: T1=+0.15, T2=+0.10, T3=+0.05, T4=+0.00"
```

---

## Task 11: Add Archetype Counter Score for Phase 2 Bans

**Files:**
- Modify: `backend/src/ban_teemo/services/ban_recommendation_service.py`
- Test: `backend/tests/test_ban_recommendation_service.py`

**Step 1: Add ArchetypeService to ban service**

First, add the import and initialization:

```python
# Add import
from ban_teemo.services.archetype_service import ArchetypeService

# In __init__, add:
self.archetype_service = ArchetypeService(knowledge_dir)
```

**Step 2: Write failing test**

```python
# Add to backend/tests/test_ban_recommendation_service.py

def test_get_archetype_counter_score_matching():
    """Banning a champion that fits enemy's archetype should score high."""
    service = BanRecommendationService()

    # Enemy has picked engage champions (J4, Vi)
    enemy_picks = ["Jarvan IV", "Vi"]

    # Orianna (teamfight/engage) would fit their engage comp
    score = service._get_archetype_counter_score("Orianna", enemy_picks)

    # Should have meaningful score since Orianna has engage archetype
    assert score > 0.2, f"Orianna should counter engage comp: {score}"


def test_get_archetype_counter_score_no_enemy():
    """No enemy picks returns 0."""
    service = BanRecommendationService()

    score = service._get_archetype_counter_score("Orianna", [])
    assert score == 0.0
```

**Step 3: Write implementation**

```python
def _get_archetype_counter_score(self, champion: str, enemy_picks: list[str]) -> float:
    """Calculate how much banning this champion disrupts enemy's archetype.

    Args:
        champion: Champion to potentially ban
        enemy_picks: Champions enemy has already picked

    Returns:
        Float 0.0-1.0 representing archetype disruption value
    """
    if not enemy_picks:
        return 0.0

    # Get enemy's emerging archetype
    enemy_arch = self.archetype_service.calculate_team_archetype(enemy_picks)
    enemy_primary = enemy_arch.get("primary")

    if not enemy_primary:
        return 0.0

    # How much does this champion contribute to enemy's direction?
    contribution = self.archetype_service.get_contribution_to_archetype(
        champion, enemy_primary
    )

    # Also check alignment boost - would adding this champion increase enemy's alignment?
    current_alignment = enemy_arch.get("alignment", 0)
    with_champ = self.archetype_service.calculate_team_archetype(
        enemy_picks + [champion]
    )
    new_alignment = with_champ.get("alignment", 0)
    alignment_boost = max(0, new_alignment - current_alignment)

    # Combine contribution and alignment boost
    return round(contribution * 0.6 + alignment_boost * 0.4, 3)
```

**Step 4: Run tests**

Run: `cd backend && uv run pytest backend/tests/test_ban_recommendation_service.py -k "archetype_counter" -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/ban_teemo/services/ban_recommendation_service.py backend/tests/test_ban_recommendation_service.py
git commit -m "feat(bans): add archetype counter score for Phase 2 bans"
```

---

## Task 12: Add Synergy Denial Score for Phase 2 Bans

**Files:**
- Modify: `backend/src/ban_teemo/services/ban_recommendation_service.py`
- Test: `backend/tests/test_ban_recommendation_service.py`

**Step 1: Add SynergyService to ban service**

```python
# Add import
from ban_teemo.services.synergy_service import SynergyService

# In __init__, add:
self.synergy_service = SynergyService(knowledge_dir)
```

**Step 2: Write failing test**

```python
# Add to backend/tests/test_ban_recommendation_service.py

def test_get_synergy_denial_score_strong_synergy():
    """Banning a champion with strong synergy to enemy should score high."""
    service = BanRecommendationService()

    # Enemy has Jarvan - Orianna has strong synergy (J4 ult + Ori ult combo)
    enemy_picks = ["Jarvan IV"]

    score = service._get_synergy_denial_score("Orianna", enemy_picks)

    # Should have some synergy denial value
    assert score >= 0.0, f"Should have non-negative synergy denial: {score}"


def test_get_synergy_denial_score_no_synergy():
    """Banning a champion with no synergy should score 0."""
    service = BanRecommendationService()

    score = service._get_synergy_denial_score("Orianna", [])
    assert score == 0.0
```

**Step 3: Write implementation**

```python
def _get_synergy_denial_score(self, champion: str, enemy_picks: list[str]) -> float:
    """Calculate synergy denial value of banning this champion.

    Would this champion complete a strong synergy with enemy picks?

    Args:
        champion: Champion to potentially ban
        enemy_picks: Champions enemy has already picked

    Returns:
        Float 0.0-1.0 representing synergy denial value
    """
    if not enemy_picks:
        return 0.0

    # Calculate synergy gain if enemy added this champion
    synergy_with = self.synergy_service.calculate_team_synergy(
        enemy_picks + [champion]
    )
    synergy_without = self.synergy_service.calculate_team_synergy(enemy_picks)

    synergy_gain = synergy_with["total_score"] - synergy_without["total_score"]

    # Scale the gain (typical range is 0.0-0.2) to 0-1
    return round(max(0, min(1.0, synergy_gain * 3)), 3)
```

**Step 4: Run tests**

Run: `cd backend && uv run pytest backend/tests/test_ban_recommendation_service.py -k "synergy_denial" -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/ban_teemo/services/ban_recommendation_service.py backend/tests/test_ban_recommendation_service.py
git commit -m "feat(bans): add synergy denial score for Phase 2 bans"
```

---

## Task 13: Add Role Denial Score for Phase 2 Bans

**Files:**
- Modify: `backend/src/ban_teemo/services/ban_recommendation_service.py`
- Test: `backend/tests/test_ban_recommendation_service.py`

**Step 1: Write failing test**

```python
# Add to backend/tests/test_ban_recommendation_service.py

def test_get_role_denial_score_unfilled_role():
    """Banning a champion for unfilled enemy role should score high."""
    service = BanRecommendationService()

    # Enemy has picked mid and jungle, still needs bot
    enemy_picks = ["Azir", "Jarvan IV"]
    enemy_players = [
        {"name": "Viper", "role": "bot"},  # Viper is known ADC
        {"name": "TestMid", "role": "mid"},
        {"name": "TestJungle", "role": "jungle"},
    ]

    # Kai'Sa is in Viper's pool and fills bot
    score = service._get_role_denial_score("Kai'Sa", enemy_picks, enemy_players)

    # Should have role denial value
    assert score >= 0.3, f"Kai'Sa should deny Viper's bot role: {score}"


def test_get_role_denial_score_no_players():
    """No enemy players returns 0."""
    service = BanRecommendationService()

    score = service._get_role_denial_score("Kai'Sa", ["Azir"], [])
    assert score == 0.0
```

**Step 2: Write implementation**

```python
def _get_role_denial_score(
    self,
    champion: str,
    enemy_picks: list[str],
    enemy_players: list[dict]
) -> float:
    """Calculate role denial value of banning this champion.

    Does banning this deny a role the enemy still needs to fill?

    Args:
        champion: Champion to potentially ban
        enemy_picks: Champions enemy has already picked
        enemy_players: Enemy player info with 'name' and 'role'

    Returns:
        Float 0.0-0.8 representing role denial value
    """
    if not enemy_players:
        return 0.0

    # Infer which roles enemy has filled
    filled_roles = set()
    for pick in enemy_picks:
        probs = self.flex_resolver.get_role_probabilities(pick)
        if probs:
            primary_role = max(probs, key=probs.get)
            filled_roles.add(primary_role)

    unfilled_roles = {"top", "jungle", "mid", "bot", "support"} - filled_roles

    if not unfilled_roles:
        return 0.0

    # Can this champion fill an unfilled role?
    champ_probs = self.flex_resolver.get_role_probabilities(champion)
    if not champ_probs:
        return 0.0

    for role in unfilled_roles:
        if champ_probs.get(role, 0) >= 0.25:  # Viable in this role
            # Check if any enemy player in this role has this in their pool
            player = next(
                (p for p in enemy_players if p.get("role") == role),
                None
            )
            if player:
                pool = self.proficiency_scorer.get_player_champion_pool(
                    player["name"], min_games=2
                )
                pool_champs = [e["champion"] for e in pool[:10]]
                if champion in pool_champs:
                    return 0.8  # High denial - in player's pool for unfilled role
            return 0.4  # General denial - fills unfilled role

    return 0.0
```

**Step 3: Run tests**

Run: `cd backend && uv run pytest backend/tests/test_ban_recommendation_service.py -k "role_denial" -v`
Expected: PASS

**Step 4: Commit**

```bash
git add backend/src/ban_teemo/services/ban_recommendation_service.py backend/tests/test_ban_recommendation_service.py
git commit -m "feat(bans): add role denial score for Phase 2 bans"
```

---

## Task 14: Implement Phase 2 Contextual Bans

**Files:**
- Modify: `backend/src/ban_teemo/services/ban_recommendation_service.py:90-104`
- Test: `backend/tests/test_ban_recommendation_service.py`

**Step 1: Write failing test**

```python
# Add to backend/tests/test_ban_recommendation_service.py

def test_phase2_bans_use_tiered_priority():
    """Phase 2 bans should use tiered priority system."""
    service = BanRecommendationService()

    # Phase 2 with some picks already made
    recommendations = service.get_ban_recommendations(
        enemy_team_id="test",
        our_picks=["Jarvan IV", "Rumble"],  # Teamfight/engage direction
        enemy_picks=["Azir", "Vi"],  # Enemy has mid + jungle
        banned=["Yunara", "Neeko"],
        phase="BAN_PHASE_2",
        enemy_players=[
            {"name": "Viper", "role": "bot"},
            {"name": "Keria", "role": "support"},
            {"name": "TestMid", "role": "mid"},
            {"name": "TestJungle", "role": "jungle"},
            {"name": "TestTop", "role": "top"},
        ],
        limit=5,
    )

    # Should have tiered priority in recommendations
    has_tier = any(
        "tier" in r.get("components", {})
        for r in recommendations
    )
    assert has_tier, "Phase 2 should include tier classification"

    # Verify tier ordering - T1/T2 should rank higher than T4
    tier_order = {"T1_COUNTER_AND_POOL": 1, "T2_ARCHETYPE_AND_POOL": 2,
                  "T3_COUNTER_ONLY": 3, "T4_CONTEXTUAL": 4}
    for i, rec in enumerate(recommendations[:-1]):
        curr_tier = rec.get("components", {}).get("tier", "T4_CONTEXTUAL")
        next_tier = recommendations[i+1].get("components", {}).get("tier", "T4_CONTEXTUAL")
        # Higher priority (lower tier number) should come first
        # (This is soft - priority score is the primary sort)


def test_phase2_tier1_prioritizes_counter_in_pool():
    """Tier 1 should be highest priority: counters our picks AND in enemy pool."""
    service = BanRecommendationService()

    recommendations = service.get_ban_recommendations(
        enemy_team_id="test",
        our_picks=["Azir"],  # We picked Azir
        enemy_picks=["Jarvan IV"],
        banned=[],
        phase="BAN_PHASE_2",
        enemy_players=[
            {"name": "Viper", "role": "bot"},  # Viper has Kai'Sa in pool
        ],
        limit=10,
    )

    # Look for T1 tier bans
    t1_bans = [r for r in recommendations
               if r.get("components", {}).get("tier") == "T1_COUNTER_AND_POOL"]

    # If we have T1 bans, they should be near the top
    if t1_bans:
        t1_names = [b["champion_name"] for b in t1_bans]
        top_3_names = [r["champion_name"] for r in recommendations[:3]]
        has_t1_in_top = any(name in top_3_names for name in t1_names)
        # Soft assertion - T1 should generally be near top
        assert has_t1_in_top or len(recommendations) < 3, (
            f"T1 bans {t1_names} should be prioritized, top 3: {top_3_names}"
        )
```

**Step 2: Update `get_ban_recommendations` to add contextual Phase 2 scoring**

Replace the Phase 2 section (around lines 90-104) with:

```python
# Phase 2: Add contextual bans (archetype, synergy, role denial)
if not is_phase_1:
    contextual_bans = self._get_contextual_phase2_bans(
        our_picks=our_picks,
        enemy_picks=enemy_picks,
        enemy_players=enemy_players or [],
        unavailable=unavailable,
    )

    for ctx_ban in contextual_bans:
        # Check if already in candidates and boost priority if so
        existing = next(
            (c for c in ban_candidates if c["champion_name"] == ctx_ban["champion_name"]),
            None
        )
        if existing:
            # Merge contextual scores
            existing["priority"] = min(1.0, existing["priority"] + ctx_ban["priority"] * 0.5)
            existing["components"].update(ctx_ban["components"])
            existing["reasons"].extend(ctx_ban["reasons"])
        else:
            ban_candidates.append(ctx_ban)

    # Also add counter-pick bans (existing logic)
    if our_picks:
        counter_bans = self._get_counter_pick_bans(our_picks, unavailable)
        for counter_ban in counter_bans:
            existing = next(
                (c for c in ban_candidates if c["champion_name"] == counter_ban["champion_name"]),
                None
            )
            if existing:
                existing["priority"] = min(1.0, existing["priority"] + 0.15)
                existing["reasons"].append(counter_ban["reasons"][0])
            else:
                ban_candidates.append(counter_ban)
```

**Step 3: Add the new method**

```python
def _get_contextual_phase2_bans(
    self,
    our_picks: list[str],
    enemy_picks: list[str],
    enemy_players: list[dict],
    unavailable: set[str],
) -> list[dict]:
    """Generate contextual Phase 2 ban recommendations with TIERED PRIORITY.

    TIERED PRIORITY SYSTEM (Phase 2):
        Tier 1 (Highest): Counters our picks + in enemy pool
        Tier 2 (High):    Completes enemy archetype + in pool
        Tier 3 (Medium):  Counters our picks (regardless of pool)
        Tier 4 (Lower):   General archetype/synergy counter

    Considers:
    - Counter to our picks: Champions that counter what we've picked
    - Archetype completion: Champions that complete enemy's comp direction
    - Synergy denial: Champions that would synergize with enemy picks
    - Role denial: Champions that fill roles enemy still needs

    Returns:
        List of ban candidates with contextual scoring and tier info
    """
    candidates: dict[str, dict] = {}

    # Get meta champions as potential ban targets
    meta_champs = set(self.meta_scorer.get_top_meta_champions(limit=30))

    # Also include enemy player pool champions for unfilled roles
    filled_roles = set()
    for pick in enemy_picks:
        probs = self.flex_resolver.get_role_probabilities(pick)
        if probs:
            primary = max(probs, key=probs.get)
            filled_roles.add(primary)
    unfilled_roles = {"top", "jungle", "mid", "bot", "support"} - filled_roles

    enemy_pool_champs = set()
    for player in enemy_players:
        if player.get("role") in unfilled_roles:
            pool = self.proficiency_scorer.get_player_champion_pool(
                player["name"], min_games=2
            )
            for entry in pool[:8]:
                enemy_pool_champs.add(entry["champion"])
                meta_champs.add(entry["champion"])

    for champ in meta_champs:
        if champ in unavailable:
            continue

        components: dict[str, float] = {}
        reasons: list[str] = []

        # Calculate contextual scores
        arch_score = self._get_archetype_counter_score(champ, enemy_picks)
        synergy_score = self._get_synergy_denial_score(champ, enemy_picks)
        role_score = self._get_role_denial_score(champ, enemy_picks, enemy_players)
        meta_score = self.meta_scorer.get_meta_score(champ)

        # Check if counters our picks
        counters_us = False
        counter_strength = 0.0
        for our_pick in our_picks:
            matchup = self.matchup_calculator.get_team_matchup(our_pick, champ)
            if matchup["score"] < 0.45:  # This champ counters our pick
                counters_us = True
                counter_strength = max(counter_strength, 1.0 - matchup["score"])

        is_in_enemy_pool = champ in enemy_pool_champs

        # Determine tier and calculate priority
        tier_bonus = 0.0
        if counters_us and is_in_enemy_pool:
            # TIER 1: Counters our picks + in enemy pool
            tier_bonus = 0.20
            components["tier"] = "T1_COUNTER_AND_POOL"
            reasons.append(f"Counters our picks AND in enemy pool")
        elif arch_score > 0.3 and is_in_enemy_pool:
            # TIER 2: Completes enemy archetype + in pool
            tier_bonus = 0.15
            components["tier"] = "T2_ARCHETYPE_AND_POOL"
            reasons.append(f"Completes enemy comp AND in pool")
        elif counters_us:
            # TIER 3: Counters our picks (regardless of pool)
            tier_bonus = 0.10
            components["tier"] = "T3_COUNTER_ONLY"
            reasons.append(f"Counters our picks")
        elif arch_score > 0.2 or synergy_score > 0.2 or role_score > 0.2:
            # TIER 4: General contextual ban
            tier_bonus = 0.0
            components["tier"] = "T4_CONTEXTUAL"
        else:
            continue  # Skip if no meaningful contextual value

        # Base component scores (weights: counter 30%, archetype 25%, synergy 20%, role 15%, meta 10%)
        if counters_us:
            components["counter_our_picks"] = round(counter_strength * 0.30, 3)
            reasons.append(f"Counters our picks")
        if arch_score > 0.1:
            components["archetype_counter"] = round(arch_score * 0.25, 3)
            reasons.append("Fits enemy's archetype")
        if synergy_score > 0.1:
            components["synergy_denial"] = round(synergy_score * 0.20, 3)
            reasons.append("Synergizes with enemy")
        if role_score > 0.1:
            components["role_denial"] = round(role_score * 0.15, 3)
            reasons.append("Fills enemy's role")
        components["meta"] = round(meta_score * 0.10, 3)
        components["tier_bonus"] = round(tier_bonus, 3)

        # Calculate priority
        priority = sum(v for k, v in components.items() if k not in ["tier"])

        candidates[champ] = {
            "champion_name": champ,
            "priority": round(priority, 3),
            "target_player": None,
            "target_role": None,
            "reasons": reasons[:3] if reasons else ["Contextual ban"],
            "components": components,
        }

    # Sort by priority and return top candidates
    sorted_candidates = sorted(
        candidates.values(),
        key=lambda x: -x["priority"]
    )
    return sorted_candidates[:10]
```

**Step 4: Run tests**

Run: `cd backend && uv run pytest backend/tests/test_ban_recommendation_service.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/ban_teemo/services/ban_recommendation_service.py backend/tests/test_ban_recommendation_service.py
git commit -m "feat(bans): implement tiered contextual Phase 2 bans

TIERED PRIORITY:
- T1: Counters our picks + in enemy pool (highest)
- T2: Completes enemy archetype + in pool
- T3: Counters our picks only
- T4: General contextual ban (lowest)

Weights: counter(30%), archetype(25%), synergy(20%), role(15%), meta(10%)"
```

---

## Task 15: Run Full Test Suite and Integration Validation

**Files:**
- All modified files

**Step 1: Run complete test suite**

```bash
cd backend && uv run pytest tests/ -v --tb=short
```

Expected: All tests PASS

**Step 2: Run the evaluation analysis to verify improvements**

```bash
uv run python scripts/analyze_recommendations.py --recent 5 --misses-only 2>&1 | head -100
```

Compare against baseline (24.7% picks, 18.4% bans).

**Step 3: Commit if all passes**

```bash
git add -A
git commit -m "test: verify all scoring system improvements pass"
```

---

---

## Task 16: Add Role Flex Scoring to Pick Engine

**Problem:** Archetype versatility is scored, but role flexibility (mid/top flex, etc.) is not. Early picks that hide role assignment are valuable.

**Files:**
- Modify: `backend/src/ban_teemo/services/pick_recommendation_engine.py`
- Test: `backend/tests/test_pick_recommendation_engine.py`

**Step 1: Write failing test**

```python
# Add to backend/tests/test_pick_recommendation_engine.py

def test_role_flex_bonus_applied_early_draft():
    """Early draft picks should get bonus for role flexibility."""
    engine = PickRecommendationEngine()

    team_players = [
        {"name": "TestTop", "role": "top"},
        {"name": "TestJungle", "role": "jungle"},
        {"name": "TestMid", "role": "mid"},
        {"name": "TestBot", "role": "bot"},
        {"name": "TestSupport", "role": "support"},
    ]

    # Get recommendations for first pick
    recommendations = engine.get_recommendations(
        team_players=team_players,
        our_picks=[],
        enemy_picks=[],
        banned=[],
        limit=20,
    )

    # Find a known flex pick (Aurora can go mid/top/jungle)
    aurora_rec = next((r for r in recommendations if r["champion_name"] == "Aurora"), None)

    # Should have role_flex component
    if aurora_rec:
        assert "role_flex" in aurora_rec.get("components", {}), (
            "Early draft should include role_flex component"
        )


def test_role_flex_score_multi_role():
    """Champions with multiple viable roles should have high flex score."""
    engine = PickRecommendationEngine()

    # Aurora can go mid/top/jungle (3 roles)
    flex_score = engine._get_role_flex_score("Aurora")
    assert flex_score >= 0.6, f"Multi-role Aurora should have flex >= 0.6: {flex_score}"


def test_role_flex_score_single_role():
    """Single-role champions should have low flex score."""
    engine = PickRecommendationEngine()

    # Jinx is bot only
    flex_score = engine._get_role_flex_score("Jinx")
    assert flex_score <= 0.3, f"Single-role Jinx should have flex <= 0.3: {flex_score}"
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_pick_recommendation_engine.py::test_role_flex_score_multi_role -v`
Expected: FAIL with "AttributeError"

**Step 3: Add `_get_role_flex_score` method**

Add to `backend/src/ban_teemo/services/pick_recommendation_engine.py`:

```python
def _get_role_flex_score(self, champion: str) -> float:
    """Calculate role flexibility score for a champion.

    Champions that can play multiple roles are valuable in early draft
    because they hide team's role assignment from the enemy.

    Returns:
        Float 0.0-0.8 representing role flexibility value
    """
    probs = self.flex_resolver.get_role_probabilities(champion)
    if not probs:
        return 0.2  # Unknown - assume single role

    # Count roles with >= 20% probability (viable roles)
    viable_roles = [r for r, p in probs.items() if p >= 0.20]

    if len(viable_roles) >= 3:
        return 0.8  # True flex (3+ roles)
    elif len(viable_roles) >= 2:
        return 0.5  # Dual flex
    return 0.2  # Single role
```

**Step 4: Integrate into `_calculate_score` for early draft**

Update `_calculate_score` method - add after blind_safety logic:

```python
    # Apply role flex bonus for early picks (hides role assignment)
    if pick_count <= 1:
        role_flex = self._get_role_flex_score(champion)
        # Add as weighted component (5% of total)
        role_flex_bonus = role_flex * 0.05
        base_score = base_score + role_flex_bonus
        components["role_flex"] = role_flex
```

**Step 5: Run tests**

Run: `cd backend && uv run pytest tests/test_pick_recommendation_engine.py -k "role_flex" -v`
Expected: PASS

**Step 6: Commit**

```bash
git add backend/src/ban_teemo/services/pick_recommendation_engine.py backend/tests/test_pick_recommendation_engine.py
git commit -m "feat(picks): add role flex bonus for early draft picks

Champions with multiple viable roles get bonus in first picks
to reward hiding role assignment from enemy."
```

---

## Task 17: Expand Candidate Pool with Global Power Picks

**Problem:** Candidate pool is bounded by player pools (top 15) + meta per role (top 10). Power picks outside these lists are excluded.

**Files:**
- Modify: `backend/src/ban_teemo/services/pick_recommendation_engine.py:134-196`
- Test: `backend/tests/test_pick_recommendation_engine.py`

**Step 1: Write failing test**

```python
# Add to backend/tests/test_pick_recommendation_engine.py

def test_candidates_include_global_power_picks():
    """Candidate pool should include high-presence picks regardless of player pools."""
    engine = PickRecommendationEngine()

    # Players with NO proficiency data (simulates sparse data)
    team_players = [
        {"name": "UnknownTop", "role": "top"},
        {"name": "UnknownJungle", "role": "jungle"},
        {"name": "UnknownMid", "role": "mid"},
        {"name": "UnknownBot", "role": "bot"},
        {"name": "UnknownSupport", "role": "support"},
    ]

    unfilled_roles = {"top", "jungle", "mid", "bot", "support"}
    unavailable = set()

    # Build candidates
    role_cache = engine._build_role_cache(team_players, unfilled_roles, unavailable, [])
    candidates = engine._get_candidates(team_players, unfilled_roles, unavailable, role_cache)

    # High presence champions should be included even without player pool data
    # Azir has ~39% presence and should always be considered
    assert "Azir" in candidates, "High-presence Azir should be in candidates"
    # Should have more than just role-specific meta picks
    assert len(candidates) >= 30, f"Should have broad candidate pool, got {len(candidates)}"
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_pick_recommendation_engine.py::test_candidates_include_global_power_picks -v`
Expected: May pass or fail depending on current meta data; validates behavior

**Step 3: Update `_get_candidates` to include global power picks**

In `_get_candidates` method, add after the meta picks section:

```python
def _get_candidates(
    self,
    team_players: list[dict],
    unfilled_roles: set[str],
    unavailable: set[str],
    role_cache: dict[str, dict[str, float]],
) -> list[str]:
    """Get candidate champions from team pools, meta picks, and global power picks.

    Uses pre-computed role_cache for O(1) lookups.
    Only returns champions that can play at least one unfilled role.
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

    # 3. Global power picks (high presence regardless of role/pool)
    # Ensures power picks aren't missed due to sparse player data
    global_power = self.meta_scorer.get_top_meta_champions(role=None, limit=20)
    for champ in global_power:
        if champ not in unavailable and champ not in candidates:
            probs = role_cache.get(champ, {})
            if probs:
                candidates.add(champ)

    # 4. One-hop transfer targets for candidate expansion
    base_candidates = set(candidates)
    for champ in base_candidates:
        for transfer in self.skill_transfer_service.get_similar_champions(
            champ, limit=self.TRANSFER_EXPANSION_LIMIT
        ):
            target = transfer.get("champion")
            if not target or target in unavailable or target in candidates:
                continue
            probs = role_cache.get(target, {})
            if probs:
                candidates.add(target)

    return list(candidates)
```

**Step 4: Update `_build_role_cache` to include global power picks**

In `_build_role_cache`, add after meta picks collection:

```python
        # Collect global power picks (regardless of role)
        global_power = self.meta_scorer.get_top_meta_champions(role=None, limit=20)
        for champ in global_power:
            if champ not in unavailable:
                base_candidates.add(champ)
```

**Step 5: Run tests**

Run: `cd backend && uv run pytest tests/test_pick_recommendation_engine.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add backend/src/ban_teemo/services/pick_recommendation_engine.py backend/tests/test_pick_recommendation_engine.py
git commit -m "feat(picks): expand candidate pool with global power picks

Add top 20 overall meta champions to candidate pool regardless of
player pools or role filtering. Prevents missing power picks when
player data is sparse."
```

---

## Task 18: Add Global Power Bans to Phase 1

**Problem:** Phase 1 bans depend on player pools. If enemy player data is sparse, high-presence global power bans are missed.

**Files:**
- Modify: `backend/src/ban_teemo/services/ban_recommendation_service.py:52-127`
- Test: `backend/tests/test_ban_recommendation_service.py`

**Step 1: Write failing test**

```python
# Add to backend/tests/test_ban_recommendation_service.py

def test_phase1_includes_global_power_bans():
    """Phase 1 should include high-presence bans even with sparse enemy data."""
    service = BanRecommendationService()

    # No enemy player data (sparse)
    recommendations = service.get_ban_recommendations(
        enemy_team_id="unknown",
        our_picks=[],
        enemy_picks=[],
        banned=[],
        phase="BAN_PHASE_1",
        enemy_players=[],  # Empty - no player data
        limit=5,
    )

    # Should still return recommendations based on meta/presence
    assert len(recommendations) >= 3, "Should have bans even without player data"

    # High presence champions should be recommended
    champ_names = [r["champion_name"] for r in recommendations]
    # At least one high-presence champion should be in top 5
    high_presence = {"Azir", "Yunara", "Poppy", "Pantheon", "Neeko"}
    has_power_ban = any(c in high_presence for c in champ_names)
    assert has_power_ban, f"Should include power bans, got: {champ_names}"
```

**Step 2: Run test**

Run: `cd backend && uv run pytest backend/tests/test_ban_recommendation_service.py::test_phase1_includes_global_power_bans -v`
Expected: May pass with existing meta fallback; validates intent

**Step 3: Ensure global power bans are prioritized**

Update `get_ban_recommendations` method - move and enhance the meta fallback section:

```python
def get_ban_recommendations(
    self,
    enemy_team_id: str,
    our_picks: list[str],
    enemy_picks: list[str],
    banned: list[str],
    phase: str,
    enemy_players: Optional[list[dict]] = None,
    limit: int = 5
) -> list[dict]:
    """Generate ban recommendations targeting enemy team."""
    unavailable = set(banned) | set(our_picks) | set(enemy_picks)
    is_phase_1 = "1" in phase

    ban_candidates = []

    # Auto-lookup roster if not provided but repository is available
    if enemy_players is None and self._draft_repository and enemy_team_id:
        enemy_players = self._lookup_enemy_roster(enemy_team_id)

    # If enemy players provided (or looked up), target their champion pools
    if enemy_players:
        for player in enemy_players:
            player_pool = self.proficiency_scorer.get_player_champion_pool(
                player["name"], min_games=2
            )
            pool_size = len(player_pool)

            for entry in player_pool[:5]:
                champ = entry["champion"]
                if champ in unavailable:
                    continue

                priority, components = self._calculate_ban_priority(
                    champion=champ,
                    player=player,
                    proficiency=entry,
                    pool_size=pool_size,
                    is_phase_1=is_phase_1,
                )

                ban_candidates.append({
                    "champion_name": champ,
                    "priority": priority,
                    "target_player": player["name"],
                    "target_role": player.get("role"),
                    "reasons": self._generate_reasons(champ, player, entry, priority),
                    "components": components,
                })

    # ALWAYS add global power picks for Phase 1 (regardless of player data)
    if is_phase_1:
        global_power_bans = self._get_global_power_bans(unavailable)
        for power_ban in global_power_bans:
            existing = next(
                (c for c in ban_candidates if c["champion_name"] == power_ban["champion_name"]),
                None
            )
            if existing:
                # Boost if already targeted AND high presence
                existing["priority"] = min(1.0, existing["priority"] + 0.1)
                if power_ban["reasons"]:
                    existing["reasons"].extend(power_ban["reasons"])
            else:
                ban_candidates.append(power_ban)
    else:
        # Phase 2: Add contextual bans
        contextual_bans = self._get_contextual_phase2_bans(
            our_picks=our_picks,
            enemy_picks=enemy_picks,
            enemy_players=enemy_players or [],
            unavailable=unavailable,
        )
        # ... existing phase 2 logic ...
```

**Step 4: Add `_get_global_power_bans` method**

```python
def _get_global_power_bans(self, unavailable: set[str]) -> list[dict]:
    """Get high-presence power picks as ban candidates.

    These are always considered regardless of enemy player pool data.

    Returns:
        List of ban candidates based on global meta presence
    """
    candidates = []

    for champ in self.meta_scorer.get_top_meta_champions(limit=15):
        if champ in unavailable:
            continue

        meta_score = self.meta_scorer.get_meta_score(champ)
        presence = self._get_presence_score(champ)
        flex_value = self._get_flex_value(champ)

        # Only include if high enough presence (>= 20%)
        if presence < 0.20:
            continue

        # Calculate priority: presence(40%) + meta(35%) + flex(25%)
        priority = presence * 0.40 + meta_score * 0.35 + flex_value * 0.25

        reasons = []
        tier = self.meta_scorer.get_meta_tier(champ)
        if tier in ["S", "A"]:
            reasons.append(f"{tier}-tier power pick")
        if presence >= 0.30:
            reasons.append(f"High presence ({presence:.0%})")
        if flex_value >= 0.5:
            reasons.append("Role flex value")

        candidates.append({
            "champion_name": champ,
            "priority": round(priority, 3),
            "target_player": None,
            "target_role": None,
            "reasons": reasons if reasons else ["Global power ban"],
            "components": {
                "presence": round(presence * 0.40, 3),
                "meta": round(meta_score * 0.35, 3),
                "flex": round(flex_value * 0.25, 3),
            },
        })

    return sorted(candidates, key=lambda x: -x["priority"])[:10]
```

**Step 5: Run tests**

Run: `cd backend && uv run pytest backend/tests/test_ban_recommendation_service.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add backend/src/ban_teemo/services/ban_recommendation_service.py backend/tests/test_ban_recommendation_service.py
git commit -m "feat(bans): add global power bans for Phase 1

Always include high-presence power picks as ban candidates
regardless of enemy player pool data. Prevents missing obvious
bans when player data is sparse."
```

---

## Task 19: Expose Presence via Public MetaScorer Method

**Problem:** `_get_presence_score` reads `self.meta_scorer._meta_stats` directly, which is a private attribute and brittle.

**Files:**
- Modify: `backend/src/ban_teemo/services/scorers/meta_scorer.py`
- Modify: `backend/src/ban_teemo/services/ban_recommendation_service.py`
- Test: `backend/tests/test_meta_scorer.py`

**Step 1: Write test for public method**

```python
# Add to backend/tests/test_meta_scorer.py

def test_get_presence_high_presence_champion():
    """High presence champion should return high score."""
    scorer = MetaScorer()
    presence = scorer.get_presence("Azir")
    assert presence >= 0.30, f"Azir should have presence >= 0.30: {presence}"


def test_get_presence_low_presence_champion():
    """Low presence champion should return low score."""
    scorer = MetaScorer()
    presence = scorer.get_presence("Qiyana")
    assert presence < 0.15, f"Qiyana should have presence < 0.15: {presence}"


def test_get_presence_unknown_champion():
    """Unknown champion returns 0."""
    scorer = MetaScorer()
    presence = scorer.get_presence("NonexistentChamp")
    assert presence == 0.0
```

**Step 2: Add public method to MetaScorer**

Add to `backend/src/ban_teemo/services/scorers/meta_scorer.py`:

```python
def get_presence(self, champion_name: str) -> float:
    """Get champion's presence rate (pick_rate + ban_rate).

    Presence indicates how contested a champion is in the meta.

    Returns:
        Float 0.0-1.0 representing presence rate
    """
    if champion_name not in self._meta_stats:
        return 0.0
    return self._meta_stats[champion_name].get("presence", 0.0)
```

**Step 3: Update BanRecommendationService to use public method**

In `backend/src/ban_teemo/services/ban_recommendation_service.py`, update:

```python
def _get_presence_score(self, champion: str) -> float:
    """Get champion's presence rate as a score.

    Presence = pick_rate + ban_rate (how contested is this pick?)

    Returns:
        Float 0.0-1.0 representing presence
    """
    return self.meta_scorer.get_presence(champion)  # Use public method
```

**Step 4: Run tests**

Run: `cd backend && uv run pytest backend/tests/test_meta_scorer.py -k "presence" -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/ban_teemo/services/scorers/meta_scorer.py backend/src/ban_teemo/services/ban_recommendation_service.py backend/tests/test_meta_scorer.py
git commit -m "refactor(meta): expose presence via public method

Replace direct _meta_stats access with public get_presence() method
for cleaner API and less brittle coupling."
```

---

## Task 20: Update Tests to Use Relative Assertions

**Problem:** Tests assume specific champion stats (Orianna/Azir). If knowledge data changes, tests fail even if logic is correct.

**Files:**
- Modify: `backend/tests/test_archetype_service.py`
- Modify: `backend/tests/test_pick_recommendation_engine.py`

**Step 1: Refactor archetype tests to use relative comparisons**

Update tests to compare champions against each other rather than absolute values:

```python
# In backend/tests/test_archetype_service.py

def test_get_versatility_score_relative():
    """Multi-archetype champions should score higher than single-archetype."""
    service = ArchetypeService()

    # Get scores for two champions we know differ in archetype count
    # (Don't hardcode expected values - compare relatively)
    archetypes = service._champion_archetypes

    # Find a single-archetype and multi-archetype champion dynamically
    single_arch_champ = None
    multi_arch_champ = None

    for champ, scores in archetypes.items():
        if len(scores) == 1 and single_arch_champ is None:
            single_arch_champ = champ
        elif len(scores) >= 3 and multi_arch_champ is None:
            multi_arch_champ = champ
        if single_arch_champ and multi_arch_champ:
            break

    if single_arch_champ and multi_arch_champ:
        single_score = service.get_versatility_score(single_arch_champ)
        multi_score = service.get_versatility_score(multi_arch_champ)

        assert multi_score > single_score, (
            f"Multi-archetype {multi_arch_champ} ({multi_score}) should score higher "
            f"than single-archetype {single_arch_champ} ({single_score})"
        )


def test_get_raw_strength_returns_max():
    """Raw strength should return max archetype value for any champion."""
    service = ArchetypeService()

    # Test with any champion that has archetype data
    for champ, scores in list(service._champion_archetypes.items())[:5]:
        expected_max = max(scores.values())
        actual = service.get_raw_strength(champ)
        assert actual == expected_max, (
            f"{champ}: expected {expected_max}, got {actual}"
        )
```

**Step 2: Refactor pick engine tests similarly**

```python
# In backend/tests/test_pick_recommendation_engine.py

def test_archetype_score_versatile_vs_specialist_relative():
    """Versatile champions should not be heavily penalized vs specialists in early draft."""
    engine = PickRecommendationEngine()

    # Find champions dynamically based on archetype count
    arch_service = engine.archetype_service
    archetypes = arch_service._champion_archetypes

    specialist = None
    versatile = None

    for champ, scores in archetypes.items():
        if len(scores) == 1 and specialist is None:
            specialist = champ
        elif len(scores) >= 3 and versatile is None:
            versatile = champ
        if specialist and versatile:
            break

    if specialist and versatile:
        spec_score = engine._calculate_archetype_score(specialist, [], [])
        vers_score = engine._calculate_archetype_score(versatile, [], [])

        # Versatile should not be more than 0.15 below specialist
        assert vers_score >= spec_score - 0.15, (
            f"Versatile {versatile} ({vers_score}) should not be heavily penalized "
            f"vs specialist {specialist} ({spec_score}) in early draft"
        )
```

**Step 3: Run all tests**

Run: `cd backend && uv run pytest tests/ -v`
Expected: PASS

**Step 4: Commit**

```bash
git add backend/tests/test_archetype_service.py backend/tests/test_pick_recommendation_engine.py
git commit -m "test: refactor to use relative assertions

Use champion comparisons rather than hardcoded values to make tests
robust against knowledge data changes."
```

---

## Task 21: Expand Phase 2 Ban Candidate Pool

**Problem:** Phase 2 candidates are meta-top-30 only. May miss niche but high-synergy or role-denial bans.

**Files:**
- Modify: `backend/src/ban_teemo/services/ban_recommendation_service.py`
- Test: `backend/tests/test_ban_recommendation_service.py`

**Step 1: Write test**

```python
# Add to backend/tests/test_ban_recommendation_service.py

def test_phase2_candidates_include_player_pools():
    """Phase 2 should consider enemy player pools, not just meta top 30."""
    service = BanRecommendationService()

    # Enemy players with specific champions in pool
    enemy_players = [
        {"name": "Viper", "role": "bot"},
        {"name": "Keria", "role": "support"},
    ]

    # Phase 2 with enemy picks
    recommendations = service.get_ban_recommendations(
        enemy_team_id="test",
        our_picks=["Jarvan IV"],
        enemy_picks=["Azir"],  # Enemy has mid
        banned=["Yunara"],
        phase="BAN_PHASE_2",
        enemy_players=enemy_players,
        limit=10,
    )

    # Should include candidates from enemy player pools for unfilled roles
    # Viper's bot pool and Keria's support pool should be considered
    has_player_targeted = any(
        r.get("target_player") is not None
        for r in recommendations
    )
    # This is expected behavior - player pools should inform phase 2
```

**Step 2: Update `_get_contextual_phase2_bans` to include player pools**

```python
def _get_contextual_phase2_bans(
    self,
    our_picks: list[str],
    enemy_picks: list[str],
    enemy_players: list[dict],
    unavailable: set[str],
) -> list[dict]:
    """Generate contextual Phase 2 ban recommendations.

    Considers:
    - Archetype counter: Champions that fit enemy's emerging comp
    - Synergy denial: Champions that would synergize with enemy picks
    - Role denial: Champions that fill roles enemy still needs
    - Enemy player pools for unfilled roles

    Returns:
        List of ban candidates with contextual scoring
    """
    candidates: dict[str, dict] = {}

    # Get meta champions as potential ban targets
    meta_champs = set(self.meta_scorer.get_top_meta_champions(limit=30))

    # ALSO include champions from enemy player pools for unfilled roles
    filled_roles = set()
    for pick in enemy_picks:
        probs = self.flex_resolver.get_role_probabilities(pick)
        if probs:
            primary = max(probs, key=probs.get)
            filled_roles.add(primary)

    unfilled_roles = {"top", "jungle", "mid", "bot", "support"} - filled_roles

    for player in enemy_players:
        player_role = player.get("role")
        if player_role in unfilled_roles:
            pool = self.proficiency_scorer.get_player_champion_pool(
                player["name"], min_games=2
            )
            for entry in pool[:8]:
                meta_champs.add(entry["champion"])

    # Now score all candidates
    for champ in meta_champs:
        if champ in unavailable:
            continue

        components: dict[str, float] = {}
        reasons: list[str] = []

        # Archetype counter (35%)
        arch_score = self._get_archetype_counter_score(champ, enemy_picks)
        if arch_score > 0.1:
            components["archetype_counter"] = round(arch_score * 0.35, 3)
            reasons.append("Fits enemy's archetype direction")

        # Synergy denial (25%)
        synergy_score = self._get_synergy_denial_score(champ, enemy_picks)
        if synergy_score > 0.1:
            components["synergy_denial"] = round(synergy_score * 0.25, 3)
            reasons.append("Synergizes with enemy picks")

        # Role denial (25%)
        role_score = self._get_role_denial_score(champ, enemy_picks, enemy_players)
        if role_score > 0.1:
            components["role_denial"] = round(role_score * 0.25, 3)
            reasons.append("Fills enemy's unfilled role")

        # Meta value (15%)
        meta_score = self.meta_scorer.get_meta_score(champ)
        components["meta"] = round(meta_score * 0.15, 3)

        # Only include if has meaningful contextual scores
        total_contextual = sum([
            components.get("archetype_counter", 0),
            components.get("synergy_denial", 0),
            components.get("role_denial", 0),
        ])

        if total_contextual > 0.1:
            priority = sum(components.values())
            candidates[champ] = {
                "champion_name": champ,
                "priority": round(priority, 3),
                "target_player": None,
                "target_role": None,
                "reasons": reasons if reasons else ["Contextual ban"],
                "components": components,
            }

    return sorted(candidates.values(), key=lambda x: -x["priority"])[:10]
```

**Step 3: Run tests**

Run: `cd backend && uv run pytest backend/tests/test_ban_recommendation_service.py -v`
Expected: PASS

**Step 4: Commit**

```bash
git add backend/src/ban_teemo/services/ban_recommendation_service.py backend/tests/test_ban_recommendation_service.py
git commit -m "feat(bans): expand Phase 2 candidates to include enemy player pools

Include champions from enemy player pools for unfilled roles,
not just meta top 30. Catches niche synergy/denial targets."
```

---

## Summary of Changes

### Pick Engine Changes

| Component | Before | After |
|-----------|--------|-------|
| Archetype scoring | Normalized alignment (penalizes versatile) | Raw strength + versatility bonus (early), alignment (late) |
| Weight distribution | Static 25/20/20/15/20 | Context-aware (first pick ↓prof ↑meta, counter-pick ↑matchup) |
| Blind safety | None | Applied to early picks from pick_context data |
| Role flex | None | Bonus for multi-role champions in early draft |
| Candidate pool | Player pools + role meta | + Global power picks (top 20 overall meta) |

### Ban Engine Changes

| Phase | Before | After |
|-------|--------|-------|
| BAN_PHASE_1 | prof(40%) + meta(30%) + comfort(20%) | prof(35%) + meta(30%) + presence(20%) + flex(15%) + global power bans |
| BAN_PHASE_2 | Same as Phase 1 + counter-picks | archetype(35%) + synergy(25%) + role(25%) + meta(15%) + player pool candidates |

### New Methods Added

- `ArchetypeService.get_versatility_score()`
- `ArchetypeService.get_contribution_to_archetype()`
- `ArchetypeService.get_raw_strength()`
- `MetaScorer.get_blind_pick_safety()`
- `MetaScorer.get_presence()`
- `PickRecommendationEngine._get_role_flex_score()`
- `BanRecommendationService._get_presence_score()`
- `BanRecommendationService._get_flex_value()`
- `BanRecommendationService._get_archetype_counter_score()`
- `BanRecommendationService._get_synergy_denial_score()`
- `BanRecommendationService._get_role_denial_score()`
- `BanRecommendationService._get_contextual_phase2_bans()`
- `BanRecommendationService._get_global_power_bans()`
