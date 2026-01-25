#!/usr/bin/env python3
"""
Leaguepedia Player Role Fetcher

Fetches player role mappings from Leaguepedia's Cargo API and saves them
to a JSON file for use during GRID data export.

Usage:
    python fetch_player_roles.py --output player_roles.json
    python fetch_player_roles.py --players "Faker,Chovy,Zeus"
    python fetch_player_roles.py --from-grid ./outputs/full_2024_2025_v2/raw/
"""

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import urlencode

import requests

# Leaguepedia API endpoint
LEAGUEPEDIA_API = "https://lol.fandom.com/api.php"

# Rate limiting
REQUEST_DELAY = 2.0  # seconds between requests
MAX_RETRIES = 3
RETRY_DELAY = 10.0  # seconds to wait after rate limit

# Standard role mappings (normalize various forms)
ROLE_ALIASES = {
    # Top
    "top": "top",
    "top laner": "top",
    "toplane": "top",
    "top lane": "top",
    # Jungle
    "jungle": "jungle",
    "jungler": "jungle",
    "jng": "jungle",
    "jg": "jungle",
    # Mid
    "mid": "mid",
    "mid laner": "mid",
    "midlane": "mid",
    "mid lane": "mid",
    "middle": "mid",
    # Bot/ADC
    "bot": "bot",
    "adc": "bot",
    "bot laner": "bot",
    "botlane": "bot",
    "bot lane": "bot",
    "ad carry": "bot",
    "marksman": "bot",
    # Support
    "support": "support",
    "sup": "support",
    "supp": "support",
}


def normalize_role(role: str) -> Optional[str]:
    """Normalize a role string to standard form."""
    if not role:
        return None
    role_lower = role.lower().strip()
    return ROLE_ALIASES.get(role_lower, role_lower)


