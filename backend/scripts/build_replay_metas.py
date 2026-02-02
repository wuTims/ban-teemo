#!/usr/bin/env python3
"""
Build per-series meta files for historical replay.

For each series, computes meta statistics from games played within
the lookback window BEFORE that series date. This ensures replays
use only data that would have been available at game time.

Uses authoritative player roles from player_roles.json instead of
unreliable role column in player_game_stats.csv.

Usage:
    uv run python backend/scripts/build_replay_metas.py \
        --data-dir outputs/full_2024_2025_v2/csv \
        --output-dir knowledge/replay_meta \
        --knowledge-dir knowledge
"""

import argparse
import csv
import json
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path


# Extended window to capture full competitive split (regular season + play-in + etc.)
WINDOW_WEEKS = 18
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


def load_player_roles(knowledge_dir: Path) -> dict:
    """Load authoritative player roles from player_roles.json.

    Returns dict keyed by player_id -> role.
    """
    roles_path = knowledge_dir / "player_roles.json"
    if not roles_path.exists():
        print(f"  Warning: {roles_path} not found, will use CSV role fallback")
        return {}

    with open(roles_path, encoding="utf-8") as f:
        data = json.load(f)
        # Build lookup by player_id
        player_roles = {}
        for player_key, player_data in data.get("players", {}).items():
            player_id = player_data.get("id")
            role = player_data.get("role")
            if player_id and role:
                player_roles[player_id] = normalize_role(role)
        return player_roles


