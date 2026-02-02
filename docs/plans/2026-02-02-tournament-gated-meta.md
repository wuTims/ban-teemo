# Tournament-Gated Meta for Unified Scoring

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Unify all meta scoring to use objective tournament statistics (priority + performance), with tournament-specific data files for historical accuracy.

**Architecture:** Replace tier-based `MetaScorer` with parameterized `TournamentScorer`. Simulator uses current tournament meta (`tournament_meta.json`), historical replay uses era-appropriate meta (`replay_meta/{tournament_id}.json`). Remove `simulator_mode` branching - everything uses tournament scoring.

**Tech Stack:** Python, DuckDB, FastAPI, pytest

---

## Task 1: Parameterize TournamentScorer to Accept Custom Data File

**Files:**
- Modify: `backend/src/ban_teemo/services/scorers/tournament_scorer.py:19-31`
- Test: `backend/tests/test_tournament_scorer.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_tournament_scorer.py`:

```python
def test_custom_data_file_path(tmp_path):
    """TournamentScorer can load data from a custom file path."""
    knowledge_dir = tmp_path / "knowledge"
    knowledge_dir.mkdir(exist_ok=True)
    replay_meta_dir = knowledge_dir / "replay_meta"
    replay_meta_dir.mkdir(exist_ok=True)

    # Write custom meta file
    custom_data = {
        "metadata": {
            "tournament_id": "756908",
            "tournament_name": "LCK - Spring 2024 (Playoffs)",
            "window_start": "2024-02-01",
            "window_end": "2024-03-30",
            "games_analyzed": 150,
        },
        "champions": {
            "Azir": {"priority": 0.75, "roles": {"mid": {"adjusted_performance": 0.55, "picks": 20}}}
        },
        "defaults": {"missing_champion_priority": 0.05, "missing_champion_performance": 0.35},
    }
    (replay_meta_dir / "756908.json").write_text(json.dumps(custom_data))

    scorer = TournamentScorer(knowledge_dir=knowledge_dir, data_file="replay_meta/756908.json")

    assert scorer.get_priority("Azir") == 0.75
    assert scorer.get_performance("Azir", "mid") == 0.55
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest backend/tests/test_tournament_scorer.py::test_custom_data_file_path -v`
Expected: FAIL with `TypeError: __init__() got an unexpected keyword argument 'data_file'`

**Step 3: Write minimal implementation**

Modify `backend/src/ban_teemo/services/scorers/tournament_scorer.py`:

```python
class TournamentScorer:
    """Scores champions based on recent tournament pick/ban data.

    Provides two distinct scoring signals:
    - tournament_priority: Role-agnostic contestation (how often pros pick/ban)
    - tournament_performance: Role-specific winrate with sample-size adjustment

    Can load data from custom files for historical replay support.
    """

    def __init__(self, knowledge_dir: Optional[Path] = None, data_file: Optional[str] = None):
        if knowledge_dir is None:
            knowledge_dir = Path(__file__).parents[5] / "knowledge"
        self.knowledge_dir = knowledge_dir
        self._data_file = data_file or "tournament_meta.json"
        self._tournament_data: dict = {}
        self._defaults: dict = {}
        self._metadata: dict = {}
        self._load_data()

    def _load_data(self):
        """Load tournament meta data."""
        tournament_path = self.knowledge_dir / self._data_file
        if tournament_path.exists():
            with open(tournament_path) as f:
                data = json.load(f)
                self._tournament_data = data.get("champions", {})
                self._defaults = data.get("defaults", {})
                self._metadata = data.get("metadata", {})
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest backend/tests/test_tournament_scorer.py::test_custom_data_file_path -v`
Expected: PASS

**Step 5: Run all tournament scorer tests**

Run: `uv run pytest backend/tests/test_tournament_scorer.py -v`
Expected: All PASS (existing tests use default file)

**Step 6: Commit**

