# MVP Design Decisions

This document captures the reasoning process, experiments, and final design decisions made during the development of Ban Teemo, a League of Legends draft assistant.

## Project Timeline Overview

| Phase | Dates | Focus |
|-------|-------|-------|
| Foundation | Jan 23-25 | Replay infrastructure, UI components, data architecture |
| Recommendation Engine | Jan 26-27 | Multi-factor scoring system, team evaluation |
| Draft Simulator | Jan 27-29 | Interactive practice mode with AI opponents |
| Quality & Refinement | Jan 29-30 | Bug fixes, data quality, UI polish |
| Advanced Features | Jan 31-Feb 2 | LLM insights, tournament meta, draft quality scoring |

---

## 1. Data Architecture

### Decision: GitHub Releases for Large Data Files

**Problem:** The project requires ~50MB+ of CSV data and pre-built DuckDB files, too large for git tracking.

**Options Considered:**
1. Git LFS - requires LFS quota, complicates cloning
2. S3/Cloud storage - requires AWS credentials
3. GitHub Releases - free, authenticated via `gh` CLI, semantic versioning

**Decision:** GitHub Releases with `gh` CLI download script.

**Rationale:**
- Zero cost for public repos
- Semantic versioning (`data-v1.0.0`, `v0.4.0`) tracks data changes
- `gh` CLI handles auth for private repos
- Tarball compression reduces download size

**Final State:**
- Release: `v0.4.0` (latest)
- Contents: CSVs, DuckDB database, replay metadata
- Download: `./scripts/download-data.sh` or `make setup-data`

### Decision: Patch-Based Weighting (Not Time-Based)

**Problem:** Pro match data spans multiple patches with significant balance changes.

**Options Considered:**
1. Time-based decay - recent = higher weight
2. Patch-based weighting - current patch = highest weight

**Decision:** Patch-based weighting.

**Rationale:**
- Balance patches fundamentally change champion viability
- A champion's 60% win rate on patch 14.1 may drop to 45% after nerfs on 14.2
- Time alone doesn't capture meta shifts

**Weights Applied:**
| Patch Distance | Weight |
|----------------|--------|
| Current | 1.0 |
| 1-2 ago | 0.9 |
| 3-5 ago | 0.7 |
| 6-10 ago | 0.5 |
| 10+ ago | 0.3 |

---

## 2. Recommendation Engine Architecture

### Decision: Synergy as Multiplier (Not Additive Component)

**Problem:** How should team synergy factor into champion recommendations?

**Options Considered:**
1. Additive component - synergy as 15-20% of base score
2. Multiplier - synergy scales the final score

**Decision:** Multiplier approach.

**Formula:**
```
final_score = base_score × synergy_multiplier
synergy_multiplier = 1.0 + (synergy_score - 0.5) × 0.5
```

**Rationale:**
- Prevents weak picks from being "rescued" by high synergy
- A terrible champion with great synergy is still a terrible pick
- Synergy amplifies good picks rather than creating false positives
- Multiplier range: 0.75x (anti-synergy) to 1.25x (perfect synergy)

### Decision: Tournament-First Scoring Weights

**Problem:** How to weight different scoring components for pro play recommendations?

**Experiments:**
- Initial weights (Jan 26): Meta 25%, Proficiency 35%, Matchup 25%, Counter 15%
- Mid iteration: Over-weighted proficiency led to comfort picks over power picks
- Final iteration: Tournament data as primary signal

**Final Weights (Picks):**
| Component | Weight | Rationale |
|-----------|--------|-----------|
| Tournament Priority | 25% | "Pick contested champions" - role-agnostic contestation |
| Tournament Performance | 20% | "Pick winners" - role-specific adjusted win rate |
| Matchup/Counter | 25% | "Don't feed" - combined lane + team matchups |
| Archetype | 15% | Team composition fit |
| Proficiency | 15% | Player comfort (lowest - "pros can play anything") |

**Phase-Adjusted Weights:**
- **Early blind picks:** Priority +5%, Matchup -10%, Archetype +10%
- **Late counter-picks:** Priority -10%, Matchup +10%, Proficiency -5%

### Decision: Role-Phase Prior

**Problem:** Certain roles are picked at specific phases in pro drafts.

**Observation:** Analyzing 68,529 draft actions revealed clear patterns:
- ADC/Support: Often picked early (P1/P2)
- Mid/Jungle: Flex picks, mid draft
- Top: Often saved for counter-pick

**Implementation:**
- `RolePhaseScorer` applies multipliers based on pick order
- Support in early P1: ~0.40x penalty (unusual)
- Jungle in P2: ~0.63x penalty
- This guides recommendations toward realistic draft patterns

