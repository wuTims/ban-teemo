#!/usr/bin/env python3
"""Analyze evaluation results to identify scoring system gaps.

This script reads JSON output from analyze_recommendations.py and produces
deeper analysis to understand WHY our recommendations are off.

Usage:
    uv run python scripts/analyze_eval_results.py outputs/evals/eval_recent25_*.json
    uv run python scripts/analyze_eval_results.py outputs/evals/*.json --combine
"""

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


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


def load_eval_files(paths: list[str]) -> dict:
    """Load and optionally combine multiple eval JSON files."""
    combined = {
        "games": [],
        "aggregate": {
            "games_analyzed": 0,
            "picks": {"hits": 0, "top3": 0, "total": 0},
            "bans": {"hits": 0, "top3": 0, "total": 0},
        }
    }

    for path in paths:
        with open(path) as f:
            data = json.load(f)
            combined["games"].extend(data["games"])
            combined["aggregate"]["games_analyzed"] += data["aggregate"]["games_analyzed"]

            # Handle both old format (picks/bans) and new format (primary_recommendations)
            if "picks" in data["aggregate"]:
                # Old format
                for key in ["picks", "bans"]:
                    for stat in ["hits", "top3", "total"]:
                        combined["aggregate"][key][stat] += data["aggregate"][key][stat]
            elif "primary_recommendations" in data["aggregate"]:
                # New format - extract picks/bans from primary_recommendations
                primary = data["aggregate"]["primary_recommendations"]
                picks = primary.get("picks", {})
                bans = primary.get("bans", {})
                combined["aggregate"]["picks"]["hits"] += picks.get("top5_hits", 0)
                combined["aggregate"]["picks"]["top3"] += picks.get("top3_hits", 0)
                combined["aggregate"]["picks"]["total"] += picks.get("total", 0)
                combined["aggregate"]["bans"]["hits"] += bans.get("top5_hits", 0)
                combined["aggregate"]["bans"]["top3"] += bans.get("top3_hits", 0)
                combined["aggregate"]["bans"]["total"] += bans.get("total", 0)

    # Recalculate percentages
    for key in ["picks", "bans"]:
        total = combined["aggregate"][key]["total"]
        if total > 0:
            combined["aggregate"][key]["hit_pct"] = round(
                combined["aggregate"][key]["hits"] / total * 100, 1
            )
            combined["aggregate"][key]["top3_pct"] = round(
                combined["aggregate"][key]["top3"] / total * 100, 1
            )

    return combined


def analyze_by_phase(data: dict) -> dict:
    """Analyze accuracy by draft phase."""
    phase_stats = defaultdict(lambda: {
        "picks": {"hits": 0, "top3": 0, "total": 0},
        "bans": {"hits": 0, "top3": 0, "total": 0},
    })

    for game in data["games"]:
        for action in game["actions"]:
            phase = action["phase"]
            action_type = action["action_type"]

            phase_stats[phase][f"{action_type}s"]["total"] += 1
            if action["was_in_recommendations"]:
                phase_stats[phase][f"{action_type}s"]["hits"] += 1
                if action["recommendation_rank"] and action["recommendation_rank"] <= 3:
                    phase_stats[phase][f"{action_type}s"]["top3"] += 1

    return dict(phase_stats)


def analyze_by_sequence(data: dict) -> dict:
    """Analyze accuracy by action sequence number (1-20)."""
    seq_stats = defaultdict(lambda: {"hits": 0, "total": 0, "misses": []})

    for game in data["games"]:
        for action in game["actions"]:
            seq = action["sequence"]
            seq_stats[seq]["total"] += 1
            if action["was_in_recommendations"]:
                seq_stats[seq]["hits"] += 1
            else:
                seq_stats[seq]["misses"].append(action["actual_champion"])

    return dict(seq_stats)