```bash
git add backend/src/ban_teemo/services/scorers/tournament_scorer.py backend/tests/test_tournament_scorer.py
git commit -m "$(cat <<'EOF'
feat(scorer): parameterize TournamentScorer with data_file option

Allow TournamentScorer to load from custom data files for historical
replay support. Default remains tournament_meta.json for backwards
compatibility.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Add Fallback Behavior for Missing Data Files

**Files:**
- Modify: `backend/src/ban_teemo/services/scorers/tournament_scorer.py`
- Test: `backend/tests/test_tournament_scorer.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_tournament_scorer.py`:

```python
def test_missing_data_file_falls_back_to_default(tmp_path):
    """Missing custom file falls back to tournament_meta.json."""
    knowledge_dir = tmp_path / "knowledge"
    knowledge_dir.mkdir(exist_ok=True)

    # Write default tournament_meta.json only
    default_data = {
        "metadata": {"source": "default"},
        "champions": {
            "Jayce": {"priority": 0.86, "roles": {"jungle": {"adjusted_performance": 0.47, "picks": 19}}}
        },
        "defaults": {"missing_champion_priority": 0.05, "missing_champion_performance": 0.35},
    }
    (knowledge_dir / "tournament_meta.json").write_text(json.dumps(default_data))

    # Request non-existent file
    scorer = TournamentScorer(knowledge_dir=knowledge_dir, data_file="replay_meta/nonexistent.json")

    # Should fall back to default
    assert scorer.get_priority("Jayce") == 0.86
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest backend/tests/test_tournament_scorer.py::test_missing_data_file_falls_back_to_default -v`
Expected: FAIL with `AssertionError` (returns 0.05 penalty instead of 0.86)

**Step 3: Write minimal implementation**

Update `_load_data` method in `tournament_scorer.py`:

```python
def _load_data(self):
    """Load tournament meta data with fallback to default."""
    tournament_path = self.knowledge_dir / self._data_file

    # Try custom file first, fall back to default
    if not tournament_path.exists() and self._data_file != "tournament_meta.json":
        fallback_path = self.knowledge_dir / "tournament_meta.json"
        if fallback_path.exists():
            tournament_path = fallback_path

    if tournament_path.exists():
        with open(tournament_path) as f:
            data = json.load(f)
            self._tournament_data = data.get("champions", {})
            self._defaults = data.get("defaults", {})
            self._metadata = data.get("metadata", {})
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest backend/tests/test_tournament_scorer.py::test_missing_data_file_falls_back_to_default -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/ban_teemo/services/scorers/tournament_scorer.py backend/tests/test_tournament_scorer.py
git commit -m "$(cat <<'EOF'
feat(scorer): add fallback to default when custom data file missing

TournamentScorer now gracefully falls back to tournament_meta.json
when a requested custom data file doesn't exist.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Remove simulator_mode Flag from PickRecommendationEngine

**Files:**
- Modify: `backend/src/ban_teemo/services/pick_recommendation_engine.py`
- Test: `backend/tests/test_pick_recommendation_engine.py` (if exists, or create)

**Step 1: Write the failing test**

Create or add to `backend/tests/test_pick_recommendation_engine.py`:

```python
import pytest
from ban_teemo.services.pick_recommendation_engine import PickRecommendationEngine


def test_engine_uses_tournament_scoring_by_default():
    """Engine uses tournament scoring (priority + performance) by default."""
    engine = PickRecommendationEngine()

    # Verify tournament scorer is used, not meta scorer for main scoring
    # The engine should have tournament weights as base weights
    assert "tournament_priority" in engine.BASE_WEIGHTS
    assert "tournament_performance" in engine.BASE_WEIGHTS
    assert "meta" not in engine.BASE_WEIGHTS
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest backend/tests/test_pick_recommendation_engine.py::test_engine_uses_tournament_scoring_by_default -v`
Expected: FAIL with `AssertionError` or `KeyError`

**Step 3: Write implementation**

Update `backend/src/ban_teemo/services/pick_recommendation_engine.py`:

