# Computed Datasets Design

**Date:** 2026-01-25
**Status:** Draft
**Prerequisite:** Run CSV export on v2 raw data first

---

## Overview

This document defines the computed knowledge files needed for the recommendation engine.

### Data Sources

| Source | Type | Coverage |
|--------|------|----------|
| `player_game_stats.csv` | Raw game data | 100% (v3.43+ has full stats) |
| `draft_actions.csv` | Pick/ban history | 100% |
| `games.csv` + `series.csv` | Game metadata + dates + patch | 100% |
| `knowledge_base.json` | Champion mechanics | 172 champions |
| `synergies.json` | Curated mechanical synergies | 164 synergies |
| `player_roles.json` | Player role mapping | 347 players (Leaguepedia) |

### Schema Version Coverage

| Version | Series Count | Available Fields |
|---------|--------------|------------------|
| v3.43+ | 693 (45%) | ALL: roles, moneyPerMinute, damageDealt, visionScore, kdaRatio, killParticipation |
| v3.36-3.42 | ~100 (6%) | moneyPerMinute, killParticipation |
| v3.30-3.35 | ~70 (5%) | visionScore, kdaRatio |
| Older | ~684 (44%) | Basic: kills, deaths, assists, netWorth only |

---

## Patch-Based Lookback Strategy

**Why patch-based, not time-based:**
- Champions get buffed/nerfed each patch - a 3-month-old game may be irrelevant if the champion was changed
- Meta shifts happen at patch boundaries, not gradually over time
- Player proficiency on a reworked champion resets to zero at the rework patch
- "Current meta" = last 2-3 patches, not "last 3 months"

### Patch Distance Weighting

Each game is weighted by how far its patch is from the current patch:

```
current_patch:     1.0 weight
1-2 patches ago:   0.9 weight
3-5 patches ago:   0.7 weight
6-10 patches ago:  0.5 weight
10+ patches ago:   0.3 weight
rework boundary:   0.0 (exclude entirely)
```

**Example:** Caps on Orianna with 5 games across patches:
- 2 games on 14.24 (current) → 2.0 weighted
- 1 game on 14.22 (2 ago) → 0.9 weighted
- 2 games on 14.15 (9 ago) → 1.0 weighted
- **Total: 3.9 weighted games** (recent games count more, but volume still matters)

### Analysis-Specific Lookback

| Analysis Type | Patch Window | Rationale |
|---------------|--------------|-----------|
| **Meta stats** | Last 2-3 patches | Current meta only |
| **Player proficiency** | All patches, weighted by distance | Habits persist but context changes |
| **Matchups** | All patches post-rework | Need sample size, mechanics stable |
| **Synergies** | All patches post-rework | Combo mechanics don't change |
| **Role baselines** | Last 5-6 patches | Role meta evolves slower |

### Existing: rework_patch_mapping.json

Already created by domain expert. Contains all champion reworks with Riot version format:

```json
{
  "Skarner": ["V4.2", "V4.10", "V5.16", "V14.7"],
  "Aurelion Sol": ["V13.3"],
  "Lee Sin": ["V5.6", "V8.14", "V8.19", "V14.9"],
  ...
}
```

**Recent reworks relevant to our 2024-2025 data:**
- V14.x: Skarner, Lee Sin, Corki, Janna, Teemo
- V13.x: Aurelion Sol, Yuumi, Neeko, Rell, Jax

**Usage:** For each champion, use the LATEST rework patch as the filter boundary.

### To Generate: patch_info.json

Computed from games.csv patch_version field:

```json
{
  "metadata": {
    "generated_at": "2026-01-25T...",
    "current_patch": "14.24"
  },
  "patches": [
    { "patch": "14.24", "games_in_data": 245 },
    { "patch": "14.23", "games_in_data": 312 },
    { "patch": "14.22", "games_in_data": 287 }
  ]
}
```

### Patch Distance Calculation

```sql
-- Helper: Convert patch string to numeric for distance calc
-- "14.24" -> 1424, "14.3" -> 1403
CREATE MACRO patch_to_num(p) AS
  CAST(SPLIT_PART(p, '.', 1) AS INT) * 100 +
  CAST(SPLIT_PART(p, '.', 2) AS INT);

-- Calculate patch distance weight
CREATE MACRO patch_weight(game_patch, current_patch) AS
  CASE
    WHEN patch_to_num(game_patch) = patch_to_num(current_patch) THEN 1.0
    WHEN patch_to_num(current_patch) - patch_to_num(game_patch) <= 2 THEN 0.9
    WHEN patch_to_num(current_patch) - patch_to_num(game_patch) <= 5 THEN 0.7
    WHEN patch_to_num(current_patch) - patch_to_num(game_patch) <= 10 THEN 0.5
    ELSE 0.3
  END;
```

