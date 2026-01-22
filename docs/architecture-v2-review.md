# Architecture v2 Review - Data & API Analysis

**Date:** 2026-01-21
**Updated:** 2026-01-21
**Scope:** Data evaluation, API design validation, gap analysis
**Dataset:** GRID API 2024-2025 Pro Match Data

---

## 1. Executive Summary

The complete dataset **massively exceeds** all original spec targets, providing an exceptional foundation for the draft assistant. The data now includes **LPL coverage** (458 series) alongside LCK, LEC, and LCS, plus significantly improved field coverage for previously sparse metrics like **patch version (61.5%)**, **damage dealt (61.3%)**, and **vision score (61.3%)**.

| Metric | Spec Target | Previous | **Current** | Status |
|--------|-------------|----------|-------------|--------|
| Series | 200 | 363 | **1,482** | ✅ 7.4x Target |
| Games | 500 | 631 | **3,436** | ✅ 6.9x Target |
| Draft Actions | 10,000 | 12,618 | **68,529** | ✅ 6.9x Target |
| Player Stats | 5,000 | 6,332 | **34,416** | ✅ 6.9x Target |
| Teams | ~30 | 38 | **57** | ✅ 1.9x Target |
| Players | ~150 | 218 | **445** | ✅ 3.0x Target |
| Champions | ~170 | 130 | **162** | ✅ Near Complete |

### Updated Layer Support Status

| Layer | Previous Assessment | **Current Assessment** |
|-------|--------------------|-----------------------|
| Layer 1 (Meta) | ✅ Fully supported | ✅ Fully supported |
| Layer 2 (Tendencies) | ⚠️ Partial (no vision) | ✅ **Mostly supported** (vision 61.3%, damage 61.3%, KP 96.3%) |
| Layer 3 (Proficiency) | ✅ Fully supported | ✅ Fully supported |
| Layer 4 (Relationships) | ✅ Synergies + Counters | ✅ Synergies + Counters both supported |

---

## 2. Data Structure Analysis

### 2.1 Available CSV Tables

```
outputs/full_2024_2025/csv/
├── teams.csv           # 57 teams (id, name)
├── players.csv         # 445 players (id, name, team_id, team_name)
├── champions.csv       # 162 champions (id, name)
├── series.csv          # 1,482 series (id, blue/red_team_id, format, match_date)
├── games.csv           # 3,436 games (id, series_id, game_number, winner_team_id, duration, patch_version)
├── draft_actions.csv   # 68,529 actions (game_id, sequence, action_type, team_id, champion)
└── player_game_stats.csv # 34,416 stats (KDA, role, team_side, damage, vision, etc.)
```

### 2.2 Critical Data Relationships for Matchup Analysis

The key insight is that `player_game_stats` contains **both teams** for each game with `role` and `team_side` columns. This enables matchup detection via self-join:

```
player_game_stats (self-join on game_id)
├── game_id        → Links both teams in same game
├── role           → TOP/JNG/MID/ADC/SUP identifies lane opponents
├── team_side      → "blue" or "red" distinguishes teams
├── team_won       → Outcome for win rate calculation
├── champion_name  → For champion vs champion analysis
└── player_name    → For player vs player analysis
```

### 2.3 Raw JSON Structure (GRID API)

The raw JSON files contain richer data than what's currently extracted:

```json
{
  "seriesState": {
    "teams": [{ "id", "name", "won", "score" }],
    "games": [{
      "draftActions": [{ "sequenceNumber", "type", "drafter", "draftable" }],
      "teams": [{
        "side": "blue|red",
        "won": true|false,
        "kills", "deaths", "structuresDestroyed",
        "objectives": [{ "type": "slayBaron|slayDrake|..." }],
        "players": [{
          "name", "character", "kills", "deaths", "killAssistsGiven"
        }]
      }]
    }]
  }
}
```

---

## 3. Data Quality Assessment

### 3.1 Fields with High Availability (>95%)

| Field | Coverage | Notes |
|-------|----------|-------|
| Draft actions | 100% | Complete 20-action sequences per game |
| Player KDA | 100% | kills, deaths, assists, kda_ratio |
| Role assignment | 98.7% | TOP/JNG/MID/ADC/SUP (1.3% UNKNOWN) |
| Team side | 100% | blue/red correctly captured |
| Game duration | 99% | duration_seconds available |
| Match date | 100% | ISO format timestamps |
| Series format | 100% | best-of-1, best-of-3, best-of-5 |

### 3.2 Fields with Improved/Partial Availability

| Field | Previous | **Current** | Notes |
|-------|----------|-------------|-------|
| **patch_version** | 0.5% | **61.5%** | ✅ Can now filter by meta/patch (patches 14.1-15.18) |
| **tournament_id** | 0% | 0% | ⚠️ Still derivable from team participation (Section 6) |
| **damage_dealt** | 0.5% | **61.3%** | ✅ Damage share analysis now viable |
| **vision_score** | 0.5% | **61.3%** | ✅ Vision-based tendencies now calculable |
| **first_kill (player)** | 5.8% | **79.7%** | ✅ First blood analysis now supported |
| **kill_participation** | N/A | **96.3%** | ✅ New field with excellent coverage |
| **experience_points** | N/A | **61.2%** | ✅ New field for XP analysis |
| **cs/gold** | 0% | 0% | ❌ Still cannot calculate CSD@15 |
| **riot_key** | 0% | 0% | ⚠️ No Data Dragon icon mapping |