def analyze_miss_patterns(data: dict) -> dict:
    """Analyze patterns in misses - what do we consistently miss?"""
    miss_analysis = {
        "by_champion": defaultdict(lambda: {"count": 0, "contexts": []}),
        "by_action_type": {"pick": 0, "ban": 0},
        "by_team_side": {"blue": 0, "red": 0},
        "first_pick_misses": [],
        "total_misses": 0,
    }

    for game in data["games"]:
        for action in game["actions"]:
            if not action["was_in_recommendations"]:
                miss_analysis["total_misses"] += 1
                miss_analysis["by_action_type"][action["action_type"]] += 1
                miss_analysis["by_team_side"][action["team_side"]] += 1

                champ = action["actual_champion"]
                miss_analysis["by_champion"][champ]["count"] += 1
                miss_analysis["by_champion"][champ]["contexts"].append({
                    "phase": action["phase"],
                    "sequence": action["sequence"],
                    "our_picks": action["our_picks"],
                    "enemy_picks": action["enemy_picks"],
                    "top_3_recommended": [r["champion"] for r in action["top_recommended"][:3]],
                })

                # Track first picks specifically (seq 7-8 are first picks after bans)
                if action["sequence"] in [7, 8] and action["action_type"] == "pick":
                    miss_analysis["first_pick_misses"].append({
                        "champion": champ,
                        "game_id": game["game_id"],
                        "team_side": action["team_side"],
                        "recommended": [r["champion"] for r in action["top_recommended"][:5]],
                    })

    # Convert defaultdict
    miss_analysis["by_champion"] = dict(miss_analysis["by_champion"])
    return miss_analysis


def analyze_component_gaps(data: dict, action_type: str = "pick") -> dict:
    """Analyze scoring component patterns for hits vs misses by action type."""
    component_stats = {
        "hits": defaultdict(list),
        "misses_top_rec": defaultdict(list),  # Components of our #1 when we miss
    }

    for game in data["games"]:
        for action in game["actions"]:
            if action["action_type"] != action_type:
                continue

            if not action["top_recommended"]:
                continue

            top_rec = action["top_recommended"][0]
            components = top_rec.get("components", {})

            if action["was_in_recommendations"] and action["recommendation_rank"] == 1:
                # We got it right as #1
                for comp, val in components.items():
                    if isinstance(val, (int, float)):
                        component_stats["hits"][comp].append(val)
            elif not action["was_in_recommendations"]:
                # We missed entirely
                for comp, val in components.items():
                    if isinstance(val, (int, float)):
                        component_stats["misses_top_rec"][comp].append(val)

    # Calculate averages
    result = {"hits_avg": {}, "misses_top_rec_avg": {}, "delta": {}}
    for comp in component_stats["hits"]:
        hit_vals = component_stats["hits"][comp]
        miss_vals = component_stats["misses_top_rec"].get(comp, [])

        hit_avg = sum(hit_vals) / len(hit_vals) if hit_vals else 0
        miss_avg = sum(miss_vals) / len(miss_vals) if miss_vals else 0

        result["hits_avg"][comp] = round(hit_avg, 3)
        result["misses_top_rec_avg"][comp] = round(miss_avg, 3)
        result["delta"][comp] = round(hit_avg - miss_avg, 3)

    return result


def analyze_proficiency_source(data: dict) -> dict:
    """Analyze if proficiency source affects accuracy."""
    source_stats = defaultdict(lambda: {"hits": 0, "total": 0})

    for game in data["games"]:
        for action in game["actions"]:
            if action["action_type"] != "pick":
                continue
            if not action["top_recommended"]:
                continue

            # Check the top recommendation's proficiency source
            top_rec = action["top_recommended"][0]
            source = top_rec.get("proficiency_source", "unknown")

            if action["was_in_recommendations"] and action["recommendation_rank"] == 1:
                source_stats[source]["hits"] += 1
            source_stats[source]["total"] += 1

    return dict(source_stats)


def analyze_score_distribution(data: dict) -> dict:
    """Analyze score distributions - are scores clustered or spread?"""
    score_gaps = {
        "top1_to_top2": [],
        "top1_to_top5": [],
        "hit_scores": [],
        "miss_top1_scores": [],
    }

    for game in data["games"]:
        for action in game["actions"]:
            if action["action_type"] != "pick":
                continue
            if len(action["top_recommended"]) < 2:
                continue

            scores = [r.get("score", 0) for r in action["top_recommended"][:5]]
            if scores[0] > 0:
                score_gaps["top1_to_top2"].append(scores[0] - scores[1])
                if len(scores) >= 5:
                    score_gaps["top1_to_top5"].append(scores[0] - scores[4])

            if action["was_in_recommendations"] and action["recommendation_rank"] == 1:
                score_gaps["hit_scores"].append(scores[0])
            elif not action["was_in_recommendations"]:
                score_gaps["miss_top1_scores"].append(scores[0])

    result = {}
    for key, vals in score_gaps.items():
        if vals:
            result[key] = {
                "avg": round(sum(vals) / len(vals), 3),
                "min": round(min(vals), 3),
                "max": round(max(vals), 3),
            }
    return result


