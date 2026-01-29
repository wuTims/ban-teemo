#!/usr/bin/env python3
"""
Build computed datasets for the recommendation engine.

Usage:
    python scripts/build_computed_datasets.py --all
    python scripts/build_computed_datasets.py --dataset role_baselines
    python scripts/build_computed_datasets.py --dataset meta_stats --current-patch 15.17
"""

import argparse
import json
import csv
from pathlib import Path
from datetime import datetime
from collections import defaultdict
import math

# Paths
BASE_DIR = Path(__file__).parent.parent
CSV_DIR = BASE_DIR / "outputs" / "full_2024_2025_v2" / "csv"
KNOWLEDGE_DIR = BASE_DIR / "knowledge"
OUTPUT_DIR = KNOWLEDGE_DIR

# Input files
PATCH_DATES_FILE = KNOWLEDGE_DIR / "patch_dates.json"
REWORK_MAPPING_FILE = KNOWLEDGE_DIR / "rework_patch_mapping.json"
PLAYER_ROLES_FILE = KNOWLEDGE_DIR / "player_roles.json"  # Corrected roles
KNOWLEDGE_BASE_FILE = KNOWLEDGE_DIR / "knowledge_base.json"
SYNERGIES_FILE = KNOWLEDGE_DIR / "synergies.json"

# Cached player roles (loaded once)
_PLAYER_ROLES_CACHE = None

# CSV files
PLAYER_GAME_STATS_CSV = CSV_DIR / "player_game_stats.csv"
GAMES_CSV = CSV_DIR / "games.csv"
SERIES_CSV = CSV_DIR / "series.csv"
DRAFT_ACTIONS_CSV = CSV_DIR / "draft_actions.csv"


def load_json(path: Path) -> dict | list:
    """Load a JSON file."""
    with open(path) as f:
        return json.load(f)


def save_json(data: dict | list, path: Path):
    """Save data to a JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"  Saved: {path}")


def load_csv(path: Path) -> list[dict]:
    """Load a CSV file as list of dicts."""
    with open(path) as f:
        return list(csv.DictReader(f))


def load_player_roles() -> dict[str, str]:
    """Load corrected player roles (from Leaguepedia + champion inference)."""
    global _PLAYER_ROLES_CACHE
    if _PLAYER_ROLES_CACHE is not None:
        return _PLAYER_ROLES_CACHE

    _PLAYER_ROLES_CACHE = {}
    if PLAYER_ROLES_FILE.exists():
        data = load_json(PLAYER_ROLES_FILE)
        _PLAYER_ROLES_CACHE = {k: v["role"] for k, v in data.get("players", {}).items()}
    return _PLAYER_ROLES_CACHE


def get_player_role(player_name: str, csv_role: str = "") -> str:
    """Get player role using corrected data, falling back to CSV if needed.

    Returns normalized role: TOP, JUNGLE, MID, ADC, SUP
    """
    player_roles = load_player_roles()
    player_key = player_name.lower()

    if player_key in player_roles:
        role = player_roles[player_key].upper()
    else:
        role = csv_role.upper()

    # Normalize
    if role == "BOT":
        role = "ADC"
    if role == "SUPPORT":
        role = "SUP"

    return role if role in ["TOP", "JUNGLE", "MID", "ADC", "SUP"] else ""


def patch_to_num(patch: str) -> int:
    """Convert patch string to numeric for comparison. '14.24' -> 1424, '15.3' -> 1503"""
    if not patch:
        return 0
    parts = patch.split(".")
    if len(parts) != 2:
        return 0
    try:
        return int(parts[0]) * 100 + int(parts[1])
    except ValueError:
        return 0


def get_patch_weight(game_patch: str, current_patch: str) -> float:
    """Calculate weight based on patch distance."""
    if not game_patch or not current_patch:
        return 0.3  # Default low weight for unknown patches

    current_num = patch_to_num(current_patch)
    game_num = patch_to_num(game_patch)

    if game_num == 0 or current_num == 0:
        return 0.3

    distance = current_num - game_num

    if distance <= 0:  # Same or future patch
        return 1.0
    elif distance <= 2:
        return 0.9
    elif distance <= 5:
        return 0.7
    elif distance <= 10:
        return 0.5
    else:
        return 0.3


def is_post_rework(champion: str, game_patch: str, reworks: dict) -> bool:
    """Check if game is after champion's most recent rework."""
    if champion not in reworks:
        return True  # No rework, all data valid

    rework_patches = reworks[champion]
    if not rework_patches:
        return True

    # Get the most recent rework patch
    latest_rework = max(rework_patches, key=lambda p: patch_to_num(p.replace("V", "")))
    latest_rework_num = patch_to_num(latest_rework.replace("V", ""))
    game_patch_num = patch_to_num(game_patch)

    return game_patch_num >= latest_rework_num


# ============================================================================
# Dataset Builders
# ============================================================================

def build_patch_info(current_patch: str) -> dict:
    """Build patch_info.json with patch metadata."""
    print("Building patch_info.json...")

    patch_dates = load_json(PATCH_DATES_FILE)
    games = load_csv(GAMES_CSV)

    # Count games per patch
    patch_counts = defaultdict(int)
    for game in games:
        patch = game.get("patch_version", "")
        if patch:
            patch_counts[patch] += 1

    # Build patch list
    patches = []
    for patch, date in sorted(patch_dates.items(), key=lambda x: patch_to_num(x[0]), reverse=True):
        patches.append({
            "patch": patch,
            "date": date,
            "games_in_data": patch_counts.get(patch, 0)
        })

    result = {
        "metadata": {
            "generated_at": datetime.now().isoformat(),
            "current_patch": current_patch,
            "total_patches": len(patches),
            "patches_with_games": sum(1 for p in patches if p["games_in_data"] > 0)
        },
        "patches": patches
    }

    save_json(result, OUTPUT_DIR / "patch_info.json")
    return result