### 3.3 Series Format Distribution

```
best-of-3:  895 series (60.4%)
best-of-1:  345 series (23.3%)
best-of-5:  242 series (16.3%)
```

### 3.4 Time Range Coverage

Data spans **January 2024 - September 2025**, covering 5 competitive splits:

| Region | Total Series | Splits Covered |
|--------|--------------|----------------|
| LPL | **458** | Spring 2024, Summer 2024, Winter 2025, Spring 2025, Summer 2025 |
| LCK | **409** | Spring 2024, Summer 2024, Winter 2025, Spring 2025, Summer 2025 |
| LEC | **323** | Spring 2024, Summer 2024, Winter 2025, Spring 2025, Summer 2025 |
| LCS | **174** | Spring 2024, Summer 2024, Winter 2025, Spring 2025, Summer 2025 |
| International | **117** | Various (Winter 2025, Spring 2025, Summer 2025) |

### 3.5 Role Distribution

```
TOP:     8,013 records (23.3%)
ADC:     6,968 records (20.2%)
MID:     6,596 records (19.2%)
SUP:     6,303 records (18.3%)
JNG:     5,846 records (17.0%)
UNKNOWN:   690 records (2.0%)
```

---

## 4. Achievable Analytics (Layer Status)

### 4.1 Layer 1: Champion Meta Strength ✅ FULLY SUPPORTED

```sql
-- Example: Champion tier calculation
SELECT
    champion_name,
    COUNT(*) as total_appearances,
    SUM(CASE WHEN action_type = 'pick' THEN 1 ELSE 0 END) as picks,
    SUM(CASE WHEN action_type = 'ban' THEN 1 ELSE 0 END) as bans,
    ROUND(COUNT(*) * 100.0 / (3436 * 2), 1) as presence_pct,
    CASE
        WHEN COUNT(*) * 100.0 / (3436 * 2) >= 35 THEN 'S'
        WHEN COUNT(*) * 100.0 / (3436 * 2) >= 25 THEN 'A'
        WHEN COUNT(*) * 100.0 / (3436 * 2) >= 15 THEN 'B'
        WHEN COUNT(*) * 100.0 / (3436 * 2) >= 8 THEN 'C'
        ELSE 'D'
    END as tier
FROM draft_actions
GROUP BY champion_name
ORDER BY total_appearances DESC;
```

**Top Meta Champions (Current Dataset):**

| Tier | Champions | Presence |
|------|-----------|----------|
| A | Rumble, Vi, Varus, Kalista, Azir | 25-31% |
| B | Taliyah, Corki, Rell, Poppy, Nautilus, Ezreal, Yone, Alistar, K'Sante, Ashe, Rakan, Sejuani, Renekton, Gwen, Kai'Sa, Leona, Skarner, Maokai, Lucian, Xin Zhao | 15-25% |

**Win Rate Leaders (50+ picks):**
- Twisted Fate: 58.1%
- Aurelion Sol: 57.7%
- Kennen: 57.5%
- Neeko: 57.0%
- Yunara: 56.3%

### 4.2 Layer 2: Player Tendencies ✅ MOSTLY SUPPORTED

**Available metrics:**
- Overall win rate per player
- KDA averages
- Champion pool depth (unique champions played)
- Role consistency
- Head-to-head records vs specific opponents
- **Vision score (61.3% coverage)** - NEW
- **Damage dealt (61.3% coverage)** - NEW
- **Kill participation (96.3% coverage)** - NEW
- **First blood percentage (79.7% coverage)** - Improved

**Missing metrics (spec requirement):**
- CSD@15 (CS differential at 15 min) - Not in GRID data
- Forward percentage - Not in GRID data

```sql
-- Example: Player performance overview
SELECT
    player_name,
    role,
    COUNT(DISTINCT champion_name) as unique_champions,
    COUNT(*) as total_games,
    ROUND(AVG(CASE WHEN team_won = 'True' THEN 1.0 ELSE 0.0 END) * 100, 1) as win_rate,
    ROUND(AVG(kda_ratio), 2) as avg_kda
FROM player_game_stats
GROUP BY player_name, role
HAVING COUNT(*) >= 20
ORDER BY win_rate DESC;
```

**Top Performers by Win Rate (100+ games):**
- Canyon (JNG): 80.1% WR, 7.83 KDA, 156 games
- Chovy (MID): 79.5% WR, 7.75 KDA, 171 games
- Kiin (TOP): 78.8% WR, 5.96 KDA, 184 games
- Caps (MID): 75.4% WR, 6.66 KDA, 122 games
- Hans Sama (ADC): 72.8% WR, 7.57 KDA, 151 games

### 4.3 Layer 3: Player-Champion Proficiency ✅ FULLY SUPPORTED

```sql
-- Example: Player signature champions
SELECT
    player_name,
    champion_name,
    COUNT(*) as games,
    SUM(CASE WHEN team_won = 'True' THEN 1 ELSE 0 END) as wins,
    ROUND(AVG(CASE WHEN team_won = 'True' THEN 1.0 ELSE 0.0 END) * 100, 1) as win_rate,
    ROUND(AVG(kda_ratio), 2) as avg_kda,
    CASE
        WHEN COUNT(*) >= 8 THEN 'HIGH'
        WHEN COUNT(*) >= 4 THEN 'MEDIUM'
        ELSE 'LOW'
    END as confidence
FROM player_game_stats
GROUP BY player_name, champion_name
HAVING COUNT(*) >= 5
ORDER BY games DESC;
```