---

## 1. role_baselines.json

**Purpose:** Normalization baselines for comparing player stats within roles.

**Why needed:** A support's 2.0 KDA means something different than a top laner's 2.0 KDA.

```json
{
  "metadata": {
    "generated_at": "2026-01-25T...",
    "games_analyzed": 3447,
    "min_games_per_role": 500
  },
  "baselines": {
    "TOP": {
      "kda_ratio": { "mean": 2.8, "stddev": 1.2, "p25": 1.9, "p50": 2.6, "p75": 3.5 },
      "kill_participation": { "mean": 58.0, "stddev": 12.0 },
      "damage_dealt": { "mean": 22000, "stddev": 8000 },
      "vision_score": { "mean": 28, "stddev": 10 },
      "net_worth": { "mean": 12500, "stddev": 2500 },
      "money_per_minute": { "mean": 420, "stddev": 60 }
    },
    "JNG": { ... },
    "MID": { ... },
    "ADC": { ... },
    "SUP": { ... }
  }
}
```

**Computation:**
```sql
-- Using DuckDB on player_game_stats.csv
SELECT
  role,
  AVG(kda_ratio) as kda_mean,
  STDDEV(kda_ratio) as kda_stddev,
  PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY kda_ratio) as kda_p25,
  PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY kda_ratio) as kda_p50,
  PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY kda_ratio) as kda_p75,
  -- repeat for other metrics
FROM player_game_stats
WHERE role IS NOT NULL
  AND kda_ratio IS NOT NULL  -- only v3.43+ has this field populated
GROUP BY role
```

**Note:** For older schema data, calculate kda_ratio = (kills + assists) / NULLIF(deaths, 0)

---

## 2. player_proficiency.json

**Purpose:** How well does each player perform on each champion?

**Why needed:** Core of recommendation engine - "Should Caps pick Aurora?"

```json
{
  "metadata": {
    "generated_at": "2026-01-25T...",
    "current_patch": "14.24",
    "patch_weights": {
      "current": 1.0,
      "1-2_patches_ago": 0.9,
      "3-5_patches_ago": 0.7,
      "6-10_patches_ago": 0.5,
      "10+_patches_ago": 0.3
    }
  },
  "proficiencies": {
    "Caps": {
      "Orianna": {
        "games_raw": 23,
        "games_weighted": 18.5,
        "win_rate": 0.67,
        "win_rate_weighted": 0.71,
        "kda_normalized": 1.45,
        "kp_normalized": 0.82,
        "confidence": "HIGH",
        "last_patch": "14.24",
        "patches_played": ["14.24", "14.23", "14.20", "14.15"]
      },
      "Aurora": {
        "games_raw": 2,
        "games_weighted": 2.0,
        "win_rate": 0.50,
        "win_rate_weighted": 0.50,
        "kda_normalized": null,
        "kp_normalized": null,
        "confidence": "LOW",
        "last_patch": "14.22",
        "patches_played": ["14.22"]
      }
    }
  }
}
```

**Computation:**
```sql
WITH patch_weighted AS (
  SELECT
    pgs.player_name,
    pgs.champion_name,
    pgs.team_won,
    pgs.kda_ratio,
    pgs.kill_participation,
    g.patch_version,
    -- Patch distance weighting (assuming current_patch = '14.24')
    CASE
      WHEN g.patch_version = '14.24' THEN 1.0
      WHEN patch_to_num('14.24') - patch_to_num(g.patch_version) <= 2 THEN 0.9
      WHEN patch_to_num('14.24') - patch_to_num(g.patch_version) <= 5 THEN 0.7
      WHEN patch_to_num('14.24') - patch_to_num(g.patch_version) <= 10 THEN 0.5
      ELSE 0.3
    END as patch_weight
  FROM player_game_stats pgs
  JOIN games g ON pgs.game_id = g.id
  -- Exclude games before champion rework (join with reworks table)
  WHERE NOT EXISTS (
    SELECT 1 FROM champion_reworks cr
    WHERE cr.champion_name = pgs.champion_name
    AND g.patch_version < cr.rework_patch
  )
)
SELECT
  player_name,
  champion_name,
  COUNT(*) as games_raw,
  SUM(patch_weight) as games_weighted,
  AVG(CASE WHEN team_won THEN 1 ELSE 0 END) as win_rate,
  SUM(CASE WHEN team_won THEN patch_weight ELSE 0 END) / SUM(patch_weight) as win_rate_weighted,
  AVG(kda_ratio) as avg_kda,
  MAX(patch_version) as last_patch,
  LIST(DISTINCT patch_version ORDER BY patch_version DESC) as patches_played
FROM patch_weighted
GROUP BY player_name, champion_name
HAVING COUNT(*) >= 1
```

