# Archetype/Synergy Data Fixes & Role-Based UI Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix all identified archetype and synergy data issues with audit trail, rebalance scoring weights based on domain expert feedback, then add a supplemental role-grouped view (top 2 per unfilled role) as an alternative to the primary top-5 recommendations.

**Architecture:** Four phases: (1) Data quality audit and fixes, (2) Scoring weight rebalancing (combine matchup+counter, adjust priorities), (3) Backend API changes for supplemental role-grouped recommendations, (4) Frontend UI updates with clear primary/supplemental distinction.

**Important Design Constraint - Role-Grouped View:**
The role-grouped view (top 2 per role) is SUPPLEMENTAL, not primary. The top-5 overall recommendations remain the primary recommendation. Role-grouped is an alternative view for:
- Late draft when a specific role must be filled
- Draft planning to see strength across all roles
- "What if" analysis when exploring alternatives

The UI must clearly distinguish these views. Evaluation data must track them separately.

**Tech Stack:** Python (backend), TypeScript/React (frontend), JSON data files

**Domain Expert Priority Order:**
1. **Team composition** (archetype + synergy) - "draft the best team possible"
2. **Meta strength** - "don't pick weak champions"
3. **Matchup/Counter** (combined) - "don't feed"
4. **Proficiency** - lowest priority, "they're pros anyway"

---

## Phase 1: Data Quality Audit & Fixes

### Task 1.0: Audit Matchup/Counter Data Sources

**Decision Path:**
- Before combining matchup + counter, verify we're not missing data
- Root cause any data gaps before making scoring changes
- Document data coverage for future reference

**Files:**
- Read: `knowledge/matchup_stats.json`
- Create: `scripts/audit_matchup_data.py`
- Output: `docs/plans/matchup_data_audit_2026-01-30.md`

**Step 1: Create matchup data audit script**

Create `scripts/audit_matchup_data.py`:

```python
#!/usr/bin/env python3
"""Audit matchup and counter data quality.

Checks:
1. Coverage: How many champion pairs have matchup data?
2. Completeness: Are both lane and team matchups present?
3. Sample sizes: Do we have enough games for reliable data?
4. Missing data: Which common matchups are missing?
"""

import json
from pathlib import Path
from collections import defaultdict


def main():
    knowledge_dir = Path(__file__).parent.parent / "knowledge"

    # Load matchup data
    matchup_path = knowledge_dir / "matchup_stats.json"
    with open(matchup_path) as f:
        matchup_data = json.load(f)

    # Load meta stats to know which champions are relevant
    meta_path = knowledge_dir / "meta_stats.json"
    with open(meta_path) as f:
        meta_data = json.load(f)
    meta_champs = set(meta_data.get("champions", {}).keys())

    print("=" * 70)
    print("MATCHUP DATA AUDIT")
    print("=" * 70)

    # Check structure
    print(f"\nData structure: {type(matchup_data)}")
    if isinstance(matchup_data, dict):
        print(f"Top-level keys: {list(matchup_data.keys())[:10]}")

    # Analyze coverage
    champions_with_data = set()
    total_matchups = 0
    matchups_by_role = defaultdict(int)
    low_sample_matchups = []

    for champ, data in matchup_data.items():
        if champ == "metadata":
            continue
        champions_with_data.add(champ)

        # Check vs_lane (role-specific matchups)
        vs_lane = data.get("vs_lane", {})
        for role, matchups in vs_lane.items():
            for enemy, stats in matchups.items():
                total_matchups += 1
                matchups_by_role[role] += 1
                games = stats.get("games", 0)
                if games < 10:
                    low_sample_matchups.append((champ, enemy, role, games))

        # Check vs_team (team-wide matchups)
        vs_team = data.get("vs_team", {})
        total_matchups += len(vs_team)

    print(f"\n--- COVERAGE ---")
    print(f"Champions with matchup data: {len(champions_with_data)}")
    print(f"Meta champions: {len(meta_champs)}")
    print(f"Coverage: {len(champions_with_data & meta_champs)}/{len(meta_champs)} meta champs")
    print(f"Total matchup entries: {total_matchups}")

    print(f"\n--- BY ROLE ---")
    for role, count in sorted(matchups_by_role.items()):
        print(f"  {role}: {count} matchups")

    print(f"\n--- LOW SAMPLE SIZE (<10 games) ---")
    print(f"Count: {len(low_sample_matchups)}")
    if low_sample_matchups[:10]:
        print("Examples:")
        for champ, enemy, role, games in low_sample_matchups[:10]:
            print(f"  {champ} vs {enemy} ({role}): {games} games")

    # Check for missing meta champion matchups
    missing_meta = meta_champs - champions_with_data
    if missing_meta:
        print(f"\n--- MISSING META CHAMPIONS ---")
        print(f"Count: {len(missing_meta)}")
        print(f"Champions: {sorted(missing_meta)[:20]}")

    # Summary
    print(f"\n--- SUMMARY ---")
    coverage_pct = len(champions_with_data & meta_champs) / len(meta_champs) * 100 if meta_champs else 0
    print(f"Data coverage: {coverage_pct:.1f}%")
    print(f"Low sample matchups: {len(low_sample_matchups)} ({len(low_sample_matchups)/max(total_matchups,1)*100:.1f}%)")

    if coverage_pct < 80:
        print("\n⚠️  WARNING: Coverage below 80% - investigate data pipeline")
    if len(low_sample_matchups) > total_matchups * 0.3:
        print("\n⚠️  WARNING: >30% of matchups have low sample size")


if __name__ == "__main__":
    main()
```

**Step 2: Run the audit**

Run:
```bash
uv run python scripts/audit_matchup_data.py 2>&1 | tee docs/plans/matchup_data_audit_2026-01-30.md
```

**Step 3: Analyze results and document findings**

Review output for:
- Coverage gaps (missing champions)
- Low sample size issues
- Role distribution imbalances

**Step 4: Commit audit script and results**