1. Remove `simulator_mode` parameter from `__init__`
2. Replace `BASE_WEIGHTS` with tournament weights (merge old `SIMULATOR_BASE_WEIGHTS`)
3. Remove old `SIMULATOR_BASE_WEIGHTS`
4. Update `_calculate_score` to always use tournament scoring
5. Update `_get_effective_weights` to remove simulator_mode branching
6. Add `data_file` parameter to allow custom tournament data

```python
class PickRecommendationEngine:
    """Generates pick recommendations using weighted multi-factor scoring."""

    # Unified weights using tournament data for all modes
    # Tournament data provides objective pro meta signals (picks/bans/winrates)
    BASE_WEIGHTS = {
        "tournament_priority": 0.25,    # Role-agnostic contestation
        "tournament_performance": 0.20, # Role-specific adjusted winrate
        "matchup_counter": 0.25,        # Combined lane + team matchups
        "archetype": 0.15,              # Team composition fit
        "proficiency": 0.15,            # Player comfort
    }

    # ... keep SYNERGY_MULTIPLIER_RANGE, ALL_ROLES, TRANSFER_EXPANSION_LIMIT ...

    def __init__(self, knowledge_dir: Optional[Path] = None, tournament_data_file: Optional[str] = None):
        self.meta_scorer = MetaScorer(knowledge_dir)  # Keep for get_top_meta_champions, blind_pick_safety
        self.flex_resolver = FlexResolver(knowledge_dir)
        self.proficiency_scorer = ProficiencyScorer(knowledge_dir)
        self.matchup_calculator = MatchupCalculator(knowledge_dir)
        self.synergy_service = SynergyService(knowledge_dir)
        self.archetype_service = ArchetypeService(knowledge_dir)
        self.skill_transfer_service = SkillTransferService(knowledge_dir)
        self.tournament_scorer = TournamentScorer(knowledge_dir, data_file=tournament_data_file)
```

**Step 4: Update _calculate_score to always use tournament scoring**

In `_calculate_score` method, replace the if/else branch with:

```python
# Tournament scoring (unified for all modes)
tournament_scores = self.tournament_scorer.get_tournament_scores(
    champion, suggested_role
)
components["tournament_priority"] = tournament_scores["priority"]
components["tournament_performance"] = tournament_scores["performance"]
```

**Step 5: Update _get_effective_weights to remove simulator_mode**

Remove the `simulator_mode` parameter and simplify:

```python
def _get_effective_weights(
    self,
    prof_conf: str,
    pick_count: int = 0,
    has_enemy_picks: bool = False,
    matchup_conf: str = "FULL",
) -> dict[str, float]:
    """Get context-adjusted scoring weights."""
    weights = dict(self.BASE_WEIGHTS)

    # Early blind picks
    if pick_count == 0 and not has_enemy_picks:
        weights["tournament_priority"] += 0.05
        weights["tournament_performance"] -= 0.05
        weights["matchup_counter"] -= 0.10
        weights["archetype"] += 0.10

    # Late counter-pick phase
    elif has_enemy_picks and pick_count >= 3:
        weights["tournament_priority"] -= 0.10
        weights["tournament_performance"] += 0.05
        weights["matchup_counter"] += 0.10
        weights["proficiency"] -= 0.05

    # Handle NO_DATA matchup
    if matchup_conf == "NO_DATA":
        redistribute = weights["matchup_counter"] * 0.5
        weights["matchup_counter"] *= 0.5
        weights["tournament_priority"] += redistribute
    elif matchup_conf == "PARTIAL":
        redistribute = weights["matchup_counter"] * 0.25
        weights["matchup_counter"] *= 0.75
        weights["tournament_priority"] += redistribute * 0.6
        weights["tournament_performance"] += redistribute * 0.4

    # Handle NO_DATA proficiency
    if prof_conf == "NO_DATA":
        redistribute = weights["proficiency"] * 0.8
        weights["proficiency"] *= 0.2
        weights["tournament_priority"] += redistribute * 0.4
        weights["tournament_performance"] += redistribute * 0.3
        weights["matchup_counter"] += redistribute * 0.3

    return weights
```

**Step 6: Run test to verify it passes**