**Confidence levels:**
- HIGH: games_weighted >= 8
- MEDIUM: games_weighted >= 4
- LOW: games_weighted >= 1
- NO_DATA: 0 games

---

## 3. champion_synergies.json (Statistical)

**Purpose:** Quantitative synergy scores based on game outcomes.

**Different from synergies.json:** That's curated mechanical synergies (qualitative). This is statistical win rate analysis.

```json
{
  "metadata": {
    "generated_at": "2026-01-25T...",
    "min_games_together": 15,
    "synergy_pairs_count": 850
  },
  "synergies": {
    "Orianna": {
      "Nocturne": {
        "games_together": 127,
        "win_rate_together": 0.62,
        "baseline_expected": 0.55,
        "synergy_delta": 0.07,
        "synergy_score": 0.85,
        "co_pick_lift": 1.55,
        "has_mechanical_synergy": true
      },
      "Lee Sin": {
        "games_together": 89,
        "win_rate_together": 0.54,
        "baseline_expected": 0.55,
        "synergy_delta": -0.01,
        "synergy_score": 0.48,
        "co_pick_lift": 0.92,
        "has_mechanical_synergy": false
      }
    }
  }
}
```

**Computation approach:**

1. **Calculate baseline expected win rate:**
   - For each champion pair, compare against same-tier alternatives
   - "Does Aurora win MORE with Nocturne than with other A-tier junglers?"

2. **Calculate co-pick lift:**
   - How often are they picked together vs expected by individual pick rates?

3. **Link to curated synergies:**
   - Set `has_mechanical_synergy: true` if pair exists in synergies.json

```sql
-- Step 1: Get all same-team champion pairs
WITH team_pairs AS (
  SELECT
    g.id as game_id,
    a.champion_name as champ_a,
    b.champion_name as champ_b,
    a.team_won
  FROM player_game_stats a
  JOIN player_game_stats b
    ON a.game_id = b.game_id
    AND a.team_id = b.team_id
    AND a.champion_name < b.champion_name  -- avoid duplicates
)
SELECT
  champ_a,
  champ_b,
  COUNT(*) as games_together,
  AVG(CASE WHEN team_won THEN 1 ELSE 0 END) as win_rate_together
FROM team_pairs
GROUP BY champ_a, champ_b
HAVING COUNT(*) >= 15
```

---

## 4. champion_counters.json

**Purpose:** Matchup win rates for lane and team counters.

```json
{
  "metadata": {
    "generated_at": "2026-01-25T...",
    "min_matchup_games": 10
  },
  "counters": {
    "Syndra": {
      "vs_lane": {
        "Azir": { "games": 45, "win_rate": 0.48, "confidence": "HIGH" },
        "Aurora": { "games": 12, "win_rate": 0.42, "confidence": "MEDIUM" }
      },
      "vs_team": {
        "Azir": { "games": 156, "win_rate": 0.51 },
        "Aurora": { "games": 67, "win_rate": 0.49 }
      }
    }
  }
}
```

**Computation:**

```sql
-- Lane matchups (same role, opposite teams)
WITH lane_matchups AS (
  SELECT
    a.champion_name as our_champ,
    a.role as our_role,
    b.champion_name as enemy_champ,
    a.team_won as we_won
  FROM player_game_stats a
  JOIN player_game_stats b
    ON a.game_id = b.game_id
    AND a.team_id != b.team_id
    AND a.role = b.role  -- same lane
  WHERE a.role IS NOT NULL
)
SELECT
  our_champ,
  our_role,
  enemy_champ,
  COUNT(*) as games,
  AVG(CASE WHEN we_won THEN 1 ELSE 0 END) as win_rate
FROM lane_matchups
GROUP BY our_champ, our_role, enemy_champ
HAVING COUNT(*) >= 10
```

---

## 5. flex_champions.json

**Purpose:** Role probability distribution for flex picks.

