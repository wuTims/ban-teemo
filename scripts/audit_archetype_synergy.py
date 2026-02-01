#!/usr/bin/env python3
"""Audit and improve archetype & synergy data quality.

This script evaluates our archetype and synergy data against:
1. Champion class/role expectations (engage junglers should be 'engage', etc.)
2. Pro play pick patterns (champions picked together should have synergy)
3. Common combo knowledge (Yasuo+knockups, Orianna+engage, etc.)

Usage:
    # Full audit with recommendations
    uv run python scripts/audit_archetype_synergy.py

    # Check specific champions
    uv run python scripts/audit_archetype_synergy.py --champions "Xin Zhao,Vi,Jarvan IV"

    # Analyze why champion X was picked over Y in similar situations
    uv run python scripts/audit_archetype_synergy.py --compare "Xin Zhao" "Vi" --context jungle

    # Generate fix recommendations
    uv run python scripts/audit_archetype_synergy.py --generate-fixes

    # Apply fixes interactively
    uv run python scripts/audit_archetype_synergy.py --apply-fixes
"""

import argparse
import json
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend" / "src"))


class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    RESET = '\033[0m'


# Expected archetypes by champion class/playstyle
# Used to detect misclassifications
EXPECTED_ARCHETYPES = {
    # Engage champions - should have high 'engage' scores
    "engage_champions": {
        "champions": [
            "Vi", "Jarvan IV", "Xin Zhao", "Nocturne", "Rell", "Leona",
            "Nautilus", "Alistar", "Rakan", "Sejuani", "Zac", "Amumu",
            "Malphite", "Ornn", "Maokai", "Wukong", "Camille", "Kled",
            "Renekton", "Yone", "Yasuo", "Diana", "Gragas"
        ],
        "expected": {"engage": 0.6},  # Should have at least 0.6 engage
        "not_expected": {"split": 0.5},  # Should NOT have high split
    },
    # Split push champions
    "split_champions": {
        "champions": [
            "Fiora", "Jax", "Tryndamere", "Yorick", "Nasus", "Shen",
            "Camille", "Gwen", "Kayle"
        ],
        "expected": {"split": 0.5},
        "not_expected": {},
    },
    # Poke/siege champions
    "poke_champions": {
        "champions": [
            "Jayce", "Nidalee", "Xerath", "Ziggs", "Varus", "Zoe",
            "Corki", "Ezreal", "Lux"
        ],
        "expected": {},  # We don't have a poke archetype
        "not_expected": {"engage": 0.7},
    },
    # Protect/peel champions
    "protect_champions": {
        "champions": [
            "Lulu", "Janna", "Karma", "Braum", "Tahm Kench", "Poppy",
            "Ivern", "Zilean", "Soraka", "Yuumi"
        ],
        "expected": {"protect": 0.5},
        "not_expected": {},
    },
    # Teamfight/wombo champions
    "teamfight_champions": {
        "champions": [
            "Orianna", "Kennen", "Rumble", "Miss Fortune", "Seraphine",
            "Galio", "Neeko", "Zyra", "Brand", "Swain"
        ],
        "expected": {"teamfight": 0.5},
        "not_expected": {"split": 0.5},
    },
    # Pick/assassin champions
    "pick_champions": {
        "champions": [
            "Lee Sin", "Elise", "Nidalee", "Rengar", "Kha'Zix",
            "Pyke", "Thresh", "Blitzcrank", "Ahri", "Syndra", "LeBlanc"
        ],
        "expected": {"pick": 0.5},
        "not_expected": {},
    },
}

