# Role-Phase Prior Multiplier Design

## Problem Statement

Poppy is consistently recommended as #1 for both picks and bans across all phases, despite being a support champion that pro teams typically pick late (phase 2). The algorithm treats all roles equally regardless of draft phase, which contradicts empirical pro pick order patterns.

### Evidence from Replay Analysis

- Poppy was #1 recommendation in 17 of 20 actions in replay `087f37e4`
- Actual pick: Poppy was picked 5th (last slot) for blue team
- Support is picked in phase 2 **63% of the time**, only 12% in early phase 1

## Solution: Data-Driven Role-Phase Multiplier

Apply empirical pick order probabilities as a prior multiplier to recommendation scores.

### Empirical Data (3,419 pro games)

| Role | Early P1 (picks 1-3) | Late P1 (picks 4-6) | Phase 2 (picks 7-10) |
|------|---------------------|---------------------|----------------------|
| Support | 8.0% | 16.8% | 32.0% |
| Jungle | 27.3% | 21.5% | 12.6% |
| Mid | 23.8% | 24.9% | 13.8% |
| Bot | 22.7% | 16.4% | 20.7% |
| Top | 18.3% | 20.4% | 21.0% |

### Multiplier Formula

```python
# Penalty-only (cap at 1.0, no boost)
multiplier = min(1.0, empirical_prob / 0.20)
```

**Resulting multipliers:**

| Role | Early P1 | Late P1 | Phase 2 |
|------|----------|---------|---------|
| Support | 0.40x | 0.84x | 1.00x |
| Jungle | 1.00x | 1.00x | 0.63x |
| Mid | 1.00x | 1.00x | 0.69x |
| Bot | 1.00x | 0.82x | 1.00x |
| Top | 0.92x | 1.00x | 1.00x |

## Implementation

### New Files

1. **`knowledge/role_pick_phase.json`** - Empirical pick order distribution
2. **`backend/src/ban_teemo/services/scorers/role_phase_scorer.py`** - New scorer class
3. **`backend/scripts/build_role_pick_phase.py`** - Data pipeline script
4. **`backend/tests/test_role_phase_scorer.py`** - Unit tests

### Modified Files

1. **`backend/src/ban_teemo/services/pick_recommendation_engine.py`**
   - Import `RolePhaseScorer`
   - Apply multiplier in `_calculate_score()` after base score calculation
   - Store in components for transparency

2. **`backend/src/ban_teemo/services/ban_recommendation_service.py`**
   - Import `RolePhaseScorer`
   - Apply `sqrt(multiplier)` in `_calculate_ban_priority()` for softer penalty
   - Only apply when targeting a specific player's role

3. **`backend/src/ban_teemo/services/scorers/__init__.py`**
   - Export `RolePhaseScorer`

### RolePhaseScorer Class

```python
class RolePhaseScorer:
    """Applies role-phase prior multipliers based on pro pick order data."""

    UNIFORM_PROB = 0.20  # 1/5 roles

    def __init__(self, knowledge_dir: Path):
        self._load_distribution(knowledge_dir / "role_pick_phase.json")

    def get_multiplier(self, role: str, total_picks: int) -> float:
        """Get penalty multiplier for role at current draft phase.

        Args:
            role: The role being considered (top, jungle, mid, bot, support)
            total_picks: Total picks made by both teams (0-9)

        Returns:
            Multiplier between 0.4 and 1.0 (penalty-only, no boost)
        """
        phase = self._get_phase(total_picks)
        empirical = self.distribution.get(role, {}).get(phase, self.UNIFORM_PROB)
        return min(1.0, empirical / self.UNIFORM_PROB)

    def _get_phase(self, total_picks: int) -> str:
        if total_picks <= 2:
            return "early_p1"
        elif total_picks <= 5:
            return "late_p1"
        return "p2"
```

### Pick Engine Integration

```python
# In _calculate_score(), after base_score calculation:
role_phase_mult = self.role_phase_scorer.get_multiplier(suggested_role, pick_count)
components["role_phase"] = role_phase_mult

# Apply as final multiplier
total_score = base_score * synergy_multiplier * role_phase_mult
```

### Ban Service Integration

```python
# In _calculate_ban_priority(), for player-targeted bans:
if target_role and is_phase_1:
    pick_mult = self.role_phase_scorer.get_multiplier(target_role, pick_count=0)
    ban_mult = math.sqrt(pick_mult)  # Softer penalty for bans
    priority *= ban_mult
    components["role_phase_penalty"] = round(ban_mult, 3)
```

## Expected Impact

### Poppy Scenario (Before → After)

| Phase | Current Score | Multiplier | New Score | Expected Rank |
|-------|--------------|------------|-----------|---------------|
| Ban Phase 1 (support target) | 0.763 | 0.63 (sqrt) | 0.48 | #3-4 |
| Pick Phase 1 (as support) | 0.666 | 0.40 | 0.27 | #4-5 |
| Pick Phase 2 (as support) | 0.641 | 1.00 | 0.64 | #1 ✓ |

## Edge Cases

| Case | Behavior |
|------|----------|
| Unknown role | Return 1.0 (no penalty) |
| Missing knowledge file | Log warning, return 1.0 |
| Flex champion | Use `suggested_role` from scoring |
| Phase 2 bans | Apply penalty (jungle/mid bans less valuable late) |

## Testing

```python
def test_support_early_p1_penalty():
    mult = scorer.get_multiplier("support", total_picks=0)
    assert 0.35 <= mult <= 0.45

def test_jungle_p2_penalty():
    mult = scorer.get_multiplier("jungle", total_picks=7)
    assert 0.60 <= mult <= 0.70

def test_poppy_not_top_recommendation_phase1():
    recs = engine.get_recommendations(team_players=[...], our_picks=[], ...)
    assert recs[0]["champion_name"] != "Poppy" or recs[0]["suggested_role"] != "support"
```

## Data Pipeline

The `build_role_pick_phase.py` script:
1. Reads `draft_actions.csv` for pick sequence
2. Joins with `player_game_stats.csv` for role
3. Maps sequence → slot → phase
4. Calculates P(role | phase)
5. Writes `role_pick_phase.json`

Regenerate when new tournament data is added or at split boundaries.