def build_role_baselines(current_patch: str) -> dict:
    """Build role_baselines.json with stat averages by role."""
    print("Building role_baselines.json...")

    stats = load_csv(PLAYER_GAME_STATS_CSV)
    games = load_csv(GAMES_CSV)

    # Build game -> patch mapping
    game_patches = {g["id"]: g.get("patch_version", "") for g in games}

    # Collect stats by role (only recent patches for baselines)
    role_stats = defaultdict(lambda: defaultdict(list))

    for row in stats:
        # Use corrected player role
        role = get_player_role(row.get("player_name", ""), row.get("role", ""))
        if not role:
            continue

        game_patch = game_patches.get(row["game_id"], "")

        # Only use last 6 patches for baselines
        if patch_to_num(current_patch) - patch_to_num(game_patch) > 6:
            continue

        # Collect numeric stats
        def safe_float(val):
            try:
                return float(val) if val else None
            except ValueError:
                return None

        if (kda := safe_float(row.get("kda_ratio"))):
            role_stats[role]["kda_ratio"].append(kda)
        if (kp := safe_float(row.get("kill_participation"))):
            role_stats[role]["kill_participation"].append(kp)
        if (dmg := safe_float(row.get("damage_dealt"))):
            role_stats[role]["damage_dealt"].append(dmg)
        if (vision := safe_float(row.get("vision_score"))):
            role_stats[role]["vision_score"].append(vision)
        if (nw := safe_float(row.get("net_worth"))):
            role_stats[role]["net_worth"].append(nw)
        if (mpm := safe_float(row.get("money_per_minute"))):
            role_stats[role]["money_per_minute"].append(mpm)

    # Calculate baselines
    def calc_stats(values: list) -> dict:
        if not values:
            return None
        n = len(values)
        mean = sum(values) / n
        variance = sum((x - mean) ** 2 for x in values) / n
        stddev = math.sqrt(variance) if variance > 0 else 0
        sorted_vals = sorted(values)
        return {
            "mean": round(mean, 2),
            "stddev": round(stddev, 2),
            "p25": round(sorted_vals[int(n * 0.25)], 2),
            "p50": round(sorted_vals[int(n * 0.50)], 2),
            "p75": round(sorted_vals[int(n * 0.75)], 2),
            "sample_size": n
        }

    baselines = {}
    for role in ["TOP", "JUNGLE", "MID", "ADC", "SUP"]:
        baselines[role] = {}
        for stat_name in ["kda_ratio", "kill_participation", "damage_dealt",
                          "vision_score", "net_worth", "money_per_minute"]:
            if role in role_stats and stat_name in role_stats[role]:
                baselines[role][stat_name] = calc_stats(role_stats[role][stat_name])

    result = {
        "metadata": {
            "generated_at": datetime.now().isoformat(),
            "current_patch": current_patch,
            "patch_window": 6,
            "description": "Stats baselines for normalization by role"
        },
        "baselines": baselines
    }

    save_json(result, OUTPUT_DIR / "role_baselines.json")
    return result


def classify_pick_context(sequence: int) -> str:
    """
    Classify if a pick is blind, early, or counter based on draft sequence.

    Draft sequence for picks:
    - Seq 7: Pick 1 (Blue) - 0 enemy picks visible (blind)
    - Seq 8-9: Pick 2-3 (Red) - 1 enemy pick visible (early)
    - Seq 10-11: Pick 4-5 (Blue) - 2 enemy picks visible (early)
    - Seq 12: Pick 6 (Red) - 3 enemy picks visible (counter)
    - Seq 17: Pick 7 (Red) - 3 enemy picks visible (counter)
    - Seq 18-19: Pick 8-9 (Blue) - 4 enemy picks visible (counter)
    - Seq 20: Pick 10 (Red) - 5 enemy picks visible (counter)
    """
    if sequence == 7:
        return "blind"
    elif sequence in [8, 9, 10, 11]:
        return "early"
    elif sequence in [12, 17, 18, 19, 20]:
        return "counter"
    else:
        return "unknown"