**Notable Player-Champion Proficiencies (10+ games, 65%+ WR):**

| Player | Champion | Games | Win Rate | KDA | Confidence |
|--------|----------|-------|----------|-----|------------|
| Peanut | Sejuani | 43 | 74.4% | 7.40 | HIGH |
| Kiin | K'Sante | 39 | 79.5% | 5.78 | HIGH |
| Chovy | Corki | 36 | 83.3% | 7.47 | HIGH |
| Faker | Azir | 36 | 75.0% | 5.98 | HIGH |
| Delight | Alistar | 35 | 80.0% | 7.50 | HIGH |
| JackeyLove | Ezreal | 34 | 73.5% | 7.17 | HIGH |
| Peanut | Maokai | 27 | 85.2% | 8.57 | HIGH |
| Bwipo | Renekton | 27 | 81.5% | 4.93 | HIGH |

### 4.4 Layer 4: Champion Relationships ✅ FULLY SUPPORTED (UPDATED)

**Key Discovery**: Both synergies AND counters are fully calculable via self-join on `player_game_stats`.

#### 4.4.1 Synergy Detection (Same-Team Pairs)

```sql
-- Champion pairs with above-baseline win rates (same team)
WITH team_picks AS (
    SELECT game_id, team_id, champion_name
    FROM draft_actions
    WHERE action_type = 'pick'
),
champion_pairs AS (
    SELECT
        t1.game_id, t1.team_id,
        t1.champion_name as champ_a,
        t2.champion_name as champ_b
    FROM team_picks t1
    JOIN team_picks t2 ON t1.game_id = t2.game_id
        AND t1.team_id = t2.team_id
        AND t1.champion_name < t2.champion_name
)
SELECT
    champ_a, champ_b,
    COUNT(*) as games_together,
    SUM(CASE WHEN g.winner_team_id = cp.team_id THEN 1 ELSE 0 END) as wins,
    ROUND(AVG(CASE WHEN g.winner_team_id = cp.team_id THEN 1.0 ELSE 0.0 END) * 100, 1) as win_rate,
    ROUND((AVG(CASE WHEN g.winner_team_id = cp.team_id THEN 1.0 ELSE 0.0 END) - 0.5) * 100, 1) as synergy_delta
FROM champion_pairs cp
JOIN games g ON cp.game_id = g.id
GROUP BY champ_a, champ_b
HAVING COUNT(*) >= 5
ORDER BY synergy_delta DESC;
```

**Top Synergies (15+ games):**

| Pair | Games | Win Rate | Synergy Delta |
|------|-------|----------|---------------|
| Naafiri + Neeko | 18 | 83.3% | +33.3% |
| Annie + Rakan | 29 | 82.8% | +32.8% |
| Alistar + Kennen | 17 | 82.4% | +32.4% |
| Neeko + Sylas | 21 | 81.0% | +31.0% |
| Galio + Poppy | 15 | 80.0% | +30.0% |
| Nami + Taliyah | 19 | 78.9% | +28.9% |
| Nidalee + Yone | 31 | 74.2% | +24.2% |

#### 4.4.2 Counter Detection (Opponent Matchups) ✅ NEW

```sql
-- Champion vs Champion matchups by role (opposing teams)
WITH matchups AS (
    SELECT
        pgs1.role,
        pgs1.champion_name as champ1,
        pgs2.champion_name as champ2,
        pgs1.team_won
    FROM player_game_stats pgs1
    JOIN player_game_stats pgs2
        ON pgs1.game_id = pgs2.game_id
        AND pgs1.role = pgs2.role              -- Same lane position
        AND pgs1.team_side != pgs2.team_side   -- Opposing teams
    WHERE pgs1.role NOT IN ('', 'UNKNOWN')
      AND pgs1.champion_name < pgs2.champion_name  -- Avoid duplicates
)
SELECT
    role,
    champ1,
    champ2,
    COUNT(*) as games,
    SUM(CASE WHEN team_won = 'True' THEN 1 ELSE 0 END) as champ1_wins,
    SUM(CASE WHEN team_won = 'False' THEN 1 ELSE 0 END) as champ2_wins,
    ROUND(AVG(CASE WHEN team_won = 'True' THEN 1.0 ELSE 0.0 END) * 100, 1) as champ1_wr
FROM matchups
GROUP BY role, champ1, champ2
HAVING COUNT(*) >= 5
ORDER BY games DESC;
```

**Top Role-Specific Matchups (20+ games):**

| Role | Matchup | Games | Champ1 WR | Interpretation |
|------|---------|-------|-----------|----------------|
| SUP | Nautilus vs Rell | 199 | 43.2% | Rell favored |
| SUP | Alistar vs Rell | 185 | 56.8% | Alistar favored |
| MID | Azir vs Taliyah | 168 | 42.9% | Taliyah favored |
| SUP | Leona vs Rell | 166 | 48.8% | Even |
| JNG | Vi vs Xin Zhao | 130 | 54.6% | Vi favored |
| ADC | Ezreal vs Kai'Sa | 133 | 43.6% | Kai'Sa favored |
| TOP | K'Sante vs Renekton | 145 | 49.7% | Even |
| TOP | K'Sante vs Rumble | 92 | 42.4% | Rumble favored |

### 4.5 Role-Specific Analysis ✅ SUPPORTED

