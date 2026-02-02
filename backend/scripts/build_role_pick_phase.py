#!/usr/bin/env python3
"""Build role pick phase distribution from draft data.

Analyzes pro games to calculate P(role | phase) - the probability that
each role is picked during each draft phase.

Draft phases:
- early_p1: Picks 1-3 (first 3 picks in draft, sequence 7-9 after ban phase 1)
- late_p1: Picks 4-6 (sequence 10-12, some after ban phase 2)
- p2: Picks 7-10 (remaining picks, sequence 17-20 after ban phase 2)

Usage:
    uv run python scripts/build_role_pick_phase.py [data_path]

Default data_path: outputs/full_2024_2025_v2/csv (relative to repo root)
Output: knowledge/role_pick_phase.json
"""
import csv
import json
from collections import defaultdict
from pathlib import Path
import sys


def load_draft_actions(csv_path: Path) -> list[dict]:
    """Load draft actions from CSV."""
    actions = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["action_type"] == "pick":
                actions.append({
                    "game_id": row["game_id"],
                    "sequence_number": int(row["sequence_number"]),
                    "team_id": row["team_id"],
                    "champion_name": row["champion_name"],
                })
    return actions


def load_player_stats(csv_path: Path) -> dict[tuple, str]:
    """Load player stats and return (game_id, team_id, champion_name) -> role mapping."""
    role_map = {}
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            key = (row["game_id"], row["team_id"], row["champion_name"])
            role = row["role"].lower() if row["role"] else None
            if role:
                role_map[key] = role
    return role_map


def sequence_to_pick_number(sequence: int) -> int | None:
    """Convert draft sequence number to pick number (1-10).

    Standard draft sequence:
    - 1-6: Ban phase 1 (3 bans per team)
    - 7-12: Pick phase 1 (6 picks: 1-1-2-2-1-1 pattern)
    - 13-16: Ban phase 2 (2 bans per team)
    - 17-20: Pick phase 2 (4 picks: 2-2 pattern)

    Returns None for non-pick sequences.
    """
    if 7 <= sequence <= 12:
        return sequence - 6  # Picks 1-6
    elif 17 <= sequence <= 20:
        return sequence - 10  # Picks 7-10
    return None


def pick_number_to_phase(pick_num: int) -> str:
    """Convert pick number (1-10) to draft phase.

    Phases match what RolePhaseScorer expects:
    - early_p1: picks 1-3 (first 3 picks)
    - late_p1: picks 4-6 (remaining phase 1 picks)
    - p2: picks 7-10 (phase 2 picks)
    """
    if pick_num <= 3:
        return "early_p1"
    elif pick_num <= 6:
        return "late_p1"
    return "p2"


def build_role_pick_phase(data_path: Path, output_path: Path | None = None) -> Path:
    """Build role pick phase distribution from CSV data.

    Args:
        data_path: Directory containing CSV files
        output_path: Where to write JSON (default: knowledge/role_pick_phase.json)

    Returns:
        Path to the created JSON file
    """
    if output_path is None:
        repo_root = Path(__file__).parent.parent.parent
        output_path = repo_root / "knowledge" / "role_pick_phase.json"

    draft_csv = data_path / "draft_actions.csv"
    stats_csv = data_path / "player_game_stats.csv"

    if not draft_csv.exists():
        print(f"Error: {draft_csv} not found")
        sys.exit(1)
    if not stats_csv.exists():
        print(f"Error: {stats_csv} not found")
        sys.exit(1)

    print(f"Loading draft actions from {draft_csv}...")
    picks = load_draft_actions(draft_csv)
    print(f"  Loaded {len(picks):,} picks")

    print(f"Loading player stats from {stats_csv}...")
    role_map = load_player_stats(stats_csv)
    print(f"  Loaded {len(role_map):,} player-champion-game mappings")

    # Count role occurrences per phase
    phase_role_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    phase_totals: dict[str, int] = defaultdict(int)
    matched = 0
    unmatched = 0

    for pick in picks:
        pick_num = sequence_to_pick_number(pick["sequence_number"])
        if pick_num is None:
            continue

        key = (pick["game_id"], pick["team_id"], pick["champion_name"])
        role = role_map.get(key)

        if role:
            phase = pick_number_to_phase(pick_num)
            phase_role_counts[phase][role] += 1
            phase_totals[phase] += 1
            matched += 1
        else:
            unmatched += 1

    print(f"\nMatched {matched:,} picks to roles ({unmatched:,} unmatched)")

    # Calculate probabilities
    roles = ["top", "jungle", "mid", "bot", "support"]
    phases = ["early_p1", "late_p1", "p2"]

    distribution = {}
    for role in roles:
        distribution[role] = {}
        for phase in phases:
            count = phase_role_counts[phase][role]
            total = phase_totals[phase]
            prob = count / total if total > 0 else 0.2
            distribution[role][phase] = round(prob, 3)

    # Print summary
    print("\nRole Pick Phase Distribution:")
    print("-" * 60)
    print(f"{'Role':<10} {'Early P1':>12} {'Late P1':>12} {'P2':>12}")
    print("-" * 60)
    for role in roles:
        early = distribution[role]["early_p1"]
        late = distribution[role]["late_p1"]
        p2 = distribution[role]["p2"]
        print(f"{role:<10} {early:>11.1%} {late:>11.1%} {p2:>11.1%}")
    print("-" * 60)
    print(f"{'Total':>10} {phase_totals['early_p1']:>12,} {phase_totals['late_p1']:>12,} {phase_totals['p2']:>12,}")

    # Calculate multipliers for reference
    print("\nResulting Multipliers (penalty-only, capped at 1.0):")
    print("-" * 60)
    print(f"{'Role':<10} {'Early P1':>12} {'Late P1':>12} {'P2':>12}")
    print("-" * 60)
    uniform = 0.20
    for role in roles:
        mults = []
        for phase in phases:
            mult = min(1.0, distribution[role][phase] / uniform)
            mults.append(f"{mult:.2f}x")
        print(f"{role:<10} {mults[0]:>12} {mults[1]:>12} {mults[2]:>12}")
    print("-" * 60)

    # Write output
    with open(output_path, "w") as f:
        json.dump(distribution, f, indent=2)
    print(f"\nWrote distribution to {output_path}")

    return output_path


def main():
    if len(sys.argv) > 1:
        data_path = Path(sys.argv[1])
    else:
        script_dir = Path(__file__).parent
        repo_root = script_dir.parent.parent
        data_path = repo_root / "outputs" / "full_2024_2025_v2" / "csv"

    if not data_path.exists():
        print(f"Error: Data path not found: {data_path}")
        print(f"Make sure CSV files exist at: {data_path}")
        sys.exit(1)

    build_role_pick_phase(data_path)
    print("\nDone!")


if __name__ == "__main__":
    main()