```bash
git add scripts/audit_matchup_data.py docs/plans/matchup_data_audit_2026-01-30.md
git commit -m "audit: matchup/counter data quality assessment

Documents current data coverage before combining matchup+counter.
Findings will inform whether data pipeline improvements are needed."
```

---

### Task 1.1: Document Current State & Create Backup

**Files:**
- Read: `knowledge/archetype_counters.json`
- Read: `knowledge/synergies.json`
- Create: `knowledge/backups/archetype_counters_2026-01-30.json`
- Create: `knowledge/backups/synergies_2026-01-30.json`

**Step 1: Create backup directory and copy files**

Run:
```bash
mkdir -p knowledge/backups
cp knowledge/archetype_counters.json knowledge/backups/archetype_counters_2026-01-30.json
cp knowledge/synergies.json knowledge/backups/synergies_2026-01-30.json
```

**Step 2: Run audit script to document current issues**

Run:
```bash
uv run python scripts/audit_archetype_synergy.py --generate-fixes -o docs/plans/archetype_synergy_audit_2026-01-30.json
```

**Step 3: Commit baseline**

```bash
git add knowledge/backups/ docs/plans/archetype_synergy_audit_2026-01-30.json
git commit -m "docs: backup archetype/synergy data before fixes"
```

---

### Task 1.2: Fix Engage Champion Archetypes

**Decision Path:**
- Champions identified as engage (Vi, Jarvan IV, etc.) should have `engage >= 0.6`
- Champions incorrectly labeled as `split` when they're engage should be corrected
- Reference: `scripts/audit_archetype_synergy.py` EXPECTED_ARCHETYPES["engage_champions"]

**Files:**
- Modify: `knowledge/archetype_counters.json`

**Step 1: Apply Xin Zhao fix**

In `archetype_counters.json`, find `"Xin Zhao"` entry and update:

**Before:**
```json
"Xin Zhao": {"split": 0.4, "engage": 0.32}
```

**After:**
```json
"Xin Zhao": {"engage": 0.9, "teamfight": 0.5}
```

**Rationale:** Xin Zhao is a dive/engage jungler, not a split pusher. His kit (E dash, R knockback) is designed for team fighting.

**Step 2: Apply Nautilus fix**

**Before:**
```json
"Nautilus": {"teamfight": 0.6, "pick": 0.5, "protect": 0.15}
```

**After:**
```json
"Nautilus": {"engage": 0.8, "teamfight": 0.6, "pick": 0.5, "protect": 0.15}
```

**Rationale:** Nautilus is primarily an engage support with hook and passive root.

**Step 3: Apply Amumu fix**

**Before:**
```json
"Amumu": {"teamfight": 1.0}
```

**After:**
```json
"Amumu": {"engage": 0.8, "teamfight": 1.0}
```

**Rationale:** Amumu's Q and R are primary engage tools for team fighting.

**Step 4: Apply Sejuani fix**

**Before:**
```json
"Sejuani": {"teamfight": 0.6, "engage": 0.2}
```

**After:**
```json
"Sejuani": {"engage": 0.7, "teamfight": 0.6}
```

**Rationale:** Sejuani is an engage tank with Q dash and R stun.

**Step 5: Apply Malphite fix**

**Before:**
```json
"Malphite": {"teamfight": 0.6}
```

**After:**
```json
"Malphite": {"engage": 0.9, "teamfight": 0.8}
```

**Rationale:** Malphite R is one of the most iconic engage ultimates.

**Step 6: Apply Ornn fix**

**Before:**
```json
"Ornn": {"teamfight": 0.9}
```

**After:**
```json
"Ornn": {"engage": 0.7, "teamfight": 0.9}
```

**Rationale:** Ornn R is a major engage tool.

**Step 7: Apply Maokai fix**

**Before:**
```json
"Maokai": {"teamfight": 0.9}
```

**After:**
```json
"Maokai": {"engage": 0.7, "teamfight": 0.9}
```

**Rationale:** Maokai W and R provide engage.

**Step 8: Apply Yasuo fix**

**Before:**
```json
"Yasuo": {"teamfight": 0.5}
```

**After:**
```json
"Yasuo": {"engage": 0.6, "teamfight": 0.5}
```

**Rationale:** Yasuo R requires knockup partners - he's part of engage comps.

**Step 9: Apply Yone fix**

**Before:**
```json
"Yone": {"teamfight": 0.5}
```

**After:**
```json
"Yone": {"engage": 0.7, "teamfight": 0.6}
```

**Rationale:** Yone R is a primary engage tool.

**Step 10: Apply Gragas fix**

**Before:**
```json
"Gragas": {"teamfight": 0.5}
```

**After:**
```json
"Gragas": {"engage": 0.7, "teamfight": 0.6, "pick": 0.5}
```

**Rationale:** Gragas E+R combo is engage/disengage.

**Step 11: Run tests to verify no regressions**

Run:
```bash
uv run pytest backend/tests/test_pick_recommendation_engine.py -v
```

Expected: All tests pass

**Step 12: Commit archetype fixes**

```bash
git add knowledge/archetype_counters.json
git commit -m "fix(data): correct engage champion archetypes

Champions fixed:
- Xin Zhao: split→engage (was incorrectly classified as split pusher)
- Nautilus: added engage (primary engage support)
- Amumu: added engage (Q/R engage)
- Sejuani: boosted engage (tank engage jungler)
- Malphite: added engage (iconic R engage)
- Ornn: added engage (R engage)
- Maokai: added engage (W/R engage)
- Yasuo: added engage (R synergy with knockups)
- Yone: added engage (R engage)
- Gragas: added engage (E/R combo)

Decision rationale: Champions with dash/knockup/AoE CC initiations
should have engage >= 0.6 to properly score with Orianna ball delivery
and other teamfight synergies.

Audit: scripts/audit_archetype_synergy.py --compare"
```

---

### Task 1.3: Add Missing Orianna Synergies

**Decision Path:**
- Orianna + engage champions should have synergy >= 0.6 (ball delivery combo)
- Reference: KNOWN_SYNERGIES["orianna_engage"] in audit script

**Files:**
- Modify: `knowledge/synergies.json`

**Step 1: Check current Orianna synergies**