def query_leaguepedia(
    tables: str,
    fields: str,
    where: Optional[str] = None,
    join_on: Optional[str] = None,
    order_by: Optional[str] = None,
    limit: int = 500,
    offset: int = 0,
) -> List[Dict]:
    """Execute a Cargo query against Leaguepedia API with retry logic."""
    params = {
        "action": "cargoquery",
        "format": "json",
        "tables": tables,
        "fields": fields,
        "limit": str(limit),
        "offset": str(offset),
    }
    if where:
        params["where"] = where
    if join_on:
        params["join_on"] = join_on
    if order_by:
        params["order_by"] = order_by

    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(LEAGUEPEDIA_API, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            if "error" in data:
                error_code = data["error"].get("code", "")
                if error_code == "ratelimited":
                    print(f"  Rate limited, waiting {RETRY_DELAY}s (attempt {attempt + 1}/{MAX_RETRIES})...")
                    time.sleep(RETRY_DELAY)
                    continue
                print(f"API Error: {data['error']}")
                return []

            results = data.get("cargoquery", [])
            return [item.get("title", {}) for item in results]

        except requests.exceptions.RequestException as e:
            print(f"Request failed (attempt {attempt + 1}/{MAX_RETRIES}): {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)
            continue
        except json.JSONDecodeError as e:
            print(f"JSON decode error: {e}")
            return []

    return []


def fetch_all_players(limit_per_query: int = 500) -> List[Dict]:
    """Fetch all players from Leaguepedia Players table."""
    all_players = []
    offset = 0

    print("Fetching players from Leaguepedia...")

    while True:
        results = query_leaguepedia(
            tables="Players",
            fields="ID,Name,Player,Role,Team,Country,Region,IsRetired,ToWin",
            order_by="ID ASC",
            limit=limit_per_query,
            offset=offset,
        )

        if not results:
            break

        all_players.extend(results)
        print(f"  Fetched {len(all_players)} players...")

        if len(results) < limit_per_query:
            break

        offset += limit_per_query
        time.sleep(REQUEST_DELAY)  # Be nice to the API

    return all_players


def fetch_players_by_names(names: List[str]) -> List[Dict]:
    """Fetch specific players by their IDs/names."""
    if not names:
        return []

    # Build WHERE clause with OR conditions
    conditions = []
    for name in names:
        escaped_name = name.replace('"', '\\"')
        conditions.append(f'ID="{escaped_name}"')
        conditions.append(f'Player="{escaped_name}"')

    where_clause = " OR ".join(conditions)

    return query_leaguepedia(
        tables="Players",
        fields="ID,Name,Player,Role,Team,Country,Region",
        where=where_clause,
        limit=500,
    )


def fetch_tournament_players(tournament: str) -> List[Dict]:
    """Fetch players who participated in a specific tournament."""
    results = query_leaguepedia(
        tables="TournamentPlayers=TP,Players=P",
        fields="TP.Player,TP.Team,TP.Role,P.ID,P.Name,P.Role=PlayerRole",
        join_on="TP.Player=P.ID",
        where=f'TP.Tournament="{tournament}"',
        limit=500,
    )
    return results


def fetch_scoreboard_players(limit: int = 5000) -> List[Dict]:
    """Fetch player roles from ScoreboardPlayers (game-level data)."""
    all_results = []
    offset = 0

    print("Fetching scoreboard player data...")

    while offset < limit:
        batch_limit = min(500, limit - offset)
        results = query_leaguepedia(
            tables="ScoreboardPlayers",
            fields="Link,Name,Role,Team,DateTime_UTC",
            where="Role IS NOT NULL AND Role != ''",
            order_by="DateTime_UTC DESC",
            limit=batch_limit,
            offset=offset,
        )

        if not results:
            break

        all_results.extend(results)
        print(f"  Fetched {len(all_results)} scoreboard entries...")

        if len(results) < batch_limit:
            break

        offset += batch_limit
        time.sleep(REQUEST_DELAY)

    return all_results


def extract_player_names_from_grid(raw_dir: Path) -> Set[str]:
    """Extract unique player names from GRID raw JSON files."""
    player_names = set()

    if not raw_dir.exists():
        print(f"Directory not found: {raw_dir}")
        return player_names

    series_files = list(raw_dir.glob("series_*.json"))
    print(f"Scanning {len(series_files)} series files...")

    for series_file in series_files:
        try:
            with open(series_file, "r") as f:
                data = json.load(f)

            series_state = data.get("data", {}).get("seriesState", {})
            for game in series_state.get("games", []):
                for team in game.get("teams", []):
                    for player in team.get("players", []):
                        name = player.get("name")
                        if name:
                            player_names.add(name)
        except (json.JSONDecodeError, IOError) as e:
            print(f"  Error reading {series_file.name}: {e}")
            continue

    print(f"Found {len(player_names)} unique player names")
    return player_names


def extract_short_name(full_name: str) -> str:
    """Extract the short name from a full name like 'Adam (Adam Maanane)'."""
    # Remove disambiguation in parentheses
    match = re.match(r'^([^(]+)', full_name)
    if match:
        return match.group(1).strip()
    return full_name.strip()


def build_player_role_mapping(
    players: List[Dict],
    scoreboard_data: Optional[List[Dict]] = None,
) -> Dict[str, Dict]:
    """Build a mapping of player names to their roles and metadata."""
    mapping = {}

    def add_to_mapping(key: str, data: Dict):
        """Add to mapping, preferring players_table over scoreboard."""
        key_lower = key.lower()
        if key_lower not in mapping or mapping[key_lower].get("source") == "scoreboard":
            mapping[key_lower] = data

    # First, process Players table data (canonical roles)
    for player in players:
        player_id = player.get("ID", "").strip()
        player_name = player.get("Player") or player.get("Name") or player_id
        role = normalize_role(player.get("Role", ""))

        if not role:
            continue

        data = {
            "id": player_id,
            "name": player_name,
            "role": role,
            "team": player.get("Team", ""),
            "region": player.get("Region", ""),
            "source": "players_table",
        }

        # Add by ID
        if player_id:
            add_to_mapping(player_id, data)
            # Also add short name version of ID
            short_id = extract_short_name(player_id)
            if short_id != player_id:
                add_to_mapping(short_id, data)

        # Add by player name if different
        if player_name and player_name != player_id:
            add_to_mapping(player_name, data)
            short_name = extract_short_name(player_name)
            if short_name != player_name:
                add_to_mapping(short_name, data)

    # Then, augment with scoreboard data (more recent, game-specific roles)
    if scoreboard_data:
        # Group by player and count role occurrences
        player_role_counts: Dict[str, Dict[str, int]] = {}
        player_teams: Dict[str, str] = {}

        for entry in scoreboard_data:
            name = (entry.get("Link") or entry.get("Name") or "").strip()
            role = normalize_role(entry.get("Role", ""))
            team = entry.get("Team", "")

            if not name or not role:
                continue

            name_lower = name.lower()
            if name_lower not in player_role_counts:
                player_role_counts[name_lower] = {}

            player_role_counts[name_lower][role] = (
                player_role_counts[name_lower].get(role, 0) + 1
            )

            if team:
                player_teams[name_lower] = team

        # For each player, use most common role from recent games
        for name_lower, role_counts in player_role_counts.items():
            most_common_role = max(role_counts.items(), key=lambda x: x[1])[0]

            data = {
                "id": name_lower,
                "name": name_lower,
                "role": most_common_role,
                "team": player_teams.get(name_lower, ""),
                "region": "",
                "source": "scoreboard",
            }

            add_to_mapping(name_lower, data)

            # Also add short name version
            short_name = extract_short_name(name_lower)
            if short_name != name_lower:
                add_to_mapping(short_name, data)

    return mapping


def save_mapping(mapping: Dict, output_path: Path):
    """Save the player-role mapping to a JSON file."""
    # Convert to a more useful format for lookups
    output = {
        "metadata": {
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "total_players": len(mapping),
            "source": "leaguepedia",
        },
        "players": mapping,
    }

    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"Saved {len(mapping)} player mappings to {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Fetch player role mappings from Leaguepedia"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="player_roles.json",
        help="Output JSON file path",
    )
    parser.add_argument(
        "--players",
        type=str,
        help="Comma-separated list of specific player names to fetch",
    )
    parser.add_argument(
        "--from-grid",
        type=str,
        help="Path to GRID raw directory to extract player names from",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Fetch all players from Leaguepedia (slow)",
    )
    parser.add_argument(
        "--scoreboard-limit",
        type=int,
        default=10000,
        help="Number of recent scoreboard entries to fetch (default: 10000)",
    )
    parser.add_argument(
        "--skip-players-table",
        action="store_true",
        help="Skip fetching from Players table (use only scoreboard data)",
    )

    args = parser.parse_args()

    output_path = Path(args.output)
    players_data = []
    scoreboard_data = []

    # Determine which players to fetch
    if args.players:
        # Fetch specific players
        names = [n.strip() for n in args.players.split(",") if n.strip()]
        print(f"Fetching {len(names)} specific players...")
        players_data = fetch_players_by_names(names)

    elif args.from_grid:
        # Extract names from GRID data for reference
        raw_dir = Path(args.from_grid)
        player_names = extract_player_names_from_grid(raw_dir)
        print(f"Will match against {len(player_names)} player names from GRID data")
        # Don't batch-fetch by name - just use scoreboard data which is more reliable

    elif args.all:
        # Fetch all players
        players_data = fetch_all_players()

    else:
        # Default: fetch recent scoreboard data
        print("No specific players requested. Fetching recent scoreboard data...")

    # Always fetch scoreboard data for more accurate recent roles
    scoreboard_data = fetch_scoreboard_players(limit=args.scoreboard_limit)

    # If we didn't get player data from Players table, still build from scoreboard
    if not players_data and not scoreboard_data:
        print("No data fetched. Try with --all or --from-grid options.")
        sys.exit(1)

    # Build and save mapping
    mapping = build_player_role_mapping(players_data, scoreboard_data)
    save_mapping(mapping, output_path)

    # Print summary
    print("\n=== Summary ===")
    role_counts = {}
    for player in mapping.values():
        role = player.get("role", "unknown")
        role_counts[role] = role_counts.get(role, 0) + 1

    for role, count in sorted(role_counts.items()):
        print(f"  {role}: {count}")


if __name__ == "__main__":
    main()
