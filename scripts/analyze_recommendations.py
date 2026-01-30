#!/usr/bin/env python3
"""Analyze recommendation accuracy against historical game data.

This script simulates what the frontend replay component does,
stepping through historical drafts and comparing our recommendations
to actual picks/bans to identify scoring gaps.

Usage:
    # Analyze a specific series
    uv run python scripts/analyze_recommendations.py --series <series_id>

    # Analyze a specific game
    uv run python scripts/analyze_recommendations.py --series <series_id> --game 1

    # Analyze recent series (default: 5)
    uv run python scripts/analyze_recommendations.py --recent 10

    # Show verbose output with full scoring details
    uv run python scripts/analyze_recommendations.py --series <series_id> --verbose

    # Only show misses (actual pick not in our recommendations)
    uv run python scripts/analyze_recommendations.py --series <series_id> --misses-only
"""

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend" / "src"))

from ban_teemo.models.draft import DraftAction, DraftPhase, DraftState
from ban_teemo.models.team import Player, TeamContext
from ban_teemo.repositories.draft_repository import DraftRepository
from ban_teemo.services.draft_service import DraftService


# ANSI colors for terminal output
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


@dataclass
class ActionAnalysis:
    """Analysis of a single draft action."""
    sequence: int
    action_type: str  # "pick" or "ban"
    team_side: str
    actual_champion: str
    was_in_recommendations: bool
    recommendation_rank: Optional[int]
    actual_score: Optional[float]
    top_recommended: list[dict]  # Top 5 with scores
    phase: str
    our_picks: list[str]
    enemy_picks: list[str]
    # Role-grouped tracking (for picks only)
    was_in_role_grouped: bool = False  # In top 2 for any role
    role_grouped_role: Optional[str] = None  # Which role it appeared in
    role_grouped_rank: Optional[int] = None  # Rank within that role (1 or 2)


@dataclass
class GameAnalysis:
    """Analysis results for a single game."""
    game_id: str
    series_id: str
    game_number: int
    blue_team: str
    red_team: str
    actions: list[ActionAnalysis] = field(default_factory=list)

    @property
    def pick_accuracy(self) -> tuple[int, int, int]:
        """Returns (hits, top3, total) for picks."""
        picks = [a for a in self.actions if a.action_type == "pick"]
        hits = sum(1 for a in picks if a.was_in_recommendations)
        top3 = sum(1 for a in picks if a.recommendation_rank and a.recommendation_rank <= 3)
        return hits, top3, len(picks)

    @property
    def ban_accuracy(self) -> tuple[int, int, int]:
        """Returns (hits, top3, total) for bans."""
        bans = [a for a in self.actions if a.action_type == "ban"]
        hits = sum(1 for a in bans if a.was_in_recommendations)
        top3 = sum(1 for a in bans if a.recommendation_rank and a.recommendation_rank <= 3)
        return hits, top3, len(bans)

    @property
    def role_grouped_accuracy(self) -> tuple[int, int, int]:
        """Returns (role_grouped_hits, additional_hits, total) for picks.

        role_grouped_hits: Picks that were in top 2 for their role
        additional_hits: Picks that role-grouped caught but primary top 5 missed
        total: Total number of picks
        """
        picks = [a for a in self.actions if a.action_type == "pick"]
        role_grouped_hits = sum(1 for a in picks if a.was_in_role_grouped)
        additional_hits = sum(
            1 for a in picks
            if a.was_in_role_grouped and not a.was_in_recommendations
        )
        return role_grouped_hits, additional_hits, len(picks)


def get_role_grouped_recommendations(picks: list[dict], top_n: int = 2) -> dict[str, list[dict]]:
    """Group recommendations by role and return top N per role.

    Args:
        picks: List of pick recommendation dicts with 'role' field
        top_n: Number of recommendations per role (default 2)

    Returns:
        Dict mapping role -> list of top N recommendations for that role
    """
    ROLES = ["top", "jungle", "mid", "bot", "support"]
    role_grouped: dict[str, list[dict]] = {role: [] for role in ROLES}

    for rec in picks:
        role = rec.get("role")
        if role and role.lower() in ROLES:
            role_key = role.lower()
            if len(role_grouped[role_key]) < top_n:
                role_grouped[role_key].append(rec)

    return role_grouped


