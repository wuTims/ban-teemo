#!/usr/bin/env python3
"""
Build tournament meta JSON from tournament CSV data.

Converts tournament pick/ban data into a structured JSON format for use
by the TournamentScorer in simulator mode.

Usage:
    uv run python scripts/build_tournament_meta.py \
        --input data/input/2026_winter_tournaments.csv \
        --patch 26.1 \
        --output knowledge/tournament_meta.json
"""

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path


# Asymmetric blending threshold - picks needed for full confidence
SAMPLE_THRESHOLD = 10

# Default penalties for missing champions
# TUNING NOTE: If recommendations feel too punishing toward off-meta picks,
# adjust these values in the output JSON -> defaults
DEFAULT_MISSING_PRIORITY = 0.05
DEFAULT_MISSING_PERFORMANCE = 0.35


def parse_percentage(value: str) -> float:
    """Convert percentage string (e.g., '56%') to float (0.56)."""
    return float(value.rstrip("%")) / 100


def calculate_adjusted_performance(winrate: float, picks: int) -> float:
    """
    Adjust winrate based on sample size.

    - High WR + low sample: blend toward 0.5 (reduce false optimism)
    - Low WR + any sample: preserve as warning signal
    - Threshold: 10 picks for full confidence
    """
    if winrate > 0.5 and picks < SAMPLE_THRESHOLD:
        sample_weight = picks / SAMPLE_THRESHOLD
        return sample_weight * winrate + (1 - sample_weight) * 0.5
    return winrate


def normalize_role(role: str) -> str:
    """Normalize role names to lowercase."""
    role_map = {
        "Top": "top",
        "Jungle": "jungle",
        "Jungl": "jungle",  # Handle truncated role name in CSV
        "Mid": "mid",
        "ADC": "adc",
        "Support": "support",
    }
    return role_map.get(role, role.lower())


def build_tournament_meta(input_path: Path, patch: str) -> dict:
    """
    Build tournament meta data from CSV.

    Args:
        input_path: Path to the tournament CSV file
        patch: Patch version string (e.g., "26.1")

    Returns:
        Dictionary with metadata, champions, and defaults
    """
    champions: dict[str, dict] = {}

    with open(input_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            champion = row["Champion"]
            role = normalize_role(row["Role"])
            picks = int(row["Picks"])
            winrate = parse_percentage(row["Winrate"])
            prio_score = parse_percentage(row["PrioScore"])

            # Initialize champion entry if needed
            if champion not in champions:
                champions[champion] = {
                    "priority": 0.0,
                    "roles": {},
                }

            # Priority is role-agnostic: take max across all roles
            champions[champion]["priority"] = max(
                champions[champion]["priority"], prio_score
            )

            # Performance is role-specific with asymmetric blending
            adjusted_performance = calculate_adjusted_performance(winrate, picks)

            # Store role data (may have duplicates per role in CSV, take highest picks)
            if role not in champions[champion]["roles"]:
                champions[champion]["roles"][role] = {
                    "winrate": round(winrate, 3),
                    "picks": picks,
                    "adjusted_performance": round(adjusted_performance, 3),
                }
            else:
                # If duplicate role entry, merge by taking the one with more picks
                existing = champions[champion]["roles"][role]
                if picks > existing["picks"]:
                    champions[champion]["roles"][role] = {
                        "winrate": round(winrate, 3),
                        "picks": picks,
                        "adjusted_performance": round(adjusted_performance, 3),
                    }

    # Round priority values
    for champ_data in champions.values():
        champ_data["priority"] = round(champ_data["priority"], 3)

    return {
        "metadata": {
            "source": input_path.name,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "patch": patch,
            "champion_count": len(champions),
        },
        "champions": champions,
        "defaults": {
            "missing_champion_priority": DEFAULT_MISSING_PRIORITY,
            "missing_champion_performance": DEFAULT_MISSING_PERFORMANCE,
            "note": "Penalty for champions with zero pro presence - traceable for tuning",
        },
    }


def main():
    parser = argparse.ArgumentParser(
        description="Build tournament meta JSON from CSV data"
    )
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Path to tournament CSV file",
    )
    parser.add_argument(
        "--patch",
        type=str,
        required=True,
        help="Patch version (e.g., 26.1)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output path for tournament_meta.json",
    )

    args = parser.parse_args()

    if not args.input.exists():
        raise FileNotFoundError(f"Input file not found: {args.input}")

    print(f"Building tournament meta from {args.input}...")
    tournament_meta = build_tournament_meta(args.input, args.patch)

    # Ensure output directory exists
    args.output.parent.mkdir(parents=True, exist_ok=True)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(tournament_meta, f, indent=2)

    print(f"Generated {args.output}")
    print(f"  - Champions: {tournament_meta['metadata']['champion_count']}")
    print(f"  - Patch: {tournament_meta['metadata']['patch']}")


if __name__ == "__main__":
    main()