Run: `uv run pytest backend/tests/test_pick_recommendation_engine.py::test_engine_uses_tournament_scoring_by_default -v`
Expected: PASS

**Step 7: Commit**

```bash
git add backend/src/ban_teemo/services/pick_recommendation_engine.py backend/tests/test_pick_recommendation_engine.py
git commit -m "$(cat <<'EOF'
refactor(engine): unify scoring to always use tournament data

Remove simulator_mode branching. All recommendations now use tournament
scoring (priority + performance) instead of tier-based meta scoring.
Add tournament_data_file parameter for historical replay support.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Update Simulator Routes to Remove simulator_mode

**Files:**
- Modify: `backend/src/ban_teemo/api/routes/simulator.py`
- Test: Manual verification (routes still work)

**Step 1: Find and update simulator_mode=True calls**

Search for `simulator_mode=True` in `simulator.py` and remove the parameter:

```python
# Before
request.app.state.pick_engine = PickRecommendationEngine(simulator_mode=True)

# After
request.app.state.pick_engine = PickRecommendationEngine()
```

**Step 2: Update BanRecommendationService if it has simulator_mode**

Check `ban_recommendation_service.py` for similar `simulator_mode` handling and update accordingly.

**Step 3: Run existing tests**

Run: `uv run pytest backend/tests/ -v -k "simulator or ban"`
Expected: All PASS (or identify tests that need updating)

**Step 4: Commit**

```bash
git add backend/src/ban_teemo/api/routes/simulator.py
git commit -m "$(cat <<'EOF'
refactor(api): remove simulator_mode from route initialization

Simulator routes now use unified tournament scoring by default.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Create Build Script for Replay Meta Files

**Files:**
- Create: `backend/scripts/build_replay_metas.py`
- Test: Manual run with sample data

**Step 1: Write the build script**

Create `backend/scripts/build_replay_metas.py`:

```python
#!/usr/bin/env python3
"""
Build per-tournament meta files for historical replay.

For each tournament, computes meta statistics from games played within
6-8 weeks before that tournament's start date.

Usage:
    uv run python backend/scripts/build_replay_metas.py \
        --data-dir outputs/full_2024_2025_v2/csv \
        --output-dir knowledge/replay_meta
"""

import argparse
import csv
import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path


WINDOW_WEEKS = 7  # 6-8 weeks, use 7 as middle ground
SAMPLE_THRESHOLD = 10


def parse_date(date_str: str) -> datetime:
    """Parse ISO date string to datetime."""
    if not date_str:
        return None
    return datetime.fromisoformat(date_str.replace("Z", "+00:00"))


def calculate_adjusted_performance(winrate: float, picks: int) -> float:
    """Adjust winrate based on sample size."""
    if winrate > 0.5 and picks < SAMPLE_THRESHOLD:
        sample_weight = picks / SAMPLE_THRESHOLD
        return sample_weight * winrate + (1 - sample_weight) * 0.5
    return winrate


def normalize_role(role: str) -> str:
    """Normalize role to lowercase canonical form."""
    role_map = {
        "TOP": "top", "JUNGLE": "jungle", "JNG": "jungle",
        "MID": "mid", "MIDDLE": "mid",
        "ADC": "adc", "BOT": "bot", "BOTTOM": "bot",
        "SUPPORT": "support", "SUP": "support",
    }
    return role_map.get(role.upper(), role.lower())


def load_tournaments(data_dir: Path) -> dict:
    """Load tournaments with their start dates."""
    tournaments = {}
    with open(data_dir / "tournaments.csv", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            tournaments[row["id"]] = {
                "id": row["id"],
                "name": row["name"],
            }
    return tournaments


def load_series_with_dates(data_dir: Path) -> list[dict]:
    """Load series with tournament_id and match_date."""
    series_list = []
    with open(data_dir / "series.csv", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            match_date = parse_date(row.get("match_date") or row.get("scheduled_start_time"))
            if match_date:
                series_list.append({
                    "id": row["id"],
                    "tournament_id": row["tournament_id"],
                    "match_date": match_date,
                })
    return series_list


def load_games(data_dir: Path) -> dict:
    """Load games keyed by game_id."""
    games = {}
    with open(data_dir / "games.csv", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            games[row["id"]] = {
                "series_id": row["series_id"],
                "winner_team_id": row["winner_team_id"],
            }
    return games


def load_draft_actions(data_dir: Path) -> list[dict]:
    """Load all draft actions."""
    actions = []
    with open(data_dir / "draft_actions.csv", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            actions.append({
                "game_id": row["game_id"],
                "action_type": row["action_type"],
                "team_id": row["team_id"],
                "champion_name": row["champion_name"],
            })
    return actions


def get_tournament_start_date(tournament_id: str, series_list: list[dict]) -> datetime | None:
    """Get earliest match date for a tournament."""
    dates = [s["match_date"] for s in series_list if s["tournament_id"] == tournament_id]
    return min(dates) if dates else None


def compute_meta_for_window(
    window_start: datetime,
    window_end: datetime,
    series_list: list[dict],
    games: dict,
    draft_actions: list[dict],
) -> dict:
    """Compute champion meta stats for games in the time window."""
    # Find series in window
    series_in_window = {
        s["id"] for s in series_list
        if window_start <= s["match_date"] < window_end
    }

    # Find games in those series
    games_in_window = {
        gid for gid, g in games.items()
        if g["series_id"] in series_in_window
    }

    if not games_in_window:
        return {}

    # Aggregate pick/ban stats
    champion_stats = defaultdict(lambda: {
        "picks": 0,
        "bans": 0,
        "wins": 0,
        "roles": defaultdict(lambda: {"picks": 0, "wins": 0}),
    })

    for action in draft_actions:
        if action["game_id"] not in games_in_window:
            continue

        champ = action["champion_name"]
        action_type = action["action_type"]

        if action_type == "ban":
            champion_stats[champ]["bans"] += 1
        elif action_type == "pick":
            champion_stats[champ]["picks"] += 1
            # Check if this pick's team won
            game = games.get(action["game_id"])
            if game and game["winner_team_id"] == action["team_id"]:
                champion_stats[champ]["wins"] += 1

    # Calculate priority and performance
    total_games = len(games_in_window)
    champions = {}

    for champ, stats in champion_stats.items():
        picks = stats["picks"]
        bans = stats["bans"]
        wins = stats["wins"]

        # Priority: (picks + bans) / (2 * total_games) - max is 1.0 if picked/banned every game
        priority = (picks + bans) / (2 * total_games) if total_games > 0 else 0

        # Performance: winrate with sample adjustment
        winrate = wins / picks if picks > 0 else 0.5
        adjusted_perf = calculate_adjusted_performance(winrate, picks)

        champions[champ] = {
            "priority": round(priority, 3),
            "roles": {
                "all": {  # Simplified: not tracking per-role in draft_actions without player data
                    "winrate": round(winrate, 3),
                    "picks": picks,
                    "adjusted_performance": round(adjusted_perf, 3),
                }
            },
        }

    return champions


def build_replay_metas(data_dir: Path, output_dir: Path):
    """Build meta files for all tournaments."""
    print(f"Loading data from {data_dir}...")

    tournaments = load_tournaments(data_dir)
    series_list = load_series_with_dates(data_dir)
    games = load_games(data_dir)
    draft_actions = load_draft_actions(data_dir)

    print(f"Loaded {len(tournaments)} tournaments, {len(series_list)} series, {len(games)} games")

    output_dir.mkdir(parents=True, exist_ok=True)

    for tournament_id, tournament in tournaments.items():
        start_date = get_tournament_start_date(tournament_id, series_list)
        if not start_date:
            print(f"  Skipping {tournament['name']}: no series data")
            continue

        window_end = start_date
        window_start = start_date - timedelta(weeks=WINDOW_WEEKS)

        champions = compute_meta_for_window(
            window_start, window_end, series_list, games, draft_actions
        )

        if not champions:
            print(f"  Skipping {tournament['name']}: no games in window")
            continue

        meta_data = {
            "metadata": {
                "tournament_id": tournament_id,
                "tournament_name": tournament["name"],
                "window_start": window_start.isoformat(),
                "window_end": window_end.isoformat(),
                "games_analyzed": len([
                    s for s in series_list
                    if window_start <= s["match_date"] < window_end
                ]),
                "champion_count": len(champions),
            },
            "champions": champions,
            "defaults": {
                "missing_champion_priority": 0.05,
                "missing_champion_performance": 0.35,
            },
        }

        output_path = output_dir / f"{tournament_id}.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(meta_data, f, indent=2)

        print(f"  Generated {output_path.name}: {len(champions)} champions")

    print("Done!")


def main():
    parser = argparse.ArgumentParser(description="Build per-tournament replay meta files")
    parser.add_argument("--data-dir", type=Path, required=True, help="CSV data directory")
    parser.add_argument("--output-dir", type=Path, required=True, help="Output directory for meta files")

    args = parser.parse_args()

    if not args.data_dir.exists():
        raise FileNotFoundError(f"Data directory not found: {args.data_dir}")

    build_replay_metas(args.data_dir, args.output_dir)


if __name__ == "__main__":
    main()
```