def check_in_role_grouped(
    champion_name: str,
    role_grouped: dict[str, list[dict]]
) -> tuple[bool, Optional[str], Optional[int]]:
    """Check if a champion is in the role-grouped recommendations.

    Returns:
        (was_found, role, rank_within_role)
    """
    for role, recs in role_grouped.items():
        for i, rec in enumerate(recs):
            if rec.get("champion") == champion_name:
                return True, role, i + 1
    return False, None, None


def load_game_data(repo: DraftRepository, series_id: str, game_number: int) -> tuple[DraftState, list[DraftAction]]:
    """Load game data and build initial draft state."""
    game_info = repo.get_game_info(series_id, game_number)
    if not game_info:
        raise ValueError(f"Game not found: {series_id} game {game_number}")

    game_id = game_info["game_id"]

    # Get team contexts
    blue_team_info = repo.get_team_for_game_side(game_id, "blue")
    red_team_info = repo.get_team_for_game_side(game_id, "red")

    blue_players = repo.get_players_for_game_by_side(game_id, "blue")
    red_players = repo.get_players_for_game_by_side(game_id, "red")

    blue_team = TeamContext(
        id=blue_team_info["id"],
        name=blue_team_info["name"],
        side="blue",
        players=[Player(id=p["id"], name=p["name"], role=p["role"]) for p in blue_players],
    )

    red_team = TeamContext(
        id=red_team_info["id"],
        name=red_team_info["name"],
        side="red",
        players=[Player(id=p["id"], name=p["name"], role=p["role"]) for p in red_players],
    )

    # Get draft actions
    raw_actions = repo.get_draft_actions(game_id)
    actions = [
        DraftAction(
            sequence=int(a["sequence"]),
            action_type=a["action_type"],
            team_side=a["team_side"],
            champion_id=a["champion_id"],
            champion_name=a["champion_name"],
        )
        for a in raw_actions
    ]

    # Build initial state
    initial_state = DraftState(
        game_id=game_id,
        series_id=series_id,
        game_number=game_number,
        patch_version=game_info.get("patch_version", "unknown"),
        match_date=game_info.get("match_date"),
        blue_team=blue_team,
        red_team=red_team,
        actions=[],
        current_phase=DraftPhase.BAN_PHASE_1,
        next_team="blue",
        next_action="ban",
    )

    return initial_state, actions