Run:
```bash
uv run python -c "
import json
with open('knowledge/synergies.json') as f:
    data = json.load(f)
orianna_entries = [e for e in data if 'Orianna' in e.get('champions', [])]
print(f'Found {len(orianna_entries)} Orianna synergies')
for e in orianna_entries:
    print(f\"  {e['champions']}: {e['strength']}\")
"
```

**Step 2: Add missing Orianna + engage synergies**

Add entries to `synergies.json` array:

```json
{
  "id": "orianna_xin_zhao",
  "champions": ["Orianna", "Xin Zhao"],
  "type": "ability_combo",
  "category": "ball_delivery",
  "strength": "A",
  "confidence": "high",
  "description": "Orianna attaches ball to Xin Zhao. Xin E delivers ball into enemy team for Shockwave.",
  "mechanic_explanation": "Ball follows allied champion through dashes",
  "comp_archetypes": ["dive", "teamfight"],
  "source": "curated"
},
{
  "id": "orianna_vi",
  "champions": ["Orianna", "Vi"],
  "type": "ability_combo",
  "category": "ball_delivery",
  "strength": "A",
  "confidence": "high",
  "description": "Orianna attaches ball to Vi. Vi Q/R delivers guaranteed Shockwave to priority target.",
  "mechanic_explanation": "Ball follows allied champion through dashes and blinks",
  "comp_archetypes": ["dive", "teamfight"],
  "source": "curated"
},
{
  "id": "orianna_wukong",
  "champions": ["Orianna", "Wukong"],
  "type": "ability_combo",
  "category": "ball_delivery",
  "strength": "S",
  "confidence": "high",
  "description": "Orianna attaches ball to Wukong. Wukong E+R delivers ball for double AoE wombo combo.",
  "mechanic_explanation": "Ball follows allied champion through dashes",
  "comp_archetypes": ["teamfight", "engage"],
  "source": "curated"
},
{
  "id": "orianna_rell",
  "champions": ["Orianna", "Rell"],
  "type": "ability_combo",
  "category": "ball_delivery",
  "strength": "A",
  "confidence": "high",
  "description": "Orianna attaches ball to Rell. Rell W engage delivers ball for AoE combo.",
  "mechanic_explanation": "Ball follows allied champion through dashes",
  "comp_archetypes": ["teamfight", "engage"],
  "source": "curated"
}
```

**Step 3: Verify synergy additions**

Run:
```bash
uv run python -c "
import json
with open('knowledge/synergies.json') as f:
    data = json.load(f)
orianna_entries = [e for e in data if 'Orianna' in e.get('champions', [])]
print(f'Found {len(orianna_entries)} Orianna synergies')
for e in orianna_entries:
    print(f\"  {e['champions']}: {e['strength']}\")
"
```

Expected: Should show new entries including Xin Zhao, Vi, Wukong, Rell

**Step 4: Commit synergy fixes**

```bash
git add knowledge/synergies.json
git commit -m "fix(data): add missing Orianna ball delivery synergies

Added synergies:
- Orianna + Xin Zhao (A): E dash delivers ball
- Orianna + Vi (A): Q/R delivers ball to target
- Orianna + Wukong (S): E+R double AoE combo
- Orianna + Rell (A): W engage delivers ball

Decision rationale: Ball delivery combos are core pro play
synergies that enable guaranteed multi-target Shockwave.

Audit: scripts/audit_archetype_synergy.py"
```

---

### Task 1.4: Add Missing Yasuo/Yone Knockup Synergies

**Decision Path:**
- Yasuo/Yone + knockup champions should have synergy >= 0.6 (Last Breath enablers)
- Reference: KNOWN_SYNERGIES["yasuo_knockups"] in audit script

**Files:**
- Modify: `knowledge/synergies.json`

**Step 1: Add Yasuo knockup synergies**

Add entries to `synergies.json`:

```json
{
  "id": "yasuo_malphite",
  "champions": ["Yasuo", "Malphite"],
  "type": "ability_combo",
  "category": "knockup_synergy",
  "strength": "S",
  "confidence": "high",
  "description": "Malphite R knockup enables guaranteed Yasuo Last Breath on entire enemy team.",
  "mechanic_explanation": "Any knockup enables Last Breath",
  "comp_archetypes": ["teamfight", "engage"],
  "source": "curated"
},
{
  "id": "yasuo_diana",
  "champions": ["Yasuo", "Diana"],
  "type": "ability_combo",
  "category": "knockup_synergy",
  "strength": "A",
  "confidence": "high",
  "description": "Diana R pulls enemies together and triggers knockup for Yasuo Last Breath.",
  "mechanic_explanation": "Diana R counts as knockup displacement",
  "comp_archetypes": ["teamfight", "engage"],
  "source": "curated"
},
{
  "id": "yasuo_gragas",
  "champions": ["Yasuo", "Gragas"],
  "type": "ability_combo",
  "category": "knockup_synergy",
  "strength": "A",
  "confidence": "high",
  "description": "Gragas E knockup and R displacement enable Yasuo Last Breath.",
  "mechanic_explanation": "Gragas E is knockup, R is displacement",
  "comp_archetypes": ["teamfight", "pick"],
  "source": "curated"
},
{
  "id": "yasuo_alistar",
  "champions": ["Yasuo", "Alistar"],
  "type": "ability_combo",
  "category": "knockup_synergy",
  "strength": "S",
  "confidence": "high",
  "description": "Alistar W+Q combo provides reliable knockup for Yasuo Last Breath.",
  "mechanic_explanation": "Alistar Q is knockup",
  "comp_archetypes": ["engage", "teamfight"],
  "source": "curated"
},
{
  "id": "yasuo_rakan",
  "champions": ["Yasuo", "Rakan"],
  "type": "ability_combo",
  "category": "knockup_synergy",
  "strength": "A",
  "confidence": "high",
  "description": "Rakan W knockup enables Yasuo Last Breath on grouped enemies.",
  "mechanic_explanation": "Rakan W is knockup",
  "comp_archetypes": ["engage", "teamfight"],
  "source": "curated"
}
```