**Step 2: Run the script**

Run: `uv run python backend/scripts/build_replay_metas.py --data-dir outputs/full_2024_2025_v2/csv --output-dir knowledge/replay_meta`
Expected: Creates `knowledge/replay_meta/*.json` files

**Step 3: Verify output**

Run: `ls -la knowledge/replay_meta/ | head -10`
Expected: Multiple JSON files named by tournament_id

**Step 4: Commit**

```bash
git add backend/scripts/build_replay_metas.py knowledge/replay_meta/
git commit -m "$(cat <<'EOF'
feat(scripts): add build_replay_metas for historical meta files

Creates per-tournament meta files based on 7-week rolling window
before each tournament's start date. Used for accurate historical
replay recommendations.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Add Tournament ID Lookup to Repository

**Files:**
- Modify: `backend/src/ban_teemo/repositories/draft_repository.py`
- Test: `backend/tests/test_draft_repository.py` (if exists)

**Step 1: Write the failing test**

```python
def test_get_tournament_id_for_game(test_repo):
    """Repository can lookup tournament_id from game_id."""
    # Use a known game_id from the test data
    game_id = "8d1ba7c3-eaf3-4773-b4b4-b48450bf6503"  # From LCK Spring 2024

    tournament_id = test_repo.get_tournament_id_for_game(game_id)

    assert tournament_id == "756908"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest backend/tests/test_draft_repository.py::test_get_tournament_id_for_game -v`
Expected: FAIL with `AttributeError: 'DraftRepository' object has no attribute 'get_tournament_id_for_game'`

**Step 3: Write implementation**

Add to `backend/src/ban_teemo/repositories/draft_repository.py`:

```python
def get_tournament_id_for_game(self, game_id: str) -> str | None:
    """Get tournament_id for a game.

    Args:
        game_id: The game ID to look up

    Returns:
        Tournament ID string, or None if not found
    """
    query = """
        SELECT s.tournament_id
        FROM games g
        JOIN series s ON g.series_id = s.id
        WHERE g.id = ?
    """
    result = self.conn.execute(query, [game_id]).fetchone()
    return result[0] if result else None
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest backend/tests/test_draft_repository.py::test_get_tournament_id_for_game -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/ban_teemo/repositories/draft_repository.py backend/tests/test_draft_repository.py
git commit -m "$(cat <<'EOF'
feat(repo): add get_tournament_id_for_game lookup

Enables looking up tournament context for a game to load
era-appropriate meta data for replay.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Integrate Tournament-Gated Meta into Replay

**Files:**
- Modify: `backend/src/ban_teemo/api/routes/replay.py`
- Modify: `backend/src/ban_teemo/services/replay_manager.py`
- Modify: `backend/src/ban_teemo/services/draft_service.py`

