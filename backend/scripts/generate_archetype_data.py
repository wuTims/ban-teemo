#!/usr/bin/env python3
"""Generate archetype data for all champions from knowledge_base.json.

Sources:
1. comp_archetypes.markers - explicit champion assignments
2. classification.subclass - class-based inference
3. attributes - attribute-based refinement
"""
import json
import re
from pathlib import Path

KNOWLEDGE_DIR = Path(__file__).parents[2] / "knowledge"


def normalize_champion_name(name: str) -> str:
    """Convert various name formats to canonical format.

    Examples:
        XinZhao -> Xin Zhao
        JarvanIV -> Jarvan IV
        DrMundo -> Dr. Mundo
        Velkoz -> Vel'Koz
        Kaisa -> Kai'Sa
    """
    # Special cases - map to canonical names
    special_cases = {
        "MonkeyKing": "Wukong",
        "DrMundo": "Dr. Mundo",
        # Apostrophe names
        "Velkoz": "Vel'Koz",
        "Kaisa": "Kai'Sa",
        "Kogmaw": "Kog'Maw",
        "KogMaw": "Kog'Maw",
        "Kog Maw": "Kog'Maw",
        "Khazix": "Kha'Zix",
        "KhaZix": "Kha'Zix",
        "Chogath": "Cho'Gath",
        "ChoGath": "Cho'Gath",
        "Reksai": "Rek'Sai",
        "RekSai": "Rek'Sai",
        "Belveth": "Bel'Veth",
        "BelVeth": "Bel'Veth",
        # Case normalization
        "Leblanc": "LeBlanc",
        "Renata": "Renata Glasc",
    }

    # Check special cases first (case-insensitive)
    for key, canonical in special_cases.items():
        if name.lower().replace("'", "").replace(" ", "") == key.lower().replace("'", "").replace(" ", ""):
            return canonical

    # Insert space before uppercase letters (but not at start)
    result = re.sub(r'([a-z])([A-Z])', r'\1 \2', name)
    result = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1 \2', result)

    return result

# Map comp_archetypes names to archetype_counters.json names
ARCHETYPE_MAP = {
    "dive": "engage",
    "protect": "protect",
    "front_to_back": "teamfight",
    "splitpush": "split",
    "poke": "teamfight",  # Poke comps often teamfight at range
    "pick": "pick",
    "skirmish": "pick",  # Skirmish is similar to pick
}

# Map subclass to archetype scores
SUBCLASS_ARCHETYPES = {
    # Tanks
    "Vanguard": {"engage": 0.9, "teamfight": 0.5},
    "Warden": {"protect": 0.8, "engage": 0.4},

    # Fighters
    "Diver": {"engage": 0.7, "pick": 0.6},
    "Skirmisher": {"split": 0.8, "pick": 0.4},
    "Juggernaut": {"teamfight": 0.6, "split": 0.5},

    # Mages
    "Burst": {"teamfight": 0.7, "pick": 0.5},
    "Artillery": {"teamfight": 0.8},
    "Battlemage": {"teamfight": 0.7, "engage": 0.3},

    # Assassins
    "Assassin": {"pick": 0.9},

    # Marksmen
    "Marksman": {"teamfight": 0.6},

    # Controllers
    "Enchanter": {"protect": 0.9, "teamfight": 0.4},
    "Catcher": {"pick": 0.7, "engage": 0.5},

    # Specialists
    "Specialist": {"split": 0.5},  # Default for specialists
}

# Attribute modifiers
def get_attribute_modifiers(attrs: dict) -> dict:
    """Adjust archetype scores based on attributes."""
    mods = {}

    control = attrs.get("control", 2)
    mobility = attrs.get("mobility", 2)
    damage = attrs.get("damage", 2)
    utility = attrs.get("utility", 2)
    toughness = attrs.get("toughness", 2)

    # High control + mobility = engage
    if control >= 3 and mobility >= 2:
        mods["engage"] = mods.get("engage", 0) + 0.2

    # High control + toughness = protect
    if control >= 2 and toughness >= 3:
        mods["protect"] = mods.get("protect", 0) + 0.15

    # High damage + mobility = pick
    if damage >= 3 and mobility >= 3:
        mods["pick"] = mods.get("pick", 0) + 0.2

    # High utility = protect
    if utility >= 3:
        mods["protect"] = mods.get("protect", 0) + 0.2

    # Low mobility + high damage = teamfight (immobile carries)
    if mobility <= 1 and damage >= 2:
        mods["teamfight"] = mods.get("teamfight", 0) + 0.15

    return mods