**Step 2: Add equivalent Yone synergies**

Add entries for Yone (same partners):

```json
{
  "id": "yone_malphite",
  "champions": ["Yone", "Malphite"],
  "type": "ability_combo",
  "category": "knockup_synergy",
  "strength": "S",
  "confidence": "high",
  "description": "Malphite R knockup enables guaranteed Yone Last Breath on entire enemy team.",
  "mechanic_explanation": "Any knockup enables Last Breath",
  "comp_archetypes": ["teamfight", "engage"],
  "source": "curated"
},
{
  "id": "yone_diana",
  "champions": ["Yone", "Diana"],
  "type": "ability_combo",
  "category": "knockup_synergy",
  "strength": "A",
  "confidence": "high",
  "description": "Diana R pulls enemies together for Yone R engage.",
  "mechanic_explanation": "Diana R groups enemies for Yone",
  "comp_archetypes": ["teamfight", "engage"],
  "source": "curated"
}
```

**Step 3: Verify synergies**

Run:
```bash
uv run python scripts/audit_archetype_synergy.py 2>&1 | grep -A5 "SYNERGY AUDIT"
```

Expected: Fewer missing synergies

**Step 4: Commit**

```bash
git add knowledge/synergies.json
git commit -m "fix(data): add Yasuo/Yone knockup synergies

Added knockup synergies:
- Yasuo + Malphite/Diana/Gragas/Alistar/Rakan
- Yone + Malphite/Diana

Decision rationale: Knockup champions enable Last Breath,
which is a core pro play draft consideration.

Audit: scripts/audit_archetype_synergy.py"
```

---

### Task 1.5: Verify All Data Fixes with Evaluation

**Files:**
- Run: `scripts/audit_archetype_synergy.py`
- Run: `scripts/analyze_recommendations.py`

**Step 1: Run audit to confirm fixes**

Run:
```bash
uv run python scripts/audit_archetype_synergy.py 2>&1
```

Expected: Significantly fewer issues than before

**Step 2: Re-run evaluation on 100 games**

Run:
```bash
uv run python scripts/analyze_recommendations.py --recent 35 --quiet --json outputs/evals/eval_post_data_fixes.json
```

**Step 3: Compare results**

Run:
```bash
uv run python scripts/analyze_eval_results.py outputs/evals/eval_post_data_fixes.json 2>&1 | head -40
```

Expected: Improved pick accuracy, especially for engage junglers

**Step 4: Commit evaluation results**

```bash
git add outputs/evals/eval_post_data_fixes.json
git commit -m "docs: post-data-fix evaluation results"
```

---

## Phase 2: Scoring Weight Rebalancing

### Task 2.0: Combine Matchup + Counter into Single Component

**Decision Path (Domain Expert Feedback):**
- Matchup and counter are conceptually related ("don't feed")
- Combining simplifies the model and reduces over-fitting
- Combined weight should be ~0.25 (from 0.20 + 0.20 = 0.40)

**Files:**
- Modify: `backend/src/ban_teemo/services/pick_recommendation_engine.py`
- Modify: `backend/tests/test_pick_recommendation_engine.py`

**Step 1: Write test for combined matchup_counter component**

Add to `backend/tests/test_pick_recommendation_engine.py`:

```python
def test_components_include_matchup_counter():
    """Matchup and counter should be combined into matchup_counter."""
    engine = PickRecommendationEngine()

    # Minimal setup
    team_players = [{"name": "Test", "role": "mid"}]
    recs = engine.get_recommendations(
        team_players=team_players,
        our_picks=[],
        enemy_picks=["Ahri"],  # Need enemy for matchup data
        banned=[],
        limit=1
    )

    if recs:
        components = recs[0]["components"]
        # Should have combined component
        assert "matchup_counter" in components or ("matchup" in components and "counter" in components)
```

**Step 2: Update BASE_WEIGHTS in pick_recommendation_engine.py**

Change from:
```python
BASE_WEIGHTS = {
    "meta": 0.25,
    "proficiency": 0.20,
    "matchup": 0.20,
    "counter": 0.20,
    "archetype": 0.15,
}
```

To:
```python
# Domain expert priority order:
# 1. Team composition (archetype) - "draft best team possible"
# 2. Meta strength - "don't pick weak champions"
# 3. Matchup/Counter - "don't feed"
# 4. Proficiency - "they're pros anyway"
#
# NOTE: Synergy is NOT a base weight - it's applied as a multiplier to the
# final score. This is intentional: synergy is a team-wide modifier that
# scales the entire recommendation, not an individual champion attribute.
# Adding synergy here would double-count it (once as weight, once as multiplier).
BASE_WEIGHTS = {
    "archetype": 0.30,       # Team composition fit (highest - defines team identity)
    "meta": 0.30,            # Champion power level
    "matchup_counter": 0.25, # Combined lane + team matchups
    "proficiency": 0.15,     # Player comfort (lowest - they're pros)
}
```

**Step 3: Update _calculate_score to combine matchup + counter**

In `_calculate_score` method, replace separate matchup/counter with:

```python
# Combined matchup_counter (lane + team matchups)
matchup_scores = []
counter_scores = []

for enemy in enemy_picks:
    # Lane matchup
    role_probs = role_cache.get(enemy, {})
    if suggested_role in role_probs and role_probs[suggested_role] > 0:
        result = self.matchup_calculator.get_lane_matchup(champion, enemy, suggested_role)
        matchup_scores.append(result["score"])

    # Team counter
    result = self.matchup_calculator.get_team_matchup(champion, enemy)
    counter_scores.append(result["score"])

# Combine: weight lane matchup slightly higher (60/40)
matchup_avg = sum(matchup_scores) / len(matchup_scores) if matchup_scores else 0.5
counter_avg = sum(counter_scores) / len(counter_scores) if counter_scores else 0.5
components["matchup_counter"] = matchup_avg * 0.6 + counter_avg * 0.4
```

**Step 4: Update base_score calculation**

