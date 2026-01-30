# Proficiency Scoring Data Quality Fix Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

---

## ⚠️ Superseded by Champion Comfort + Role Strength Refactor (2026-01-30)

**Status:** Tasks 2-4 (skill transfer approach) superseded by the two-component model.

The skill transfer approach was replaced with champion comfort + role strength:
- See: `docs/plans/2026-01-30-role-baseline-proficiency.md`

Key changes from this plan that were retained:
- Task 1 (current viable roles) - Retained in FlexResolver and MetaScorer
- Role-aware proficiency tied to player assignments - Retained
- Dynamic weight redistribution for NO_DATA - Retained
- Candidate expansion with transfer targets - Retained for discovery (not scoring)

Key changes from this plan that were replaced:
- Skill transfer blending for proficiency scoring → Champion comfort + role strength
- Role selection using player proficiency → Role selection decoupled from proficiency
- Hard role fill → Soft role fill (≥0.9 threshold)

---

**Goal:** Fix proficiency scoring to eliminate NO_DATA noise, use role-aware proficiency tied to actual player assignments, and leverage skill transfers + current-role viability to surface realistic recommendations.

**Architecture:** Role-aware proficiency + skill transfer fallback + dynamic weighting when proficiency is NO_DATA. Role filtering must use **current_viable** roles (recent patch window), not all-time history. Add limited candidate expansion so transfer targets are actually scored.

**Tech Stack:** Python, pytest, existing knowledge JSON files:
`skill_transfers.json`, `player_proficiency.json`, `champion_role_history.json`, `flex_champions.json`

---

## Problem Summary (Updated)

Current issues:
1. **Role selection for proficiency is detached from roster**: suggested role is based on max role probability, not the role that fits the assigned player.
2. **Role filtering is stale**: role viability should be based on `current_viable_roles` / `current_distribution`, not all-time history.
3. **NO_DATA = 0.5 is too generous**: it silently inflates scores; we should redistribute weights instead of pretending neutral proficiency.
4. **Skill transfers exist but are not used in scoring** (still true).
5. **Transfer targets don’t surface**: candidate pool is only player pools + meta picks, so transfer targets with sparse data never get scored.

---

## Solution Overview (Updated)

1. **Role viability uses recent data**:
   - `FlexResolver` and `MetaScorer` use `current_viable_roles` / `current_distribution` first.
2. **Role-aware proficiency tied to player assignments**:
   - Proficiency is calculated only for the player assigned to the suggested role.
   - For flex picks, select the role that maximizes roster-fit (role probability × role player’s proficiency).
3. **Skill transfer fallback**:
   - When confidence is LOW/NO_DATA, use skill transfers from champions the player has **real data** on.
4. **Dynamic weighting for NO_DATA**:
   - If proficiency is NO_DATA, set proficiency weight to 0 and redistribute to other components (meta/matchup/counter/archetype).
5. **Candidate expansion**:
   - Seed candidate pool with **transfer targets** so new/sparse champs can be recommended.

---

## Task 1: Use Current Viable Roles in Role Filtering

**Files:**
- Modify: `backend/src/ban_teemo/services/scorers/flex_resolver.py`
- Modify: `backend/src/ban_teemo/services/scorers/meta_scorer.py`
- Test: `backend/tests/test_flex_resolver.py` (new or extend)
- Test: `backend/tests/test_meta_scorer.py` (new or extend)

**Changes:**
1. **FlexResolver**:
   - If `champion_role_history.json` has `current_distribution` or `current_viable_roles`,
     use those to filter/zero roles (before fallback).
2. **MetaScorer._champion_plays_role**:
   - Prefer `current_viable_roles` or `current_distribution` ≥ threshold
   - Fall back to `all_time_distribution` only if current data missing.

**Implementation detail (handoff-ready):**
- Add a helper to extract **current role viability** from `champion_role_history.json`:
  - Use `current_viable_roles` if present (canonicalize to top/jungle/mid/bot/support).
  - Otherwise use `current_distribution` with a threshold (e.g., ≥ 0.10).
  - Fall back to all-time data only if current fields are missing.