# Known synergy combos that should have high synergy scores
KNOWN_SYNERGIES = {
    # Yasuo/Yone + knockup combos
    "yasuo_knockups": {
        "primary": ["Yasuo", "Yone"],
        "partners": ["Malphite", "Gragas", "Diana", "Alistar", "Ornn", "Rakan",
                     "Jarvan IV", "Vi", "Rell", "Nautilus", "Braum", "Xin Zhao"],
        "reason": "Knockup enables Last Breath",
        "min_synergy": 0.6,
    },
    # Orianna ball delivery
    "orianna_engage": {
        "primary": ["Orianna"],
        "partners": ["Jarvan IV", "Vi", "Xin Zhao", "Nocturne", "Camille",
                     "Renekton", "Wukong", "Malphite", "Rell", "Leona", "Alistar"],
        "reason": "Ball delivery for Shockwave",
        "min_synergy": 0.6,
    },
    # Kalista + melee support
    "kalista_support": {
        "primary": ["Kalista"],
        "partners": ["Thresh", "Alistar", "Leona", "Nautilus", "Rell", "Rakan",
                     "Braum", "Tahm Kench"],
        "reason": "Fate's Call engage",
        "min_synergy": 0.65,
    },
    # Seraphine/Sona + follow-up
    "seraphine_combos": {
        "primary": ["Seraphine", "Sona"],
        "partners": ["Miss Fortune", "Amumu", "Jarvan IV", "Orianna"],
        "reason": "AoE ult combos",
        "min_synergy": 0.6,
    },
    # Renata + ADC
    "renata_adc": {
        "primary": ["Renata Glasc"],
        "partners": ["Jinx", "Kog'Maw", "Twitch", "Aphelios"],
        "reason": "Bailout + hypercarry",
        "min_synergy": 0.6,
    },
    # Lulu + hypercarry
    "lulu_protect": {
        "primary": ["Lulu"],
        "partners": ["Kog'Maw", "Jinx", "Twitch", "Vayne", "Kai'Sa"],
        "reason": "Protect the carry",
        "min_synergy": 0.65,
    },
}


@dataclass
class ArchetypeIssue:
    """Detected issue with archetype classification."""
    champion: str
    issue_type: str  # "missing", "wrong_primary", "unexpected_high"
    current: dict
    expected: dict
    severity: str  # "high", "medium", "low"
    suggestion: dict


@dataclass
class SynergyIssue:
    """Detected issue with synergy data."""
    champion1: str
    champion2: str
    issue_type: str  # "missing", "too_low", "too_high"
    current_score: Optional[float]
    expected_min: float
    reason: str
    severity: str


@dataclass
class AuditResult:
    """Complete audit results."""
    archetype_issues: list[ArchetypeIssue] = field(default_factory=list)
    synergy_issues: list[SynergyIssue] = field(default_factory=list)
    archetype_stats: dict = field(default_factory=dict)
    synergy_stats: dict = field(default_factory=dict)