def print_analysis(data: dict, analysis: dict):
    """Print formatted analysis results."""
    print(f"\n{Colors.BOLD}{'='*70}{Colors.RESET}")
    print(f"{Colors.BOLD}RECOMMENDATION SYSTEM EVALUATION ANALYSIS{Colors.RESET}")
    print(f"{Colors.BOLD}{'='*70}{Colors.RESET}")

    agg = data["aggregate"]
    print(f"\n{Colors.CYAN}Dataset: {agg['games_analyzed']} games{Colors.RESET}")
    print(f"  Picks: {agg['picks']['hits']}/{agg['picks']['total']} in recs "
          f"({agg['picks'].get('hit_pct', 0)}%), "
          f"{agg['picks']['top3']}/{agg['picks']['total']} in top 3 "
          f"({agg['picks'].get('top3_pct', 0)}%)")
    print(f"  Bans:  {agg['bans']['hits']}/{agg['bans']['total']} in recs "
          f"({agg['bans'].get('hit_pct', 0)}%), "
          f"{agg['bans']['top3']}/{agg['bans']['total']} in top 3 "
          f"({agg['bans'].get('top3_pct', 0)}%)")

    # Phase analysis
    print(f"\n{Colors.BOLD}ACCURACY BY PHASE{Colors.RESET}")
    print("-" * 50)
    for phase in ["BAN_PHASE_1", "PICK_PHASE_1", "BAN_PHASE_2", "PICK_PHASE_2"]:
        if phase in analysis["by_phase"]:
            stats = analysis["by_phase"][phase]
            pick_pct = (stats["picks"]["hits"] / stats["picks"]["total"] * 100) if stats["picks"]["total"] else 0
            ban_pct = (stats["bans"]["hits"] / stats["bans"]["total"] * 100) if stats["bans"]["total"] else 0

            if "PICK" in phase:
                print(f"  {phase}: {stats['picks']['hits']}/{stats['picks']['total']} picks ({pick_pct:.1f}%)")
            else:
                print(f"  {phase}: {stats['bans']['hits']}/{stats['bans']['total']} bans ({ban_pct:.1f}%)")

    # Sequence analysis
    print(f"\n{Colors.BOLD}ACCURACY BY SEQUENCE (worst positions){Colors.RESET}")
    print("-" * 50)
    seq_sorted = sorted(
        analysis["by_sequence"].items(),
        key=lambda x: x[1]["hits"] / x[1]["total"] if x[1]["total"] else 1
    )
    for seq, stats in seq_sorted[:5]:
        pct = stats["hits"] / stats["total"] * 100 if stats["total"] else 0
        top_misses = ", ".join(list(set(stats["misses"]))[:3])
        print(f"  Seq {seq:2d}: {stats['hits']}/{stats['total']} ({pct:.1f}%) - top misses: {top_misses}")

    # Miss patterns
    print(f"\n{Colors.BOLD}MOST MISSED CHAMPIONS{Colors.RESET}")
    print("-" * 50)
    miss_sorted = sorted(
        analysis["miss_patterns"]["by_champion"].items(),
        key=lambda x: -x[1]["count"]
    )[:15]
    for champ, info in miss_sorted:
        phases = [c["phase"] for c in info["contexts"]]
        phase_dist = {p: phases.count(p) for p in set(phases)}
        phase_str = ", ".join(f"{p.replace('_PHASE_', '')}:{n}" for p, n in phase_dist.items())
        print(f"  {champ:<15} {info['count']:3d} misses  ({phase_str})")

    # First pick analysis
    print(f"\n{Colors.BOLD}FIRST PICK ANALYSIS{Colors.RESET}")
    print("-" * 50)
    first_picks = analysis["miss_patterns"]["first_pick_misses"]
    if first_picks:
        first_pick_champs = [fp["champion"] for fp in first_picks]
        from collections import Counter
        fp_counts = Counter(first_pick_champs).most_common(10)
        print(f"  First pick misses: {len(first_picks)} total")
        print(f"  Most missed first picks: {', '.join(f'{c}({n})' for c, n in fp_counts[:5])}")

    def print_component_gaps(title: str, comps: dict, max_items: int = 8):
        print(f"\n{Colors.BOLD}{title}{Colors.RESET}")
        print("-" * 50)
        print("  When we hit #1 vs when we miss entirely (our #1 rec's components):")
        if not comps.get("delta"):
            print("  (no component data)")
            return

        items = []
        for comp, delta in comps["delta"].items():
            hit = comps["hits_avg"].get(comp, 0)
            miss = comps["misses_top_rec_avg"].get(comp, 0)
            items.append((comp, hit, miss, delta))

        items.sort(key=lambda x: abs(x[3]), reverse=True)
        for comp, hit, miss, delta in items[:max_items]:
            indicator = Colors.GREEN if delta > 0.02 else (Colors.RED if delta < -0.02 else "")
            print(f"  {comp:<18}: hit={hit:.3f}  miss={miss:.3f}  delta={indicator}{delta:+.3f}{Colors.RESET}")

    # Component analysis (picks + bans)
    print_component_gaps("COMPONENT ANALYSIS (picks)", analysis.get("component_gaps", {}))
    print_component_gaps("COMPONENT ANALYSIS (bans)", analysis.get("ban_component_gaps", {}))

    # Score distribution
    print(f"\n{Colors.BOLD}SCORE DISTRIBUTION{Colors.RESET}")
    print("-" * 50)
    scores = analysis["score_distribution"]
    if "top1_to_top2" in scores:
        print(f"  Score gap #1 to #2: avg={scores['top1_to_top2']['avg']:.3f}")
    if "top1_to_top5" in scores:
        print(f"  Score gap #1 to #5: avg={scores['top1_to_top5']['avg']:.3f}")
    if "hit_scores" in scores:
        print(f"  When we hit #1: avg score={scores['hit_scores']['avg']:.3f}")
    if "miss_top1_scores" in scores:
        print(f"  When we miss: our #1 avg score={scores['miss_top1_scores']['avg']:.3f}")

    # Proficiency source
    print(f"\n{Colors.BOLD}PROFICIENCY SOURCE IMPACT{Colors.RESET}")
    print("-" * 50)
    for source, stats in analysis["proficiency_source"].items():
        pct = stats["hits"] / stats["total"] * 100 if stats["total"] else 0
        print(f"  {source:<15}: {stats['hits']}/{stats['total']} #1 hits ({pct:.1f}%)")

    # Key insights
    print(f"\n{Colors.BOLD}KEY INSIGHTS{Colors.RESET}")
    print("-" * 50)

    # Identify worst phase
    worst_phase = None
    worst_pct = 100
    for phase, stats in analysis["by_phase"].items():
        key = "picks" if "PICK" in phase else "bans"
        if stats[key]["total"] > 0:
            pct = stats[key]["hits"] / stats[key]["total"] * 100
            if pct < worst_pct:
                worst_pct = pct
                worst_phase = phase

    if worst_phase:
        print(f"  - Worst phase: {worst_phase} ({worst_pct:.1f}% accuracy)")

    # Identify component issues (picks)
    comps = analysis.get("component_gaps", {})
    if comps.get("delta"):
        worst_comp = min(comps["delta"].items(), key=lambda x: x[1])
        best_comp = max(comps["delta"].items(), key=lambda x: x[1])
        print(f"  - Weakest pick component signal: {worst_comp[0]} (delta={worst_comp[1]:+.3f})")
        print(f"  - Strongest pick component signal: {best_comp[0]} (delta={best_comp[1]:+.3f})")

    # First pick issue
    if first_picks:
        print(f"  - First pick accuracy is a problem ({len(first_picks)} misses)")