def analyze_game(
    service: DraftService,
    initial_state: DraftState,
    actions: list[DraftAction],
    verbose: bool = False,
    misses_only: bool = False,
) -> GameAnalysis:
    """Step through a game and analyze our recommendations vs actual picks/bans."""

    analysis = GameAnalysis(
        game_id=initial_state.game_id,
        series_id=initial_state.series_id,
        game_number=initial_state.game_number,
        blue_team=initial_state.blue_team.name,
        red_team=initial_state.red_team.name,
    )

    for i, action in enumerate(actions):
        # Build state BEFORE this action (so we get recommendations for what should happen)
        current_state = service.build_draft_state_at(initial_state, actions, i)

        if current_state.next_team is None:
            continue

        # Get recommendations for the team that's about to act
        recommendations = service.get_recommendations(current_state, for_team=current_state.next_team)

        # Determine our picks and enemy picks from perspective of acting team
        if current_state.next_team == "blue":
            our_picks = current_state.blue_picks
            enemy_picks = current_state.red_picks
        else:
            our_picks = current_state.red_picks
            enemy_picks = current_state.blue_picks

        # Check if actual action was in recommendations
        was_recommended = False
        rank = None
        actual_score = None
        top_recs = []

        # Role-grouped tracking (picks only)
        was_in_role_grouped = False
        role_grouped_role = None
        role_grouped_rank = None

        if action.action_type == "pick" and recommendations.picks:
            for j, rec in enumerate(recommendations.picks):
                top_recs.append({
                    "champion": rec.champion_name,
                    "score": rec.score,
                    "base_score": rec.base_score,
                    "synergy_multiplier": rec.synergy_multiplier,
                    "components": rec.components,
                    "role": rec.suggested_role,
                    "reasons": rec.reasons,
                    "proficiency_source": rec.proficiency_source,
                    "proficiency_player": rec.proficiency_player,
                })
                if rec.champion_name == action.champion_name:
                    was_recommended = True
                    rank = j + 1
                    actual_score = rec.score

            # Check role-grouped (top 2 per role)
            role_grouped = get_role_grouped_recommendations(top_recs, top_n=2)
            was_in_role_grouped, role_grouped_role, role_grouped_rank = check_in_role_grouped(
                action.champion_name, role_grouped
            )
        elif action.action_type == "ban" and recommendations.bans:
            for j, rec in enumerate(recommendations.bans):
                top_recs.append({
                    "champion": rec.champion_name,
                    "priority": rec.priority,
                    "target_player": rec.target_player,
                    "reasons": rec.reasons,
                    "components": rec.components,
                })
                if rec.champion_name == action.champion_name:
                    was_recommended = True
                    rank = j + 1
                    actual_score = rec.priority

        action_analysis = ActionAnalysis(
            sequence=action.sequence,
            action_type=action.action_type,
            team_side=action.team_side,
            actual_champion=action.champion_name,
            was_in_recommendations=was_recommended,
            recommendation_rank=rank,
            actual_score=actual_score,
            top_recommended=top_recs,
            phase=current_state.current_phase.value,
            our_picks=our_picks,
            enemy_picks=enemy_picks,
            was_in_role_grouped=was_in_role_grouped,
            role_grouped_role=role_grouped_role,
            role_grouped_rank=role_grouped_rank,
        )

        analysis.actions.append(action_analysis)

        # Print action analysis if verbose or if it's a miss
        should_print = verbose or (misses_only and not was_recommended)
        if should_print:
            print_action_analysis(action_analysis, verbose)

    return analysis


def print_action_analysis(action: ActionAnalysis, verbose: bool = False):
    """Print detailed analysis for a single action."""
    # Status indicator
    if action.was_in_recommendations:
        if action.recommendation_rank and action.recommendation_rank <= 3:
            status = f"{Colors.GREEN}✓ #{action.recommendation_rank}{Colors.RESET}"
        else:
            status = f"{Colors.YELLOW}~ #{action.recommendation_rank}{Colors.RESET}"
    else:
        status = f"{Colors.RED}✗ MISS{Colors.RESET}"

    team_color = Colors.BLUE if action.team_side == "blue" else Colors.RED

    print(f"\n{Colors.BOLD}[{action.sequence:02d}] {action.phase}{Colors.RESET}")
    print(f"  {team_color}{action.team_side.upper()}{Colors.RESET} {action.action_type}: "
          f"{Colors.BOLD}{action.actual_champion}{Colors.RESET} {status}")

    if action.actual_score is not None:
        print(f"  Score: {action.actual_score:.3f}")

    print(f"  {Colors.DIM}Context: our_picks={action.our_picks}, enemy_picks={action.enemy_picks}{Colors.RESET}")

    # Show top recommendations
    print(f"  {Colors.CYAN}Our recommendations:{Colors.RESET}")
    for i, rec in enumerate(action.top_recommended[:5]):
        marker = "→" if rec["champion"] == action.actual_champion else " "

        if action.action_type == "pick":
            score = rec.get("score", 0)
            base = rec.get("base_score", 0)
            syn = rec.get("synergy_multiplier", 1.0)
            role = rec.get("role", "?")
            print(f"    {marker} {i+1}. {rec['champion']:<15} score={score:.3f} "
                  f"(base={base:.3f} × syn={syn:.2f}) role={role}")

            if verbose and rec.get("components"):
                comps = rec["components"]
                print(f"       Components: meta={comps.get('meta', 0):.2f} "
                      f"prof={comps.get('proficiency', 0):.2f} "
                      f"match={comps.get('matchup', 0):.2f} "
                      f"counter={comps.get('counter', 0):.2f} "
                      f"arch={comps.get('archetype', 0):.2f}")
                if rec.get("proficiency_source"):
                    print(f"       Proficiency: {rec['proficiency_source']} "
                          f"(player: {rec.get('proficiency_player', 'N/A')})")
                if rec.get("reasons"):
                    print(f"       Reasons: {', '.join(rec['reasons'][:3])}")
        else:  # ban
            priority = rec.get("priority", 0)
            target = rec.get("target_player", "N/A")
            print(f"    {marker} {i+1}. {rec['champion']:<15} priority={priority:.3f} target={target}")
            if verbose and rec.get("reasons"):
                print(f"       Reasons: {', '.join(rec['reasons'][:3])}")