def build_meta_stats(current_patch: str) -> dict:
    """Build meta_stats.json with current meta tier for champions and counter-pick detection."""
    print("Building meta_stats.json...")

    draft_actions = load_csv(DRAFT_ACTIONS_CSV)
    stats = load_csv(PLAYER_GAME_STATS_CSV)
    games = load_csv(GAMES_CSV)

    # Build game -> (patch, winner_team_id) mapping
    game_info = {}
    for g in games:
        game_info[g["id"]] = {
            "patch": g.get("patch_version", ""),
            "winner_team_id": g.get("winner_team_id", "")
        }

    # Filter to last 3 patches (current meta)
    current_num = patch_to_num(current_patch)

    def is_recent(game_id: str) -> bool:
        patch = game_info.get(game_id, {}).get("patch", "")
        return current_num - patch_to_num(patch) <= 2

    # Count picks, bans, and track pick context
    picks = defaultdict(int)
    bans = defaultdict(int)
    total_games = set()

    # Counter-pick tracking: champion -> {context -> {games, wins}}
    pick_context_stats = defaultdict(lambda: {
        "blind": {"games": 0, "wins": 0},
        "early": {"games": 0, "wins": 0},
        "counter": {"games": 0, "wins": 0}
    })

    for action in draft_actions:
        game_id = action["game_id"]
        if not is_recent(game_id):
            continue

        total_games.add(game_id)
        champ = action.get("champion_name", "")
        if not champ:
            continue

        if action["action_type"] == "pick":
            picks[champ] += 1

            # Track pick context for counter-pick detection
            sequence = int(action.get("sequence_number", 0))
            context = classify_pick_context(sequence)

            if context in ["blind", "early", "counter"]:
                pick_context_stats[champ][context]["games"] += 1

                # Check if this team won
                winner_team_id = game_info.get(game_id, {}).get("winner_team_id", "")
                team_id = action.get("team_id", "")
                if team_id and winner_team_id and team_id == winner_team_id:
                    pick_context_stats[champ][context]["wins"] += 1

        elif action["action_type"] == "ban":
            bans[champ] += 1

    # Calculate win rates from player stats (more reliable)
    wins = defaultdict(int)
    games_played = defaultdict(int)

    for row in stats:
        if not is_recent(row["game_id"]):
            continue

        champ = row.get("champion_name", "")
        if not champ:
            continue

        games_played[champ] += 1
        if row.get("team_won") == "True":
            wins[champ] += 1

    # Build meta stats
    num_games = len(total_games)
    champions = {}
    min_games_for_tier = 15

    all_champs = set(picks.keys()) | set(bans.keys())

    for champ in all_champs:
        pick_count = picks.get(champ, 0)
        ban_count = bans.get(champ, 0)
        games_count = games_played.get(champ, 0)
        win_count = wins.get(champ, 0)

        # Picks are per-game (2 teams, so divide by 2 for rate per side)
        pick_rate = (pick_count / 2) / num_games if num_games > 0 else 0
        ban_rate = (ban_count / 2) / num_games if num_games > 0 else 0
        presence = pick_rate + ban_rate
        win_rate = win_count / games_count if games_count > 0 else 0.5

        # Calculate counter-pick bias
        context_data = pick_context_stats[champ]
        blind_early_games = context_data["blind"]["games"] + context_data["early"]["games"]
        blind_early_wins = context_data["blind"]["wins"] + context_data["early"]["wins"]
        counter_games = context_data["counter"]["games"]
        counter_wins = context_data["counter"]["wins"]

        blind_early_wr = blind_early_wins / blind_early_games if blind_early_games >= 5 else None
        counter_wr = counter_wins / counter_games if counter_games >= 5 else None

        # Counter-pick bias = difference in win rate when picked late vs early
        counter_pick_bias = None
        is_counter_pick_dependent = False

        if blind_early_wr is not None and counter_wr is not None:
            counter_pick_bias = counter_wr - blind_early_wr
            # If win rate is 15%+ higher when counter-picking, flag it
            is_counter_pick_dependent = counter_pick_bias > 0.15

        # Sample sufficient check
        sample_sufficient = games_count >= min_games_for_tier

        # Tier calculation (only for sufficient samples)
        if not sample_sufficient:
            tier = None
            tier_score = None
        elif presence >= 0.6 and win_rate >= 0.50:
            tier = "S"
            tier_score = 0.9 + (presence - 0.6) * 0.25
        elif presence >= 0.3 and win_rate >= 0.48:
            tier = "A"
            tier_score = 0.7 + (presence - 0.3) * 0.33
        elif presence >= 0.1 and win_rate >= 0.46:
            tier = "B"
            tier_score = 0.5 + (presence - 0.1) * 0.5
        else:
            tier = "C"
            tier_score = 0.3 + presence * 0.5

        # Build flags
        flags = []
        if not sample_sufficient:
            flags.append("insufficient_data")
        if is_counter_pick_dependent:
            flags.append("counter_pick_inflated")

        champ_data = {
            "games_picked": pick_count,
            "games_banned": ban_count,
            "pick_rate": round(pick_rate, 3),
            "ban_rate": round(ban_rate, 3),
            "presence": round(presence, 3),
            "win_rate": round(win_rate, 3),
            "games": games_count,
            "pick_context": {
                "blind_early_games": blind_early_games,
                "counter_games": counter_games,
                "blind_early_win_rate": round(blind_early_wr, 3) if blind_early_wr is not None else None,
                "counter_win_rate": round(counter_wr, 3) if counter_wr is not None else None,
                "counter_pick_bias": round(counter_pick_bias, 3) if counter_pick_bias is not None else None,
                "is_counter_pick_dependent": is_counter_pick_dependent
            },
            "meta_tier": tier,
            "meta_score": round(min(tier_score, 1.0), 3) if tier_score is not None else None,
            "sample_sufficient": sample_sufficient,
            "flags": flags
        }

        champions[champ] = champ_data

    result = {
        "metadata": {
            "generated_at": datetime.now().isoformat(),
            "current_patch": current_patch,
            "patches_included": 3,
            "games_analyzed": num_games,
            "champions_count": len(champions),
            "min_games_for_tier": min_games_for_tier,
            "counter_pick_threshold": 0.15
        },
        "champions": dict(sorted(champions.items(), key=lambda x: -(x[1]["presence"] or 0)))
    }

    save_json(result, OUTPUT_DIR / "meta_stats.json")
    return result


