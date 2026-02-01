# Tournament Meta Integration Design

**Date:** 2026-02-01
**Status:** Approved
**Patch:** 26.1

## Overview

Integrate recent tournament data (2026 Winter tournaments) as a distinct scoring component to provide up-to-date pro meta signals in simulator mode. This replaces the existing `meta` component with two new tournament-derived components while keeping data sources clearly separated.

## Problem Statement

1. Current meta data (`meta_stats.json`) is not current enough
2. Proficiency data has been skewed
3. Need stronger signals from actual pro play priority and performance

## Solution

Add two new scoring components derived from tournament data:

- **`tournament_priority`**: Role-agnostic contestation score (how often pros pick/ban)
- **`tournament_performance`**: Role-specific winrate with sample-size adjustment

These replace the `meta` component in simulator mode only.

---

## Data Model

### Source File
`2026_winter_tournaments.csv` with columns:
- Champion ID, Champion, Winrate, Picks, Bans, PrioScore, Wins, Losses, Role

### Generated File
`knowledge/tournament_meta.json`

```json
{
  "metadata": {
    "source": "2026_winter_tournaments.csv",
    "generated_at": "2026-02-01T12:00:00Z",
    "patch": "26.1"
  },
  "champions": {
    "Rumble": {
      "priority": 0.70,
      "roles": {
        "top": { "winrate": 0.56, "picks": 64, "adjusted_performance": 0.56 }
      }
    },
    "Jayce": {
      "priority": 0.86,
      "roles": {
        "top": { "winrate": 1.0, "picks": 1, "adjusted_performance": 0.55 },
        "jungle": { "winrate": 0.47, "picks": 19, "adjusted_performance": 0.47 },
        "mid": { "winrate": 1.0, "picks": 1, "adjusted_performance": 0.55 }
      }
    }
  },
  "defaults": {
    "missing_champion_priority": 0.05,
    "missing_champion_performance": 0.35,
    "note": "Penalty for champions with zero pro presence - traceable for tuning"
  }
}
```

### Key Decisions

| Decision | Value | Rationale |
|----------|-------|-----------|
| Priority is role-agnostic | Max across roles | Bans don't have roles; represents overall contestation |
| Performance is role-specific | Per-role winrate | Jayce jungle (47%) ≠ Jayce top (100% on 1 game) |
| Bans duplicated across roles | Use for priority only | Ban count same regardless of intended role |

---

## Scoring Formulas

### Tournament Performance (Asymmetric Blending)

```python
def calculate_adjusted_performance(winrate: float, picks: int) -> float:
    """
    Adjust winrate based on sample size.

    - High WR + low sample: blend toward 0.5 (reduce false optimism)
    - Low WR + any sample: preserve as warning signal
    - Threshold: 10 picks for full confidence
    """
    if winrate > 0.5 and picks < 10:
        sample_weight = picks / 10
        return sample_weight * winrate + (1 - sample_weight) * 0.5
    return winrate
```

**Examples:**

| Champion | Picks | Raw WR | Adjusted | Reasoning |
|----------|-------|--------|----------|-----------|
| Azir | 82 | 49% | 49% | Enough sample |
| Kai'Sa | 33 | 76% | 76% | Enough sample |
| LeBlanc | 7 | 71% | 65% | Reduced optimism |
| Malzahar | 2 | 100% | 60% | Heavy blend |
| Rell | 38 | 32% | 32% | Warning preserved |
| Mordekaiser | 9 | 11% | 11% | Warning preserved |

### Missing Champion Penalties

```python
# Champions with zero tournament presence
# These values are intentionally conservative - pros avoiding a champion is signal
#
# TUNING NOTE: If recommendations feel too punishing toward off-meta picks,
# adjust these values in tournament_meta.json -> defaults
MISSING_CHAMPION_PRIORITY = 0.05      # Almost never contested
MISSING_CHAMPION_PERFORMANCE = 0.35   # Below average expectation
```

---

## Weight Configuration

### Simulator Mode Base Weights

Replaces existing meta (0.45) with tournament components:

```python
SIMULATOR_BASE_WEIGHTS = {
    "tournament_priority": 0.25,
    "tournament_performance": 0.20,
    "matchup_counter": 0.25,
    "archetype": 0.15,
    "proficiency": 0.15,
}
```

### Aggressive Phase Adjustments