```python
# NOTE: Synergy is applied as a multiplier AFTER base_score, not as a component.
# This avoids double-counting synergy (which is already a multiplier in the
# current implementation). See _calculate_score for synergy_multiplier usage.
base_score = (
    components["archetype"] * effective_weights["archetype"] +
    components["meta"] * effective_weights["meta"] +
    components["matchup_counter"] * effective_weights["matchup_counter"] +
    components["proficiency"] * effective_weights["proficiency"]
)
# Synergy multiplier is applied separately: total_score = base_score * synergy_multiplier
```

**Step 5: Run tests**

```bash
uv run pytest backend/tests/test_pick_recommendation_engine.py -v
```

Fix any failing tests due to weight changes.

**Step 6: Commit**

```bash
git add backend/src/ban_teemo/services/pick_recommendation_engine.py backend/tests/test_pick_recommendation_engine.py
git commit -m "refactor(scoring): combine matchup+counter, rebalance weights

Domain expert priority order:
1. archetype (0.30) - team composition fit (highest)
2. meta (0.30) - champion power level
3. matchup_counter (0.25) - combined lane+team matchups
4. proficiency (0.15) - player comfort (lowest)

NOTE: Synergy remains a MULTIPLIER, not a base weight.
This avoids double-counting since synergy scales the final score.

Rationale:
- Team composition is top priority (archetype at 0.30)
- Pros can play anything, proficiency matters least
- Combined matchup+counter simplifies model"
```

---

### Task 2.1: Add Meta Weight to Ban Tier 1

**Decision Path (Domain Expert Feedback):**
- Ban Tier 1 should consider meta strength
- High-meta champions are worth banning even without player targeting
- Adds ~10% weight to meta in Tier 1 calculations

**Files:**
- Modify: `backend/src/ban_teemo/services/ban_recommendation_service.py`
- Modify: `backend/tests/test_ban_recommendation_service.py`

**Step 1: Locate Tier 1 priority calculation**

Find the ban priority calculation in `ban_recommendation_service.py`.

**Step 2: Add meta component to Tier 1**

In the priority calculation for Tier 1 (T1_POOL_AND_POWER), add:

```python
# Add meta weight to Tier 1 bans
if tier == "T1_POOL_AND_POWER":
    meta_score = self.meta_scorer.get_meta_score(champion)
    priority += meta_score * 0.10  # 10% weight for meta in Tier 1
    components["meta"] = meta_score
```

**Step 3: Add test for meta in Tier 1**

```python
def test_tier1_bans_include_meta_weight():
    """Tier 1 bans should factor in meta score."""
    service = BanRecommendationService()

    # Get ban recommendations
    recs = service.get_ban_recommendations(
        enemy_team_id="test",
        our_picks=[],
        enemy_picks=[],
        banned=[],
        phase="BAN_PHASE_1",
        enemy_players=[{"name": "Test", "role": "mid"}],
    )

    # Check that high-meta champions have higher priority
    # (implementation-specific assertion)
    tier1_recs = [r for r in recs if r.components.get("tier") == "T1_POOL_AND_POWER"]
    if tier1_recs:
        assert "meta" in tier1_recs[0].components
```

**Step 4: Run tests**

```bash
uv run pytest backend/tests/test_ban_recommendation_service.py -v
```

**Step 5: Commit**

```bash
git add backend/src/ban_teemo/services/ban_recommendation_service.py backend/tests/test_ban_recommendation_service.py
git commit -m "feat(bans): add meta weight to Tier 1 ban priority

High-meta champions now factor into Tier 1 ban calculations.
Adds 10% weight for meta score in T1_POOL_AND_POWER tier.

Domain expert feedback: meta should influence which comfort picks
are worth targeting."
```

---

### Task 2.2: Update Weight Adjustment Logic

**Files:**
- Modify: `backend/src/ban_teemo/services/pick_recommendation_engine.py`

**Step 1: Update _get_effective_weights for new weight structure**

```python
def _get_effective_weights(
    self,
    prof_conf: str,
    pick_count: int = 0,
    has_enemy_picks: bool = False
) -> dict[str, float]:
    """Get context-adjusted scoring weights.

    Priority order (domain expert):
    1. archetype - team composition (NEVER reduced - defines team identity)
    2. meta - champion power
    3. matchup_counter - don't feed
    4. proficiency - lowest (pros can play anything)

    Design rationale:
    - Archetype is never reduced because first pick often defines team identity
    - Meta is boosted early (power picks) and reduced late (counters matter more)
    - Matchup_counter is boosted late when counter-picking is possible
    - Proficiency is always lowest priority for pro play
    """
    weights = dict(self.BASE_WEIGHTS)

    # First pick: boost meta, reduce proficiency further
    # NOTE: Archetype is NOT reduced - first pick often sets team identity
    if pick_count == 0 and not has_enemy_picks:
        # Blind picks are about power level + team identity
        weights["meta"] += 0.05           # 0.30 -> 0.35
        weights["proficiency"] -= 0.05    # 0.15 -> 0.10

    # Late draft: boost matchup_counter, reduce meta
    elif has_enemy_picks and pick_count >= 3:
        weights["matchup_counter"] += 0.05  # 0.25 -> 0.30
        weights["meta"] -= 0.05             # 0.30 -> 0.25

    # Handle NO_DATA proficiency
    if prof_conf == "NO_DATA":
        redistribute = weights["proficiency"] * 0.8
        weights["proficiency"] *= 0.2
        # Distribute to archetype and meta (most important factors)
        weights["archetype"] += redistribute * 0.5
        weights["meta"] += redistribute * 0.3
        weights["matchup_counter"] += redistribute * 0.2

    return weights
```

**Step 2: Run tests**

```bash
uv run pytest backend/tests/test_pick_recommendation_engine.py -v
```

**Step 3: Commit**

```bash
git add backend/src/ban_teemo/services/pick_recommendation_engine.py
git commit -m "refactor(scoring): update weight adjustment logic for new priorities

- First pick: meta 0.35, archetype 0.30 (unchanged), proficiency 0.10
- Late draft: matchup_counter 0.30, meta 0.25
- NO_DATA: redistribute 50% to archetype, 30% to meta, 20% to matchup_counter

Key design decision: Archetype is NEVER reduced because first pick
often defines team identity. Team composition remains top priority."
```