def build_player_proficiency(current_patch: str) -> dict:
    """Build player_proficiency.json with player-champion performance."""
    print("Building player_proficiency.json...")

    stats = load_csv(PLAYER_GAME_STATS_CSV)
    games = load_csv(GAMES_CSV)
    reworks = load_json(REWORK_MAPPING_FILE)
    role_baselines = load_json(OUTPUT_DIR / "role_baselines.json")

    # Build game -> patch mapping
    game_patches = {g["id"]: g.get("patch_version", "") for g in games}

    # Collect player-champion stats
    player_champ_stats = defaultdict(lambda: defaultdict(list))

    for row in stats:
        player = row.get("player_name", "")
        champion = row.get("champion_name", "")

        if not player or not champion:
            continue

        # Use corrected player role
        role = get_player_role(player, row.get("role", ""))

        game_patch = game_patches.get(row["game_id"], "")

        # Skip pre-rework data
        if not is_post_rework(champion, game_patch, reworks):
            continue

        patch_weight = get_patch_weight(game_patch, current_patch)
        won = row.get("team_won") == "True"

        def safe_float(val):
            try:
                return float(val) if val else None
            except ValueError:
                return None

        player_champ_stats[player][champion].append({
            "patch": game_patch,
            "patch_weight": patch_weight,
            "won": won,
            "role": role,
            "kda": safe_float(row.get("kda_ratio")),
            "kp": safe_float(row.get("kill_participation")),
        })

    # Calculate proficiencies
    proficiencies = {}

    for player, champions in player_champ_stats.items():
        proficiencies[player] = {}

        for champion, games_list in champions.items():
            games_raw = len(games_list)
            games_weighted = sum(g["patch_weight"] for g in games_list)

            wins = sum(1 for g in games_list if g["won"])
            win_rate = wins / games_raw if games_raw > 0 else 0

            weighted_wins = sum(g["patch_weight"] for g in games_list if g["won"])
            win_rate_weighted = weighted_wins / games_weighted if games_weighted > 0 else 0

            # Get patches played
            patches = sorted(set(g["patch"] for g in games_list if g["patch"]),
                           key=patch_to_num, reverse=True)
            last_patch = patches[0] if patches else None

            # Confidence level
            if games_weighted >= 8:
                confidence = "HIGH"
            elif games_weighted >= 4:
                confidence = "MEDIUM"
            elif games_weighted >= 1:
                confidence = "LOW"
            else:
                confidence = "NO_DATA"

            # Normalized KDA (if we have baseline for the role)
            kda_normalized = None
            kp_normalized = None

            # Get most common role for this player-champion
            roles = [g["role"] for g in games_list if g["role"]]
            if roles:
                most_common_role = max(set(roles), key=roles.count)
                baselines = role_baselines.get("baselines", {}).get(most_common_role, {})

                # Calculate normalized stats
                kdas = [g["kda"] for g in games_list if g["kda"] is not None]
                if kdas and baselines.get("kda_ratio"):
                    avg_kda = sum(kdas) / len(kdas)
                    baseline = baselines["kda_ratio"]
                    if baseline["stddev"] > 0:
                        kda_normalized = round((avg_kda - baseline["mean"]) / baseline["stddev"], 2)

                kps = [g["kp"] for g in games_list if g["kp"] is not None]
                if kps and baselines.get("kill_participation"):
                    avg_kp = sum(kps) / len(kps)
                    baseline = baselines["kill_participation"]
                    if baseline["stddev"] > 0:
                        kp_normalized = round((avg_kp - baseline["mean"]) / baseline["stddev"], 2)

            proficiencies[player][champion] = {
                "games_raw": games_raw,
                "games_weighted": round(games_weighted, 2),
                "win_rate": round(win_rate, 3),
                "win_rate_weighted": round(win_rate_weighted, 3),
                "kda_normalized": kda_normalized,
                "kp_normalized": kp_normalized,
                "confidence": confidence,
                "last_patch": last_patch,
                "patches_played": patches[:5]  # Keep last 5
            }

    result = {
        "metadata": {
            "generated_at": datetime.now().isoformat(),
            "current_patch": current_patch,
            "players_count": len(proficiencies),
            "total_player_champions": sum(len(c) for c in proficiencies.values())
        },
        "proficiencies": proficiencies
    }

    save_json(result, OUTPUT_DIR / "player_proficiency.json")
    return result


def build_flex_champions(current_patch: str) -> dict:
    """Build flex_champions.json with role probability distributions."""
    print("Building flex_champions.json...")

    stats = load_csv(PLAYER_GAME_STATS_CSV)
    knowledge_base = load_json(KNOWLEDGE_BASE_FILE)

    # Pre-load player roles for logging
    player_roles = load_player_roles()
    print(f"  Using {len(player_roles)} corrected player roles")

    # Count role occurrences per champion
    champ_roles = defaultdict(lambda: defaultdict(int))

    for row in stats:
        champion = row.get("champion_name", "")
        if not champion:
            continue

        # Use corrected player role
        role = get_player_role(row.get("player_name", ""), row.get("role", ""))
        if not role:
            continue

        champ_roles[champion][role] += 1

    # Build flex picks data
    flex_picks = {}

    for champion, roles in champ_roles.items():
        total = sum(roles.values())
        if total == 0:
            continue

        role_probs = {role: count / total for role, count in roles.items()}

        # Check if it's a flex pick (more than one role with >10% presence)
        significant_roles = [r for r, p in role_probs.items() if p >= 0.1]
        is_flex = len(significant_roles) > 1

        # Get primary role from knowledge_base if available
        kb_positions = []
        if champion in knowledge_base.get("champions", {}):
            kb_positions = knowledge_base["champions"][champion].get("positions", [])
            kb_flex = knowledge_base["champions"][champion].get("flex_positions", [])
            if kb_flex:
                kb_positions.extend(kb_flex)

        flex_picks[champion] = {
            **{role: round(prob, 3) for role, prob in sorted(role_probs.items(), key=lambda x: -x[1])},
            "is_flex": is_flex,
            "games_total": total,
            "kb_positions": kb_positions
        }

    result = {
        "metadata": {
            "generated_at": datetime.now().isoformat(),
            "champions_count": len(flex_picks),
            "flex_picks_count": sum(1 for c in flex_picks.values() if c["is_flex"])
        },
        "flex_picks": dict(sorted(flex_picks.items()))
    }

    save_json(result, OUTPUT_DIR / "flex_champions.json")
    return result


def build_champion_synergies(current_patch: str) -> dict:
    """Build champion_synergies.json with statistical synergy scores."""
    print("Building champion_synergies.json...")

    stats = load_csv(PLAYER_GAME_STATS_CSV)
    curated_synergies = load_json(SYNERGIES_FILE)

    # Build curated synergy lookup
    curated_pairs = set()
    for syn in curated_synergies:
        champs = syn.get("champions", [])
        if len(champs) >= 2:
            curated_pairs.add(tuple(sorted(champs[:2])))

    # Group stats by game and team
    game_team_champs = defaultdict(lambda: defaultdict(list))
    game_team_won = {}

    for row in stats:
        game_id = row.get("game_id", "")
        team_id = row.get("team_id", "")
        champion = row.get("champion_name", "")
        won = row.get("team_won") == "True"

        if not game_id or not team_id or not champion:
            continue

        game_team_champs[game_id][team_id].append(champion)
        game_team_won[(game_id, team_id)] = won

    # Count co-occurrences and wins
    pair_games = defaultdict(int)
    pair_wins = defaultdict(int)
    champ_games = defaultdict(int)
    champ_wins = defaultdict(int)

    for game_id, teams in game_team_champs.items():
        for team_id, champions in teams.items():
            won = game_team_won.get((game_id, team_id), False)

            # Count individual champion stats
            for champ in champions:
                champ_games[champ] += 1
                if won:
                    champ_wins[champ] += 1

            # Count pair stats
            for i, champ_a in enumerate(champions):
                for champ_b in champions[i+1:]:
                    pair = tuple(sorted([champ_a, champ_b]))
                    pair_games[pair] += 1
                    if won:
                        pair_wins[pair] += 1

    # Calculate synergy scores
    synergies = {}
    min_games = 15

    for pair, games in pair_games.items():
        if games < min_games:
            continue

        champ_a, champ_b = pair
        wins = pair_wins[pair]
        win_rate = wins / games

        # Expected win rate based on individual performance
        wr_a = champ_wins[champ_a] / champ_games[champ_a] if champ_games[champ_a] > 0 else 0.5
        wr_b = champ_wins[champ_b] / champ_games[champ_b] if champ_games[champ_b] > 0 else 0.5
        expected = (wr_a + wr_b) / 2  # Simple average as baseline

        synergy_delta = win_rate - expected

        # Convert to 0-1 score
        synergy_score = 0.5 + synergy_delta  # Center at 0.5
        synergy_score = max(0, min(1, synergy_score))  # Clamp

        # Check if curated
        has_mechanical = pair in curated_pairs

        if champ_a not in synergies:
            synergies[champ_a] = {}

        synergies[champ_a][champ_b] = {
            "games_together": games,
            "win_rate_together": round(win_rate, 3),
            "expected_win_rate": round(expected, 3),
            "synergy_delta": round(synergy_delta, 3),
            "synergy_score": round(synergy_score, 3),
            "has_mechanical_synergy": has_mechanical
        }

    result = {
        "metadata": {
            "generated_at": datetime.now().isoformat(),
            "min_games_together": min_games,
            "synergy_pairs_count": sum(len(v) for v in synergies.values())
        },
        "synergies": synergies
    }

    save_json(result, OUTPUT_DIR / "champion_synergies.json")
    return result