**Step 1: Update replay.py to lookup tournament and pass to session**

In `start_replay` function, after getting `game_id`:

```python
# Get tournament ID for era-appropriate meta
tournament_id = repo.get_tournament_id_for_game(game_id)
tournament_data_file = f"replay_meta/{tournament_id}.json" if tournament_id else None
```

Pass to session creation:

```python
session = manager.create_session(
    game_id=game_id,
    series_id=body.series_id,
    game_number=body.game_number,
    actions=actions,
    draft_state=initial_state,
    speed=body.speed,
    delay_seconds=body.delay_seconds,
    series_score_before=series_score_before,
    series_score_after=series_score_after,
    winner_team_id=winner_team_id,
    winner_side=winner_side,
    llm_enabled=body.llm_enabled,
    llm_api_key=body.llm_api_key,
    wait_for_llm=body.wait_for_llm,
    llm_timeout=body.llm_timeout,
    tournament_data_file=tournament_data_file,  # NEW
)
```

**Step 2: Update ReplaySession and ReplayManager**

Add `tournament_data_file` to `ReplaySession` dataclass and `create_session` method.

**Step 3: Update DraftService to accept tournament_data_file**

Modify DraftService initialization or create per-session recommendation engines with the tournament data file.

**Step 4: Run integration test**

Run: `uv run pytest backend/tests/ -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add backend/src/ban_teemo/api/routes/replay.py backend/src/ban_teemo/services/replay_manager.py backend/src/ban_teemo/services/draft_service.py
git commit -m "$(cat <<'EOF'
feat(replay): integrate tournament-gated meta for historical accuracy

Replay sessions now load era-appropriate meta data based on the
tournament the game belongs to. Uses 7-week rolling window meta
computed from games before tournament start.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: Update _generate_reasons for Tournament Scoring

**Files:**
- Modify: `backend/src/ban_teemo/services/pick_recommendation_engine.py`

**Step 1: Update _generate_reasons method**

Replace meta-tier based reasons with tournament-based reasons:

```python
def _generate_reasons(self, champion: str, result: dict) -> list[str]:
    """Generate human-readable reasons based on component strengths."""
    reasons = []
    components = result["components"]

    # Tournament priority - high contestation in pro play
    priority = components.get("tournament_priority", 0)
    if priority >= 0.6:
        reasons.append("Highly contested in pro play")
    elif priority >= 0.35:
        reasons.append("Regularly contested pick")

    # Tournament performance - role-specific winrate
    performance = components.get("tournament_performance", 0.5)
    if performance >= 0.6:
        reasons.append("Strong tournament winrate")
    elif performance >= 0.55:
        reasons.append("Positive tournament winrate")

    # Proficiency
    prof = components.get("proficiency", 0)
    if prof >= 0.85:
        reasons.append("Elite team proficiency")
    elif prof >= 0.7:
        reasons.append("Strong team proficiency")

    # Matchup/Counter
    matchup_counter = components.get("matchup_counter", 0.5)
    if matchup_counter >= 0.6:
        reasons.append("Strong matchups vs enemy")
    elif matchup_counter >= 0.55:
        reasons.append("Favorable matchups")

    # Synergy
    synergy_mult = result.get("synergy_multiplier", 1.0)
    if synergy_mult >= 1.08:
        reasons.append("Strong team synergy")
    elif components.get("synergy", 0.5) >= 0.55:
        reasons.append("Good team synergy")

    # Archetype
    archetype = components.get("archetype", 0.5)
    if archetype >= 0.7:
        reasons.append("Strengthens team identity")
    elif archetype >= 0.55:
        reasons.append("Fits team composition")

    return reasons if reasons else ["Solid overall pick"]
```

**Step 2: Update _compute_flag method**

Replace meta check with tournament_priority:

```python
def _compute_flag(self, result: dict) -> str | None:
    """Compute recommendation flag for UI badges."""
    if result["confidence"] < 0.7:
        return "LOW_CONFIDENCE"

    # Check for surprise pick: low tournament priority but high proficiency
    priority = result["components"].get("tournament_priority", 0)
    if priority < 0.2 and result["components"].get("proficiency", 0) >= 0.7:
        return "SURPRISE_PICK"
    return None