- Apply this in:
  - `FlexResolver.get_role_probabilities()` when deciding viable roles.
  - `MetaScorer._champion_plays_role()` when filtering top meta picks by role.

**Explicit test cases:**
1. `test_current_viable_roles_override_all_time`  
   - Champion has all-time TOP, but `current_viable_roles=["MID"]`  
   - Expect: role viability returns MID only; TOP filtered out.
2. `test_current_distribution_threshold_blocks_old_role`  
   - `current_distribution` has TOP=0.04, MID=0.96  
   - Expect: TOP filtered; MID allowed.
3. `test_fallback_all_time_if_current_missing`  
   - No current fields; all-time distribution shows ADC=0.8  
   - Expect: ADC allowed.

---

## Task 2: Create SkillTransferService (Same as Original Plan)

**Files:**
- Create: `backend/src/ban_teemo/services/scorers/skill_transfer_service.py`
- Test: `backend/tests/test_skill_transfer_service.py`

**No change to original logic**; keep `get_similar_champions()` and `get_best_transfer()`.

**Implementation detail (handoff-ready):**
- Service should **not** apply role filtering; that is handled upstream in candidate selection.
- Keep sorted output by `co_play_rate` descending for deterministic picks.

**Explicit test cases:**
1. `test_get_similar_champions_returns_sorted`  
   - Ensure highest `co_play_rate` appears first.
2. `test_get_best_transfer_respects_available_pool`  
   - Only returns champions present in `available_champions`.

---

## Task 3: Role-Aware Proficiency + Role Fit Selection

**Files:**
- Modify: `backend/src/ban_teemo/services/scorers/proficiency_scorer.py`
- Modify: `backend/src/ban_teemo/services/pick_recommendation_engine.py`
- Test: `backend/tests/test_proficiency_scorer.py`
- Test: `backend/tests/test_pick_recommendation_engine.py`

**Changes:**
1. Add `get_role_proficiency()` (role player only).
2. Add `get_role_proficiency_with_transfer()` (see Task 4).
3. In pick engine, **select suggested_role by roster fit**:
   - Evaluate each viable role from role probabilities.
   - Score = role_prob × (role_player_prof_score or transfer score).
   - Choose the role with the highest score; tie-break by role_prob.

**Important:** Normalize roles using existing `normalize_role()` utilities.

**Implementation detail (handoff-ready):**
- Add a `choose_best_role()` helper in the pick engine:
  - Inputs: `role_probs`, `team_players`, `champion`.
  - For each role in `role_probs`:
    - Find the assigned player for that role (normalize role names).
    - Fetch role proficiency (with transfer fallback).
    - Compute role-fit score = `role_prob * role_prof_score`.
  - Select max role-fit; fallback to max role_prob if no player assigned.

**Explicit test cases:**
1. `test_role_fit_prefers_assigned_player_strength`  
   - Flex champ (MID 0.6 / TOP 0.4)  
   - MID player has NO_DATA; TOP player has HIGH  
   - Expect: suggested role = TOP
2. `test_role_normalization_prevents_no_data`  
   - Team player role "ADC"  
   - Suggested role "bot"  
   - Expect: player resolved correctly, not None.

---

## Task 4: Skill Transfer Fallback + Candidate Expansion

**Files:**
- Modify: `backend/src/ban_teemo/services/scorers/proficiency_scorer.py`
- Modify: `backend/src/ban_teemo/services/pick_recommendation_engine.py`
- Modify: `backend/src/ban_teemo/services/scorers/__init__.py`
- Test: `backend/tests/test_proficiency_scorer.py`
- Test: `backend/tests/test_pick_recommendation_engine.py`

**Changes:**
1. **Transfer fallback** (same logic as prior plan):
   - Use best transfer champ from player’s pool (HIGH/MEDIUM only).
   - Blend direct score with transfer score (co_play_rate weighted).