def build_matchup_stats(current_patch: str) -> dict:
    """Build matchup_stats.json with empirical matchup win rates from pro play."""
    print("Building matchup_stats.json...")

    stats = load_csv(PLAYER_GAME_STATS_CSV)

    # Group by game to find matchups
    game_players = defaultdict(list)

    for row in stats:
        game_id = row.get("game_id", "")
        if not game_id:
            continue

        # Use corrected player role
        role = get_player_role(row.get("player_name", ""), row.get("role", ""))

        game_players[game_id].append({
            "champion": row.get("champion_name", ""),
            "role": role,
            "team_id": row.get("team_id", ""),
            "won": row.get("team_won") == "True"
        })

    # Count lane matchups
    lane_matchups = defaultdict(lambda: {"games": 0, "wins": 0})
    team_matchups = defaultdict(lambda: {"games": 0, "wins": 0})

    for game_id, players in game_players.items():
        # Group by team
        teams = defaultdict(list)
        for p in players:
            teams[p["team_id"]].append(p)

        team_ids = list(teams.keys())
        if len(team_ids) != 2:
            continue

        team_a, team_b = teams[team_ids[0]], teams[team_ids[1]]

        # Lane matchups (same role)
        for player_a in team_a:
            role_a = player_a["role"]

            for player_b in team_b:
                role_b = player_b["role"]

                if role_a == role_b and role_a in ["TOP", "JUNGLE", "MID", "ADC", "SUP"]:
                    # Lane matchup
                    key = (player_a["champion"], role_a, player_b["champion"])
                    lane_matchups[key]["games"] += 1
                    if player_a["won"]:
                        lane_matchups[key]["wins"] += 1

                # Team matchup (any champion vs any)
                key = (player_a["champion"], player_b["champion"])
                team_matchups[key]["games"] += 1
                if player_a["won"]:
                    team_matchups[key]["wins"] += 1

    # Build counters data
    counters = {}
    min_games = 10

    # Process lane matchups
    for (our_champ, role, enemy_champ), data in lane_matchups.items():
        if data["games"] < min_games:
            continue

        if our_champ not in counters:
            counters[our_champ] = {"vs_lane": {}, "vs_team": {}}

        win_rate = data["wins"] / data["games"]
        confidence = "HIGH" if data["games"] >= 20 else "MEDIUM"

        if role not in counters[our_champ]["vs_lane"]:
            counters[our_champ]["vs_lane"][role] = {}

        counters[our_champ]["vs_lane"][role][enemy_champ] = {
            "games": data["games"],
            "win_rate": round(win_rate, 3),
            "confidence": confidence
        }

    # Process team matchups
    for (our_champ, enemy_champ), data in team_matchups.items():
        if data["games"] < min_games:
            continue

        if our_champ not in counters:
            counters[our_champ] = {"vs_lane": {}, "vs_team": {}}

        win_rate = data["wins"] / data["games"]

        counters[our_champ]["vs_team"][enemy_champ] = {
            "games": data["games"],
            "win_rate": round(win_rate, 3)
        }

    result = {
        "metadata": {
            "generated_at": datetime.now().isoformat(),
            "min_matchup_games": min_games,
            "champions_with_counters": len(counters)
        },
        "counters": counters
    }

    save_json(result, OUTPUT_DIR / "matchup_stats.json")
    return result


def build_skill_transfers(current_patch: str) -> dict:
    """Build skill_transfers.json from co-play patterns."""
    print("Building skill_transfers.json...")

    stats = load_csv(PLAYER_GAME_STATS_CSV)

    # Build player -> champion pools
    player_pools = defaultdict(lambda: defaultdict(int))

    for row in stats:
        player = row.get("player_name", "")
        champion = row.get("champion_name", "")

        if player and champion:
            player_pools[player][champion] += 1

    # Count co-play (players who play both champions)
    co_play = defaultdict(lambda: defaultdict(int))
    champ_players = defaultdict(int)

    for player, champions in player_pools.items():
        # Only count if player has at least 3 games on a champion
        champs_with_games = [c for c, g in champions.items() if g >= 3]

        for champ in champs_with_games:
            champ_players[champ] += 1

        for i, champ_a in enumerate(champs_with_games):
            for champ_b in champs_with_games[i+1:]:
                co_play[champ_a][champ_b] += 1
                co_play[champ_b][champ_a] += 1

    # Calculate similarity scores
    transfers = {}
    min_co_play = 3

    for champ_a, partners in co_play.items():
        similar = []
        players_a = champ_players[champ_a]

        for champ_b, players_both in partners.items():
            if players_both < min_co_play:
                continue

            players_b = champ_players[champ_b]

            # Jaccard-like similarity
            co_play_rate = players_both / min(players_a, players_b) if min(players_a, players_b) > 0 else 0

            if co_play_rate >= 0.3:  # At least 30% overlap
                similar.append({
                    "champion": champ_b,
                    "co_play_rate": round(co_play_rate, 3),
                    "players_both": players_both
                })

        if similar:
            # Sort by co-play rate and take top 5
            similar.sort(key=lambda x: -x["co_play_rate"])
            transfers[champ_a] = {
                "similar_champions": similar[:5]
            }

    result = {
        "metadata": {
            "generated_at": datetime.now().isoformat(),
            "min_co_play_players": min_co_play,
            "min_co_play_rate": 0.3,
            "champions_with_transfers": len(transfers)
        },
        "transfers": transfers
    }

    save_json(result, OUTPUT_DIR / "skill_transfers.json")
    return result