```json
{
  "metadata": {
    "generated_at": "2026-01-25T...",
    "source": "player_game_stats role field + knowledge_base positions"
  },
  "flex_picks": {
    "Aurora": {
      "MID": 0.65,
      "TOP": 0.35,
      "is_flex": true,
      "games_total": 234
    },
    "Tristana": {
      "ADC": 0.85,
      "MID": 0.15,
      "is_flex": true,
      "games_total": 178
    },
    "Syndra": {
      "MID": 1.0,
      "is_flex": false,
      "games_total": 312
    }
  }
}
```

**Computation:**

```sql
-- From player_game_stats (v3.43+ has roles field)
SELECT
  champion_name,
  role,
  COUNT(*) as games,
  COUNT(*) * 1.0 / SUM(COUNT(*)) OVER (PARTITION BY champion_name) as role_pct
FROM player_game_stats
WHERE role IS NOT NULL
GROUP BY champion_name, role
```

**Fallback for older data:**
- Join with player_roles.json to infer role from player's primary position
- Use knowledge_base.json `positions` field as secondary source

---

## 6. skill_transfers.json

**Purpose:** Champion similarity for surprise pick detection.

**Computation approach:** Mine co-play patterns from player pools.

```json
{
  "metadata": {
    "generated_at": "2026-01-25T...",
    "min_co_play_rate": 0.3,
    "min_player_games": 5
  },
  "transfers": {
    "Aurora": {
      "similar_champions": [
        { "champion": "Ahri", "co_play_rate": 0.78, "score": 0.85 },
        { "champion": "LeBlanc", "co_play_rate": 0.71, "score": 0.78 },
        { "champion": "Akali", "co_play_rate": 0.65, "score": 0.72 }
      ]
    }
  }
}
```

**Computation:**

```sql
-- Build player champion pools
WITH player_pools AS (
  SELECT
    player_name,
    champion_name,
    COUNT(*) as games
  FROM player_game_stats
  GROUP BY player_name, champion_name
  HAVING COUNT(*) >= 3
),
-- Count co-play (players who play both champions)
co_play AS (
  SELECT
    a.champion_name as champ_a,
    b.champion_name as champ_b,
    COUNT(DISTINCT a.player_name) as players_both
  FROM player_pools a
  JOIN player_pools b
    ON a.player_name = b.player_name
    AND a.champion_name < b.champion_name
  GROUP BY a.champion_name, b.champion_name
),
-- Get total players per champion
champ_players AS (
  SELECT champion_name, COUNT(DISTINCT player_name) as total_players
  FROM player_pools
  GROUP BY champion_name
)
SELECT
  cp.champ_a,
  cp.champ_b,
  cp.players_both,
  cp.players_both * 1.0 / LEAST(ca.total_players, cb.total_players) as co_play_rate
FROM co_play cp
JOIN champ_players ca ON cp.champ_a = ca.champion_name
JOIN champ_players cb ON cp.champ_b = cb.champion_name
WHERE cp.players_both >= 3
ORDER BY co_play_rate DESC
```

---

## 7. meta_stats.json

**Purpose:** Current meta tier for champions (pick/ban rates, win rates).

**Patch window:** Last 2-3 patches only (current meta).

```json
{
  "metadata": {
    "generated_at": "2026-01-25T...",
    "current_patch": "14.24",
    "patches_included": ["14.24", "14.23", "14.22"],
    "games_analyzed": 1200
  },
  "champions": {
    "Aurora": {
      "pick_rate": 0.32,
      "ban_rate": 0.45,
      "presence": 0.77,
      "win_rate": 0.52,
      "tier": "S",
      "tier_score": 0.92,
      "games": 156
    },
    "Syndra": {
      "pick_rate": 0.28,
      "ban_rate": 0.12,
      "presence": 0.40,
      "win_rate": 0.51,
      "tier": "A",
      "tier_score": 0.75,
      "games": 134
    }
  }
}
```

**Computation:**

