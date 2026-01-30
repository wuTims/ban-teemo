#!/usr/bin/env python3
"""Audit matchup and counter data quality.

Checks:
1. Coverage: How many champion pairs have matchup data?
2. Completeness: Are both lane and team matchups present?
3. Sample sizes: Do we have enough games for reliable data?
4. Missing data: Which common matchups are missing?
"""

import json
from pathlib import Path
from collections import defaultdict


def main():
    knowledge_dir = Path(__file__).parent.parent / "knowledge"

    # Load matchup data
    matchup_path = knowledge_dir / "matchup_stats.json"
    with open(matchup_path) as f:
        matchup_data = json.load(f)

    # Load meta stats to know which champions are relevant
    meta_path = knowledge_dir / "meta_stats.json"
    with open(meta_path) as f:
        meta_data = json.load(f)
    meta_champs = set(meta_data.get("champions", {}).keys())

    print("=" * 70)
    print("MATCHUP DATA AUDIT")
    print("=" * 70)

    # Check structure
    print(f"\nData structure: {type(matchup_data)}")
    if isinstance(matchup_data, dict):
        print(f"Top-level keys: {list(matchup_data.keys())[:10]}")

    # Print metadata if present
    if "metadata" in matchup_data:
        print(f"\nMetadata: {matchup_data['metadata']}")

    # Handle nested 'counters' structure
    if "counters" in matchup_data:
        champion_data = matchup_data["counters"]
    else:
        champion_data = matchup_data

    # Analyze coverage
    champions_with_data = set()
    total_matchups = 0
    matchups_by_role = defaultdict(int)
    low_sample_matchups = []

    for champ, data in champion_data.items():
        if champ == "metadata":
            continue
        champions_with_data.add(champ)

        # Check vs_lane (role-specific matchups)
        vs_lane = data.get("vs_lane", {})
        for role, matchups in vs_lane.items():
            for enemy, stats in matchups.items():
                total_matchups += 1
                matchups_by_role[role] += 1
                games = stats.get("games", 0)
                if games < 10:
                    low_sample_matchups.append((champ, enemy, role, games))

        # Check vs_team (team-wide matchups)
        vs_team = data.get("vs_team", {})
        total_matchups += len(vs_team)

    print(f"\n--- COVERAGE ---")
    print(f"Champions with matchup data: {len(champions_with_data)}")
    print(f"Meta champions: {len(meta_champs)}")
    print(f"Coverage: {len(champions_with_data & meta_champs)}/{len(meta_champs)} meta champs")
    print(f"Total matchup entries: {total_matchups}")

    print(f"\n--- BY ROLE ---")
    for role, count in sorted(matchups_by_role.items()):
        print(f"  {role}: {count} matchups")

    print(f"\n--- LOW SAMPLE SIZE (<10 games) ---")
    print(f"Count: {len(low_sample_matchups)}")
    if low_sample_matchups[:10]:
        print("Examples:")
        for champ, enemy, role, games in low_sample_matchups[:10]:
            print(f"  {champ} vs {enemy} ({role}): {games} games")

    # Check for missing meta champion matchups
    missing_meta = meta_champs - champions_with_data
    if missing_meta:
        print(f"\n--- MISSING META CHAMPIONS ---")
        print(f"Count: {len(missing_meta)}")
        print(f"Champions: {sorted(missing_meta)[:20]}")

    # Summary
    print(f"\n--- SUMMARY ---")
    coverage_pct = len(champions_with_data & meta_champs) / len(meta_champs) * 100 if meta_champs else 0
    print(f"Data coverage: {coverage_pct:.1f}%")
    print(f"Low sample matchups: {len(low_sample_matchups)} ({len(low_sample_matchups)/max(total_matchups,1)*100:.1f}%)")

    if coverage_pct < 80:
        print("\nWARNING: Coverage below 80% - investigate data pipeline")
    if len(low_sample_matchups) > total_matchups * 0.3:
        print("\nWARNING: >30% of matchups have low sample size")


if __name__ == "__main__":
    main()