def build_champion_role_history(current_patch: str) -> dict:
    """Build champion_role_history.json with per-patch role tracking and meta shift detection.

    This dataset tracks:
    1. Canonical roles (from knowledge_base.json) - the "intended" role
    2. Per-patch role distributions - how roles evolved over time
    3. Meta shifts - when off-meta roles emerged and ended
    4. Current viable roles - what should be recommended NOW
    """
    print("Building champion_role_history.json...")

    stats = load_csv(PLAYER_GAME_STATS_CSV)
    games = load_csv(GAMES_CSV)
    knowledge_base = load_json(KNOWLEDGE_BASE_FILE)

    # Build game -> patch mapping
    game_patches = {g["id"]: g.get("patch_version", "") for g in games}

    # Normalize role names from knowledge_base
    def normalize_kb_role(role: str) -> str:
        """Convert knowledge_base role names to our format."""
        mapping = {
            "Top": "TOP",
            "Jungle": "JUNGLE",
            "Mid": "MID",
            "ADC": "ADC",
            "Bot": "ADC",
            "Support": "SUP",
        }
        return mapping.get(role, role.upper())

    # Get canonical roles from knowledge_base
    canonical_roles = {}
    for champ_name, champ_data in knowledge_base.get("champions", {}).items():
        positions = champ_data.get("positions", [])
        flex_positions = champ_data.get("flex_positions", [])

        if positions:
            canonical_roles[champ_name] = {
                "primary": normalize_kb_role(positions[0]),
                "all": [normalize_kb_role(p) for p in positions + flex_positions],
                "source": "knowledge_base",
            }

    # Collect role data per champion per patch
    # Structure: {champion: {patch: {role: count}}}
    champ_patch_roles = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    champ_patch_games = defaultdict(lambda: defaultdict(int))

    for row in stats:
        champion = row.get("champion_name", "")
        if not champion:
            continue

        game_id = row.get("game_id", "")
        patch = game_patches.get(game_id, "")
        if not patch:
            continue

        # Use corrected player role
        role = get_player_role(row.get("player_name", ""), row.get("role", ""))
        if not role:
            continue

        champ_patch_roles[champion][patch][role] += 1
        champ_patch_games[champion][patch] += 1

    # Get all patches sorted
    all_patches = sorted(
        set(game_patches.values()) - {""},
        key=patch_to_num
    )

    current_num = patch_to_num(current_patch)

    # Configuration
    META_WINDOW = 3  # Patches to consider for "current" viability
    MIN_ROLE_RATE_FOR_VIABLE = 0.10  # 10% threshold to be considered viable
    MIN_GAMES_FOR_STATS = 3  # Minimum games in a patch for reliable stats
    META_SHIFT_THRESHOLD = 0.15  # 15% in off-role to be considered a meta shift
    MIN_GAMES_FOR_META_SHIFT = 10  # Minimum total games to count as a real meta shift

    # Build champion role history
    champion_history = {}

    for champion in sorted(champ_patch_roles.keys()):
        patch_data = champ_patch_roles[champion]
        games_data = champ_patch_games[champion]

        # Get canonical role
        canonical = canonical_roles.get(champion, {})
        canonical_primary = canonical.get("primary", None)
        canonical_all = canonical.get("all", [])

        # Build per-patch role distributions
        role_by_patch = {}
        for patch in all_patches:
            if patch not in patch_data:
                continue

            total = games_data[patch]
            if total < 1:
                continue

            patch_roles = {}
            for role, count in patch_data[patch].items():
                rate = count / total
                if rate >= 0.01:  # Only include roles with at least 1%
                    patch_roles[role] = round(rate, 3)

            if patch_roles:
                role_by_patch[patch] = {
                    **dict(sorted(patch_roles.items(), key=lambda x: -x[1])),
                    "games": total,
                }

        # Calculate ALL-TIME role distribution first (used for pro_play_primary)
        all_time_roles = defaultdict(float)
        all_time_total = 0
        for patch_info in role_by_patch.values():
            games = patch_info["games"]
            all_time_total += games
            for role, rate in patch_info.items():
                if role != "games":
                    all_time_roles[role] += rate * games

        # Calculate all_time_distribution as percentages
        all_time_distribution = {}
        pro_play_primary_role = None
        if all_time_total > 0:
            for role, weighted in sorted(all_time_roles.items(), key=lambda x: -x[1]):
                pct = weighted / all_time_total
                if pct >= 0.01:  # At least 1%
                    all_time_distribution[role] = round(pct, 3)
            # Pro play primary = most played role in all data
            pro_play_primary_role = max(all_time_roles.items(), key=lambda x: x[1])[0]

        # Calculate current viable roles (last N patches)
        recent_patches = [
            p for p in all_patches
            if current_num - patch_to_num(p) <= META_WINDOW - 1 and current_num >= patch_to_num(p)
        ]

        recent_role_weighted = defaultdict(float)
        recent_total_games = 0

        for patch in recent_patches:
            if patch in role_by_patch:
                games = role_by_patch[patch]["games"]
                recent_total_games += games
                for role, rate in role_by_patch[patch].items():
                    if role != "games":
                        recent_role_weighted[role] += rate * games

        # Determine current viable roles
        current_viable = set()

        # Include ALL canonical positions (not just primary)
        for role in canonical_all:
            current_viable.add(role)

        # Add roles with significant recent play
        if recent_total_games >= MIN_GAMES_FOR_STATS:
            for role, weighted in recent_role_weighted.items():
                rate = weighted / recent_total_games
                if rate >= MIN_ROLE_RATE_FOR_VIABLE:
                    current_viable.add(role)

        # Also add pro_play_primary if it's dominant (>50%) and not already included
        if pro_play_primary_role and all_time_total >= 10:
            primary_pct = all_time_distribution.get(pro_play_primary_role, 0)
            if primary_pct >= 0.5:  # Dominant role
                current_viable.add(pro_play_primary_role)

        # If still no viable roles, use pro_play_primary
        if not current_viable and pro_play_primary_role:
            current_viable.add(pro_play_primary_role)

        # Detect meta shifts (off-meta roles that emerged)
        meta_shifts = []

        # Find roles that aren't canonical but were played significantly
        for role in set(r for pd in role_by_patch.values() for r in pd if r != "games"):
            if canonical_primary and role == canonical_primary:
                continue  # Skip canonical role
            if role in canonical_all:
                continue  # Skip known flex positions

            # Find patches where this role was significant
            significant_patches = []
            total_games_in_role = 0
            for patch in all_patches:
                if patch in role_by_patch:
                    rate = role_by_patch[patch].get(role, 0)
                    games_in_patch = role_by_patch[patch]["games"]
                    if rate >= META_SHIFT_THRESHOLD:
                        significant_patches.append((patch, rate, games_in_patch))
                        # Count actual games played in this role
                        total_games_in_role += int(rate * games_in_patch)

            # Require both significant patches AND minimum total games
            if not significant_patches or total_games_in_role < MIN_GAMES_FOR_META_SHIFT:
                continue

            # Determine start and end of meta shift
            started_patch = significant_patches[0][0]
            peak_rate = max(r for _, r, _ in significant_patches)
            peak_patch = next(p for p, r, _ in significant_patches if r == peak_rate)

            # Check if meta ended (no significant play in recent patches)
            recent_rate = 0
            if recent_total_games > 0:
                recent_rate = recent_role_weighted.get(role, 0) / recent_total_games

            if recent_rate < MIN_ROLE_RATE_FOR_VIABLE:
                # Meta ended - find when
                ended_patch = None
                for patch in reversed(all_patches):
                    if patch in role_by_patch:
                        rate = role_by_patch[patch].get(role, 0)
                        if rate >= META_SHIFT_THRESHOLD:
                            # This was the last patch with significant play
                            patch_idx = all_patches.index(patch)
                            if patch_idx + 1 < len(all_patches):
                                ended_patch = all_patches[patch_idx + 1]
                            break

                meta_shifts.append({
                    "role": role,
                    "started_patch": started_patch,
                    "ended_patch": ended_patch,
                    "peak_patch": peak_patch,
                    "peak_rate": round(peak_rate, 3),
                    "total_games": total_games_in_role,
                    "status": "ended",
                    "reason": "no_recent_picks",
                })
            else:
                # Meta still active
                meta_shifts.append({
                    "role": role,
                    "started_patch": started_patch,
                    "ended_patch": None,
                    "peak_patch": peak_patch,
                    "peak_rate": round(peak_rate, 3),
                    "total_games": total_games_in_role,
                    "status": "active",
                    "reason": None,
                })

        # Calculate current role distribution for quick access
        current_distribution = {}
        if recent_total_games > 0:
            for role, weighted in sorted(recent_role_weighted.items(), key=lambda x: -x[1]):
                rate = weighted / recent_total_games
                if rate >= 0.01:
                    current_distribution[role] = round(rate, 3)

        champion_history[champion] = {
            "canonical_role": canonical_primary,
            "canonical_all": canonical_all,
            "canonical_source": canonical.get("source", "inferred"),
            "pro_play_primary_role": pro_play_primary_role,
            "all_time_distribution": all_time_distribution,
            "all_time_games": all_time_total,
            "role_by_patch": role_by_patch,
            "meta_shifts": meta_shifts,
            "current_viable_roles": sorted(current_viable),
            "current_distribution": current_distribution,
            "current_patch_window": recent_patches,
            "recent_games": recent_total_games,
        }

    # Summary stats
    total_meta_shifts = sum(len(c["meta_shifts"]) for c in champion_history.values())
    active_meta_shifts = sum(
        1 for c in champion_history.values()
        for ms in c["meta_shifts"]
        if ms["status"] == "active"
    )
    ended_meta_shifts = total_meta_shifts - active_meta_shifts

    result = {
        "metadata": {
            "generated_at": datetime.now().isoformat(),
            "current_patch": current_patch,
            "meta_window_patches": META_WINDOW,
            "min_role_rate_for_viable": MIN_ROLE_RATE_FOR_VIABLE,
            "meta_shift_threshold": META_SHIFT_THRESHOLD,
            "min_games_for_meta_shift": MIN_GAMES_FOR_META_SHIFT,
            "champions_count": len(champion_history),
            "total_meta_shifts_detected": total_meta_shifts,
            "active_meta_shifts": active_meta_shifts,
            "ended_meta_shifts": ended_meta_shifts,
        },
        "champions": champion_history,
    }

    save_json(result, OUTPUT_DIR / "champion_role_history.json")
    return result