def print_game_summary(analysis: GameAnalysis):
    """Print summary statistics for a game."""
    pick_hits, pick_top3, pick_total = analysis.pick_accuracy
    ban_hits, ban_top3, ban_total = analysis.ban_accuracy
    role_grouped_hits, additional_hits, _ = analysis.role_grouped_accuracy

    print(f"\n{Colors.BOLD}{'='*60}{Colors.RESET}")
    print(f"{Colors.BOLD}Game Summary: {analysis.blue_team} vs {analysis.red_team} (Game {analysis.game_number}){Colors.RESET}")
    print(f"{'='*60}")

    pick_pct = (pick_hits / pick_total * 100) if pick_total else 0
    pick_top3_pct = (pick_top3 / pick_total * 100) if pick_total else 0
    ban_pct = (ban_hits / ban_total * 100) if ban_total else 0
    ban_top3_pct = (ban_top3 / ban_total * 100) if ban_total else 0
    role_grouped_pct = (role_grouped_hits / pick_total * 100) if pick_total else 0

    print(f"  {Colors.BOLD}Primary Recommendations (top 5):{Colors.RESET}")
    print(f"    Picks: {pick_hits}/{pick_total} in top 5 ({pick_pct:.1f}%), "
          f"{pick_top3}/{pick_total} in top 3 ({pick_top3_pct:.1f}%)")
    print(f"    Bans:  {ban_hits}/{ban_total} in top 5 ({ban_pct:.1f}%), "
          f"{ban_top3}/{ban_total} in top 3 ({ban_top3_pct:.1f}%)")

    print(f"  {Colors.BOLD}Supplemental (top 2 per role):{Colors.RESET}")
    print(f"    Picks: {role_grouped_hits}/{pick_total} in role-grouped ({role_grouped_pct:.1f}%)")
    if additional_hits > 0:
        print(f"    {Colors.GREEN}+{additional_hits} additional hits{Colors.RESET} (missed by primary, caught by role-grouped)")

    # Show misses
    misses = [a for a in analysis.actions if not a.was_in_recommendations]
    if misses:
        print(f"\n  {Colors.RED}Misses ({len(misses)}):{Colors.RESET}")
        for m in misses:
            team_color = Colors.BLUE if m.team_side == "blue" else Colors.RED
            role_note = ""
            if m.action_type == "pick" and m.was_in_role_grouped:
                role_note = f" {Colors.CYAN}[in role-grouped: {m.role_grouped_role} #{m.role_grouped_rank}]{Colors.RESET}"
            print(f"    [{m.sequence:02d}] {team_color}{m.team_side}{Colors.RESET} "
                  f"{m.action_type}: {m.actual_champion}{role_note}")