2. **Candidate expansion**:
   - For each candidate in pool/meta, add top N transfer targets
   - Limit N (e.g., 2–3) to avoid explosion.
   - Require role viability (current roles filter) and not banned/unavailable.

**Implementation detail (handoff-ready):**
- Candidate expansion should **not** add duplicates and must respect `unavailable`.
- Limit transfer expansion to a fixed small N per candidate for performance.

**Explicit test cases:**
1. `test_transfer_target_surfaces_in_candidates`  
   - Champion X in pool, transfer target Y not in pool/meta  
   - Expect: Y appears in candidates.
2. `test_transfer_target_filtered_by_current_role`  
   - Transfer target exists but role is not currently viable  
   - Expect: excluded.

---

## Task 5: Dynamic Weighting When Proficiency is NO_DATA

**Files:**
- Modify: `backend/src/ban_teemo/services/pick_recommendation_engine.py`
- Test: `backend/tests/test_pick_recommendation_engine.py`

**Behavior:**
- If `prof_conf == "NO_DATA"`:
  - Set proficiency weight to 0.
  - Redistribute its weight proportionally to the other components.
  - Keep `components["proficiency"]` as 0.5 for transparency, but do not let it influence total score.

**Implementation detail (handoff-ready):**
- Compute `effective_weights` each scoring pass:
  - If `NO_DATA`, set `proficiency_weight=0`, then scale other weights by `1 / (1 - base_prof_weight)`.
  - If LOW/HIGH/MEDIUM, use base weights unchanged.
- Store `effective_weights` in result (optional) for diagnostics.

**Explicit test cases:**
1. `test_dynamic_weights_redistribute_on_no_data`  
   - Force proficiency NO_DATA; verify other weights scale up.
2. `test_no_data_score_differs_from_low`  
   - Same champion with LOW vs NO_DATA should produce different base_score.

---

## Task 6: Diagnostics + UI Surfacing (Visibility)

**Files:**
- Modify: `backend/src/ban_teemo/services/scoring_logger.py`
- Modify: `deepdraft/src/components/SimulatorView/index.tsx`

**Changes:**
- Add archetype to diagnostic summary (component stats).
- Add “Archetype” label in top factors list.
- (Optional) add `proficiency_source` (direct/transfer/none) to logs for debugging.

**Implementation detail (handoff-ready):**
- Update `scoring_logger` to include archetype in component stats list.
- Update UI factor labels to include archetype, ensuring it can be surfaced as a top factor.

---

## Task 7: Update Documentation

**Files:**
- Modify: `docs/analysis/2026-01-29-scoring-system-root-cause-analysis.md`

**Add:**
- Role-fit selection
- Current viable role filtering
- Transfer fallback + candidate expansion
- Dynamic weighting for NO_DATA

**Implementation detail (handoff-ready):**
- Add an explicit “Fix Implementation (Updated)” section with bullets for each change
  and expected before/after impact in the root-cause doc.

---

## Addendum (Not in Scope for This Plan)

**Optional future modifiers** from `player_game_stats`:
- `kda_ratio`, `kill_participation`, `vision_score`, `net_worth`

These can be used as **small, capped modifiers** to proficiency or confidence,
but are intentionally **excluded** from this fix to avoid new noise.

---

## Handoff Notes (For Next Agent)

1. **Role normalization** is critical: use `normalize_role()` everywhere roles are compared.
2. **Candidate expansion** must respect `unavailable` and `current_viable_roles`, or it will reintroduce invalid picks.
3. **Dynamic weighting** should be implemented in a single utility to avoid divergence between pick and ban logic later.
4. **Tests must not rely on live knowledge files** if possible; prefer fixtures or inline mock data.

---

## Core Logic Guardrails (Deep Reasoning + Explicit Checks)

This section defines **non-optional logic checks** and **pseudocode** for the core changes.
Treat these as invariants when implementing.

