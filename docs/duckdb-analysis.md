# DuckDB Analysis Layer

## Decision Summary

**Chosen Technology**: DuckDB
**Alternatives Considered**: csvq (CLI), pandas (Python), SQLite (file-based DB)

### Why DuckDB?

| Criteria | csvq | pandas | SQLite | DuckDB |
|----------|------|--------|--------|--------|
| SQL syntax | ✅ | ❌ | ✅ | ✅ |
| Python native | ❌ | ✅ | ✅ | ✅ |
| Reads CSV directly | ✅ | ✅ | ❌ | ✅ |
| Returns DataFrames | ❌ | ✅ | ❌ | ✅ |
| Single dependency | ✅ | ❌ | ✅ | ✅ |
| Columnar analytics | ❌ | ❌ | ❌ | ✅ |

DuckDB provides the best of all worlds:
- **SQL syntax**: Reuse all queries from architecture review without translation
- **Zero ETL**: Read CSV files directly in queries (no import step)
- **Python integration**: Native `.df()` method returns pandas DataFrames
- **Fast analytics**: Columnar storage optimized for aggregations

---

## Installation

```bash
pip install duckdb
# or with uv
uv add duckdb
```

That's it. No database server, no configuration files.

---

## Direct CSV Querying

DuckDB reads CSV files directly in the `FROM` clause:

```python
import duckdb

# Query CSV directly - no import needed
result = duckdb.query("""
    SELECT *
    FROM 'outputs/full_2024_2025/csv/champions.csv'
    LIMIT 5
""").df()
```

### Path Patterns

```sql
-- Single file
FROM 'outputs/full_2024_2025/csv/games.csv'

-- Multiple files with glob
FROM 'outputs/*/csv/games.csv'

-- Explicit read_csv for options
FROM read_csv('data.csv', header=true, delim=',')
```

---

## Core Analytics Queries

These queries work directly on our CSV files.

### 1. Champion Meta Statistics

```python
def get_champion_meta():
    return duckdb.query("""
        WITH pick_stats AS (
            SELECT
                champion,
                COUNT(*) as picks
            FROM 'outputs/full_2024_2025/csv/draft_actions.csv'
            WHERE action_type = 'pick'
            GROUP BY champion
        ),
        ban_stats AS (
            SELECT
                champion,
                COUNT(*) as bans
            FROM 'outputs/full_2024_2025/csv/draft_actions.csv'
            WHERE action_type = 'ban'
            GROUP BY champion
        ),
        win_stats AS (
            SELECT
                champion_name,
                COUNT(*) as games,
                SUM(CASE WHEN team_won = 'True' THEN 1 ELSE 0 END) as wins
            FROM 'outputs/full_2024_2025/csv/player_game_stats.csv'
            GROUP BY champion_name
        )
        SELECT
            COALESCE(p.champion, b.champion, w.champion_name) as champion,
            COALESCE(p.picks, 0) as picks,
            COALESCE(b.bans, 0) as bans,
            COALESCE(p.picks, 0) + COALESCE(b.bans, 0) as presence,
            COALESCE(w.games, 0) as games_played,
            ROUND(COALESCE(w.wins, 0) * 100.0 / NULLIF(w.games, 0), 1) as win_rate
        FROM pick_stats p
        FULL OUTER JOIN ban_stats b ON p.champion = b.champion
        FULL OUTER JOIN win_stats w ON COALESCE(p.champion, b.champion) = w.champion_name
        ORDER BY presence DESC
    """).df()
```

### 2. Champion Counter Matchups

The key insight: self-join `player_game_stats` where `game_id` matches, `role` matches, but `team_side` differs.

```python
def get_champion_counters(champion: str, role: str, min_games: int = 3):
    return duckdb.query(f"""
        SELECT
            pgs2.champion_name as enemy_champion,
            COUNT(*) as games,
            SUM(CASE WHEN pgs1.team_won = 'True' THEN 1 ELSE 0 END) as wins,
            ROUND(AVG(CASE WHEN pgs1.team_won = 'True' THEN 1.0 ELSE 0.0 END) * 100, 1) as win_rate
        FROM 'outputs/full_2024_2025/csv/player_game_stats.csv' pgs1
        JOIN 'outputs/full_2024_2025/csv/player_game_stats.csv' pgs2
            ON pgs1.game_id = pgs2.game_id
            AND pgs1.role = pgs2.role
            AND pgs1.team_side != pgs2.team_side
        WHERE pgs1.champion_name = '{champion}'
          AND pgs1.role = '{role}'
        GROUP BY pgs2.champion_name
        HAVING COUNT(*) >= {min_games}
        ORDER BY win_rate DESC
    """).df()
```

### 3. Player Champion Proficiency

```python
def get_player_proficiency(player_name: str):
    return duckdb.query(f"""
        SELECT
            champion_name,
            COUNT(*) as games,
            SUM(CASE WHEN team_won = 'True' THEN 1 ELSE 0 END) as wins,
            ROUND(AVG(CASE WHEN team_won = 'True' THEN 1.0 ELSE 0.0 END) * 100, 1) as win_rate,
            ROUND(AVG(kda_ratio), 2) as avg_kda,
            ROUND(AVG(kills), 1) as avg_kills,
            ROUND(AVG(deaths), 1) as avg_deaths,
            ROUND(AVG(assists), 1) as avg_assists
        FROM 'outputs/full_2024_2025/csv/player_game_stats.csv'
        WHERE player_name = '{player_name}'
        GROUP BY champion_name
        ORDER BY games DESC
    """).df()
```

### 4. Team Synergy Analysis