class ArchetypeSynergyAuditor:
    """Audits and suggests improvements for archetype/synergy data."""

    def __init__(self, knowledge_dir: Path):
        self.knowledge_dir = knowledge_dir
        self.archetype_data = {}
        self.synergy_data = {}
        self.champion_synergies = {}
        self.pro_play_data = {}
        self._load_data()

    def _load_data(self):
        """Load all relevant data files."""
        # Archetype data
        arch_path = self.knowledge_dir / "archetype_counters.json"
        if arch_path.exists():
            with open(arch_path) as f:
                data = json.load(f)
                self.archetype_data = data.get("champion_archetypes", {})

        # Curated synergies
        syn_path = self.knowledge_dir / "synergies.json"
        if syn_path.exists():
            with open(syn_path) as f:
                self.synergy_data = json.load(f)

        # Statistical synergies
        champ_syn_path = self.knowledge_dir / "champion_synergies.json"
        if champ_syn_path.exists():
            with open(champ_syn_path) as f:
                self.champion_synergies = json.load(f)

    def audit_archetypes(self) -> list[ArchetypeIssue]:
        """Check all archetypes against expected classifications."""
        issues = []

        for category, config in EXPECTED_ARCHETYPES.items():
            for champion in config["champions"]:
                if champion not in self.archetype_data:
                    issues.append(ArchetypeIssue(
                        champion=champion,
                        issue_type="missing",
                        current={},
                        expected=config["expected"],
                        severity="high",
                        suggestion=config["expected"],
                    ))
                    continue

                current = self.archetype_data[champion]

                # Check expected archetypes are present
                for archetype, min_score in config["expected"].items():
                    current_score = current.get(archetype, 0)
                    if current_score < min_score:
                        # Determine primary archetype
                        primary = max(current.items(), key=lambda x: x[1])[0] if current else "none"

                        issues.append(ArchetypeIssue(
                            champion=champion,
                            issue_type="missing_expected",
                            current=current,
                            expected={archetype: min_score},
                            severity="high" if min_score >= 0.6 else "medium",
                            suggestion={**current, archetype: max(min_score, current_score + 0.3)},
                        ))

                # Check unexpected archetypes aren't too high
                for archetype, max_score in config.get("not_expected", {}).items():
                    current_score = current.get(archetype, 0)
                    if current_score >= max_score:
                        issues.append(ArchetypeIssue(
                            champion=champion,
                            issue_type="unexpected_high",
                            current=current,
                            expected={"NOT " + archetype: f"< {max_score}"},
                            severity="medium",
                            suggestion={k: v for k, v in current.items() if k != archetype or v < max_score * 0.5},
                        ))

        return issues

    def audit_synergies(self) -> list[SynergyIssue]:
        """Check synergies against known combos."""
        issues = []

        for combo_name, config in KNOWN_SYNERGIES.items():
            for primary in config["primary"]:
                for partner in config["partners"]:
                    score = self._get_synergy_score(primary, partner)

                    if score is None:
                        issues.append(SynergyIssue(
                            champion1=primary,
                            champion2=partner,
                            issue_type="missing",
                            current_score=None,
                            expected_min=config["min_synergy"],
                            reason=config["reason"],
                            severity="high",
                        ))
                    elif score < config["min_synergy"]:
                        issues.append(SynergyIssue(
                            champion1=primary,
                            champion2=partner,
                            issue_type="too_low",
                            current_score=score,
                            expected_min=config["min_synergy"],
                            reason=config["reason"],
                            severity="medium" if score > config["min_synergy"] - 0.2 else "high",
                        ))

        return issues

    def _get_synergy_score(self, champ1: str, champ2: str) -> Optional[float]:
        """Get synergy score between two champions."""
        # Check curated synergies (list format)
        if isinstance(self.synergy_data, list):
            for entry in self.synergy_data:
                champions = entry.get("champions", [])
                if champ1 in champions and champ2 in champions:
                    # Convert strength rating to score
                    strength = entry.get("strength", "C")
                    return {"S": 1.0, "A": 0.8, "B": 0.6, "C": 0.4, "D": 0.2}.get(strength, 0.4)

        # Check statistical synergies
        if champ1 in self.champion_synergies:
            champ1_data = self.champion_synergies[champ1]
            if champ2 in champ1_data:
                return champ1_data[champ2].get("synergy_score", 0.5)

        # Check reverse direction in statistical synergies
        if champ2 in self.champion_synergies:
            champ2_data = self.champion_synergies[champ2]
            if champ1 in champ2_data:
                return champ2_data[champ1].get("synergy_score", 0.5)

        return None

    def compare_similar_champions(
        self,
        champion1: str,
        champion2: str,
        context: Optional[str] = None,
    ) -> dict:
        """Compare two similar champions to understand preference factors."""
        result = {
            "champion1": champion1,
            "champion2": champion2,
            "context": context,
            "archetype_comparison": {},
            "factors_favoring_1": [],
            "factors_favoring_2": [],
            "strategic_considerations": [],
        }

        # Archetype comparison
        arch1 = self.archetype_data.get(champion1, {})
        arch2 = self.archetype_data.get(champion2, {})

        result["archetype_comparison"] = {
            champion1: arch1,
            champion2: arch2,
        }

        # Analyze differences
        all_archetypes = set(arch1.keys()) | set(arch2.keys())
        for arch in all_archetypes:
            score1 = arch1.get(arch, 0)
            score2 = arch2.get(arch, 0)
            diff = score1 - score2

            if abs(diff) > 0.2:
                if diff > 0:
                    result["factors_favoring_1"].append(
                        f"Higher {arch} ({score1:.2f} vs {score2:.2f})"
                    )
                else:
                    result["factors_favoring_2"].append(
                        f"Higher {arch} ({score2:.2f} vs {score1:.2f})"
                    )

        # Strategic considerations (what our system CAN'T capture)
        result["strategic_considerations"] = [
            "Player comfort/recent practice",
            "Specific matchup considerations",
            "Team's practiced compositions",
            "Element of surprise (less common pick)",
            "Scrim results and recent form",
            "Playoff pressure (comfort over optimal)",
            "Denying the pick from enemy",
        ]

        return result

    def full_audit(self) -> AuditResult:
        """Run complete audit of all data."""
        result = AuditResult()

        # Audit archetypes
        result.archetype_issues = self.audit_archetypes()

        # Audit synergies
        result.synergy_issues = self.audit_synergies()

        # Calculate stats
        result.archetype_stats = {
            "total_champions": len(self.archetype_data),
            "issues_found": len(result.archetype_issues),
            "high_severity": len([i for i in result.archetype_issues if i.severity == "high"]),
            "medium_severity": len([i for i in result.archetype_issues if i.severity == "medium"]),
        }

        result.synergy_stats = {
            "total_synergies_checked": sum(
                len(c["primary"]) * len(c["partners"])
                for c in KNOWN_SYNERGIES.values()
            ),
            "issues_found": len(result.synergy_issues),
            "missing": len([i for i in result.synergy_issues if i.issue_type == "missing"]),
            "too_low": len([i for i in result.synergy_issues if i.issue_type == "too_low"]),
        }

        return result

    def generate_fixes(self, result: AuditResult) -> dict:
        """Generate fix recommendations as JSON patches."""
        fixes = {
            "archetype_fixes": {},
            "synergy_fixes": [],
        }

        # Group archetype fixes by champion
        for issue in result.archetype_issues:
            if issue.champion not in fixes["archetype_fixes"]:
                fixes["archetype_fixes"][issue.champion] = {
                    "current": issue.current,
                    "suggested": issue.suggestion,
                    "issues": [],
                }
            fixes["archetype_fixes"][issue.champion]["issues"].append(issue.issue_type)
            # Merge suggestions
            current_suggestion = fixes["archetype_fixes"][issue.champion]["suggested"]
            for k, v in issue.suggestion.items():
                if k not in current_suggestion or v > current_suggestion.get(k, 0):
                    current_suggestion[k] = v

        # Synergy fixes
        for issue in result.synergy_issues:
            fixes["synergy_fixes"].append({
                "champion1": issue.champion1,
                "champion2": issue.champion2,
                "current_score": issue.current_score,
                "suggested_score": issue.expected_min,
                "reason": issue.reason,
            })

        return fixes