---

### Task 2.3: Run Post-Rebalancing Evaluation

**Step 1: Run full evaluation**

```bash
uv run python scripts/analyze_recommendations.py --recent 100 --quiet --json outputs/evals/eval_post_rebalancing.json
```

**Step 2: Analyze results**

```bash
uv run python scripts/analyze_eval_results.py outputs/evals/eval_post_rebalancing.json 2>&1
```

**Step 3: Compare to baseline**

Document improvements in:
- Pick Phase 1 accuracy (should improve with higher archetype+meta weight)
- Overall pick accuracy
- Component delta changes (archetype should be less negative now)

**Step 4: Commit**

```bash
git add outputs/evals/eval_post_rebalancing.json
git commit -m "docs: post-rebalancing evaluation results

Compare to baseline to verify domain expert weight changes improved accuracy."
```

---

### Task 2.4: Update Evaluation Script for Role-Grouped Tracking

**Important:** Evaluation must track primary recommendations (top 5) separately from role-grouped (supplemental) to measure their relative accuracy.

**Files:**
- Modify: `scripts/analyze_recommendations.py`

**Step 1: Add role-grouped accuracy tracking**

The evaluation should compute:
- `primary_top5_accuracy`: Hit rate for top 5 recommendations (existing metric)
- `role_grouped_top2_accuracy`: Hit rate if we recommended top 2 per role
- `role_grouped_vs_primary_delta`: How often role-grouped would have hit when primary missed

This data informs whether role-grouped provides value or just noise.

**Step 2: Add role-grouped metrics to output**

```python
# In the evaluation output structure:
{
    "primary_recommendations": {
        "top5_accuracy": 0.XX,
        "by_phase": {...}
    },
    "role_grouped_supplemental": {
        "top2_per_role_accuracy": 0.XX,
        "additional_hits": N,  # Hits that primary missed but role-grouped caught
        "description": "Supplemental view - not primary recommendation"
    }
}
```

**Step 3: Commit**

```bash
git add scripts/analyze_recommendations.py
git commit -m "feat(eval): track primary vs supplemental recommendation accuracy

Separates evaluation metrics:
- Primary: top 5 overall (main recommendation)
- Supplemental: top 2 per role (alternative view)

This data validates whether role-grouped provides additional value."
```

---

## Phase 3: Backend API for Supplemental Role-Grouped Recommendations

**Important:** Role-grouped recommendations are SUPPLEMENTAL to the primary top-5 recommendations.
They provide an alternative view for specific use cases (late draft role filling, draft planning).
The API returns both views, clearly labeled, with the primary recommendations first.

### Task 3.1: Add Role-Grouped Recommendation Response Model

**Files:**
- Modify: `backend/src/ban_teemo/models/recommendations.py`
- Create: `backend/tests/test_recommendations_model.py`

**Step 1: Write the test**

Create `backend/tests/test_recommendations_model.py`:

```python
"""Tests for recommendation models."""
import pytest
from ban_teemo.models.recommendations import RoleGroupedRecommendations, PickRecommendation


def test_role_grouped_recommendations_structure():
    """RoleGroupedRecommendations groups picks by role."""
    pick1 = PickRecommendation(
        champion_name="Vi",
        confidence=0.9,
        suggested_role="jungle",
        flag=None,
        reasons=["Strong engage"],
        score=0.75,
        base_score=0.70,
        synergy_multiplier=1.07,
        components={"meta": 0.6, "proficiency": 0.8},
        proficiency_source="direct",
        proficiency_player="Canyon",
    )
    pick2 = PickRecommendation(
        champion_name="Xin Zhao",
        confidence=0.9,
        suggested_role="jungle",
        flag=None,
        reasons=["Comfort pick"],
        score=0.72,
        base_score=0.68,
        synergy_multiplier=1.06,
        components={"meta": 0.55, "proficiency": 0.9},
        proficiency_source="direct",
        proficiency_player="Canyon",
    )
    pick3 = PickRecommendation(
        champion_name="Rumble",
        confidence=0.85,
        suggested_role="top",
        flag=None,
        reasons=["Strong laner"],
        score=0.70,
        base_score=0.65,
        synergy_multiplier=1.08,
        components={"meta": 0.6, "proficiency": 0.7},
        proficiency_source="direct",
        proficiency_player="Kiin",
    )

    grouped = RoleGroupedRecommendations.from_picks([pick1, pick2, pick3], limit_per_role=2)

    assert "jungle" in grouped.by_role
    assert len(grouped.by_role["jungle"]) == 2
    assert grouped.by_role["jungle"][0].champion_name == "Vi"  # Higher score first
    assert grouped.by_role["jungle"][1].champion_name == "Xin Zhao"
    assert "top" in grouped.by_role
    assert len(grouped.by_role["top"]) == 1


def test_role_grouped_recommendations_to_dict():
    """RoleGroupedRecommendations serializes correctly."""
    pick = PickRecommendation(
        champion_name="Vi",
        confidence=0.9,
        suggested_role="jungle",
        flag=None,
        reasons=["Strong engage"],
        score=0.75,
        base_score=0.70,
        synergy_multiplier=1.07,
        components={"meta": 0.6},
        proficiency_source="direct",
        proficiency_player="Canyon",
    )

    grouped = RoleGroupedRecommendations.from_picks([pick], limit_per_role=2)
    result = grouped.to_dict()

    assert "by_role" in result
    assert "jungle" in result["by_role"]
    assert result["by_role"]["jungle"][0]["champion_name"] == "Vi"
```

**Step 2: Run test to verify it fails**

Run:
```bash
uv run pytest backend/tests/test_recommendations_model.py -v
```

Expected: FAIL with "cannot import name 'RoleGroupedRecommendations'"

**Step 3: Implement RoleGroupedRecommendations**

Add to `backend/src/ban_teemo/models/recommendations.py`:

```python
from dataclasses import dataclass, field, asdict
from typing import Optional
from collections import defaultdict


@dataclass
class RoleGroupedRecommendations:
    """Recommendations grouped by role for display."""
    by_role: dict[str, list["PickRecommendation"]] = field(default_factory=dict)

    @classmethod
    def from_picks(
        cls,
        picks: list["PickRecommendation"],
        limit_per_role: int = 2,
    ) -> "RoleGroupedRecommendations":
        """Group picks by suggested_role, keeping top N per role."""
        by_role: dict[str, list[PickRecommendation]] = defaultdict(list)

        # Sort by score descending
        sorted_picks = sorted(picks, key=lambda p: p.score, reverse=True)

        for pick in sorted_picks:
            role = pick.suggested_role or "unknown"
            if len(by_role[role]) < limit_per_role:
                by_role[role].append(pick)

        return cls(by_role=dict(by_role))

    def to_dict(self) -> dict:
        """Serialize to dictionary for JSON response."""
        return {
            "by_role": {
                role: [asdict(pick) for pick in picks]
                for role, picks in self.by_role.items()
            }
        }
```

**Step 4: Run test to verify it passes**

Run:
```bash
uv run pytest backend/tests/test_recommendations_model.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/ban_teemo/models/recommendations.py backend/tests/test_recommendations_model.py
git commit -m "feat(api): add RoleGroupedRecommendations model

Groups pick recommendations by role with configurable limit per role.
This is a SUPPLEMENTAL view alongside the primary top-5 recommendations.

Use cases:
- Late draft when a specific role must be filled
- Draft planning to compare options across roles
- 'What if' analysis for alternative picks"
```

---

### Task 3.2: Update Simulator API to Return Role-Grouped Recommendations

**Files:**
- Modify: `backend/src/ban_teemo/api/routes/simulator.py`
- Modify: `backend/tests/test_simulator_routes.py`

**Step 1: Add test for role-grouped response**

Add to `backend/tests/test_simulator_routes.py`:

```python
def test_recommendations_include_role_grouped(client, sample_session):
    """GET /recommendations returns role-grouped picks."""
    session_id = sample_session["session_id"]

    response = client.get(f"/api/simulator/sessions/{session_id}/recommendations")
    assert response.status_code == 200
    data = response.json()

    assert "role_grouped" in data
    assert "by_role" in data["role_grouped"]
    by_role = data["role_grouped"]["by_role"]
    assert isinstance(by_role, dict)
```

**Step 2: Run test to verify it fails**

Run:
```bash
uv run pytest backend/tests/test_simulator_routes.py::test_recommendations_include_role_grouped -v
```

Expected: FAIL (no role_grouped field)

**Step 3: Update recommendations response in simulator.py**

Add role grouping as a SUPPLEMENTAL view alongside primary recommendations:

```python
from ban_teemo.models.recommendations import RoleGroupedRecommendations

# In pick phase response building:
if phase and "PICK" in phase:
    picks = pick_engine.get_recommendations(
        team_players=team_players,
        our_picks=our_picks,
        enemy_picks=enemy_picks,
        banned=all_banned,
        limit=20,  # Get more for role grouping
    )

    role_grouped = RoleGroupedRecommendations.from_picks(picks, limit_per_role=2)

    # PRIMARY: Top 5 overall recommendations (phase-optimized)
    response["recommendations"] = [_serialize_pick(p) for p in picks[:5]]

    # SUPPLEMENTAL: Alternative view grouped by role
    # Use case: late draft role filling, draft planning
    response["role_grouped"] = {
        "view_type": "supplemental",
        "description": "Alternative view: top picks per unfilled role",
        **role_grouped.to_dict()
    }
```

**Step 4: Run test to verify it passes**

Run:
```bash
uv run pytest backend/tests/test_simulator_routes.py::test_recommendations_include_role_grouped -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/ban_teemo/api/routes/simulator.py backend/tests/test_simulator_routes.py
git commit -m "feat(api): add supplemental role_grouped field to recommendations

Returns top 2 picks per unfilled role as SUPPLEMENTAL view.
Primary recommendations (top 5) remain the main output.
role_grouped includes view_type='supplemental' to clarify its purpose."
```

---

### Task 3.3: Update Replay WebSocket to Include Role-Grouped Recommendations

**Files:**
- Modify: `backend/src/ban_teemo/api/websockets/replay_ws.py`

**Step 1: Update _serialize_recommendations in replay_ws.py**

```python
from ban_teemo.models.recommendations import RoleGroupedRecommendations

def _serialize_recommendations(self, recs: Recommendations) -> dict:
    result = {
        "for_team": recs.for_team,
        "picks": [self._serialize_pick(p) for p in recs.picks] if recs.picks else [],
        "bans": [self._serialize_ban(b) for b in recs.bans] if recs.bans else [],
    }

    if recs.picks:
        role_grouped = RoleGroupedRecommendations.from_picks(recs.picks, limit_per_role=2)
        result["role_grouped"] = role_grouped.to_dict()

    return result
```

**Step 2: Commit**

```bash
git add backend/src/ban_teemo/api/websockets/replay_ws.py
git commit -m "feat(api): add supplemental role_grouped to replay WebSocket

Consistent with simulator API: role_grouped is supplemental,
picks array remains the primary recommendation output."
```

---

## Phase 4: Frontend UI Updates

**Important UI Design Constraint:**
The role-grouped view must be clearly presented as an ALTERNATIVE view, not the primary recommendation.
- Primary view: Top 5 recommendations (default, prominent)
- Alternative view: By-role grouping (toggle, secondary placement)

The UI should NOT give equal prominence to both views.

### Task 4.0: Design UI Hierarchy

Before implementing components, establish the visual hierarchy:

1. **Primary Panel**: "Top Recommendations" - shows top 5 phase-optimized picks
2. **Alternative Panel**: "By Role" - collapsible/toggle, shows top 2 per unfilled role
3. **Toggle Control**: "View by role" toggle, OFF by default
4. **Visual Distinction**: Alternative panel uses muted styling, smaller cards

This ensures users understand that top 5 is the recommended path.