### Decision: Data Confidence Redistribution

**Problem:** Missing data (NO_DATA) returns 0.5 defaults, which can dominate scoring.

**Solution:** When data is unavailable, reduce that component's weight and redistribute to components with actual data.

**Example:**
```python
if prof_conf == "NO_DATA":
    redistribute = weights["proficiency"] * 0.8
    weights["proficiency"] *= 0.2  # Keep 20% of original weight
    weights["tournament_priority"] += redistribute * 0.4
    weights["tournament_performance"] += redistribute * 0.3
    weights["matchup_counter"] += redistribute * 0.3
```

**Rationale:** Prevents neutral 0.5 defaults from having outsized influence on final scores.

---

## 3. Ban Recommendation System

### Decision: Tiered Priority System

**Problem:** Which champions should be banned first?

**Phase 1 Tiers:**
| Tier | Condition | Bonus |
|------|-----------|-------|
| T1 Signature Power | High meta + high proficiency + in pool | +10% |
| T2 Meta Power | High presence/tournament priority | +5% |
| T3 Comfort Pick | High proficiency but lower meta | +3% |
| T4 General | Everything else | +0% |

**Phase 2 Tiers:**
| Tier | Condition | Bonus |
|------|-----------|-------|
| T1 Counter & Pool | Counters our picks + in enemy pool | +20% |
| T2 Archetype & Pool | Completes enemy comp + in pool | +15% |
| T3 Counter Only | Counters our picks | +10% |
| T4 Contextual | General archetype/synergy counter | +0% |

**Rationale:**
- Phase 1: Deny global power picks and flex threats
- Phase 2: Strategic disruption based on draft context

---

## 4. Draft Simulator Design

### Decision: REST API (Not WebSocket)

**Problem:** Should the simulator use WebSocket like replay mode?

**Decision:** REST API for simulator.

**Rationale:**
- Simulator is turn-based, not streaming
- No need for real-time push updates
- Simpler client implementation
- Easier state management

### Decision: AI Pick Generation Priority Cascade

**Problem:** How should the AI opponent select picks?

**Priority Order:**
1. **Reference game** - Randomly selected from team's last 20 games
2. **Fallback games** - Find next valid action at/after current sequence
3. **Weighted random** - Based on historical pick frequency

**Rationale:**
- Reference games produce realistic drafts
- Fallback ensures AI never gets stuck
- Weighted random as last resort maintains meta-appropriate picks

### Decision: Fearless Mode Support

**Implementation:** Track previously picked champions per team across a series.

**Rationale:**
- Fearless (no repeat picks) is common in competitive play
- Storing per-series pick history enables accurate practice

---

## 5. Team Evaluation & Draft Quality

### Decision: Archetype-Based Team Identity

**Archetypes Defined:**
| Archetype | Characteristics | Counter |
|-----------|-----------------|---------|
| Engage | Strong initiation | Poke/Disengage |
| Split | Side lane pressure | Teamfight |
| Teamfight | 5v5 combat strength | Split push |
| Protect | Carry protection | Engage |
| Pick | Catch potential | Grouped teams |

**Scoring:**
- Team archetype derived from champion contributions
- Composition score = (synergy_score + archetype_alignment) / 2
- Matchup advantage calculated via RPS-style counter matrix

### Decision: Draft Quality Scoring

**Components:**
- Synergy score (pair-wise champion synergies)
- Archetype alignment (team identity coherence)
- Composition score (combined metric)

**Display:**
- Converted to points (score × 100) for user-friendly display
- Draft quality message sent via WebSocket at draft_complete

---

## 6. Frontend Architecture

### Decision: Component Organization by Mode

**Structure:**
```
components/
├── replay/           # Replay mode components
│   ├── DraftBoard/
│   ├── ReplayControls/
│   └── ActionLog/
├── simulator/        # Simulator mode components
│   ├── ChampionPool/
│   ├── SimulatorBanRow/
│   └── SimulatorInsightPanel/
└── shared/           # Shared components
    ├── ChampionPortrait/
    ├── TeamPanel/
    └── PhaseIndicator/
```

**Rationale:**
- Clear separation between modes
- Shared components avoid duplication
- Easy to add new modes in the future

### Decision: Champion Icon Virtualization

**Problem:** Rendering 162 champion icons caused performance issues.

**Solution:** `@tanstack/react-virtual` for virtualized grid.

**Impact:**
- Only visible icons rendered
- Smooth scrolling even with role filters
- Memory usage reduced significantly

---

## 7. Knowledge Files

### Final File Inventory