```python
def get_team_synergies(team_name: str, min_games: int = 3):
    return duckdb.query(f"""
        WITH team_games AS (
            SELECT DISTINCT game_id
            FROM 'outputs/full_2024_2025/csv/player_game_stats.csv'
            WHERE team_id IN (
                SELECT id FROM 'outputs/full_2024_2025/csv/teams.csv'
                WHERE name = '{team_name}'
            )
        ),
        game_comps AS (
            SELECT
                pgs.game_id,
                pgs.team_won,
                LIST(pgs.champion_name ORDER BY pgs.role) as comp
            FROM 'outputs/full_2024_2025/csv/player_game_stats.csv' pgs
            JOIN team_games tg ON pgs.game_id = tg.game_id
            WHERE pgs.team_id IN (
                SELECT id FROM 'outputs/full_2024_2025/csv/teams.csv'
                WHERE name = '{team_name}'
            )
            GROUP BY pgs.game_id, pgs.team_won
        )
        SELECT
            comp,
            COUNT(*) as times_played,
            SUM(CASE WHEN team_won = 'True' THEN 1 ELSE 0 END) as wins
        FROM game_comps
        GROUP BY comp
        HAVING COUNT(*) >= {min_games}
        ORDER BY times_played DESC
    """).df()
```

### 5. Player vs Player Head-to-Head

```python
def get_head_to_head(player1: str, player2: str):
    return duckdb.query(f"""
        SELECT
            pgs1.champion_name as {player1}_champ,
            pgs2.champion_name as {player2}_champ,
            pgs1.role,
            CASE WHEN pgs1.team_won = 'True' THEN '{player1}' ELSE '{player2}' END as winner,
            pgs1.kills as p1_kills,
            pgs1.deaths as p1_deaths,
            pgs2.kills as p2_kills,
            pgs2.deaths as p2_deaths
        FROM 'outputs/full_2024_2025/csv/player_game_stats.csv' pgs1
        JOIN 'outputs/full_2024_2025/csv/player_game_stats.csv' pgs2
            ON pgs1.game_id = pgs2.game_id
            AND pgs1.role = pgs2.role
            AND pgs1.team_side != pgs2.team_side
        WHERE pgs1.player_name = '{player1}'
          AND pgs2.player_name = '{player2}'
        ORDER BY pgs1.game_id
    """).df()
```

---

## FastAPI Integration Pattern

```python
from fastapi import FastAPI, Query
import duckdb

app = FastAPI(title="LoL Draft Assistant API")

# Connection can be reused (DuckDB handles concurrency)
# For production, consider connection pooling
DATA_PATH = "outputs/full_2024_2025/csv"

@app.get("/champions/meta")
def champion_meta(
    min_presence: int = Query(10, description="Minimum pick+ban count")
):
    df = duckdb.query(f"""
        SELECT champion, picks, bans, presence, win_rate
        FROM (
            -- meta query here
        )
        WHERE presence >= {min_presence}
    """).df()
    return df.to_dict(orient="records")


@app.get("/champions/{champion}/counters")
def champion_counters(
    champion: str,
    role: str = Query(..., description="Role: TOP, JUNGLE, MID, ADC, SUPPORT"),
    min_games: int = Query(3)
):
    df = get_champion_counters(champion, role, min_games)
    return df.to_dict(orient="records")


@app.get("/players/{player}/proficiency")
def player_proficiency(player: str):
    df = get_player_proficiency(player)
    return df.to_dict(orient="records")
```

---

## Performance Considerations

### Why DuckDB is Fast for This Use Case

1. **Columnar Storage**: Only reads columns needed for query
2. **Vectorized Execution**: Processes data in batches
3. **Automatic Parallelization**: Uses all CPU cores
4. **CSV Caching**: Re-queries same file are faster

### Our Data Scale

| Table | Rows | Query Time (expected) |
|-------|------|----------------------|
| player_game_stats | 6,332 | < 100ms |
| draft_actions | 12,618 | < 100ms |
| games | 631 | < 50ms |
| series | 363 | < 50ms |

At this scale, DuckDB handles all queries in milliseconds without optimization.

### Optional: Persist for Faster Startup

```python
# One-time: Create persistent database
con = duckdb.connect('draft_data.duckdb')
con.execute("""
    CREATE TABLE player_game_stats AS
    SELECT * FROM 'outputs/full_2024_2025/csv/player_game_stats.csv'
""")
con.close()

# Later: Query persistent database
con = duckdb.connect('draft_data.duckdb', read_only=True)
result = con.execute("SELECT * FROM player_game_stats").df()
```

This is optional - CSV direct queries are fast enough for demo purposes.

---

## SQL Dialect Notes

DuckDB SQL is PostgreSQL-compatible with extensions:

| Feature | DuckDB | SQLite | Notes |
|---------|--------|--------|-------|
| `LIST()` aggregate | ✅ | ❌ | Use `GROUP_CONCAT` in SQLite |
| `FULL OUTER JOIN` | ✅ | ❌ | SQLite lacks this |
| CSV in FROM | ✅ | ❌ | DuckDB unique feature |
| Window functions | ✅ | ✅ | Both support |
| CTEs | ✅ | ✅ | Both support |

Our queries use standard SQL that works across DuckDB/PostgreSQL with minor adaptations.

---

## Migration Path

If data grows beyond CSV practicality:

1. **Stay with DuckDB**: Convert CSVs to `.duckdb` file (5x faster queries)
2. **PostgreSQL**: Same SQL syntax, add connection pooling
3. **Supabase**: Hosted PostgreSQL with built-in API

For hackathon demo, direct CSV querying is ideal - zero infrastructure.