def print_audit_results(result: AuditResult, verbose: bool = False):
    """Print formatted audit results."""
    print(f"\n{Colors.BOLD}{'='*70}{Colors.RESET}")
    print(f"{Colors.BOLD}ARCHETYPE & SYNERGY DATA AUDIT{Colors.RESET}")
    print(f"{'='*70}")

    # Archetype summary
    print(f"\n{Colors.CYAN}ARCHETYPE AUDIT{Colors.RESET}")
    print(f"  Champions in data: {result.archetype_stats['total_champions']}")
    print(f"  Issues found: {result.archetype_stats['issues_found']}")
    print(f"    {Colors.RED}High severity: {result.archetype_stats['high_severity']}{Colors.RESET}")
    print(f"    {Colors.YELLOW}Medium severity: {result.archetype_stats['medium_severity']}{Colors.RESET}")

    if result.archetype_issues:
        print(f"\n  {Colors.BOLD}Top Issues:{Colors.RESET}")
        # Group by champion
        by_champion = defaultdict(list)
        for issue in result.archetype_issues:
            by_champion[issue.champion].append(issue)

        for champ, issues in sorted(by_champion.items(), key=lambda x: -len(x[1]))[:15]:
            severity_color = Colors.RED if any(i.severity == "high" for i in issues) else Colors.YELLOW
            print(f"    {severity_color}{champ:<15}{Colors.RESET}: ", end="")

            current = issues[0].current
            if current:
                primary = max(current.items(), key=lambda x: x[1])
                print(f"current={primary[0]}({primary[1]:.1f})", end=" ")

            issue_types = set(i.issue_type for i in issues)
            print(f"issues={issue_types}")

            if verbose:
                for issue in issues:
                    print(f"      → Expected: {issue.expected}")
                    print(f"      → Suggestion: {issue.suggestion}")

    # Synergy summary
    print(f"\n{Colors.CYAN}SYNERGY AUDIT{Colors.RESET}")
    print(f"  Combos checked: {result.synergy_stats['total_synergies_checked']}")
    print(f"  Issues found: {result.synergy_stats['issues_found']}")
    print(f"    Missing: {result.synergy_stats['missing']}")
    print(f"    Too low: {result.synergy_stats['too_low']}")

    if result.synergy_issues:
        print(f"\n  {Colors.BOLD}Synergy Issues:{Colors.RESET}")
        for issue in result.synergy_issues[:20]:
            score_str = f"{issue.current_score:.2f}" if issue.current_score else "N/A"
            severity_color = Colors.RED if issue.severity == "high" else Colors.YELLOW
            print(f"    {severity_color}{issue.champion1} + {issue.champion2}{Colors.RESET}: "
                  f"score={score_str} (need {issue.expected_min:.2f}) - {issue.reason}")