def print_series_summary(analyses: list[GameAnalysis]):
    """Print aggregate summary across all games."""
    total_pick_hits = sum(a.pick_accuracy[0] for a in analyses)
    total_pick_top3 = sum(a.pick_accuracy[1] for a in analyses)
    total_picks = sum(a.pick_accuracy[2] for a in analyses)

    total_ban_hits = sum(a.ban_accuracy[0] for a in analyses)
    total_ban_top3 = sum(a.ban_accuracy[1] for a in analyses)
    total_bans = sum(a.ban_accuracy[2] for a in analyses)

    # Role-grouped metrics
    total_role_grouped_hits = sum(a.role_grouped_accuracy[0] for a in analyses)
    total_additional_hits = sum(a.role_grouped_accuracy[1] for a in analyses)

    print(f"\n{Colors.BOLD}{'='*60}{Colors.RESET}")
    print(f"{Colors.BOLD}AGGREGATE SUMMARY ({len(analyses)} games){Colors.RESET}")
    print(f"{'='*60}")

    pick_pct = (total_pick_hits / total_picks * 100) if total_picks else 0
    pick_top3_pct = (total_pick_top3 / total_picks * 100) if total_picks else 0
    ban_pct = (total_ban_hits / total_bans * 100) if total_bans else 0
    ban_top3_pct = (total_ban_top3 / total_bans * 100) if total_bans else 0
    role_grouped_pct = (total_role_grouped_hits / total_picks * 100) if total_picks else 0

    print(f"  {Colors.BOLD}Primary Recommendations (top 5):{Colors.RESET}")
    print(f"    Picks: {total_pick_hits}/{total_picks} in top 5 ({pick_pct:.1f}%)")
    print(f"           {total_pick_top3}/{total_picks} in top 3 ({pick_top3_pct:.1f}%)")
    print(f"    Bans:  {total_ban_hits}/{total_bans} in top 5 ({ban_pct:.1f}%)")
    print(f"           {total_ban_top3}/{total_bans} in top 3 ({ban_top3_pct:.1f}%)")

    print(f"  {Colors.BOLD}Supplemental (top 2 per role):{Colors.RESET}")
    print(f"    Picks: {total_role_grouped_hits}/{total_picks} in role-grouped ({role_grouped_pct:.1f}%)")
    if total_additional_hits > 0:
        print(f"    {Colors.GREEN}+{total_additional_hits} additional hits{Colors.RESET} "
              f"(missed by primary, caught by role-grouped)")
        delta_pct = (total_additional_hits / total_picks * 100) if total_picks else 0
        print(f"    Role-grouped vs Primary delta: +{delta_pct:.1f}% additional coverage")

    # Count total misses
    all_misses = []
    for analysis in analyses:
        misses = [a for a in analysis.actions if not a.was_in_recommendations]
        all_misses.extend([(analysis, m) for m in misses])

    if all_misses:
        print(f"\n  {Colors.RED}Total Misses: {len(all_misses)}{Colors.RESET}")

        # Group misses by champion to find patterns
        miss_by_champ: dict[str, int] = {}
        role_grouped_saves: dict[str, int] = {}
        for _, m in all_misses:
            miss_by_champ[m.actual_champion] = miss_by_champ.get(m.actual_champion, 0) + 1
            if m.action_type == "pick" and m.was_in_role_grouped:
                role_grouped_saves[m.actual_champion] = role_grouped_saves.get(m.actual_champion, 0) + 1

        if miss_by_champ:
            sorted_misses = sorted(miss_by_champ.items(), key=lambda x: -x[1])[:10]
            print(f"  Most missed champions: {', '.join(f'{c}({n})' for c, n in sorted_misses)}")

        if role_grouped_saves:
            sorted_saves = sorted(role_grouped_saves.items(), key=lambda x: -x[1])[:5]
            print(f"  {Colors.CYAN}Role-grouped catches: {', '.join(f'{c}({n})' for c, n in sorted_saves)}{Colors.RESET}")


