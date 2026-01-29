# Scoring System Root Cause Analysis

**Date:** 2026-01-29
**Status:** Investigation Complete

## Executive Summary

After systematic debugging, I identified **7 root causes** explaining why recommendations don't match actual pro draft decisions and why scores appear uniformly low (~0.5 for many components).

### Critical Issues (Blocking)
1. **Role Assignment Bug** - Champions get suggested for impossible roles
2. **Archetype Not Used** - Team composition style not factored into scoring
3. **Archetype Data Sparse** - Only 10 champions have data

### Medium Issues
4. **Early Draft Score Uniformity** - 40% of score defaults to 0.5
5. **Ban Recommendations Lack Detail** - No component breakdown

### Minor Issues
6. **Meta Data Gaps** - Some champions missing

---

## Detailed Findings

### Issue 1: Role Assignment Bug (CRITICAL)

**Location:** `FlexResolver.get_role_probabilities()` lines 121-126

**Problem:** When a champion's primary role is filled, the fallback gives uniform probability to ALL remaining roles:

```python
# Current broken behavior
# Primary is filled, return uniform over remaining
available = self.VALID_ROLES - filled
if available:
    prob = 1.0 / len(available)
    return {role: prob for role in available}  # BUG: All roles equally likely!
```

**Symptom:** With TOP and JNG filled, Camille (99.7% TOP) gets assigned:
```
{MID: 0.33, ADC: 0.33, SUP: 0.33}  # Absurd!
```

**Impact:** Recommendations include "Camille (SUP)", "Viego (SUP)", "Xin Zhao (SUP)"

**Fix:** Return empty dict for champions that can't play any unfilled role:
```python
# If champion's primary role is filled and they're not flex
if primary_role in filled:
    # Check flex data for actual secondary role probabilities
    # Only return roles where champion has > 10% historical play rate
    return {}  # Don't recommend champions for roles they don't play
```

---

### Issue 2: Archetype Not Used in Scoring (CRITICAL)

**Location:** `PickRecommendationEngine._calculate_score()`

**Current Formula:**
```python
base_score = (
    meta * 0.25 +
    proficiency * 0.35 +
    matchup * 0.25 +
    counter * 0.15
)
total_score = base_score * synergy_multiplier  # synergy only as multiplier
```

**Problem:** `ArchetypeService` exists and calculates team archetype alignment, but it's **never called** in pick recommendations.

**Impact:** Team composition style (engage, split, teamfight, protect, pick) is completely ignored when scoring picks.

**Evidence:** The `ArchetypeService` has methods like:
- `calculate_team_archetype(picks)` - Returns primary archetype and alignment score
- `get_archetype_effectiveness(our, enemy)` - RPS-style matchup
- `calculate_comp_advantage(our_picks, enemy_picks)` - Full advantage calc

None of these are called in `PickRecommendationEngine`.

**Fix:** Add archetype to scoring formula:
```python
# Add archetype alignment as component
archetype_result = self.archetype_service.calculate_team_archetype(our_picks + [champion])
components["archetype"] = archetype_result["alignment"]

# Optionally factor in archetype effectiveness vs enemy
if enemy_picks:
    enemy_arch = self.archetype_service.calculate_team_archetype(enemy_picks)
    effectiveness = self.archetype_service.get_archetype_effectiveness(...)
    components["archetype_advantage"] = effectiveness
```

---

### Issue 3: Sparse Archetype Data (CRITICAL)

**Location:** `knowledge/archetype_counters.json`

**Problem:** Only **10 champions** have archetype data:
```
Malphite, Orianna, Nocturne, Fiora, Lulu, Thresh, Jarvan IV, Jinx, Azir, Camille
```

Out of 162+ champions, this is **6% coverage**.

**Impact:** For 94% of champions:
```python
get_champion_archetypes("Aatrox")  # Returns: {"primary": None, "scores": {}}
```

Team archetype for most compositions is `primary: None`.

**Fix:** Generate archetype data for all champions. Use a rule-based system:
- Tanks with hard CC → engage
- Assassins/divers → pick
- Enchanters → protect
- Splitpushers → split
- AoE mages → teamfight

---

### Issue 4: Early Draft Score Uniformity (MEDIUM)

**Problem:** At draft start:
- `matchup = 0.5` (no enemies to match against)
- `counter = 0.5` (no enemies)
- `synergy = 0.5` (single champion, no pairs)

This means **40% of base score + synergy multiplier** are completely neutral.

**Current Weights:**
```python
BASE_WEIGHTS = {
    "meta": 0.25,      # Can differentiate
    "proficiency": 0.35,  # Can differentiate
    "matchup": 0.25,   # 0.5 at start
    "counter": 0.15    # 0.5 at start
}
```

**Result:** Early recommendations are ~95% driven by proficiency + meta only.

