#!/usr/bin/env python3
"""
One-time script to scrape team logos from Leaguepedia.
Outputs a JSON mapping of team names to logo URLs.
"""

import csv
import json
import time
from pathlib import Path

# Try leaguepedia_parser first, fall back to direct mwclient if needed
try:
    import leaguepedia_parser as lp
    USE_LP = True
except ImportError:
    USE_LP = False
    import mwclient

# Team name mappings for Leaguepedia (some names differ)
TEAM_NAME_MAPPINGS = {
    "NONGSHIM RED FORCE": "Nongshim RedForce",
    "KWANGDONG FREECS": "Kwangdong Freecs",
    "Gen.G Esports": "Gen.G",
    "SHANGHAI EDWARD GAMING HYCAN": "EDward Gaming",
    "Suzhou LNG Ninebot Esports": "LNG Esports",
    "WeiboGaming Faw Audi": "Weibo Gaming",
    "Xi'an Team WE": "Team WE",
    "Team Liquid Honda": "Team Liquid",
    "Beijing JDG Intel Esports": "JD Gaming",
    "LEVIATÁN": "Leviatan",
    "Cloud9 Kia": "Cloud9",
    "NRG Kia": "NRG",
    "Dplus KIA": "Dplus KIA",
    "OKSavingsBank BRION": "BRION",
    "BNK FearX": "BNK FearX",
    "Immortals Progressive": "Immortals",
    "Shenzhen NINJAS IN PYJAMAS": "Ninjas in Pyjamas",
    "THUNDER TALK GAMING": "ThunderTalk Gaming",
    "Vivo Keyd Stars": "Keyd Stars",
    "RED Kalunga": "RED Canids",
    "Isurus Estral": "Isurus",
    "Movistar KOI": "Movistar KOI",
    "GIANTX": "GIANTX",
    "Fluxo W7M": "Fluxo",
    "LYON": "Lyon Gaming (2024 American Team)",
    "Rare Atom": "Rare Atom",
    "FURIA": "FURIA Esports",
    "LOUD": "LOUD",
    "Anyone's Legend": "Anyone's Legend",
    "Ultra Prime": "Ultra Prime",
    "Oh My God": "Oh My God",
    "100 Thieves": "100 Thieves",
    "Dignitas": "Dignitas",
    "Shopify Rebellion": "Shopify Rebellion",
    "Disguised": "Disguised",
    "Natus Vincere": "Natus Vincere",
    "Pain Gaming": "paiN Gaming",
    "Rogue": "Rogue (European Team)",
}


def get_logo_url_lp(team_name: str) -> str | None:
    """Get logo URL using leaguepedia_parser."""
    mapped_name = TEAM_NAME_MAPPINGS.get(team_name, team_name)
    try:
        url = lp.get_team_logo(mapped_name)
        return url
    except Exception as e:
        print(f"  Error fetching {mapped_name}: {e}")
        return None


def get_logo_url_mwclient(site: mwclient.Site, team_name: str) -> str | None:
    """Get logo URL using direct mwclient queries."""
    mapped_name = TEAM_NAME_MAPPINGS.get(team_name, team_name)
    try:
        # Query the Teams table for logo filename
        result = site.api(
            "cargoquery",
            tables="Teams",
            fields="Image",
            where=f'Name="{mapped_name}" OR Short="{mapped_name}"',
            limit=1,
        )

        if result.get("cargoquery") and len(result["cargoquery"]) > 0:
            image_name = result["cargoquery"][0]["title"]["Image"]
            if image_name:
                # Get the actual file URL
                image_info = site.api(
                    "query",
                    titles=f"File:{image_name}",
                    prop="imageinfo",
                    iiprop="url",
                )
                pages = image_info.get("query", {}).get("pages", {})
                for page in pages.values():
                    if "imageinfo" in page:
                        return page["imageinfo"][0]["url"]
        return None
    except Exception as e:
        print(f"  Error fetching {mapped_name}: {e}")
        return None


def main():
    # Paths
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    teams_csv = project_root / "outputs" / "full_2024_2025" / "csv" / "teams.csv"
    output_json = project_root / "deepdraft" / "src" / "data" / "team-logos.json"

    # Ensure output directory exists
    output_json.parent.mkdir(parents=True, exist_ok=True)

    # Read teams
    teams = []
    with open(teams_csv, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["name"] and row["name"] != "TBD-1":
                teams.append({"id": row["id"], "name": row["name"]})

    print(f"Found {len(teams)} teams to process")

    # Initialize mwclient if needed
    site = None
    if not USE_LP:
        print("leaguepedia_parser not found, using mwclient directly")
        site = mwclient.Site("lol.fandom.com", path="/")
    else:
        print("Using leaguepedia_parser")

    # Scrape logos
    logo_mapping = {}
    failed = []

    for i, team in enumerate(teams):
        team_name = team["name"]
        team_id = team["id"]
        print(f"[{i+1}/{len(teams)}] Fetching logo for: {team_name}")

        if USE_LP:
            url = get_logo_url_lp(team_name)
        else:
            url = get_logo_url_mwclient(site, team_name)

        if url:
            logo_mapping[team_id] = {
                "name": team_name,
                "logoUrl": url,
            }
            print(f"  ✓ Found: {url[:80]}...")
        else:
            failed.append(team_name)
            print(f"  ✗ Not found")

        # Rate limiting - be nice to the API
        time.sleep(0.5)

    # Save results
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(logo_mapping, f, indent=2, ensure_ascii=False)

    print(f"\n{'='*50}")
    print(f"Saved {len(logo_mapping)} logos to {output_json}")

    if failed:
        print(f"\nFailed to find logos for {len(failed)} teams:")
        for name in failed:
            print(f"  - {name}")
        print("\nYou may need to add mappings to TEAM_NAME_MAPPINGS dict")


if __name__ == "__main__":
    main()