def build_frontend_champion_roles(current_patch: str) -> dict:
    """Build frontend championRoles.json from champion_role_history.json.

    This generates the frontend-compatible champion roles file by:
    1. Using current_viable_roles from pro play data (champion_role_history.json)
    2. Falling back to knowledge_base.json canonical positions
    3. Preserving existing championRoles.json entries for champions with no data

    Role name mapping: Backend uses JUNGLE, frontend uses JNG.
    """
    print("Building frontend championRoles.json...")

    # Paths
    history_file = OUTPUT_DIR / "champion_role_history.json"
    frontend_file = BASE_DIR / "deepdraft" / "src" / "data" / "championRoles.json"

    # Load data sources
    history = load_json(history_file) if history_file.exists() else {"champions": {}}
    knowledge_base = load_json(KNOWLEDGE_BASE_FILE) if KNOWLEDGE_BASE_FILE.exists() else {"champions": {}}

    # Load existing frontend file to preserve manual entries
    existing_frontend = {}
    if frontend_file.exists():
        existing_frontend = load_json(frontend_file)

    # Role mapping: backend -> frontend
    ROLE_MAP = {
        "JUNGLE": "JNG",
        "TOP": "TOP",
        "MID": "MID",
        "ADC": "ADC",
        "SUP": "SUP",
    }

    # Reverse mapping for knowledge_base (uses Title Case)
    KB_ROLE_MAP = {
        "Top": "TOP",
        "Jungle": "JNG",
        "Mid": "MID",
        "ADC": "ADC",
        "Bot": "ADC",
        "Support": "SUP",
    }

    def to_frontend_role(role: str) -> str:
        """Convert backend role to frontend format."""
        return ROLE_MAP.get(role, role)

    def kb_to_frontend_role(role: str) -> str:
        """Convert knowledge_base role to frontend format."""
        return KB_ROLE_MAP.get(role, role.upper())

    # Build the merged champion roles
    champion_roles = {}

    # Get all champion names from all sources
    all_champions = set(history.get("champions", {}).keys())
    all_champions.update(knowledge_base.get("champions", {}).keys())
    all_champions.update(existing_frontend.keys())

    for champion in sorted(all_champions):
        canonical_all = []
        canonical_role = None
        source = None

        # Priority 1: Pro play computed data (current_viable_roles)
        history_data = history.get("champions", {}).get(champion, {})
        if history_data.get("current_viable_roles"):
            canonical_all = [to_frontend_role(r) for r in history_data["current_viable_roles"]]
            # Use current_distribution to determine primary role
            current_dist = history_data.get("current_distribution", {})
            if current_dist:
                # Find the role with highest rate in current distribution
                primary = max(current_dist.items(), key=lambda x: x[1])[0]
                canonical_role = to_frontend_role(primary)
            elif history_data.get("pro_play_primary_role"):
                canonical_role = to_frontend_role(history_data["pro_play_primary_role"])
            source = "pro_play"

        # Priority 2: Knowledge base + existing manual entries (merged)
        # For champions without pro play data, merge knowledge_base with manual entries
        if not canonical_all:
            kb_data = knowledge_base.get("champions", {}).get(champion, {})
            positions = kb_data.get("positions", [])
            flex_positions = kb_data.get("flex_positions", [])
            existing = existing_frontend.get(champion, {})

            # Start with knowledge_base roles
            kb_roles = [kb_to_frontend_role(p) for p in positions + flex_positions]
            existing_roles = existing.get("canonical_all", [])

            # Merge: include both knowledge_base and manual entries
            merged_roles = list(kb_roles)
            for role in existing_roles:
                if role not in merged_roles:
                    merged_roles.append(role)

            if merged_roles:
                canonical_all = merged_roles
                # Prefer knowledge_base primary role, fall back to existing
                if positions:
                    canonical_role = kb_to_frontend_role(positions[0])
                elif existing.get("canonical_role"):
                    canonical_role = existing["canonical_role"]
                source = "knowledge_base_merged" if kb_roles else "preserved_manual"

        # Remove duplicates while preserving order
        seen = set()
        canonical_all = [r for r in canonical_all if not (r in seen or seen.add(r))]

        # Ensure canonical_role is in canonical_all
        if canonical_role and canonical_role not in canonical_all and canonical_all:
            canonical_role = canonical_all[0]
        elif not canonical_role and canonical_all:
            canonical_role = canonical_all[0]

        champion_roles[champion] = {
            "canonical_all": canonical_all,
            "canonical_role": canonical_role,
        }

    # Save to frontend location
    frontend_file.parent.mkdir(parents=True, exist_ok=True)
    save_json(champion_roles, frontend_file)

    # Summary stats
    with_roles = sum(1 for c in champion_roles.values() if c["canonical_all"])
    multi_role = sum(1 for c in champion_roles.values() if len(c["canonical_all"]) > 1)

    print(f"  Champions with roles: {with_roles}/{len(champion_roles)}")
    print(f"  Multi-role champions: {multi_role}")

    return champion_roles