def generate_archetype_data():
    """Generate archetype data for all champions."""
    # Load knowledge base
    kb_path = KNOWLEDGE_DIR / "knowledge_base.json"
    with open(kb_path) as f:
        kb = json.load(f)

    champions = kb.get("champions", {})
    comp_archetypes = kb.get("comp_archetypes", {})

    # Build champion -> archetype scores
    champion_archetypes = {}

    # First pass: Use comp_archetypes markers
    for arch_id, arch_data in comp_archetypes.items():
        target_arch = ARCHETYPE_MAP.get(arch_id, arch_id)
        if target_arch not in ["engage", "split", "teamfight", "protect", "pick"]:
            continue

        markers = arch_data.get("markers", {})

        for raw_champ in markers.get("strong", []):
            champ = normalize_champion_name(raw_champ)
            if champ not in champion_archetypes:
                champion_archetypes[champ] = {}
            champion_archetypes[champ][target_arch] = max(
                champion_archetypes[champ].get(target_arch, 0), 0.9
            )

        for raw_champ in markers.get("moderate", []):
            champ = normalize_champion_name(raw_champ)
            if champ not in champion_archetypes:
                champion_archetypes[champ] = {}
            champion_archetypes[champ][target_arch] = max(
                champion_archetypes[champ].get(target_arch, 0), 0.6
            )

        for raw_champ in markers.get("enablers", []):
            champ = normalize_champion_name(raw_champ)
            if champ not in champion_archetypes:
                champion_archetypes[champ] = {}
            champion_archetypes[champ][target_arch] = max(
                champion_archetypes[champ].get(target_arch, 0), 0.5
            )

    # Second pass: Use classification + attributes for champions without data
    for raw_name, champ_data in champions.items():
        champ_name = normalize_champion_name(raw_name)
        if champ_name in champion_archetypes and champion_archetypes[champ_name]:
            # Already has data from markers, but add attribute modifiers
            attrs = champ_data.get("attributes", {})
            mods = get_attribute_modifiers(attrs)
            for arch, mod in mods.items():
                current = champion_archetypes[champ_name].get(arch, 0)
                champion_archetypes[champ_name][arch] = min(1.0, current + mod)
            continue

        # No marker data - infer from classification
        classification = champ_data.get("classification", {})
        subclass = classification.get("subclass")
        primary_class = classification.get("primary_class")

        if champ_name not in champion_archetypes:
            champion_archetypes[champ_name] = {}

        # Class defaults for mapping
        class_defaults = {
            "Tank": {"engage": 0.5, "protect": 0.4},
            "Fighter": {"split": 0.5, "engage": 0.4},
            "Mage": {"teamfight": 0.6},
            "Assassin": {"pick": 0.8},
            "Marksman": {"teamfight": 0.5},
            "Controller": {"protect": 0.6},
            "Specialist": {"split": 0.4},
            "Support": {"protect": 0.5},
        }

        # Get base scores from subclass
        if subclass and subclass in SUBCLASS_ARCHETYPES:
            for arch, score in SUBCLASS_ARCHETYPES[subclass].items():
                champion_archetypes[champ_name][arch] = score
        elif primary_class:
            # Fallback to primary class
            for arch, score in class_defaults.get(primary_class, {}).items():
                champion_archetypes[champ_name][arch] = score
        else:
            # No classification - use legacy_tags as fallback
            legacy_tags = classification.get("legacy_tags", [])
            for tag in legacy_tags:
                if tag in class_defaults:
                    for arch, score in class_defaults[tag].items():
                        current = champion_archetypes[champ_name].get(arch, 0)
                        champion_archetypes[champ_name][arch] = max(current, score * 0.8)  # Slightly lower for tag-based
                    break  # Use first matching tag

        # Apply attribute modifiers
        attrs = champ_data.get("attributes", {})
        mods = get_attribute_modifiers(attrs)
        for arch, mod in mods.items():
            current = champion_archetypes[champ_name].get(arch, 0)
            champion_archetypes[champ_name][arch] = min(1.0, round(current + mod, 2))

    # Clean up: remove empty entries and round scores
    for champ in list(champion_archetypes.keys()):
        scores = champion_archetypes[champ]
        if not scores:
            del champion_archetypes[champ]
        else:
            champion_archetypes[champ] = {
                k: round(v, 2) for k, v in scores.items() if v > 0
            }

    # Load existing archetype_counters.json to preserve effectiveness matrix
    ac_path = KNOWLEDGE_DIR / "archetype_counters.json"
    with open(ac_path) as f:
        existing = json.load(f)

    # Update with new champion data
    existing["champion_archetypes"] = champion_archetypes
    existing["metadata"]["champion_count"] = len(champion_archetypes)
    existing["metadata"]["generated_from"] = "knowledge_base.json"

    # Write back
    with open(ac_path, "w") as f:
        json.dump(existing, f, indent=2)

    print(f"Generated archetype data for {len(champion_archetypes)} champions")

    # Show some examples
    print("\nSamples:")
    for champ in ["Poppy", "Xin Zhao", "Ambessa", "Orianna", "Jarvan IV"]:
        if champ in champion_archetypes:
            print(f"  {champ}: {champion_archetypes[champ]}")


if __name__ == "__main__":
    generate_archetype_data()