| Component | Base | Early Blind | Late Counter |
|-----------|------|-------------|--------------|
| tournament_priority | 0.25 | 0.30 (+0.05) | 0.15 (-0.10) |
| tournament_performance | 0.20 | 0.15 (-0.05) | 0.25 (+0.05) |
| matchup_counter | 0.25 | 0.15 (-0.10) | 0.35 (+0.10) |
| archetype | 0.15 | 0.25 (+0.10) | 0.15 (0) |
| proficiency | 0.15 | 0.15 (0) | 0.10 (-0.05) |

**Phase conditions:**
- **Early blind**: `pick_count == 0` and no enemy picks
- **Late counter**: `pick_count >= 3` and has enemy picks

**Design rationale:**
- Early draft: Prioritize contested picks (priority) + team identity (archetype)
- Late draft: Prioritize proven performers (performance) + counter-picking (matchup)
- Swings of 0.10-0.15 per component allow counter-picks to overcome raw priority

---

## Ban Recommendations

Add `tournament_priority` to ban scoring:

```python
BAN_WEIGHTS = {
    "tournament_priority": 0.30,  # Highly contested = worth banning
    "meta": 0.15,                 # Reduced - tournament_priority covers this
    "proficiency": 0.25,          # Enemy player comfort
    "archetype_counter": 0.15,    # Deny their team comp
    "synergy_denial": 0.15,       # Break their synergies
}
```

---

## UI Display

Show both tournament components separately in InsightsLog for transparency:

```
┌─────────────────────────────────────────┐
│ Rumble (Top)                    Score: 0.72
├─────────────────────────────────────────┤
│ tournament_priority    ████████░░  0.70 │
│ tournament_performance ██████░░░░  0.56 │
│ matchup_counter        ███████░░░  0.65 │
│ archetype              ██████░░░░  0.55 │
│ proficiency            ████░░░░░░  0.40 │
└─────────────────────────────────────────┘
```

Users can distinguish:
- "Highly contested AND performing well" (both high)
- "Contested but underperforming" (high priority, low performance)
- "Sleeper pick" (low priority, high performance)

---

## Implementation

### New Files

```
scripts/
  build_tournament_meta.py        # CSV → JSON converter

knowledge/
  tournament_meta.json            # Generated output

backend/src/ban_teemo/services/
  scorers/
    tournament_scorer.py          # TournamentScorer class
```

### Modified Files

```
backend/src/ban_teemo/services/
  pick_recommendation_engine.py   # Integrate tournament components
  ban_recommendation_service.py   # Add tournament_priority

deepdraft/src/components/
  InsightsLog/index.tsx           # Display new components
```

### Build Script

```bash
uv run python scripts/build_tournament_meta.py \
  --input 2026_winter_tournaments.csv \
  --patch 26.1 \
  --output knowledge/tournament_meta.json
```

### TournamentScorer Interface

```python
class TournamentScorer:
    def __init__(self, tournament_data_path: str):
        """Load tournament meta JSON."""

    def get_priority(self, champion: str) -> float:
        """Role-agnostic priority score (0.0-1.0)."""

    def get_performance(self, champion: str, role: str) -> float:
        """Role-specific adjusted performance (0.0-1.0)."""

    def get_tournament_scores(self, champion: str, role: str) -> dict:
        """Returns both scores + metadata for UI display."""
```

---

## Scope Boundaries

### In Scope
- Simulator mode only (replaces meta component)
- Pick recommendations with tournament weighting
- Ban recommendations with tournament_priority
- UI display of both components

### Out of Scope
- Replay/live modes (keep existing meta)
- Automatic staleness handling (manual refresh only)
- Archetype boosting (no new data to support it)

---

## Data Freshness

**Approach:** Manual refresh only

- You update the CSV when new tournament data is available
- Run build script to regenerate JSON
- No automatic staleness warnings or decay

---

## Tuning Parameters

All tunable values documented for future adjustment:

| Parameter | Value | Location |
|-----------|-------|----------|
| Sample threshold | 10 picks | `tournament_scorer.py` |
| Missing priority penalty | 0.05 | `tournament_meta.json` → defaults |
| Missing performance penalty | 0.35 | `tournament_meta.json` → defaults |
| Early phase priority boost | +0.05 | `pick_recommendation_engine.py` |
| Late phase matchup boost | +0.10 | `pick_recommendation_engine.py` |

---

## Testing Strategy

1. **Unit tests for TournamentScorer**
   - Correct priority aggregation (max across roles)
   - Asymmetric blending logic
   - Missing champion penalty application

2. **Integration tests for pick recommendations**
   - Phase-based weight adjustments work correctly
   - Tournament components display in output

3. **Manual validation**
   - Run simulator with known matchups
   - Verify high-priority champions surface early
   - Verify counter-picks can beat priority picks in late draft