```sql
-- Filter to last 3 patches (current meta window)
WITH recent_games AS (
  SELECT g.id, g.patch_version
  FROM games g
  WHERE patch_to_num(g.patch_version) >= patch_to_num('14.22')  -- current - 2
),
picks AS (
  SELECT champion_name, COUNT(*) as picks
  FROM draft_actions da
  JOIN recent_games rg ON da.game_id = rg.id
  WHERE action_type = 'pick'
  GROUP BY champion_name
),
bans AS (
  SELECT champion_name, COUNT(*) as bans
  FROM draft_actions da
  JOIN recent_games rg ON da.game_id = rg.id
  WHERE action_type = 'ban'
  GROUP BY champion_name
),
wins AS (
  SELECT
    pgs.champion_name,
    COUNT(*) as games,
    SUM(CASE WHEN pgs.team_won THEN 1 ELSE 0 END) as wins
  FROM player_game_stats pgs
  JOIN recent_games rg ON pgs.game_id = rg.id
  GROUP BY pgs.champion_name
)
SELECT
  COALESCE(p.champion_name, b.champion_name) as champion_name,
  COALESCE(p.picks, 0) as picks,
  COALESCE(b.bans, 0) as bans,
  w.games,
  w.wins * 1.0 / NULLIF(w.games, 0) as win_rate
FROM picks p
FULL OUTER JOIN bans b ON p.champion_name = b.champion_name
LEFT JOIN wins w ON COALESCE(p.champion_name, b.champion_name) = w.champion_name
```

**Tier calculation:**
- S: presence >= 0.6 AND win_rate >= 0.50
- A: presence >= 0.3 AND win_rate >= 0.48
- B: presence >= 0.1 AND win_rate >= 0.46
- C: everything else

---

## 8. player_tendencies.json

**Purpose:** Player playstyle indicators for style fit matching.

```json
{
  "metadata": {
    "generated_at": "2026-01-25T...",
    "min_games": 20
  },
  "tendencies": {
    "Caps": {
      "games_analyzed": 156,
      "aggression": 0.78,
      "carry_focus": 0.85,
      "vision_control": 0.42,
      "early_game": 0.71,
      "preferred_damage_type": "magic",
      "preferred_classes": ["Mage", "Assassin"]
    }
  }
}
```

**Computation:**

```sql
WITH player_stats AS (
  SELECT
    player_name,
    role,
    COUNT(*) as games,
    AVG(kills) as avg_kills,
    AVG(deaths) as avg_deaths,
    AVG(kda_ratio) as avg_kda,
    AVG(kill_participation) as avg_kp,
    AVG(vision_score) as avg_vision,
    SUM(CASE WHEN first_kill THEN 1 ELSE 0 END) * 1.0 / COUNT(*) as first_blood_pct,
    AVG(damage_dealt) as avg_damage
  FROM player_game_stats
  GROUP BY player_name, role
  HAVING COUNT(*) >= 20
)
SELECT
  ps.*,
  -- Normalize against role baselines
  (ps.avg_kda - rb.kda_mean) / rb.kda_stddev as kda_normalized,
  (ps.avg_kp - rb.kp_mean) / rb.kp_stddev as kp_normalized
FROM player_stats ps
JOIN role_baselines rb ON ps.role = rb.role
```

---

## Integration with Existing Files

### From knowledge_base.json
- Champion `positions` and `flex_positions` → seed flex_champions.json
- Champion `classification.primary_class` → player_tendencies preferred_classes
- Champion `comp_fit` scores → used in recommendation scoring

### From synergies.json
- Link statistical synergies to mechanical synergies via `has_mechanical_synergy` flag
- Use `strength` (S/A/B/C) as a boost to statistical synergy score
- Include `countered_by` in recommendation warnings

### From player_roles.json
- Primary role mapping for older games without API role field
- Seed player_tendencies with role information

---

## Implementation Order

1. **Run CSV export** on v2 raw data (prerequisite)
2. **role_baselines.json** - needed for normalization (no dependencies)
3. **meta_stats.json** - needed for tier scores (no dependencies)
4. **flex_champions.json** - combine API roles + knowledge_base (needs CSV export)
5. **player_proficiency.json** - needs role_baselines for normalization
6. **champion_counters.json** - straightforward matchup calculation
7. **champion_synergies.json** - needs synergies.json for mechanical link
8. **skill_transfers.json** - co-play mining
9. **player_tendencies.json** - needs role_baselines + knowledge_base

---

## Open Questions

1. ~~**Meta window:** Last 2-3 patches proposed~~ ✅ Confirmed
2. ~~**Patch weight curve:** (1.0 → 0.9 → 0.7 → 0.5 → 0.3)~~ ✅ Confirmed
3. ~~**Rework list:**~~ ✅ Created: `rework_patch_mapping.json`
4. **Minimum sample sizes:** Current proposal:
   - Matchups: 10 games
   - Synergies: 15 games together
   - Proficiency: 1 game (but confidence varies)
5. **Handling missing data:** For older schema games without full stats, use calculated values or exclude?
6. **Synergy score formula:** `(normalized_delta * 0.6) + (co_pick_lift * 0.4)` - need to validate