```sql
-- Champions by role with win rates
SELECT role, champion_name, COUNT(*) as games,
       ROUND(AVG(CASE WHEN team_won = 'True' THEN 1.0 ELSE 0.0 END) * 100, 1) as win_rate,
       ROUND(AVG(kda_ratio), 2) as avg_kda
FROM player_game_stats
WHERE role NOT IN ('', 'UNKNOWN')
GROUP BY role, champion_name
HAVING COUNT(*) >= 5
ORDER BY role, games DESC;
```

**Top Champions by Role:**

| Role | Top Champions (by games) |
|------|--------------------------|
| TOP | K'Sante (261), Aatrox (152), Renekton (107), Rumble (87) |
| JNG | Vi (170), Sejuani (165), Maokai (139), Xin Zhao (133) |
| MID | Azir (247), Taliyah (191), Corki (125), Orianna (110) |
| ADC | Varus (210), Zeri (152), Senna (136), Kalista (131) |
| SUP | Nautilus (223), Rell (221), Rakan (143), Renata (85) |

---

## 5. Player Matchup Analytics ✅ NEW SECTION

### 5.1 Player vs Player Head-to-Head

```sql
-- Player vs Player head-to-head records
WITH player_matchups AS (
    SELECT
        pgs1.player_name as player1,
        pgs2.player_name as player2,
        pgs1.role,
        pgs1.team_won as p1_won,
        pgs1.champion_name as p1_champ,
        pgs2.champion_name as p2_champ
    FROM player_game_stats pgs1
    JOIN player_game_stats pgs2
        ON pgs1.game_id = pgs2.game_id
        AND pgs1.role = pgs2.role
        AND pgs1.team_side != pgs2.team_side
    WHERE pgs1.role NOT IN ('', 'UNKNOWN')
      AND pgs1.player_name < pgs2.player_name  -- Avoid duplicates
)
SELECT
    player1, player2, role,
    COUNT(*) as games,
    SUM(CASE WHEN p1_won = 'True' THEN 1 ELSE 0 END) as p1_wins,
    SUM(CASE WHEN p1_won = 'False' THEN 1 ELSE 0 END) as p2_wins,
    ROUND(AVG(CASE WHEN p1_won = 'True' THEN 1.0 ELSE 0.0 END) * 100, 1) as p1_wr
FROM player_matchups
GROUP BY player1, player2, role
HAVING COUNT(*) >= 3
ORDER BY games DESC;
```

**Notable Player Rivalries (10+ games):**

| Player 1 | Player 2 | Role | Games | P1 Wins | P2 Wins | Notes |
|----------|----------|------|-------|---------|---------|-------|
| Kiin | Zeus | TOP | 38 | **26** | 12 | Kiin dominates |
| Doran | Kiin | TOP | 36 | 11 | **25** | Kiin dominates |
| Doran | Zeus | TOP | 35 | **20** | 15 | Doran ahead |
| Hans Sama | Supa | ADC | 34 | **23** | 11 | Hans Sama dominates |
| 369 | Bin | TOP | 33 | 13 | **20** | Bin dominates |
| Chovy | Zeka | MID | 30 | **21** | 9 | Chovy dominates |
| Chovy | Faker | MID | 29 | **19** | 10 | Chovy ahead |
| Gumayusi | Viper | ADC | 28 | 15 | 13 | Even rivalry |
| Hans Sama | Noah | ADC | 28 | **19** | 9 | Hans Sama dominates |
| Aiming | Gumayusi | ADC | 27 | 6 | **21** | Gumayusi dominates |

### 5.2 Player-Specific Champion Matchups

```sql
-- How does a specific player perform on a champion vs enemy champions?
-- e.g., "How does Faker's Azir do vs Taliyah?"
WITH player_champ_matchups AS (
    SELECT
        pgs1.player_name,
        pgs1.champion_name as player_champ,
        pgs2.champion_name as enemy_champ,
        pgs1.role,
        pgs1.team_won,
        pgs1.kda_ratio
    FROM player_game_stats pgs1
    JOIN player_game_stats pgs2
        ON pgs1.game_id = pgs2.game_id
        AND pgs1.role = pgs2.role
        AND pgs1.team_side != pgs2.team_side
    WHERE pgs1.role NOT IN ('', 'UNKNOWN')
)
SELECT
    player_name,
    player_champ,
    enemy_champ,
    COUNT(*) as games,
    SUM(CASE WHEN team_won = 'True' THEN 1 ELSE 0 END) as wins,
    ROUND(AVG(CASE WHEN team_won = 'True' THEN 1.0 ELSE 0.0 END) * 100, 1) as wr,
    ROUND(AVG(kda_ratio), 2) as avg_kda
FROM player_champ_matchups
WHERE player_name = :player_name
GROUP BY player_name, player_champ, enemy_champ
HAVING COUNT(*) >= 3
ORDER BY games DESC;
```

**Example: Notable Player Champion Matchups**

| Player | On Champion | vs Enemy | Games | WR | KDA |
|--------|-------------|----------|-------|-----|-----|
| Zeus | Aatrox | K'Sante | 7 | **100%** | 4.61 |
| Faker | Orianna | Azir | 6 | **100%** | 8.33 |
| Faker | Tristana | Ezreal | 6 | **33%** | 3.21 |
| Caps | LeBlanc | Azir | 4 | **100%** | 6.0 |
| Gumayusi | Senna | Tristana | 5 | **100%** | 11.87 |
| Chovy | Corki | Azir | 4 | **100%** | 10.88 |

