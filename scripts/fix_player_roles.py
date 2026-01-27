#!/usr/bin/env python3
"""
Fix player roles using hybrid approach:
1. Try Leaguepedia direct match
2. Try Leaguepedia API search with disambiguation
3. Fall back to champion pool inference
4. Validate Leaguepedia against champion pool (catch misclassifications)

Usage:
    python scripts/fix_player_roles.py
    python scripts/fix_player_roles.py --fetch-missing  # Query Leaguepedia for unmatched players
"""

import argparse
import json
import csv
import time
import re
from pathlib import Path
from collections import defaultdict
from datetime import datetime
from typing import Optional
import requests

BASE_DIR = Path(__file__).parent.parent
LEAGUEPEDIA_FILE = BASE_DIR / "player_roles_leaguepedia.json"
CHAMPION_ROLES_FILE = BASE_DIR / ".claude/skills/grid-lol-data-skill/references/champion_roles.json"
PLAYER_GAME_STATS_CSV = BASE_DIR / "outputs/full_2024_2025_v2/csv/player_game_stats.csv"
OUTPUT_FILE = BASE_DIR / "knowledge/player_roles.json"

# Leaguepedia API
LEAGUEPEDIA_API = "https://lol.fandom.com/api.php"
REQUEST_DELAY = 5.0  # Increased delay to avoid rate limits
MAX_RETRIES = 2

# Role normalization
ROLE_ALIASES = {
    "top": "top", "top laner": "top", "toplane": "top",
    "jungle": "jungle", "jungler": "jungle", "jng": "jungle", "jg": "jungle",
    "mid": "mid", "mid laner": "mid", "midlane": "mid", "middle": "mid",
    "bot": "bot", "adc": "bot", "bot laner": "bot", "ad carry": "bot", "marksman": "bot",
    "support": "support", "sup": "support", "supp": "support",
}

# Champion role signatures for inference
ROLE_CHAMPIONS = {
    "top": {
        "Aatrox", "Ambessa", "Camille", "Cho'Gath", "Darius", "Dr. Mundo", "Fiora",
        "Gangplank", "Gnar", "Gragas", "Gwen", "Irelia", "Jax", "Jayce", "K'Sante",
        "Kennen", "Kled", "Malphite", "Mordekaiser", "Nasus", "Olaf", "Ornn",
        "Renekton", "Rumble", "Sett", "Shen", "Sion", "Urgot", "Yorick"
    },
    "jungle": {
        "Amumu", "Brand", "Diana", "Elise", "Evelynn", "Fiddlesticks", "Graves",
        "Hecarim", "Ivern", "Jarvan IV", "Karthus", "Kha'Zix", "Kindred", "Lee Sin",
        "Lillia", "Maokai", "Naafiri", "Nidalee", "Nocturne", "Nunu & Willump",
        "Pantheon", "Poppy", "Rek'Sai", "Rengar", "Sejuani", "Skarner", "Trundle",
        "Udyr", "Vi", "Viego", "Volibear", "Wukong", "Xin Zhao", "Zac", "Zyra"
    },
    "mid": {
        "Ahri", "Akali", "Anivia", "Annie", "Aurelion Sol", "Aurora", "Azir",
        "Cassiopeia", "Corki", "Galio", "Hwei", "Kassadin", "Katarina", "LeBlanc",
        "Lissandra", "Lux", "Malzahar", "Neeko", "Orianna", "Ryze", "Swain", "Sylas",
        "Syndra", "Taliyah", "Talon", "Tristana", "Twisted Fate", "Veigar", "Vex",
        "Viktor", "Vladimir", "Xerath", "Yasuo", "Yone", "Zed", "Zoe", "Ziggs"
    },
    "bot": {
        "Aphelios", "Ashe", "Caitlyn", "Draven", "Ezreal", "Jhin", "Jinx", "Kai'Sa",
        "Kalista", "Kog'Maw", "Lucian", "Miss Fortune", "Nilah", "Samira", "Senna",
        "Sivir", "Smolder", "Twitch", "Varus", "Vayne", "Xayah", "Zeri"
    },
    "support": {
        "Alistar", "Bard", "Blitzcrank", "Braum", "Janna", "Karma", "Leona", "Lulu",
        "Milio", "Morgana", "Nami", "Nautilus", "Pyke", "Rakan", "Rell", "Renata Glasc",
        "Seraphine", "Sona", "Soraka", "Tahm Kench", "Taric", "Thresh", "Yuumi", "Zilean"
    }
}


def normalize_role(role: str) -> Optional[str]:
    """Normalize role string to standard form."""
    if not role:
        return None
    return ROLE_ALIASES.get(role.lower().strip(), role.lower().strip())


