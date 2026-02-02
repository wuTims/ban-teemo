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


def parse_date(date_str: str) -> datetime | None:
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


def load_player_game_stats(data_dir: Path) -> dict:
    """Load player game stats and create lookup for role/win info.

    Returns dict keyed by (game_id, team_id, champion_name) with role and team_won.
    """
    lookup = {}
    stats_path = data_dir / "player_game_stats.csv"
    if not stats_path.exists():
        print(f"  Warning: {stats_path} not found, will use 'all' role fallback")
        return lookup

    with open(stats_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            key = (row["game_id"], row["team_id"], row["champion_name"])
            lookup[key] = {
                "role": normalize_role(row["role"]) if row.get("role") else "unknown",
                "team_won": row.get("team_won", "").lower() == "true",
            }
    return lookup


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
    player_stats_lookup: dict,
) -> dict:
    """Compute champion meta stats for games in the time window.

    Uses player_stats_lookup to get role-specific stats when available.
    """
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

    # Aggregate pick/ban stats with role breakdown
    # Structure: champion -> {bans, total_picks, total_wins, roles: {role -> {picks, wins}}}
    champion_stats = defaultdict(lambda: {
        "bans": 0,
        "total_picks": 0,
        "total_wins": 0,
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
            champion_stats[champ]["total_picks"] += 1

            # Look up role from player_game_stats
            lookup_key = (action["game_id"], action["team_id"], champ)
            player_info = player_stats_lookup.get(lookup_key)

            if player_info:
                role = player_info["role"]
                won = player_info["team_won"]
            else:
                # Fallback if no player stats (shouldn't happen often)
                role = "unknown"
                game = games.get(action["game_id"])
                won = game and game["winner_team_id"] == action["team_id"]

            champion_stats[champ]["roles"][role]["picks"] += 1
            if won:
                champion_stats[champ]["total_wins"] += 1
                champion_stats[champ]["roles"][role]["wins"] += 1

    # Calculate priority and role-specific performance
    total_games = len(games_in_window)
    champions = {}

    for champ, stats in champion_stats.items():
        total_picks = stats["total_picks"]
        bans = stats["bans"]

        # Priority: (picks + bans) / (2 * total_games) - max is 1.0 if picked/banned every game
        priority = (total_picks + bans) / (2 * total_games) if total_games > 0 else 0

        # Build role-specific stats
        roles_data = {}
        for role, role_stats in stats["roles"].items():
            picks = role_stats["picks"]
            wins = role_stats["wins"]

            if picks > 0:
                winrate = wins / picks
                adjusted_perf = calculate_adjusted_performance(winrate, picks)
                roles_data[role] = {
                    "winrate": round(winrate, 3),
                    "picks": picks,
                    "adjusted_performance": round(adjusted_perf, 3),
                }

        # Only include champions with actual role data
        if roles_data:
            champions[champ] = {
                "priority": round(priority, 3),
                "roles": roles_data,
            }

    return champions


def build_replay_metas(data_dir: Path, output_dir: Path):
    """Build meta files for all tournaments."""
    print(f"Loading data from {data_dir}...")

    tournaments = load_tournaments(data_dir)
    series_list = load_series_with_dates(data_dir)
    games = load_games(data_dir)
    draft_actions = load_draft_actions(data_dir)
    player_stats_lookup = load_player_game_stats(data_dir)

    print(f"Loaded {len(tournaments)} tournaments, {len(series_list)} series, {len(games)} games")
    print(f"Loaded {len(player_stats_lookup)} player game stats entries for role lookup")

    output_dir.mkdir(parents=True, exist_ok=True)

    for tournament_id, tournament in tournaments.items():
        start_date = get_tournament_start_date(tournament_id, series_list)
        if not start_date:
            print(f"  Skipping {tournament['name']}: no series data")
            continue

        window_end = start_date
        window_start = start_date - timedelta(weeks=WINDOW_WEEKS)

        champions = compute_meta_for_window(
            window_start, window_end, series_list, games, draft_actions, player_stats_lookup
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