### 5.3 Player's Worst Matchups (by Enemy Champion)

```sql
-- What champions does a player struggle against?
WITH matchups AS (
    SELECT
        pgs1.player_name,
        pgs2.champion_name as enemy_champ,
        pgs1.team_won,
        pgs1.kda_ratio
    FROM player_game_stats pgs1
    JOIN player_game_stats pgs2
        ON pgs1.game_id = pgs2.game_id
        AND pgs1.role = pgs2.role
        AND pgs1.team_side != pgs2.team_side
    WHERE pgs1.player_name = :player_name
)
SELECT
    enemy_champ,
    COUNT(*) as games,
    SUM(CASE WHEN team_won = 'True' THEN 1 ELSE 0 END) as wins,
    ROUND(AVG(CASE WHEN team_won = 'True' THEN 1.0 ELSE 0.0 END) * 100, 1) as wr,
    ROUND(AVG(kda_ratio), 2) as avg_kda
FROM matchups
GROUP BY enemy_champ
HAVING COUNT(*) >= 3
ORDER BY wr ASC;  -- Worst matchups first
```

**Example: Faker's Performance by Enemy Champion**

| vs Champion | Games | WR | KDA | Assessment |
|-------------|-------|-----|-----|------------|
| vs Ezreal (mid) | 6 | 33% | 3.21 | Struggles |
| vs Taliyah | 8 | 50% | 5.46 | Even |
| vs Corki | 9 | 56% | 4.50 | Slight edge |
| vs Azir | 15 | **87%** | 7.56 | Dominates |

---

## 6. Tournament Mapping ✅ NEW SECTION

### 6.1 Strategy: Derive from Team Participation + Dates

While `tournament_id` is not in the data, we can infer tournaments from:
1. **Team participation patterns** - Teams in the same league only play each other
2. **Date ranges** - Seasons have predictable schedules

```sql
-- Tournament inference query
WITH series_enriched AS (
    SELECT
        s.id as series_id,
        s.match_date,
        s.format,
        CASE
            WHEN t1.name IN ('T1', 'Gen.G Esports', 'DRX', 'Dplus KIA', 'KT Rolster',
                           'Hanwha Life Esports', 'FearX', 'OKSavingsBank BRION',
                           'NongShim REDFORCE', 'KWANGDONG FREECS')
                 AND t2.name IN ('T1', 'Gen.G Esports', 'DRX', 'Dplus KIA', 'KT Rolster',
                           'Hanwha Life Esports', 'FearX', 'OKSavingsBank BRION',
                           'NongShim REDFORCE', 'KWANGDONG FREECS') THEN 'LCK'
            WHEN t1.name IN ('G2 Esports', 'Fnatic', 'Team BDS', 'Rogue', 'SK Gaming',
                           'MAD Lions', 'Team Vitality', 'GIANTX', 'Karmine Corp',
                           'Team Heretics')
                 AND t2.name IN ('G2 Esports', 'Fnatic', 'Team BDS', 'Rogue', 'SK Gaming',
                           'MAD Lions', 'Team Vitality', 'GIANTX', 'Karmine Corp',
                           'Team Heretics') THEN 'LEC'
            WHEN t1.name IN ('FlyQuest', 'Team Liquid', 'Cloud9', '100 Thieves',
                           'NRG', 'Dignitas', 'Immortals Progressive', 'Shopify Rebellion')
                 AND t2.name IN ('FlyQuest', 'Team Liquid', 'Cloud9', '100 Thieves',
                           'NRG', 'Dignitas', 'Immortals Progressive', 'Shopify Rebellion') THEN 'LCS'
            ELSE 'INTL'
        END as region,
        CASE
            WHEN match_date < '2024-05-01' THEN 'Spring 2024'
            WHEN match_date < '2024-09-01' THEN 'Summer 2024'
            ELSE 'Winter 2025'
        END as split
    FROM series s
    JOIN teams t1 ON s.blue_team_id = t1.id
    JOIN teams t2 ON s.red_team_id = t2.id
)
SELECT
    region,
    split,
    COUNT(*) as series_count
FROM series_enriched
GROUP BY region, split
ORDER BY region, split;
```

### 6.2 Tournament Coverage

| Region | Split | Series Count |
|--------|-------|--------------|
| **LPL** | Spring 2024 | 6 |
| **LPL** | Summer 2024 | 135 |
| **LPL** | Winter 2025 | 17 |
| **LPL** | Spring 2025 | 181 |
| **LPL** | Summer 2025 | 119 |
| LCK | Spring 2024 | 98 |
| LCK | Summer 2024 | 95 |
| LCK | Winter 2025 | 28 |
| LCK | Spring 2025 | 105 |
| LCK | Summer 2025 | 83 |
| LEC | Spring 2024 | 115 |
| LEC | Summer 2024 | 67 |
| LEC | Winter 2025 | 31 |
| LEC | Spring 2025 | 80 |
| LEC | Summer 2025 | 30 |
| LCS | Spring 2024 | 64 |
| LCS | Summer 2024 | 35 |
| LCS | Winter 2025 | 6 |
| LCS | Spring 2025 | 46 |
| LCS | Summer 2025 | 23 |
| International | Various | 117 |

### 6.3 Recommended Tournament Mapping Table