# ============================================================================
# Main
# ============================================================================

DATASETS = {
    "patch_info": build_patch_info,
    "role_baselines": build_role_baselines,
    "meta_stats": build_meta_stats,
    "flex_champions": build_flex_champions,
    "player_proficiency": build_player_proficiency,
    "champion_synergies": build_champion_synergies,
    "matchup_stats": build_matchup_stats,
    "skill_transfers": build_skill_transfers,
    "champion_role_history": build_champion_role_history,
    "frontend_champion_roles": build_frontend_champion_roles,
}


def main():
    parser = argparse.ArgumentParser(description="Build computed datasets for recommendation engine")
    parser.add_argument("--all", action="store_true", help="Build all datasets")
    parser.add_argument("--dataset", type=str, choices=list(DATASETS.keys()),
                        help="Build specific dataset")
    parser.add_argument("--current-patch", type=str, default="15.17",
                        help="Current patch for calculations (default: 15.17)")

    args = parser.parse_args()

    if not args.all and not args.dataset:
        parser.print_help()
        return

    print(f"Current patch: {args.current_patch}")
    print(f"Output directory: {OUTPUT_DIR}")
    print()

    # Ensure output directory exists
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if args.all:
        # Build in dependency order
        order = [
            "patch_info",
            "role_baselines",
            "meta_stats",
            "flex_champions",
            "player_proficiency",  # Depends on role_baselines
            "champion_synergies",
            "matchup_stats",
            "skill_transfers",
            "champion_role_history",  # Tracks role evolution and meta shifts
            "frontend_champion_roles",  # Depends on champion_role_history
        ]
        for name in order:
            DATASETS[name](args.current_patch)
            print()
    else:
        DATASETS[args.dataset](args.current_patch)

    print("Done!")


if __name__ == "__main__":
    main()