def main():
    parser = argparse.ArgumentParser(description="Analyze evaluation results")
    parser.add_argument("files", nargs="+", help="JSON eval file(s) to analyze")
    parser.add_argument("--combine", action="store_true",
                        help="Combine multiple files into single analysis")
    parser.add_argument("--json-out", "-o", type=str,
                        help="Export analysis to JSON file")

    args = parser.parse_args()

    # Load data
    data = load_eval_files(args.files)

    # Run analyses
    analysis = {
        "by_phase": analyze_by_phase(data),
        "by_sequence": analyze_by_sequence(data),
        "miss_patterns": analyze_miss_patterns(data),
        "component_gaps": analyze_component_gaps(data, action_type="pick"),
        "ban_component_gaps": analyze_component_gaps(data, action_type="ban"),
        "proficiency_source": analyze_proficiency_source(data),
        "score_distribution": analyze_score_distribution(data),
    }

    # Print results
    print_analysis(data, analysis)

    # Export if requested
    if args.json_out:
        # Make analysis JSON serializable
        output = {
            "summary": data["aggregate"],
            "analysis": analysis,
        }
        # Convert defaultdicts and clean up
        with open(args.json_out, "w") as f:
            json.dump(output, f, indent=2, default=str)
        print(f"\nAnalysis exported to: {args.json_out}")


if __name__ == "__main__":
    main()