```sql
-- Create a lookup table for more granular tournament mapping
CREATE TABLE tournament_mapping (
    series_id TEXT PRIMARY KEY,
    region TEXT NOT NULL,           -- LCK, LEC, LCS, INTL
    split TEXT NOT NULL,            -- Spring 2024, Summer 2024
    stage TEXT,                     -- Regular Season, Playoffs, Finals
    tournament_name TEXT            -- "LCK Spring 2024 Playoffs"
);

-- Populate with derived data + manual stage classification
INSERT INTO tournament_mapping (series_id, region, split, stage, tournament_name)
SELECT
    s.id,
    /* region logic from above */,
    /* split logic from above */,
    CASE
        WHEN s.format = 'best-of-5' THEN 'Playoffs'
        ELSE 'Regular Season'
    END as stage,
    /* concatenate into tournament_name */
FROM series s
JOIN teams t1 ON s.blue_team_id = t1.id
JOIN teams t2 ON s.red_team_id = t2.id;
```

### 6.4 What's Still Missing for Tournaments

| Data | Status | Workaround |
|------|--------|------------|
| Region | ✅ Derivable | Team participation patterns |
| Split (Spring/Summer) | ✅ Derivable | Date ranges |
| Stage (Regular/Playoffs) | ⚠️ Partial | BO5 = Playoffs, but misses BO3 playoffs |
| Specific event names | ❌ Manual | Need manual mapping for "Week 1" vs "Finals" |

---

## 7. Team Analytics ✅ FULLY SUPPORTED

```sql
-- Team performance rankings
WITH team_games AS (
    SELECT
        t.id as team_id,
        t.name as team_name,
        g.id as game_id,
        g.winner_team_id
    FROM teams t
    JOIN series s ON (s.blue_team_id = t.id OR s.red_team_id = t.id)
    JOIN games g ON g.series_id = s.id
)
SELECT
    team_name,
    COUNT(DISTINCT game_id) as total_games,
    SUM(CASE WHEN winner_team_id = team_id THEN 1 ELSE 0 END) as wins,
    ROUND(AVG(CASE WHEN winner_team_id = team_id THEN 1.0 ELSE 0.0 END) * 100, 1) as win_rate
FROM team_games
GROUP BY team_id, team_name
HAVING COUNT(DISTINCT game_id) >= 10
ORDER BY win_rate DESC;
```

**Top Teams by Win Rate:**

| Team | Games | Win Rate |
|------|-------|----------|
| Gen.G Esports | 67 | 85.1% |
| G2 Esports | 49 | 79.6% |
| T1 | 75 | 69.3% |
| Hanwha Life Esports | 72 | 68.1% |
| Team BDS | 47 | 66.0% |

---

## 8. Gap Analysis: Spec vs Reality (UPDATED)

### 8.1 Resolved Gaps

| Item | Previous Status | **Current Status** | How It's Solved |
|------|-----------------|-------------------|-----------------|
| Champion counters | ❌ Missing | ✅ **Calculable** | Self-join on player_game_stats by role + opposite team_side |
| Player matchups | ❌ Missing | ✅ **Calculable** | Same self-join technique |
| Tournament ID | ❌ Missing | ⚠️ **Derivable** | Team participation + date ranges |
| Patch version | ⚠️ 0.5% | ✅ **61.5%** | Now available for most games |
| Vision score | ⚠️ 0.5% | ✅ **61.3%** | Now available for ~61% of games |
| Damage dealt | ⚠️ 0.5% | ✅ **61.3%** | Now available for ~61% of games |
| First blood | ⚠️ 5.8% | ✅ **79.7%** | Now available for ~80% of games |
| LPL data | ❌ Missing | ✅ **458 series** | Full LPL coverage added |

### 8.2 Remaining Gaps

| Spec Requirement | Status | Impact | Recommendation |
|------------------|--------|--------|----------------|
| CSD@15 / Early game stats | ❌ Missing | Player tendencies incomplete | Not in GRID data; accept limitation |
| Champion rework dates | ❌ Missing | Pre-rework data filtering | Add to `knowledge/champion_reworks.json` |
| Lane-specific stats | ❌ Missing | Can't distinguish "winning lane" vs "winning game" | Use KDA/damage as proxy |
| Riot Data Dragon mapping | ❌ Missing | No champion icons | Create manual mapping file |

### 8.3 Schema Additions Required

```sql
-- Pre-computed analytics tables for API performance

-- Champion meta statistics (refresh on data import)
CREATE TABLE champion_meta_stats (
    champion_id TEXT PRIMARY KEY,
    games INTEGER,
    picks INTEGER,
    bans INTEGER,
    presence_pct REAL,
    win_rate REAL,
    tier TEXT,              -- S/A/B/C/D
    computed_at TEXT
);

-- Champion synergies (same-team pairs)
CREATE TABLE champion_synergies (
    champion_a_id TEXT,
    champion_b_id TEXT,
    games_together INTEGER,
    wins INTEGER,
    win_rate REAL,
    synergy_delta REAL,     -- vs 50% baseline
    PRIMARY KEY (champion_a_id, champion_b_id)
);

-- Champion counters (opposing matchups by role)
CREATE TABLE champion_counters (
    champion_id TEXT,
    countered_by_id TEXT,
    role TEXT,              -- TOP/JNG/MID/ADC/SUP
    games INTEGER,
    win_rate REAL,          -- Champion's WR in this matchup
    counter_delta REAL,     -- vs champion's overall WR
    PRIMARY KEY (champion_id, countered_by_id, role)
);

-- Player vs player head-to-head
CREATE TABLE player_matchups (
    player1_id TEXT,
    player2_id TEXT,
    role TEXT,
    games INTEGER,
    player1_wins INTEGER,
    player2_wins INTEGER,
    PRIMARY KEY (player1_id, player2_id, role)
);

-- Tournament mapping (derived + manual)
CREATE TABLE tournament_mapping (
    series_id TEXT PRIMARY KEY,
    region TEXT NOT NULL,
    split TEXT NOT NULL,
    stage TEXT,
    tournament_name TEXT
);
```