def load_player_game_stats(data_dir: Path, player_roles: dict) -> dict:
    """Load player game stats and create lookup for role/win info.

    Uses authoritative player_roles for role assignment instead of CSV role column.
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
            player_id = row.get("player_id")

            # Use authoritative player_roles.json, fall back to CSV role
            if player_id and player_id in player_roles:
                role = player_roles[player_id]
            elif row.get("role"):
                role = normalize_role(row["role"])
            else:
                role = "unknown"

            lookup[key] = {
                "role": role,
                "team_won": row.get("team_won", "").lower() == "true",
            }
    return lookup


def compute_meta_for_window(
    window_start: datetime,
    window_end: datetime,
    series_list: list[dict],
    games: dict,
    draft_actions: list[dict],
    player_stats_lookup: dict,
) -> tuple[dict, int]:
    """Compute champion meta stats for games in the time window.

    Uses player_stats_lookup to get role-specific stats when available.

    Returns:
        Tuple of (champions dict, games_analyzed count)
    """
    # Find series in window (strictly before window_end to avoid including target game)
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
        return {}, 0

    # Aggregate pick/ban stats with role breakdown
    # Structure: champion -> {games_present: set, total_picks, total_wins, roles: {role -> {picks, wins}}}
    champion_stats = defaultdict(lambda: {
        "games_present": set(),  # Games where champion was picked OR banned (for presence calc)
        "total_picks": 0,
        "total_wins": 0,
        "roles": defaultdict(lambda: {"picks": 0, "wins": 0}),
    })

    for action in draft_actions:
        if action["game_id"] not in games_in_window:
            continue

        champ = action["champion_name"]
        action_type = action["action_type"]
        game_id = action["game_id"]

        # Track presence (games where champion appears in pick OR ban)
        champion_stats[champ]["games_present"].add(game_id)

        if action_type == "ban":
            pass  # Already tracked in games_present
        elif action_type == "pick":
            champion_stats[champ]["total_picks"] += 1

            # Look up role from player_game_stats
            lookup_key = (game_id, action["team_id"], champ)
            player_info = player_stats_lookup.get(lookup_key)

            if player_info:
                role = player_info["role"]
                won = player_info["team_won"]
            else:
                # Fallback if no player stats (shouldn't happen often)
                role = "unknown"
                game = games.get(game_id)
                won = game and game["winner_team_id"] == action["team_id"]

            champion_stats[champ]["roles"][role]["picks"] += 1
            if won:
                champion_stats[champ]["total_wins"] += 1
                champion_stats[champ]["roles"][role]["wins"] += 1

    # Calculate priority (presence) and role-specific performance
    total_games = len(games_in_window)
    champions = {}

    for champ, stats in champion_stats.items():
        games_present = len(stats["games_present"])

        # Priority = presence = games where champion was picked OR banned / total games
        # This matches gol.gg's standard presence calculation (0-100%)
        priority = games_present / total_games if total_games > 0 else 0

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

    return champions, total_games


def build_series_metas(
    data_dir: Path,
    output_dir: Path,
    knowledge_dir: Path,
    series_ids: list[str] | None = None,
):
    """Build meta files for specific series or all series.

    Args:
        data_dir: Path to CSV data directory
        output_dir: Path to output directory for meta files
        knowledge_dir: Path to knowledge directory
        series_ids: Optional list of specific series IDs to build. If None, builds for all.
    """
    print(f"Loading data from {data_dir}...")

    tournaments = load_tournaments(data_dir)
    series_list = load_series_with_dates(data_dir)
    games = load_games(data_dir)
    draft_actions = load_draft_actions(data_dir)

    # Load authoritative player roles first
    player_roles = load_player_roles(knowledge_dir)
    print(f"Loaded {len(player_roles)} authoritative player roles from player_roles.json")

    player_stats_lookup = load_player_game_stats(data_dir, player_roles)

    print(f"Loaded {len(tournaments)} tournaments, {len(series_list)} series, {len(games)} games")
    print(f"Loaded {len(player_stats_lookup)} player game stats entries for role lookup")

    output_dir.mkdir(parents=True, exist_ok=True)

    # Build lookup for series by ID
    series_by_id = {s["id"]: s for s in series_list}

    # Determine which series to process
    if series_ids:
        target_series = [series_by_id[sid] for sid in series_ids if sid in series_by_id]
    else:
        target_series = series_list

    print(f"Building meta files for {len(target_series)} series...")

    generated = 0
    skipped = 0

    for series in target_series:
        series_id = series["id"]
        series_date = series["match_date"]
        tournament_id = series["tournament_id"]
        tournament_name = tournaments.get(tournament_id, {}).get("name", "Unknown")

        # Window ends at series date (exclusive - don't include the target game)
        window_end = series_date
        window_start = series_date - timedelta(weeks=WINDOW_WEEKS)

        champions, games_analyzed = compute_meta_for_window(
            window_start, window_end, series_list, games, draft_actions, player_stats_lookup
        )

        if not champions:
            skipped += 1
            continue

        meta_data = {
            "metadata": {
                "series_id": series_id,
                "tournament_id": tournament_id,
                "tournament_name": tournament_name,
                "series_date": series_date.isoformat(),
                "window_start": window_start.isoformat(),
                "window_end": window_end.isoformat(),
                "games_analyzed": games_analyzed,
                "champion_count": len(champions),
            },
            "champions": champions,
            "defaults": {
                "missing_champion_priority": 0.05,
                "missing_champion_performance": 0.35,
            },
        }

        output_path = output_dir / f"series_{series_id}.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(meta_data, f, indent=2)

        generated += 1

    print(f"Generated {generated} series meta files, skipped {skipped} (no data in window)")


def main():
    parser = argparse.ArgumentParser(description="Build per-series replay meta files")
    parser.add_argument("--data-dir", type=Path, required=True, help="CSV data directory")
    parser.add_argument("--output-dir", type=Path, required=True, help="Output directory for meta files")
    parser.add_argument("--knowledge-dir", type=Path, default=Path("knowledge"),
                        help="Knowledge directory containing player_roles.json (default: knowledge)")
    parser.add_argument("--series-ids", nargs="*", help="Specific series IDs to build (default: all)")

    args = parser.parse_args()

    if not args.data_dir.exists():
        raise FileNotFoundError(f"Data directory not found: {args.data_dir}")

    build_series_metas(args.data_dir, args.output_dir, args.knowledge_dir, args.series_ids)


if __name__ == "__main__":
    main()