| File | Type | Description |
|------|------|-------------|
| `meta_stats.json` | Generated | Pick/ban rates, win rates, meta tiers |
| `player_proficiency.json` | Generated | Player-champion performance (1.9MB) |
| `matchup_stats.json` | Generated | Role-specific matchup win rates |
| `champion_synergies.json` | Generated | Statistical synergy scores |
| `champion_role_history.json` | Generated | Role distributions per patch |
| `skill_transfers.json` | Generated | Similar champions from co-play |
| `role_baselines.json` | Generated | Statistical baselines for normalization |
| `patch_info.json` | Generated | Patch metadata |
| `role_pick_phase.json` | Generated | Role pick frequency by phase |
| `knowledge_base.json` | Manual | Champion metadata and abilities |
| `synergies.json` | Manual | Curated synergy ratings (S/A/B/C) |
| `archetype_counters.json` | Manual | Team archetype analysis |
| `player_roles.json` | Manual | Authoritative player role mappings |
| `tournament_meta.json` | Manual | Recent tournament pick/ban data |

**Generation:** `scripts/build_computed_datasets.py` processes CSVs into JSON.

---

## 8. Scoring Components (Final Implementation)

### Pick Recommendation Engine

```python
class PickRecommendationEngine:
    BASE_WEIGHTS = {
        "tournament_priority": 0.25,    # Role-agnostic contestation
        "tournament_performance": 0.20, # Role-specific adjusted winrate
        "matchup_counter": 0.25,        # Combined lane + team matchups
        "archetype": 0.15,              # Team composition fit
        "proficiency": 0.15,            # Player comfort
    }
    SYNERGY_MULTIPLIER_RANGE = 0.5  # 0.75x to 1.25x range
```

### Core Scorers

| Scorer | Purpose |
|--------|---------|
| `MetaScorer` | Meta tier, presence, blind pick safety |
| `FlexResolver` | Role probability distribution |
| `ProficiencyScorer` | Player-champion performance |
| `MatchupCalculator` | Lane and team matchup analysis |
| `TournamentScorer` | Tournament priority and performance |
| `RolePhaseScorer` | Role-phase prior multipliers |
| `SkillTransferService` | Similar champion recommendations |

### Enhancement Services

| Service | Purpose |
|---------|---------|
| `ArchetypeService` | Team composition analysis |
| `SynergyService` | Champion pair synergies |
| `TeamEvaluationService` | Strengths/weaknesses assessment |
| `BanRecommendationService` | Ban priority with tiered system |

---

## 9. Experiments and Iterations

### Experiment: Proficiency Weight Reduction

**Hypothesis:** High proficiency weight (35%) leads to comfort picks over power picks.

**Test:** Reduced proficiency to 15%, increased tournament components.

**Result:** Better alignment with pro draft patterns. "Pros can play anything" validated.

### Experiment: Synergy as Additive vs Multiplicative

**Hypothesis:** Additive synergy can rescue weak picks.

**Test:** Compared recommendations with additive (15% weight) vs multiplicative.

**Result:** Multiplicative produced higher quality recommendations. Weak picks with good synergy ranked appropriately lower.

### Experiment: Meta vs Tournament Priority

**Hypothesis:** Statistical meta (presence) differs from tournament priority (contestation).

**Test:** Compared recommendations using meta_scorer.get_top_meta_champions vs tournament_scorer.get_top_priority_champions.

**Result:** Tournament priority better reflects pro priorities. Adopted tournament_priority as primary signal.

---

## 10. Data Coverage

| Metric | Count |
|--------|-------|
| Series | 1,488 |
| Games | 3,446 |
| Draft Actions | 68,529 |
| Players | 445 |
| Teams | 57 |
| Champions | 162 |

**Regions:** LCK (409), LEC (323), LCS (174), LPL (458), International (117)

**Time Range:** January 2024 - September 2025

---

## 11. Key Learnings

1. **Tournament data > statistical meta** - What pros contest matters more than aggregate statistics.

2. **Synergy multiplier > additive** - Prevents synergy from rescuing fundamentally weak picks.

3. **Phase-aware scoring** - Early blind picks need different weights than late counter-picks.

4. **Data confidence matters** - Redistributing weight from missing data prevents 0.5 defaults from dominating.

5. **Role-phase priors** - Pro drafts follow predictable role patterns that can guide recommendations.

6. **Tiered ban priority** - Contextual factors (counters, archetypes) matter more in Phase 2.

---

## 12. Future Considerations

The following features were scoped but not fully implemented:

1. **LLM Reranker** - AI-powered explanations for top recommendations
2. **Tournament Meta Gating** - Using tournament context for meta selection
3. **Smart Enemy Simulator** - More sophisticated AI opponent decision-making
4. **Real-time Match Integration** - Live match data feeds (beyond replay mode)

These represent natural extensions of the current architecture.