---

## 9. API Endpoint Feasibility (UPDATED)

### 9.1 Fully Implementable (Current Data)

| Endpoint | Feasibility | Notes |
|----------|-------------|-------|
| `GET /api/series` | ✅ Ready | List/filter series |
| `GET /api/series/{id}` | ✅ Ready | Series detail with games |
| `GET /api/draft/{series_id}/{game}` | ✅ Ready | Draft action sequence |
| `POST /api/recommend/pick` | ✅ Ready | Meta + proficiency + synergy + counters |
| `POST /api/recommend/ban` | ✅ Ready | Target player pools + matchup data |
| `GET /api/player/{id}` | ✅ Ready | Profile + champion pool |
| `GET /api/player/{id}/champions` | ✅ Ready | Proficiency stats |
| `GET /api/player/{id}/matchups` | ✅ **Ready (NEW)** | Head-to-head vs opponents |
| `GET /api/team/{id}` | ✅ Ready | Team profile + players |
| `GET /api/champion/{id}` | ✅ **Ready (UPDATED)** | Meta stats + counters by role |
| `GET /api/champion/{id}/counters` | ✅ **Ready (NEW)** | Role-specific matchup data |
| `GET /api/meta/current` | ✅ Ready | Tier list calculation |
| `POST /api/analysis/comp` | ✅ Ready | Archetype detection |

### 9.2 Requires Additional Processing (But Achievable)

| Endpoint | Requirement | Solution |
|----------|-------------|----------|
| `GET /api/series?tournament=LCK` | Tournament filtering | Compute tournament_mapping table |
| Win probability prediction | Feature engineering | Use meta + synergy + counter scores |

---

## 10. Sample Queries for API Implementation

### 10.1 Pick Recommendation Query (Enhanced with Counters)

```sql
-- Multi-factor pick scoring including counter matchups
WITH meta_scores AS (
    SELECT champion_id, champion_name,
           ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) * 2 FROM games), 1) as presence,
           ROUND(AVG(CASE WHEN team_won = 'True' THEN 1.0 ELSE 0.0 END), 2) as meta_wr
    FROM draft_actions da
    JOIN player_game_stats pgs ON da.game_id = pgs.game_id
        AND da.champion_id = pgs.champion_id
    WHERE da.action_type = 'pick'
    GROUP BY da.champion_id, da.champion_name
),
player_proficiency AS (
    SELECT champion_id, champion_name,
           COUNT(*) as games,
           ROUND(AVG(CASE WHEN team_won = 'True' THEN 1.0 ELSE 0.0 END), 2) as player_wr
    FROM player_game_stats
    WHERE player_id = :player_id
    GROUP BY champion_id, champion_name
),
counter_scores AS (
    -- How well does each champion do vs the enemy's picked champions?
    SELECT
        pgs1.champion_id,
        AVG(CASE WHEN pgs1.team_won = 'True' THEN 1.0 ELSE 0.0 END) as counter_wr
    FROM player_game_stats pgs1
    JOIN player_game_stats pgs2 ON pgs1.game_id = pgs2.game_id
        AND pgs1.role = :role
        AND pgs2.role = :role
        AND pgs1.team_side != pgs2.team_side
    WHERE pgs2.champion_id IN (:enemy_picked_champions)
    GROUP BY pgs1.champion_id
)
SELECT
    ms.champion_name,
    ms.presence,
    ms.meta_wr,
    COALESCE(pp.games, 0) as player_games,
    COALESCE(pp.player_wr, 0.5) as player_wr,
    COALESCE(cs.counter_wr, 0.5) as counter_wr,
    -- Composite score with counter factor
    (ms.meta_wr * 0.25 +
     COALESCE(pp.player_wr, 0.5) * 0.35 +
     COALESCE(cs.counter_wr, 0.5) * 0.25 +
     ms.presence/100 * 0.15) as confidence
FROM meta_scores ms
LEFT JOIN player_proficiency pp ON ms.champion_id = pp.champion_id
LEFT JOIN counter_scores cs ON ms.champion_id = cs.champion_id
WHERE ms.champion_id NOT IN (:banned_champions)
  AND ms.champion_id NOT IN (:picked_champions)
ORDER BY confidence DESC
LIMIT 5;
```

### 10.2 Ban Recommendation Query (Enhanced)