**Evidence from diagnostic:**
```
Out of 20 recommendations (empty draft):
  meta: 3 at 0.5 (15%)
  proficiency: 0 at 0.5 (0%)  ← Only differentiator
  matchup: 20 at 0.5 (100%)   ← ALL default!
  counter: 20 at 0.5 (100%)   ← ALL default!
  synergy: 20 at 0.5 (100%)   ← ALL default!
```

**Fix Options:**
1. **Adjust weights dynamically** based on draft phase
2. **Add pre-draft scoring factors** like power picks, flex value
3. **Weight meta higher** in early picks (first picks are usually meta/priority)

---

### Issue 5: Ban Recommendations Lack Component Breakdown (MEDIUM)

**Location:** `BanRecommendationService`

**Problem:** Ban recommendations only return:
```python
{
    "champion_name": str,
    "priority": float,  # Single number!
    "target_player": str | None,
    "reasons": list[str]
}
```

No breakdown of HOW priority was calculated.

**Pick recommendations have:**
```python
{
    "components": {
        "meta": 0.73,
        "proficiency": 0.87,
        "matchup": 0.5,
        "counter": 0.5,
        "synergy": 0.5
    }
}
```

**Fix:** Add component breakdown to ban recommendations:
```python
{
    "champion_name": str,
    "priority": float,
    "components": {
        "proficiency": float,
        "meta": float,
        "comfort": float,
        "confidence_bonus": float,
        "pool_depth_bonus": float,
        "counter_score": float,  # Phase 2 only
    },
    "target_player": str | None,
    "reasons": list[str]
}
```

---

### Issue 6: Meta Data Gaps (MINOR)

**Location:** `knowledge/meta_stats.json`

**Problem:** 131 champions have meta data. Some notable missing:
- Jinx → defaults to 0.5
- Thresh → defaults to 0.5

**Impact:** Low but affects accuracy for popular champions.

**Fix:** Regenerate meta_stats.json with updated data source.

---

## Scoring Formula Diagnostic

**Test: T1 vs empty draft**

| Champion | Role | Score | Meta | Prof | Match | Counter | Synergy |
|----------|------|-------|------|------|-------|---------|---------|
| Azir | MID | 0.686 | 0.73 | 0.87 | 0.5 | 0.5 | 0.5 |
| Sivir | ADC | 0.649 | 0.56 | 0.89 | 0.5 | 0.5 | 0.5 |
| Camille | TOP | 0.639 | 0.5 | 0.90 | 0.5 | 0.5 | 0.5 |
| Viego | JNG | 0.634 | 0.5 | 0.88 | 0.5 | 0.5 | 0.5 |

**Observation:** Scores are tightly clustered (0.63-0.69) because:
1. Proficiency varies (0.81-0.90) - main differentiator
2. Meta varies some (0.5-0.73)
3. Matchup, counter, synergy ALL at 0.5

---

## Why Recommendations Don't Match Pro Picks

**Hypothesis:** Pro drafters consider factors we don't score:

1. **Draft context** - Hiding flex picks, bait picks, comfort level under pressure
2. **Team identity** - Preferred playstyle, practiced comps
3. **Opponent preparation** - Surprise picks, studied counters
4. **Meta timing** - New patches, undiscovered OPs
5. **Communication** - "We practiced Yasuo-Malphite, pick it"

**Our system lacks:**
- Historical team draft patterns
- Comp archetype coherence (not used!)
- Flex pick value scoring
- Power budget (don't stack all power in one role)

---

## Recommended Fix Priority

### Phase 1: Critical Fixes
1. **Fix role assignment bug** - Stop recommending impossible roles
2. **Integrate archetype scoring** - Add to pick formula
3. **Expand archetype data** - Generate for all champions

### Phase 2: Scoring Improvements
4. **Add ban component breakdown** - Match pick recommendation detail
5. **Phase-aware weighting** - Different weights for early vs late draft
6. **Add flex pick value** - Score champions that hide information

### Phase 3: Data Improvements
7. **Fill meta data gaps** - Regenerate meta_stats.json
8. **Add team pattern data** - Historical draft preferences
9. **Diagnostic logging** - Capture real runs for analysis

---

## Files Modified for Investigation

- Created: `backend/diagnostic_scoring.py` - Diagnostic script
- Created: `backend/src/ban_teemo/services/scoring_logger.py` - Runtime logging

## Files Requiring Changes

### Priority 1 (Bug Fixes)
- `backend/src/ban_teemo/services/scorers/flex_resolver.py` - Fix role fallback
- `backend/src/ban_teemo/services/pick_recommendation_engine.py` - Integrate archetype

### Priority 2 (Enhancements)
- `knowledge/archetype_counters.json` - Expand champion data
- `backend/src/ban_teemo/services/ban_recommendation_service.py` - Add components

### Priority 3 (Frontend)
- `deepdraft/src/components/SimulatorView/index.tsx` - Show ban breakdown
- `deepdraft/src/components/InsightsLog/index.tsx` - Reverse sort order