def export_to_json(analyses: list[GameAnalysis], output_path: str):
    """Export analysis results to JSON for programmatic analysis."""
    results = {
        "games": [],
        "aggregate": {},
    }

    for analysis in analyses:
        role_grouped_hits, additional_hits, _ = analysis.role_grouped_accuracy
        game_data = {
            "game_id": analysis.game_id,
            "series_id": analysis.series_id,
            "game_number": analysis.game_number,
            "blue_team": analysis.blue_team,
            "red_team": analysis.red_team,
            "pick_accuracy": {
                "hits": analysis.pick_accuracy[0],
                "top3": analysis.pick_accuracy[1],
                "total": analysis.pick_accuracy[2],
            },
            "ban_accuracy": {
                "hits": analysis.ban_accuracy[0],
                "top3": analysis.ban_accuracy[1],
                "total": analysis.ban_accuracy[2],
            },
            "role_grouped_accuracy": {
                "hits": role_grouped_hits,
                "additional_hits": additional_hits,
                "total": analysis.role_grouped_accuracy[2],
            },
            "actions": [],
        }

        for action in analysis.actions:
            action_data = {
                "sequence": action.sequence,
                "action_type": action.action_type,
                "team_side": action.team_side,
                "actual_champion": action.actual_champion,
                "was_in_recommendations": action.was_in_recommendations,
                "recommendation_rank": action.recommendation_rank,
                "actual_score": action.actual_score,
                "top_recommended": action.top_recommended,
                "phase": action.phase,
                "our_picks": action.our_picks,
                "enemy_picks": action.enemy_picks,
                # Role-grouped fields (picks only)
                "was_in_role_grouped": action.was_in_role_grouped,
                "role_grouped_role": action.role_grouped_role,
                "role_grouped_rank": action.role_grouped_rank,
            }
            game_data["actions"].append(action_data)

        results["games"].append(game_data)

    # Add aggregate stats
    total_pick_hits = sum(a.pick_accuracy[0] for a in analyses)
    total_pick_top3 = sum(a.pick_accuracy[1] for a in analyses)
    total_picks = sum(a.pick_accuracy[2] for a in analyses)
    total_ban_hits = sum(a.ban_accuracy[0] for a in analyses)
    total_ban_top3 = sum(a.ban_accuracy[1] for a in analyses)
    total_bans = sum(a.ban_accuracy[2] for a in analyses)

    # Role-grouped aggregate stats
    total_role_grouped_hits = sum(a.role_grouped_accuracy[0] for a in analyses)
    total_additional_hits = sum(a.role_grouped_accuracy[1] for a in analyses)

    results["aggregate"] = {
        "games_analyzed": len(analyses),
        "primary_recommendations": {
            "description": "Primary top 5 recommendations - main recommendation view",
            "picks": {
                "top5_hits": total_pick_hits,
                "top3_hits": total_pick_top3,
                "total": total_picks,
                "top5_accuracy": round(total_pick_hits / total_picks * 100, 1) if total_picks else 0,
                "top3_accuracy": round(total_pick_top3 / total_picks * 100, 1) if total_picks else 0,
            },
            "bans": {
                "top5_hits": total_ban_hits,
                "top3_hits": total_ban_top3,
                "total": total_bans,
                "top5_accuracy": round(total_ban_hits / total_bans * 100, 1) if total_bans else 0,
                "top3_accuracy": round(total_ban_top3 / total_bans * 100, 1) if total_bans else 0,
            },
        },
        "role_grouped_supplemental": {
            "description": "Supplemental view - top 2 per role, not primary recommendation",
            "top2_per_role_hits": total_role_grouped_hits,
            "top2_per_role_accuracy": round(total_role_grouped_hits / total_picks * 100, 1) if total_picks else 0,
            "additional_hits": total_additional_hits,
            "additional_hits_pct": round(total_additional_hits / total_picks * 100, 1) if total_picks else 0,
            "total_picks": total_picks,
        },
    }

    # Find missed champions pattern
    miss_by_champ: dict[str, int] = {}
    role_grouped_catches: dict[str, int] = {}
    for analysis in analyses:
        for action in analysis.actions:
            if not action.was_in_recommendations:
                miss_by_champ[action.actual_champion] = miss_by_champ.get(action.actual_champion, 0) + 1
                if action.action_type == "pick" and action.was_in_role_grouped:
                    role_grouped_catches[action.actual_champion] = role_grouped_catches.get(action.actual_champion, 0) + 1

    results["aggregate"]["most_missed_champions"] = sorted(
        [{"champion": c, "count": n} for c, n in miss_by_champ.items()],
        key=lambda x: -x["count"]
    )[:20]

    results["aggregate"]["role_grouped_catches"] = sorted(
        [{"champion": c, "count": n} for c, n in role_grouped_catches.items()],
        key=lambda x: -x["count"]
    )[:20]

    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\nResults exported to: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Analyze recommendation accuracy against historical games",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument("--series", "-s", help="Series ID to analyze")
    parser.add_argument("--game", "-g", type=int, help="Specific game number (requires --series)")
    parser.add_argument("--recent", "-r", type=int, default=5,
                        help="Analyze N most recent series (default: 5)")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Show full scoring component breakdown")
    parser.add_argument("--misses-only", "-m", action="store_true",
                        help="Only show actions where actual pick wasn't recommended")
    parser.add_argument("--list-series", "-l", action="store_true",
                        help="List available series and exit")
    parser.add_argument("--json", "-j", type=str, metavar="FILE",
                        help="Export results to JSON file for analysis")
    parser.add_argument("--quiet", "-q", action="store_true",
                        help="Minimal output (just summary)")

    args = parser.parse_args()

    # Initialize
    project_root = Path(__file__).parent.parent
    # Default data path - can be overridden
    data_path = project_root / "outputs" / "full_2024_2025_v2" / "csv"
    knowledge_dir = project_root / "knowledge"

    # Check for alternative data locations
    alt_paths = [
        project_root / "data",
        project_root / "outputs" / "full_2024_2025_v2" / "csv",
    ]
    for p in alt_paths:
        if (p / "draft_data.duckdb").exists():
            data_path = p
            break

    repo = DraftRepository(str(data_path), knowledge_dir=knowledge_dir)
    service = DraftService(str(data_path), knowledge_dir=knowledge_dir)

    if args.list_series:
        series_list = repo.get_series_list(limit=20)
        print(f"\n{Colors.BOLD}Available Series:{Colors.RESET}")
        for s in series_list:
            print(f"  {s['id']}: {s['blue_team_name']} vs {s['red_team_name']} ({s['match_date']})")
        return

    analyses = []

    if args.series:
        # Analyze specific series
        games = repo.get_games_for_series(args.series)
        if not games:
            print(f"No games found for series {args.series}")
            return

        if args.game:
            games = [g for g in games if int(g["game_number"]) == args.game]

        for game in games:
            game_num = int(game["game_number"])
            if not args.quiet:
                print(f"\n{Colors.HEADER}Analyzing {args.series} Game {game_num}...{Colors.RESET}")

            initial_state, actions = load_game_data(repo, args.series, game_num)
            show_verbose = args.verbose and not args.quiet
            show_misses = args.misses_only and not args.quiet
            analysis = analyze_game(service, initial_state, actions,
                                   verbose=show_verbose, misses_only=show_misses)
            analyses.append(analysis)
            if not args.quiet:
                print_game_summary(analysis)
    else:
        # Analyze recent series
        series_list = repo.get_series_list(limit=args.recent)

        for series in series_list:
            series_id = series["id"]
            games = repo.get_games_for_series(series_id)

            for game in games:
                game_num = int(game["game_number"])
                if not args.quiet:
                    print(f"\n{Colors.HEADER}Analyzing {series['blue_team_name']} vs {series['red_team_name']} Game {game_num}...{Colors.RESET}")

                try:
                    initial_state, actions = load_game_data(repo, series_id, game_num)
                    # Only print action details if not quiet mode
                    show_verbose = args.verbose and not args.quiet
                    show_misses = args.misses_only and not args.quiet
                    analysis = analyze_game(service, initial_state, actions,
                                           verbose=show_verbose, misses_only=show_misses)
                    analyses.append(analysis)
                    if not args.quiet:
                        print_game_summary(analysis)
                except Exception as e:
                    print(f"  {Colors.RED}Error: {e}{Colors.RESET}")

    if len(analyses) > 1:
        print_series_summary(analyses)

    # Export results to JSON
    if analyses:
        # Default output directory
        output_dir = project_root / "outputs" / "evals"
        output_dir.mkdir(parents=True, exist_ok=True)

        if args.json:
            output_path = args.json
        else:
            # Generate filename from analysis
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            if args.series:
                filename = f"eval_{args.series[:12]}_{timestamp}.json"
            else:
                filename = f"eval_recent{args.recent}_{timestamp}.json"
            output_path = str(output_dir / filename)

        export_to_json(analyses, output_path)


if __name__ == "__main__":
    main()