```sql
-- Target opponent's highest-value champions considering matchups
WITH opponent_pool AS (
    SELECT
        champion_id,
        champion_name,
        COUNT(*) as games,
        ROUND(AVG(CASE WHEN team_won = 'True' THEN 1.0 ELSE 0.0 END) * 100, 1) as win_rate,
        ROUND(AVG(kda_ratio), 2) as avg_kda
    FROM player_game_stats
    WHERE team_id = :opponent_team_id
      AND champion_id NOT IN (:already_banned)
    GROUP BY champion_id, champion_name
    HAVING COUNT(*) >= 3
),
our_weakness AS (
    -- Champions our players struggle against
    SELECT
        pgs2.champion_id,
        AVG(CASE WHEN pgs1.team_won = 'True' THEN 0.0 ELSE 1.0 END) as threat_score
    FROM player_game_stats pgs1
    JOIN player_game_stats pgs2 ON pgs1.game_id = pgs2.game_id
        AND pgs1.role = pgs2.role
        AND pgs1.team_side != pgs2.team_side
    WHERE pgs1.team_id = :our_team_id
    GROUP BY pgs2.champion_id
)
SELECT
    op.champion_name,
    op.games,
    op.win_rate,
    COALESCE(ow.threat_score, 0.5) as threat_to_us,
    -- Priority score: their comfort + threat to us
    (op.win_rate/100 * 0.5 + COALESCE(ow.threat_score, 0.5) * 0.5) as ban_priority
FROM opponent_pool op
LEFT JOIN our_weakness ow ON op.champion_id = ow.champion_id
ORDER BY ban_priority DESC
LIMIT 5;
```

### 10.3 Comp Archetype Detection

```python
COMP_ARCHETYPES = {
    "dive": ["Nocturne", "Renekton", "Akali", "Camille", "Diana", "Vi", "Jarvan IV"],
    "poke": ["Jayce", "Zoe", "Ezreal", "Xerath", "Varus", "Nidalee", "Corki"],
    "protect": ["Lulu", "Kog'Maw", "Jinx", "Braum", "Tahm Kench", "Orianna"],
    "teamfight": ["Orianna", "Jarvan IV", "Kennen", "Rumble", "Miss Fortune"],
    "splitpush": ["Fiora", "Jax", "Camille", "Shen", "Tryndamere"]
}

def identify_archetype(team_picks: list[str]) -> dict:
    scores = {}
    for archetype, markers in COMP_ARCHETYPES.items():
        matches = [c for c in team_picks if c in markers]
        if len(matches) >= 2:
            scores[archetype] = len(matches)
    return max(scores, key=scores.get) if scores else "flexible"
```

---

## 11. Recommendations (UPDATED)

### 11.1 High Priority (Before MVP)

1. **Compute and materialize matchup tables**
   - `champion_counters` - Role-specific win rates
   - `player_matchups` - Head-to-head records
   - These enable fast API responses

2. **Compute tournament_mapping table**
   - Use team participation + date logic
   - Add manual stage classification for playoffs

3. **Add Riot Data Dragon mapping**
   - Create `champion_riot_mapping.json` with champion names → riot keys
   - Required for champion icons in UI

4. **Compute champion_meta_stats and champion_synergies tables**
   - Pre-calculate for fast API responses
   - Refresh on data import

### 11.2 Medium Priority (MVP Enhancement)

1. **Leverage patch version data (61.5% coverage)**
   - Filter meta analysis by patch
   - Weight recent patches higher in recommendations

2. **Leverage vision/damage data (61.3% coverage)**
   - Support player tendency analysis with vision scores
   - Calculate damage share metrics for carry identification

3. **Player hidden pool (domain knowledge)**
   - Manual data entry per spec: `knowledge/player_hidden_pools.json`
   - Required for surprise pick detection

4. **Enhanced counter scoring**
   - Weight recent matchups higher
   - Factor in KDA/damage differential, not just win rate

### 11.3 Out of Scope (Accept Limitations)

1. **CSD@15 / Early game metrics** - Not in GRID Open Access data
2. **"Winning lane" detection** - Would need gold/CS differential

---

## 12. Conclusion

The complete dataset provides an **exceptional foundation** for the LoL Draft Assistant MVP. The data has grown **5-7x** from the initial extract, with **significant improvements** in previously sparse fields (patch version, vision score, damage dealt).

**Key Strengths:**
- Volume massively exceeds spec targets (7x games, 6x draft actions)
- Complete draft action sequences across 3,436 games
- Rich player analysis data: KDA, damage, vision, kill participation
- **LPL coverage added** - 458 series from China's top league
- Four major regions covered: LCK (409), LEC (323), LCS (174), LPL (458)
- **Patch version now 61.5% available** for meta filtering
- **Vision/damage data now 61.3% available** for player tendencies
- Matchup and counter data fully calculable
- Tournament info derivable from team participation patterns
- Date range: Jan 2024 - Sep 2025 (5 competitive splits)

**Key Limitations:**
- Missing CSD@15 / early-game gold metrics
- No lane-specific performance (use damage/KDA as proxy)
- Tournament ID still requires derivation from team patterns

**Updated Layer Support:**
- Layer 1 (Meta): ✅ Fully supported
- Layer 2 (Tendencies): ✅ Mostly supported (vision 61.3%, damage 61.3%, KP 96.3%)
- Layer 3 (Proficiency): ✅ Fully supported
- Layer 4 (Relationships): ✅ Fully supported (synergies + counters)

**Recommended Approach:**
1. Proceed with MVP using complete dataset
2. Pre-compute matchup/counter tables for API performance
3. Derive tournament mapping from team + date patterns
4. Leverage patch version data for meta filtering
5. Leverage vision/damage data for player tendency analysis
6. Augment with domain expert knowledge files (hidden pools, reworks)
7. Accept limitations on early-game lane metrics (use KDA/damage as proxy)

---

*Review completed: 2026-01-21*
*Updated: Full dataset re-analysis with LPL data, improved field coverage*
