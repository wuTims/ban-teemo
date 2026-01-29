#!/usr/bin/env python3
"""
Script to expand archetype_counters.json with champion data from knowledge_base.json.

This script reads comp_fit data from knowledge_base.json and maps it to the
archetype system (engage, split, teamfight, protect, pick) used in archetype_counters.json.
"""

import json
from pathlib import Path
from collections import defaultdict


# Mapping from comp_fit categories to archetypes
# Archetypes: engage, split, teamfight, protect, pick
COMP_FIT_TO_ARCHETYPE = {
    "poke": ["teamfight", "pick"],  # Poke comps excel at teamfights and picks
    "dive": ["engage"],  # Dive is a form of hard engage
    "split": ["split"],  # Direct mapping
    "splitpush": ["split"],  # Direct mapping (alternative naming)
    "protect": ["protect"],  # Direct mapping
    "teamfight": ["teamfight"],  # Direct mapping
    "pick": ["pick"],  # Direct mapping
    "skirmish": ["pick", "engage"],  # Skirmish relates to pick and engage
    "front_to_back": ["teamfight", "protect"],  # Front-to-back is teamfight/protect focused
}


def load_json(filepath: Path) -> dict:
    """Load JSON file and return data."""
    with open(filepath, "r") as f:
        return json.load(f)


def save_json(filepath: Path, data: dict) -> None:
    """Save data to JSON file with pretty formatting."""
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def convert_comp_fit_to_archetypes(comp_fit: dict) -> dict:
    """
    Convert comp_fit data to archetype scores.

    Args:
        comp_fit: Dictionary of comp_fit categories with fit and score

    Returns:
        Dictionary mapping archetypes to scores
    """
    archetype_scores = defaultdict(list)

    for category, data in comp_fit.items():
        if not data:  # Skip empty entries
            continue

        score = data.get("score", 0.5)

        # Map to archetypes
        archetypes = COMP_FIT_TO_ARCHETYPE.get(category, [])
        for archetype in archetypes:
            archetype_scores[archetype].append(score)

    # Average scores if multiple comp_fit categories map to the same archetype
    final_scores = {}
    for archetype, scores in archetype_scores.items():
        if scores:
            # Use max score rather than average to preserve strongest fit
            final_scores[archetype] = round(max(scores), 2)

    return final_scores


def main():
    """Main function to expand archetype data."""
    knowledge_dir = Path("/workspaces/web-dev-playground/ban-teemo/knowledge")

    knowledge_base_path = knowledge_dir / "knowledge_base.json"
    archetype_counters_path = knowledge_dir / "archetype_counters.json"

    print(f"Reading {knowledge_base_path}...")
    knowledge_base = load_json(knowledge_base_path)

    print(f"Reading {archetype_counters_path}...")
    archetype_counters = load_json(archetype_counters_path)

    # Get existing champion archetypes
    existing_champions = set(archetype_counters.get("champion_archetypes", {}).keys())
    print(f"Existing champions in archetype_counters.json: {len(existing_champions)}")

    # Track statistics
    stats = {
        "champions_processed": 0,
        "champions_with_comp_fit": 0,
        "champions_added": 0,
        "champions_updated": 0,
        "champions_skipped_empty": 0,
    }

    # Process champions from knowledge_base
    new_champion_archetypes = dict(archetype_counters.get("champion_archetypes", {}))

    for champ_name, champ_data in knowledge_base.get("champions", {}).items():
        stats["champions_processed"] += 1

        comp_fit = champ_data.get("comp_fit", {})

        if not comp_fit:
            stats["champions_skipped_empty"] += 1
            continue

        stats["champions_with_comp_fit"] += 1

        # Convert comp_fit to archetypes
        archetype_scores = convert_comp_fit_to_archetypes(comp_fit)

        if not archetype_scores:
            stats["champions_skipped_empty"] += 1
            continue

        if champ_name in existing_champions:
            # Update existing champion only if new data is better/different
            existing_scores = new_champion_archetypes[champ_name]
            if archetype_scores != existing_scores:
                # Merge: keep existing scores but add new ones
                merged = {**archetype_scores, **existing_scores}  # Existing takes priority
                new_champion_archetypes[champ_name] = merged
                stats["champions_updated"] += 1
        else:
            # Add new champion
            new_champion_archetypes[champ_name] = archetype_scores
            stats["champions_added"] += 1

    # Sort champions alphabetically for consistency
    sorted_champion_archetypes = dict(sorted(new_champion_archetypes.items()))

    # Build output data preserving existing structure
    output_data = {
        "metadata": archetype_counters.get("metadata", {
            "version": "1.0.0",
            "description": "RPS effectiveness matrix for team composition archetypes"
        }),
        "archetypes": archetype_counters.get("archetypes", ["engage", "split", "teamfight", "protect", "pick"]),
        "effectiveness_matrix": archetype_counters.get("effectiveness_matrix", {}),
        "champion_archetypes": sorted_champion_archetypes,
    }

    # Save the expanded file
    print(f"\nWriting expanded data to {archetype_counters_path}...")
    save_json(archetype_counters_path, output_data)

    # Print statistics
    print("\n" + "=" * 50)
    print("STATISTICS")
    print("=" * 50)
    print(f"Total champions processed: {stats['champions_processed']}")
    print(f"Champions with comp_fit data: {stats['champions_with_comp_fit']}")
    print(f"Champions added: {stats['champions_added']}")
    print(f"Champions updated: {stats['champions_updated']}")
    print(f"Champions skipped (empty comp_fit): {stats['champions_skipped_empty']}")
    print(f"Total champions in output: {len(sorted_champion_archetypes)}")
    print("=" * 50)

    # Print sample of added champions
    added_champions = [c for c in sorted_champion_archetypes if c not in existing_champions]
    if added_champions:
        print("\nSample of added champions:")
        for champ in sorted(added_champions)[:10]:
            print(f"  {champ}: {sorted_champion_archetypes[champ]}")
        if len(added_champions) > 10:
            print(f"  ... and {len(added_champions) - 10} more")


if __name__ == "__main__":
    main()