### 1) Role Viability Extraction (Current Data First)

**Rationale:** All-time roles are stale for patch-recent picks. We must prefer recent viability.

**Helper (conceptual):**
```
def get_current_role_viability(champ_data):
    if champ_data.current_viable_roles exists:
        return {normalize(role) for role in current_viable_roles}
    if champ_data.current_distribution exists:
        return {role for role, pct in current_distribution if pct >= CURRENT_THRESHOLD}
    return None  # fall back to all-time
```

**Explicit checks:**
- If `current_viable_roles` exists but is empty → treat as **no current roles** (do not fall back to all-time unless explicitly desired).
- Canonicalize all roles (`ADC`, `BOT`, `SUP`, `JNG`, etc.) using `normalize_role`.
- Ignore any role not in canonical set `{top,jungle,mid,bot,support}`.

**Invariant:** We do not suggest roles that are not in **current** viability when present.

---

### 2) Role-Fit Selection (Roster-Aware)

**Rationale:** Flex picks must be evaluated by who would play them, not by highest historical role probability.

**Helper (conceptual):**
```
def choose_best_role(role_probs, team_players, champion):
    best_role = None
    best_score = -1
    for role, prob in role_probs.items():
        player = find_player_for_role(team_players, role)
        if not player:
            continue
        prof_score, conf, _player = get_role_proficiency_with_transfer(champion, role, team_players)
        score = prob * prof_score
        if score > best_score:
            best_score = score
            best_role = role
    if best_role:
        return best_role
    return max(role_probs, key=role_probs.get, default="mid")
```

**Explicit checks:**
- If **no player assigned** to any viable role, fall back to highest `role_prob`.
- If role normalization fails, treat as unknown (do not silently match wrong role).
- If all role_probs are empty → default to `"mid"` (consistent fallback).

**Invariant:** If a player is assigned to a role with **non-NO_DATA** proficiency, that role should be preferred over a higher-probability role with NO_DATA.

---

### 3) Skill Transfer Fallback (Sparse Proficiency)

**Rationale:** LOW/NO_DATA should be boosted using similar champions the player actually plays.

**Helper (conceptual):**
```
def transfer_boost(champion, player):
    # only for LOW/NO_DATA
    pool = get_player_champion_pool(player, min_games=4)
    available = {c for c in pool if confidence in ["HIGH","MEDIUM"]}
    transfer = skill_transfer.get_best_transfer(champion, available)
    if not transfer:
        return None
    base_score = direct_score
    transfer_score = get_proficiency_score(player, transfer.champion)
    blended = base_score*(1-w) + transfer_score*w*transfer.co_play_rate
    return blended
```

**Explicit checks:**
- Only allow transfer if the **source champion** is HIGH/MEDIUM confidence.
- If `co_play_rate` missing or 0 → do not boost.
- Cap blended score to [0,1] after rounding.

**Invariant:** Transfers **must not** override HIGH/MEDIUM direct data.

---

### 4) Candidate Expansion (Transfer Targets)

**Rationale:** Transfers don’t matter if the target champion never enters the candidate pool.

**Helper (conceptual):**
```
def expand_candidates_with_transfers(candidates):
    expanded = set(candidates)
    for champ in candidates:
        for target in skill_transfer.get_top_targets(champ, limit=N):
            if target not in unavailable and role_viable(target):
                expanded.add(target)
    return expanded
```

**Explicit checks:**
- Expansion **must respect current role viability** and `unavailable`.
- Limit N to avoid candidate explosion (e.g., 2–3 per candidate).
- Avoid recursion (do not expand transfer targets of transfer targets).

**Invariant:** Expansion is a **one-hop** augmentation only.

---

### 5) Dynamic Weighting When Proficiency is NO_DATA

**Rationale:** NO_DATA should not contribute neutral mass or hide missing information.