def load_leaguepedia_roles() -> dict:
    """Load existing Leaguepedia player role mappings."""
    if not LEAGUEPEDIA_FILE.exists():
        print(f"Warning: {LEAGUEPEDIA_FILE} not found")
        return {}
    with open(LEAGUEPEDIA_FILE) as f:
        data = json.load(f)
    return data.get("players", {})


def infer_role_from_champions(champion_counts: dict) -> tuple[Optional[str], float]:
    """
    Infer player role from their champion pool.
    Returns (role, confidence) where confidence is 0-1.
    """
    if not champion_counts:
        return None, 0.0

    role_votes = defaultdict(int)
    total_games = sum(champion_counts.values())

    for champ, count in champion_counts.items():
        for role, champs in ROLE_CHAMPIONS.items():
            if champ in champs:
                role_votes[role] += count
                break

    if not role_votes:
        return None, 0.0

    best_role = max(role_votes.items(), key=lambda x: x[1])
    confidence = best_role[1] / total_games if total_games > 0 else 0
    return best_role[0], confidence


def query_leaguepedia_batch(player_names: list[str], retry_count: int = 0) -> dict[str, dict]:
    """
    Query Leaguepedia API for multiple players at once using IN clause.
    Returns dict mapping lowercase player name to player data.
    """
    if not player_names:
        return {}

    # Filter and sanitize names - remove empty/invalid names
    valid_names = []
    for name in player_names:
        name = name.strip()
        if name and len(name) >= 1:
            # Escape quotes in names
            name = name.replace('"', '\\"')
            valid_names.append(name)

    if not valid_names:
        return {}

    # Build IN clause with quoted names
    quoted_names = ','.join(f'"{name}"' for name in valid_names)
    where_clause = f'ID IN ({quoted_names})'

    params = {
        "action": "cargoquery",
        "format": "json",
        "tables": "Players",
        "fields": "ID,Name,Player,Role,Team,Region",
        "where": where_clause,
        "limit": "500",
    }

    try:
        response = requests.get(LEAGUEPEDIA_API, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        # Check for API errors
        if "error" in data:
            error_code = data["error"].get("code", "")
            error_info = str(data["error"])

            # Rate limit or MWException (often rate limit in disguise)
            if (error_code == "ratelimited" or "MWException" in error_info) and retry_count < MAX_RETRIES:
                wait_time = 120 * (retry_count + 1)  # 2min, 4min
                print(f"  Rate limited/error, waiting {wait_time}s (retry {retry_count + 1})...", flush=True)
                time.sleep(wait_time)
                return query_leaguepedia_batch(player_names, retry_count + 1)

            print(f"  API error after retries: {data['error'].get('code', 'unknown')}", flush=True)
            return {}

        results = data.get("cargoquery", [])
        found = {}

        for item in results:
            player_data = item.get("title", {})
            player_id = player_data.get("ID", "")
            role = normalize_role(player_data.get("Role", ""))

            if role and player_id:
                found[player_id.lower()] = {
                    "id": player_id,
                    "name": player_data.get("Name") or player_data.get("Player") or player_id,
                    "role": role,
                    "team": player_data.get("Team", ""),
                    "region": player_data.get("Region", ""),
                }

        return found

    except Exception as e:
        print(f"  Error querying Leaguepedia batch: {e}", flush=True)
        return {}


def query_leaguepedia_player(player_name: str, retry_count: int = 0) -> Optional[dict]:
    """
    Query Leaguepedia API to find a player by name.
    Uses simple ID match to avoid API errors from complex queries.
    """
    # Simple ID match (complex OR/LIKE queries cause API internal errors)
    params = {
        "action": "cargoquery",
        "format": "json",
        "tables": "Players",
        "fields": "ID,Name,Player,Role,Team,Region",
        "where": f'ID="{player_name}"',
        "limit": "5",
    }

    try:
        response = requests.get(LEAGUEPEDIA_API, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()

        # Check for API errors
        if "error" in data:
            error_code = data["error"].get("code", "")
            if error_code == "ratelimited" and retry_count < MAX_RETRIES:
                wait_time = 60 * (retry_count + 1)  # 60s, 120s
                print(f"  Rate limited, waiting {wait_time}s...", flush=True)
                time.sleep(wait_time)
                return query_leaguepedia_player(player_name, retry_count + 1)
            return None

        results = data.get("cargoquery", [])
        if not results:
            return None

        # Return first match with valid role
        for item in results:
            player_data = item.get("title", {})
            player_id = player_data.get("ID", "")
            role = normalize_role(player_data.get("Role", ""))

            if role:
                return {
                    "id": player_id,
                    "name": player_data.get("Name") or player_data.get("Player") or player_id,
                    "role": role,
                    "team": player_data.get("Team", ""),
                    "region": player_data.get("Region", ""),
                }

        return None

    except Exception as e:
        print(f"  Error querying Leaguepedia for {player_name}: {e}", flush=True)
        return None


def analyze_player_stats(fetch_missing: bool = False):
    """
    Analyze player_game_stats.csv and assign roles using hybrid approach.
    """
    leaguepedia = load_leaguepedia_roles()
    print(f"Loaded {len(leaguepedia)} players from Leaguepedia cache")

    # Collect player data from GRID
    player_data = defaultdict(lambda: {
        "teams": defaultdict(int),
        "champions": defaultdict(int),
        "grid_roles": defaultdict(int),
        "games": 0
    })

    with open(PLAYER_GAME_STATS_CSV) as f:
        reader = csv.DictReader(f)
        for row in reader:
            player_name = row["player_name"]
            player_key = player_name.lower()

            player_data[player_key]["player_id"] = row["player_id"]
            player_data[player_key]["player_name"] = player_name
            player_data[player_key]["teams"][row["team_id"]] += 1
            player_data[player_key]["team_names"] = player_data[player_key].get("team_names", {})
            player_data[player_key]["team_names"][row["team_id"]] = row.get("team_name", "")
            player_data[player_key]["champions"][row["champion_name"]] += 1
            if row["role"]:
                player_data[player_key]["grid_roles"][row["role"].lower()] += 1
            player_data[player_key]["games"] += 1

    print(f"Found {len(player_data)} unique players in GRID data")

    # Build corrected player roles
    corrected = {}
    stats = {
        "leaguepedia_cached": 0,
        "leaguepedia_fetched": 0,
        "champion_inference": 0,
        "leaguepedia_corrected": 0,  # Leaguepedia overridden by champion inference
    }

    # Track players needing Leaguepedia lookup
    players_to_fetch = []

    for player_key, data in player_data.items():
        # Get most frequent team
        team_id = max(data["teams"].items(), key=lambda x: x[1])[0] if data["teams"] else ""
        team_name = data.get("team_names", {}).get(team_id, "")

        # Calculate champion inference
        inferred_role, confidence = infer_role_from_champions(data["champions"])

        role = None
        source = None

        # 1. Check Leaguepedia cache
        if player_key in leaguepedia:
            lp_role = normalize_role(leaguepedia[player_key].get("role", ""))

            # Validate against champion inference
            if inferred_role and lp_role and inferred_role != lp_role and confidence >= 0.7:
                # Champion inference strongly disagrees with Leaguepedia
                # This catches misclassifications like BeryL (bot -> support)
                print(f"  Correcting {player_key}: Leaguepedia={lp_role}, Inference={inferred_role} ({confidence:.0%})")
                role = inferred_role
                source = "leaguepedia_corrected"
                stats["leaguepedia_corrected"] += 1
            else:
                role = lp_role
                source = "leaguepedia"
                stats["leaguepedia_cached"] += 1

        # 2. Not in cache - mark for API fetch
        elif fetch_missing:
            players_to_fetch.append((player_key, data, team_id, team_name, inferred_role, confidence))
            continue  # Will process after fetching

        # 3. Use champion inference
        if not role and inferred_role:
            role = inferred_role
            source = "champion_inference"
            stats["champion_inference"] += 1

        if role:
            corrected[player_key] = {
                "id": data["player_id"],
                "name": data["player_name"],
                "role": role,
                "team": team_name,
                "team_id": team_id,
                "source": source,
                "games": data["games"],
                "inference_confidence": round(confidence, 2) if inferred_role else None
            }

    # Fetch missing players from Leaguepedia API using batch queries
    if fetch_missing and players_to_fetch:
        print(f"\nFetching {len(players_to_fetch)} players from Leaguepedia API...", flush=True)
        fetched_count = 0

        # Build lookup for player data
        player_lookup = {p[0]: p for p in players_to_fetch}  # player_key -> full tuple
        player_names = [data["player_name"] for _, data, _, _, _, _ in players_to_fetch]

        # Try fetching all in one request (query is ~2000 chars, within URL limits)
        # Fall back to batches if needed
        BATCH_SIZE = 100  # Larger batches, fewer requests
        all_lp_results = {}

        for batch_start in range(0, len(player_names), BATCH_SIZE):
            batch = player_names[batch_start:batch_start + BATCH_SIZE]
            batch_num = batch_start // BATCH_SIZE + 1
            total_batches = (len(player_names) + BATCH_SIZE - 1) // BATCH_SIZE
            print(f"  Batch {batch_num}/{total_batches}: querying {len(batch)} players...", flush=True)

            batch_results = query_leaguepedia_batch(batch)
            all_lp_results.update(batch_results)
            print(f"    Found {len(batch_results)} matches", flush=True)

            # Save progress after each batch - update cache immediately
            if batch_results:
                for player_key, lp_data in batch_results.items():
                    leaguepedia[player_key] = lp_data
                # Save cache to disk
                cache_output = {
                    "metadata": {
                        "generated_at": datetime.now().isoformat(),
                        "total_players": len(leaguepedia),
                        "source": "leaguepedia",
                    },
                    "players": leaguepedia,
                }
                with open(LEAGUEPEDIA_FILE, "w") as f:
                    json.dump(cache_output, f, indent=2)
                print(f"    Saved {len(batch_results)} to cache (total: {len(leaguepedia)})", flush=True)

            if batch_start + BATCH_SIZE < len(player_names):
                time.sleep(60)  # 60s between batches to avoid rate limits

        print(f"  Total API matches: {len(all_lp_results)}", flush=True)

        # Process results
        for player_key, data, team_id, team_name, inferred_role, confidence in players_to_fetch:
            lp_data = all_lp_results.get(player_key)

            role = None
            source = None

            if lp_data and lp_data.get("role"):
                lp_role = lp_data["role"]

                # Validate against champion inference
                if inferred_role and lp_role != inferred_role and confidence >= 0.7:
                    print(f"  Correcting {player_key}: Leaguepedia={lp_role}, Inference={inferred_role} ({confidence:.0%})", flush=True)
                    role = inferred_role
                    source = "leaguepedia_corrected"
                    stats["leaguepedia_corrected"] += 1
                else:
                    role = lp_role
                    source = "leaguepedia_fetched"
                    stats["leaguepedia_fetched"] += 1
                    fetched_count += 1

                    # Update cache for future runs
                    leaguepedia[player_key] = lp_data

            # Fall back to champion inference
            if not role and inferred_role:
                role = inferred_role
                source = "champion_inference"
                stats["champion_inference"] += 1

            if role:
                corrected[player_key] = {
                    "id": data["player_id"],
                    "name": data["player_name"],
                    "role": role,
                    "team": team_name,
                    "team_id": team_id,
                    "source": source,
                    "games": data["games"],
                    "inference_confidence": round(confidence, 2) if inferred_role else None
                }

        print(f"  Fetched {fetched_count} new players from Leaguepedia", flush=True)

        # Save updated Leaguepedia cache
        if fetched_count > 0:
            cache_output = {
                "metadata": {
                    "generated_at": datetime.now().isoformat(),
                    "total_players": len(leaguepedia),
                    "source": "leaguepedia",
                },
                "players": leaguepedia,
            }
            with open(LEAGUEPEDIA_FILE, "w") as f:
                json.dump(cache_output, f, indent=2)
            print(f"  Updated Leaguepedia cache with {fetched_count} new entries")

    return corrected, stats


def main():
    parser = argparse.ArgumentParser(description="Fix player roles using hybrid approach")
    parser.add_argument(
        "--fetch-missing",
        action="store_true",
        help="Query Leaguepedia API for players not in cache"
    )
    args = parser.parse_args()

    print("Analyzing player game stats...")
    corrected, stats = analyze_player_stats(fetch_missing=args.fetch_missing)

    print(f"\n=== Role Assignment Sources ===")
    print(f"  Leaguepedia (cached):    {stats['leaguepedia_cached']}")
    print(f"  Leaguepedia (fetched):   {stats['leaguepedia_fetched']}")
    print(f"  Leaguepedia (corrected): {stats['leaguepedia_corrected']}")
    print(f"  Champion inference:      {stats['champion_inference']}")
    print(f"  Total players:           {len(corrected)}")

    # Validate known players
    print("\n=== Validation Check ===")
    test_players = ["faker", "chovy", "showmaker", "beryl", "bat", "perkz", "theshy"]
    for name in test_players:
        if name in corrected:
            p = corrected[name]
            conf = f" ({p['inference_confidence']:.0%})" if p.get('inference_confidence') else ""
            print(f"  {name}: {p['role']} (source: {p['source']}{conf})")

    # Save output
    output = {
        "metadata": {
            "generated_at": datetime.now().isoformat(),
            "total_players": len(corrected),
            "sources": stats,
            "description": "Player roles: Leaguepedia + champion inference (validated)"
        },
        "players": corrected
    }

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\nSaved to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