### Task 4.1: Add TypeScript Types for Role-Grouped Recommendations

**Files:**
- Modify: `deepdraft/src/types/index.ts`

**Step 1: Add types**

```typescript
export interface RoleGroupedRecommendations {
  by_role: {
    [role: string]: SimulatorPickRecommendation[];
  };
}

export interface RecommendationsResponse {
  for_action_count: number;
  phase: string;
  recommendations: SimulatorRecommendation[];
  role_grouped?: RoleGroupedRecommendations;
}
```

**Step 2: Commit**

```bash
git add deepdraft/src/types/index.ts
git commit -m "feat(types): add RoleGroupedRecommendations TypeScript types"
```

---

### Task 4.2: Create RoleRecommendationPanel Component

**Files:**
- Create: `deepdraft/src/components/recommendations/RoleRecommendationPanel.tsx`

**Step 1: Create component** (see full implementation in previous version)

**Step 2: Commit**

```bash
git add deepdraft/src/components/recommendations/RoleRecommendationPanel.tsx
git commit -m "feat(ui): create RoleRecommendationPanel component

Displays top 2 picks per unfilled role with score and component breakdown."
```

---

### Task 4.3: Update SimulatorView with Role-Grouped Panel and Enhanced Scores

**Files:**
- Modify: `deepdraft/src/components/SimulatorView/index.tsx`

**Step 1: Add imports, state, and RoleRecommendationPanel integration**

**Step 2: Add expandable score breakdown to RecommendationCard**

**Step 3: Commit**

```bash
git add deepdraft/src/components/SimulatorView/index.tsx
git commit -m "feat(ui): integrate role-grouped recommendations and expandable scores

- Shows top 2 picks per unfilled role
- Click cards to expand full score breakdown
- Shows all reasons and synergy impact"
```

---

### Task 4.4: Update InsightsLog with Role-Grouped View Toggle

**Files:**
- Modify: `deepdraft/src/components/InsightsLog/index.tsx`

**Step 1: Add view mode toggle and RoleRecommendationPanel**

**Step 2: Commit**

```bash
git add deepdraft/src/components/InsightsLog/index.tsx
git commit -m "feat(ui): add role-grouped view toggle to InsightsLog"
```

---

### Task 4.5: Add Component Explanation Tooltips

**Files:**
- Create: `deepdraft/src/components/recommendations/ComponentTooltip.tsx`

**Step 1: Create tooltip with updated explanations**

```typescript
const COMPONENT_EXPLANATIONS: { [key: string]: string } = {
  archetype: "Fit with team's strategic identity (engage, poke, protect, etc.)",
  meta: "Champion's current strength in pro meta (win rate, pick/ban rate)",
  matchup_counter: "Combined lane matchup and team-wide counter advantage",
  proficiency: "Player's comfort and experience with this champion",
  synergy: "How well this champion works with teammates",
};
```

**Step 2: Commit**

```bash
git add deepdraft/src/components/recommendations/ComponentTooltip.tsx
git commit -m "feat(ui): add component explanation tooltips"
```

---

## Phase 5: Final Integration & Testing

### Task 5.1: End-to-End Testing

**Step 1: Start dev servers**
**Step 2: Test Simulator flow**
**Step 3: Test Replay flow**
**Step 4: Run all tests**

```bash
uv run pytest backend/tests/ -v
cd deepdraft && npm test
```

---

### Task 5.2: Final Commit & Documentation

```bash
git add -A
git commit -m "feat: complete scoring rebalance and supplemental role-grouped UI

Phase 1: Data Fixes
- Fixed 10 engage champion archetypes
- Added 15+ missing synergies

Phase 2: Scoring Rebalance (Domain Expert Feedback)
- Combined matchup+counter into single component
- New weights: archetype 0.30, meta 0.30, matchup_counter 0.25, proficiency 0.15
- Synergy remains MULTIPLIER (not base weight - avoids double-counting)
- Archetype never reduced (team identity priority)
- Added meta weight to ban Tier 1

Phase 3: Backend API
- Added supplemental RoleGroupedRecommendations model
- Updated simulator and replay APIs with clear primary/supplemental distinction

Phase 4: Frontend UI
- Created RoleRecommendationPanel as ALTERNATIVE view (not primary)
- Toggle-based secondary panel with muted styling
- Added expandable score breakdowns
- Updated component explanations

Evaluation: Primary and supplemental metrics tracked separately."
```

---

## Summary

| Phase | Tasks | Key Changes |
|-------|-------|-------------|
| 1. Data Fixes | 6 tasks | Archetype corrections, synergy additions, matchup audit |
| 2. Scoring Rebalance | 5 tasks | Combined matchup+counter, new weights, ban Tier 1 meta, eval tracking |
| 3. Backend API | 3 tasks | Supplemental RoleGroupedRecommendations model and endpoints |
| 4. Frontend UI | 6 tasks | UI hierarchy design, RoleRecommendationPanel (alternative view), expandable scores, tooltips |
| 5. Integration | 2 tasks | Testing & documentation |

**Total: 22 tasks**

**New Weight Distribution:**
```
archetype:       0.30 (team composition - highest, never reduced)
meta:            0.30 (champion power)
matchup_counter: 0.25 (combined matchups)
proficiency:     0.15 (player comfort - lowest)
---
synergy:         MULTIPLIER (not a base weight - applied to final score)
```

**Synergy Design Decision:**
Synergy is applied as a multiplier to the final score, NOT as a base weight component.
This avoids double-counting and correctly models synergy as a team-wide scaling factor.

**Role-Grouped View Design:**
- Role-grouped (top 2 per role) is SUPPLEMENTAL, not primary
- Primary recommendation: Top 5 overall (phase-optimized)
- Supplemental view: By-role grouping (toggle, secondary placement)
- Evaluation tracks both separately to measure relative value

**Decision Audit Trail:**
- Domain expert feedback documented in plan header
- All weight changes have rationale in commit messages
- Archetype weight is never reduced (team identity priority)
- Data fixes tracked via audit scripts
- Evaluation results saved for primary vs supplemental comparison