def print_comparison(comparison: dict):
    """Print champion comparison results."""
    print(f"\n{Colors.BOLD}{'='*70}{Colors.RESET}")
    print(f"{Colors.BOLD}CHAMPION COMPARISON: {comparison['champion1']} vs {comparison['champion2']}{Colors.RESET}")
    print(f"{'='*70}")

    if comparison.get("context"):
        print(f"Context: {comparison['context']}")

    print(f"\n{Colors.CYAN}Archetype Comparison:{Colors.RESET}")
    for champ, archs in comparison["archetype_comparison"].items():
        print(f"  {champ}: {archs}")

    if comparison["factors_favoring_1"]:
        print(f"\n{Colors.GREEN}Factors favoring {comparison['champion1']}:{Colors.RESET}")
        for factor in comparison["factors_favoring_1"]:
            print(f"  • {factor}")

    if comparison["factors_favoring_2"]:
        print(f"\n{Colors.GREEN}Factors favoring {comparison['champion2']}:{Colors.RESET}")
        for factor in comparison["factors_favoring_2"]:
            print(f"  • {factor}")

    print(f"\n{Colors.YELLOW}Strategic factors our system CAN'T capture:{Colors.RESET}")
    for factor in comparison["strategic_considerations"]:
        print(f"  • {factor}")


def main():
    parser = argparse.ArgumentParser(
        description="Audit archetype and synergy data quality",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--champions", "-c", type=str,
                        help="Comma-separated list of champions to check")
    parser.add_argument("--compare", nargs=2, metavar=("CHAMP1", "CHAMP2"),
                        help="Compare two champions")
    parser.add_argument("--context", type=str,
                        help="Context for comparison (e.g., 'jungle', 'with Orianna')")
    parser.add_argument("--generate-fixes", "-g", action="store_true",
                        help="Generate fix recommendations as JSON")
    parser.add_argument("--apply-fixes", "-a", action="store_true",
                        help="Interactively apply fixes")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Show detailed output")
    parser.add_argument("--output", "-o", type=str,
                        help="Output file for fixes JSON")

    args = parser.parse_args()

    knowledge_dir = Path(__file__).parent.parent / "knowledge"
    auditor = ArchetypeSynergyAuditor(knowledge_dir)

    if args.compare:
        comparison = auditor.compare_similar_champions(
            args.compare[0],
            args.compare[1],
            context=args.context,
        )
        print_comparison(comparison)
        return

    # Run full audit
    result = auditor.full_audit()
    print_audit_results(result, verbose=args.verbose)

    if args.generate_fixes or args.output:
        fixes = auditor.generate_fixes(result)

        if args.output:
            with open(args.output, "w") as f:
                json.dump(fixes, f, indent=2)
            print(f"\nFixes written to: {args.output}")
        else:
            print(f"\n{Colors.BOLD}SUGGESTED FIXES:{Colors.RESET}")
            print(json.dumps(fixes, indent=2))

    if args.apply_fixes:
        fixes = auditor.generate_fixes(result)
        print(f"\n{Colors.BOLD}INTERACTIVE FIX MODE{Colors.RESET}")
        print("Review and apply fixes one by one.\n")

        # Load current archetype data
        arch_path = knowledge_dir / "archetype_counters.json"
        with open(arch_path) as f:
            arch_data = json.load(f)

        changes_made = False
        for champ, fix_data in fixes["archetype_fixes"].items():
            print(f"\n{Colors.CYAN}{champ}{Colors.RESET}")
            print(f"  Current:   {fix_data['current']}")
            print(f"  Suggested: {fix_data['suggested']}")
            print(f"  Issues:    {fix_data['issues']}")

            response = input("  Apply fix? [y/n/e(dit)/s(kip all)]: ").strip().lower()

            if response == 's':
                break
            elif response == 'y':
                arch_data["champion_archetypes"][champ] = fix_data["suggested"]
                changes_made = True
                print(f"  {Colors.GREEN}Applied!{Colors.RESET}")
            elif response == 'e':
                print(f"  Enter new values as JSON (e.g., {{'engage': 0.9, 'teamfight': 0.5}}): ")
                try:
                    new_value = json.loads(input("  > "))
                    arch_data["champion_archetypes"][champ] = new_value
                    changes_made = True
                    print(f"  {Colors.GREEN}Applied custom value!{Colors.RESET}")
                except json.JSONDecodeError:
                    print(f"  {Colors.RED}Invalid JSON, skipping{Colors.RESET}")

        if changes_made:
            save = input("\nSave changes to archetype_counters.json? [y/n]: ").strip().lower()
            if save == 'y':
                with open(arch_path, "w") as f:
                    json.dump(arch_data, f, indent=2)
                print(f"{Colors.GREEN}Changes saved!{Colors.RESET}")


if __name__ == "__main__":
    main()