**Helper (conceptual):**
```
def get_effective_weights(base_weights, prof_conf):
    if prof_conf != "NO_DATA":
        return base_weights
    # redistribute proficiency weight
    prof_w = base_weights["proficiency"]
    remaining = 1.0 - prof_w
    scale = 1.0 / remaining if remaining > 0 else 1.0
    return {k: (v*scale if k != "proficiency" else 0.0) for k,v in base_weights.items()}
```

**Explicit checks:**
- `sum(weights)` must be 1.0 (or extremely close after float rounding).
- If prof weight is zero already, do not rescale.
- Keep `components["proficiency"]` at 0.5 for transparency, but do not weight it.

**Invariant:** If proficiency is NO_DATA, it **cannot** increase total score.

---

## Summary

| Task | Description | Files |
|------|-------------|-------|
| 1 | Use current viable roles | FlexResolver, MetaScorer |
| 2 | Add SkillTransferService | skill_transfer_service.py |
| 3 | Role-aware proficiency + role fit selection | ProficiencyScorer, PickRecommendationEngine |
| 4 | Transfer fallback + candidate expansion | ProficiencyScorer, PickRecommendationEngine |
| 5 | Dynamic weighting for NO_DATA | PickRecommendationEngine |
| 6 | Diagnostics + UI surfacing | ScoringLogger, SimulatorView |
| 7 | Update root-cause analysis | docs/analysis |

Total: 7 tasks, expanded to cover recent findings and reduce silent fallback noise.

---

## Implementation Review Addendum (2026-01-30)

### Status (Reviewed)

| Task | Status | Notes |
|------|--------|-------|
| 1 | ✅ Complete | Added `role_viability.py`, current viability applied in `FlexResolver` + `MetaScorer`, tests added. |
| 2 | ✅ Complete | `SkillTransferService` created + tests. |
| 3 | ✅ Complete | Role-aware proficiency + roster-fit role selection in pick engine. |
| 4 | ✅ Complete | Transfer fallback in `ProficiencyScorer`; candidate expansion in `_build_role_cache` and `_get_candidates`. |
| 5 | ✅ Complete | Dynamic weighting via `_get_effective_weights`, surfaced in recs/tests. |
| 6 | ✅ Complete | Archetype added to diagnostics; UI labels include Archetype; logs include proficiency_source/player. |
| 7 | ✅ Complete | Root-cause analysis updated with expanded fix scope. |

### Implementation Notes (What Changed vs Plan)

1. **Role Viability Helper**
   - New helper: `backend/src/ban_teemo/utils/role_viability.py`
   - `extract_current_role_viability()` prefers `current_viable_roles`, then `current_distribution` (threshold = 0.10).
   - Used in both `FlexResolver` and `MetaScorer`.

2. **Roster-Fit Role Selection**
   - Added `_choose_best_role()` in `PickRecommendationEngine` to maximize `role_prob × role_prof_score`.
   - Uses role-aware proficiency with transfer fallback and role normalization.

3. **Transfer Fallback Safeguards**
   - Transfer blend weight capped by `TRANSFER_MAX_WEIGHT = 0.5`.
   - Transfers only used for LOW/NO_DATA; HIGH/MEDIUM bypassed.
   - Return `proficiency_source` (`direct`, `transfer`, `none`) and `proficiency_player`.

4. **Candidate Expansion**
   - One-hop transfer targets are added both to the **role cache** and **candidate set**.
   - Expansion limit: `TRANSFER_EXPANSION_LIMIT = 2`.
   - Role viability enforced via `role_cache` filtering.

5. **Dynamic Weighting for NO_DATA**
   - `_get_effective_weights()` redistributes proficiency weight when `NO_DATA`.
   - `effective_weights` now returned in recommendations for diagnostics/tests.

### Remaining Gaps / Follow-ups

- No direct unit tests for `ProficiencyScorer.get_role_proficiency*` (covered indirectly via pick engine tests).
- If we shift toward a **role-baseline proficiency** model (feedback), this plan should be revised and transfer usage demoted to optional.
