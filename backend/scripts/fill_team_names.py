#!/usr/bin/env python3
"""
Fill in the 'team' field in player_roles.json using teams.csv data.

Maps team_id -> team name for all players.
"""

import csv
import json
from pathlib import Path


def main():
    project_root = Path(__file__).parent.parent.parent
    teams_csv = project_root / "outputs" / "full_2024_2025_v2" / "csv" / "teams.csv"
    player_roles_json = project_root / "knowledge" / "player_roles.json"

    # Load teams mapping: id -> name
    teams = {}
    with open(teams_csv, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            teams[row["id"]] = row["name"]

    print(f"Loaded {len(teams)} teams from {teams_csv}")

    # Load player roles
    with open(player_roles_json, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Fill in team names
    updated = 0
    missing_teams = set()
    for player_key, player in data["players"].items():
        team_id = player.get("team_id", "")
        if team_id and team_id in teams:
            player["team"] = teams[team_id]
            updated += 1
        elif team_id:
            missing_teams.add(team_id)

    print(f"Updated {updated} players with team names")
    if missing_teams:
        print(f"Warning: {len(missing_teams)} team_ids not found in teams.csv: {missing_teams}")

    # Save updated player roles
    with open(player_roles_json, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"Saved updated player_roles.json")


if __name__ == "__main__":
    main()