```

**Step 3: Commit**

```bash
git add backend/src/ban_teemo/services/pick_recommendation_engine.py
git commit -m "$(cat <<'EOF'
refactor(engine): update reasons/flags for tournament scoring

Replace tier-based meta reasons with tournament-based reasons
(contestation, winrate). Update surprise pick detection to use
tournament_priority instead of meta score.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: Clean Up Deprecated MetaScorer Usage

**Files:**
- Modify: `backend/src/ban_teemo/services/pick_recommendation_engine.py`
- Review: All files importing MetaScorer

**Step 1: Audit MetaScorer usage**

The `MetaScorer` is still used for:
- `get_top_meta_champions()` - for candidate generation
- `get_blind_pick_safety()` - for blind pick multiplier
- `get_presence()` - for presence bonus

**Step 2: Decide on each usage**

- `get_top_meta_champions()` → Move to TournamentScorer using `get_top_priority_champions()`
- `get_blind_pick_safety()` → Keep in MetaScorer (pick_context data) or compute from tournament data
- `get_presence()` → Use tournament priority as proxy

**Step 3: Update candidate generation**

Replace `meta_scorer.get_top_meta_champions()` calls with `tournament_scorer.get_top_priority_champions()`:

```python
# In _build_role_cache and _get_candidates
# Before:
meta_picks = self.meta_scorer.get_top_meta_champions(role=role, limit=10)
global_power = self.meta_scorer.get_top_meta_champions(role=None, limit=20)

# After:
meta_picks = self.tournament_scorer.get_top_priority_champions(limit=10)  # Already role-agnostic
global_power = self.tournament_scorer.get_top_priority_champions(limit=20)
```

**Step 4: Commit**

```bash
git add backend/src/ban_teemo/services/pick_recommendation_engine.py
git commit -m "$(cat <<'EOF'
refactor(engine): use tournament scorer for candidate generation

Replace meta_scorer.get_top_meta_champions() with tournament_scorer
for consistent tournament-based candidate selection.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 10: Final Integration Test

**Files:**
- Test manually or create integration test

**Step 1: Start the backend**

Run: `cd backend && uv run uvicorn ban_teemo.main:app --reload`

**Step 2: Test simulator mode (should use current tournament_meta.json)**

```bash
curl -X POST http://localhost:8000/api/simulator/sessions \
  -H "Content-Type: application/json" \
  -d '{"blue_team_id": "406", "red_team_id": "3483"}'
```

Expected: Returns session with recommendations using current tournament data

**Step 3: Test replay mode (should use era-appropriate meta)**

```bash
# Start a replay for an old game
curl -X POST http://localhost:8000/api/replay/start \
  -H "Content-Type: application/json" \
  -d '{"series_id": "2616464", "game_number": 1}'
```

Expected: Returns session that will use `replay_meta/756908.json` (LCK Spring 2024)

**Step 4: Final commit**

```bash
git add -A
git commit -m "$(cat <<'EOF'
feat: complete tournament-gated meta implementation

- Unified scoring to use tournament data (priority + performance)
- Per-tournament meta files for historical replay accuracy
- 7-week rolling window for era-appropriate meta
- Removed simulator_mode branching

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

## Summary of Changes

| File | Change |
|------|--------|
| `tournament_scorer.py` | Add `data_file` parameter, fallback logic |
| `pick_recommendation_engine.py` | Remove `simulator_mode`, unify to tournament scoring |
| `simulator.py` | Remove `simulator_mode=True` |
| `replay.py` | Add tournament lookup, pass `tournament_data_file` |
| `replay_manager.py` | Add `tournament_data_file` to session |
| `draft_repository.py` | Add `get_tournament_id_for_game()` |
| `build_replay_metas.py` | New script for per-tournament meta files |
| `knowledge/replay_meta/` | New directory with tournament meta files |
