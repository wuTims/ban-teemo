#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  LLM RERANKER EXPERIMENTS                                                     ║
║                                                                               ║
║  WARNING: DO NOT RUN FROM CLAUDE CODE                                         ║
║                                                                               ║
║  This script produces large amounts of streaming output that can corrupt      ║
║  the Claude Code session context. Run this directly in a terminal:            ║
║                                                                               ║
║    cd ban-teemo                                                               ║
║    uv run python scripts/llm_experiments.py <args>                            ║
║                                                                               ║
╚══════════════════════════════════════════════════════════════════════════════╝

Run LLM reranker experiments against replay logs.

Compares baseline scoring system against LLM-enhanced recommendations,
measuring accuracy improvement, latency, and cost.

By default, only Phase 2 actions are processed with the LLM to reduce
costs (~6 calls instead of ~20 per game). Use --all-phases to process
all actions.

Usage:
    # Basic experiment (Phase 2 only, default)
    uv run python scripts/llm_experiments.py logs/scoring/replay_*.json

    # All phases (more expensive)
    uv run python scripts/llm_experiments.py logs/scoring/replay.json --all-phases

    # With series context for game 2+
    uv run python scripts/llm_experiments.py logs/scoring/game2.json \\
        --include-series-context --series-logs logs/scoring/game1.json

    # Save results to JSON
    uv run python scripts/llm_experiments.py logs/scoring/replay.json --output results/exp.json

    # Use different model
    uv run python scripts/llm_experiments.py logs/scoring/replay.json --model qwen3

Environment:
    NEBIUS_API_KEY - Required. Set in .env or export in shell.

Models:
    deepseek      - DeepSeek-V3 fast (~2s latency, default)
    deepseek-slow - DeepSeek-V3 full (~25s latency)
    qwen3         - Qwen3-235B
    llama         - Llama-3.3-70B
    glm           - GLM-4.5
"""

import asyncio
import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Optional

from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# Add project root to path
sys.path.insert(0, str(Path(__file__).parents[1] / "backend" / "src"))

from ban_teemo.services.llm_reranker import LLMReranker
from ban_teemo.services.series_context_builder import SeriesContextBuilder
from ban_teemo.models.series_context import SeriesContext


# Phase 2 phases for filtering (when --phase2-only is used, which is default)
PHASE_2_PHASES = {"BAN_PHASE_2", "PICK_PHASE_2"}


# Cost estimates (per 1K tokens) - approximate for Nebius
COST_PER_1K_INPUT = 0.001  # $0.001 per 1K input tokens
COST_PER_1K_OUTPUT = 0.002  # $0.002 per 1K output tokens
AVG_PROMPT_TOKENS = 1500
AVG_RESPONSE_TOKENS = 800


@dataclass
class ActionResult:
    """Result for a single draft action."""

    action_count: int
    action_type: str  # "pick" or "ban"
    team: str
    phase: str
    actual_champion: str

    # Baseline results
    baseline_recommendations: list[str]
    baseline_in_recs: bool
    baseline_rank: Optional[int]
    baseline_in_top3: bool

    # LLM results
    llm_recommendations: list[str]
    llm_in_recs: bool
    llm_rank: Optional[int]
    llm_in_top3: bool
    llm_reasoning: str
    llm_additional_suggestions: list[str]
    llm_draft_analysis: str

    # Metrics
    latency_ms: float
    estimated_cost: float

    # Phase filtering
    skipped: bool = False  # True if action was skipped (Phase 1 with --phase2-only)


@dataclass
class ExperimentResults:
    """Complete experiment results."""

    match_info: dict
    actions: list[ActionResult] = field(default_factory=list)

    # Aggregate metrics
    total_latency_ms: float = 0
    total_cost: float = 0

    # Baseline accuracy
    baseline_pick_accuracy: float = 0
    baseline_pick_top3: float = 0
    baseline_ban_accuracy: float = 0
    baseline_ban_top3: float = 0

    # LLM accuracy
    llm_pick_accuracy: float = 0
    llm_pick_top3: float = 0
    llm_ban_accuracy: float = 0
    llm_ban_top3: float = 0

    # Suggestions hit rate
    suggestions_hits: int = 0
    suggestions_total: int = 0

    # Phase filtering stats
    skipped_phase1: int = 0
    processed_phase2: int = 0


def load_replay(path: Path) -> dict:
    """Load replay log."""
    with open(path) as f:
        return json.load(f)


def extract_events(log_data: dict) -> list[tuple[dict, dict]]:
    """Extract (recommendation, actual_action) pairs."""
    entries = log_data.get("entries", [])
    pairs = []

    i = 0
    while i < len(entries):
        entry = entries[i]
        event_type = entry.get("event", "")

        if event_type in ("pick_recommendations", "ban_recommendations"):
            for j in range(i + 1, min(i + 5, len(entries))):
                next_entry = entries[j]
                if next_entry.get("event") == "actual_action":
                    if next_entry.get("action_count") == entry.get("action_count"):
                        pairs.append((entry, next_entry))
                        break
        i += 1

    return pairs


def build_context(rec_event: dict, metadata: dict, actual_champion: str = "") -> dict:
    """Build draft context for LLM.

    Note: The replay log records context AFTER the action, so we need to remove
    the actual champion from the banned/picks lists to reconstruct the state
    BEFORE the action was taken.
    """
    ctx = rec_event.get("context", {})
    for_team = rec_event.get("for_team", "blue")

    # Remove actual champion from banned list (it wasn't banned yet when recs were made)
    banned = ctx.get("banned", [])
    if actual_champion and actual_champion in banned:
        banned = [b for b in banned if b != actual_champion]

    # Same for picks
    our_picks = ctx.get("our_picks", [])
    enemy_picks = ctx.get("enemy_picks", [])
    if actual_champion:
        our_picks = [p for p in our_picks if p != actual_champion]
        enemy_picks = [p for p in enemy_picks if p != actual_champion]

    return {
        "phase": rec_event.get("phase", "UNKNOWN"),
        "patch": metadata.get("patch", "15.17"),
        "our_team": metadata.get("blue_team") if for_team == "blue" else metadata.get("red_team"),
        "enemy_team": metadata.get("red_team") if for_team == "blue" else metadata.get("blue_team"),
        "our_picks": our_picks,
        "enemy_picks": enemy_picks,
        "banned": banned,
    }


def get_players(rec_event: dict) -> tuple[list[dict], list[dict]]:
    """Get team and enemy players."""
    ctx = rec_event.get("context", {})
    return ctx.get("team_players", []), ctx.get("enemy_players", [])


async def run_experiment(
    log_path: Path,
    reranker: LLMReranker,
    limit: Optional[int] = None,
    phase2_only: bool = True,
    series_context: Optional[SeriesContext] = None,
) -> ExperimentResults:
    """Run the full experiment.

    Args:
        log_path: Path to replay log file
        reranker: LLM reranker instance
        limit: Limit number of actions to process
        phase2_only: If True, only run LLM for Phase 2 actions (default)
        series_context: Optional series context for games 2+

    Returns:
        ExperimentResults with accuracy metrics
    """
    log_data = load_replay(log_path)
    metadata = log_data.get("metadata", {})
    pairs = extract_events(log_data)

    if limit:
        pairs = pairs[:limit]

    results = ExperimentResults(
        match_info={
            "blue_team": metadata.get("blue_team"),
            "red_team": metadata.get("red_team"),
            "patch": metadata.get("patch"),
            "game": metadata.get("game_number"),
        }
    )

    mode_str = "Phase 2 only" if phase2_only else "All phases"
    series_str = (
        f" | Series Game {series_context.game_number}"
        if series_context and series_context.is_series_context_available
        else ""
    )
    print(f"\n{'='*70}")
    print(f"EXPERIMENT: {metadata.get('blue_team')} vs {metadata.get('red_team')}")
    print(f"Patch: {metadata.get('patch')} | Actions: {len(pairs)} | Mode: {mode_str}{series_str}")
    print(f"{'='*70}\n")

    for rec_event, actual_event in pairs:
        is_pick = rec_event.get("event") == "pick_recommendations"
        action_type = "PICK" if is_pick else "BAN"
        actual_champ = actual_event.get("champion", "")
        phase = rec_event.get("phase", "")
        team = actual_event.get("team", "")
        action_num = actual_event.get("action_count", 0)

        # Get baseline recommendations
        baseline_recs = rec_event.get("recommendations", [])
        baseline_champs = []
        for r in baseline_recs:
            name = r.get("champion_name", r.get("champion", ""))
            baseline_champs.append(name)

        baseline_rank = None
        for i, name in enumerate(baseline_champs, 1):
            if name.lower() == actual_champ.lower():
                baseline_rank = i
                break

        # Check if we should skip this action (Phase 1 with phase2_only mode)
        is_phase_2 = phase in PHASE_2_PHASES
        should_skip = phase2_only and not is_phase_2

        if should_skip:
            # Record baseline-only result for Phase 1 actions
            results.skipped_phase1 += 1
            action_result = ActionResult(
                action_count=action_num,
                action_type="pick" if is_pick else "ban",
                team=team,
                phase=phase,
                actual_champion=actual_champ,
                baseline_recommendations=baseline_champs[:5],
                baseline_in_recs=baseline_rank is not None,
                baseline_rank=baseline_rank,
                baseline_in_top3=baseline_rank is not None and baseline_rank <= 3,
                llm_recommendations=[],
                llm_in_recs=False,
                llm_rank=None,
                llm_in_top3=False,
                llm_reasoning="",
                llm_additional_suggestions=[],
                llm_draft_analysis="",
                latency_ms=0,
                estimated_cost=0,
                skipped=True,
            )
            results.actions.append(action_result)

            # Print skipped status
            baseline_status = f"B:#{baseline_rank}" if baseline_rank else "B:miss"
            print(
                f"[{action_num:2d}] {action_type:4s} {team.upper():4s} | "
                f"Actual: {actual_champ:12s} | {baseline_status:8s} → (skipped Phase 1)"
            )
            continue

        # Build context for LLM (pass actual_champ to fix context timing)
        draft_context = build_context(rec_event, metadata, actual_champ)
        team_players, enemy_players = get_players(rec_event)

        # Run LLM reranker with timing
        print(
            f"[{action_num:2d}] {action_type:4s} {team.upper():4s} | "
            f"Actual: {actual_champ:12s} | ",
            end="",
            flush=True,
        )

        start_time = time.perf_counter()
        try:
            if is_pick:
                llm_result = await reranker.rerank_picks(
                    candidates=baseline_recs,
                    draft_context=draft_context,
                    team_players=team_players,
                    enemy_players=enemy_players,
                    limit=5,
                    series_context=series_context,
                )
            else:
                llm_result = await reranker.rerank_bans(
                    candidates=baseline_recs,
                    draft_context=draft_context,
                    our_players=team_players,
                    enemy_players=enemy_players,
                    limit=5,
                    series_context=series_context,
                )
        except Exception as e:
            print(f"ERROR: {e}")
            continue

        results.processed_phase2 += 1
        latency_ms = (time.perf_counter() - start_time) * 1000
        estimated_cost = (
            AVG_PROMPT_TOKENS / 1000 * COST_PER_1K_INPUT
            + AVG_RESPONSE_TOKENS / 1000 * COST_PER_1K_OUTPUT
        )

        # Extract LLM results
        llm_champs = [r.champion for r in llm_result.reranked]
        llm_rank = None
        for i, name in enumerate(llm_champs, 1):
            if name.lower() == actual_champ.lower():
                llm_rank = i
                break

        # Check additional suggestions
        additional_hit = any(
            s.champion.lower() == actual_champ.lower() for s in llm_result.additional_suggestions
        )

        # Get reasoning for actual champion
        reasoning = ""
        for r in llm_result.reranked:
            if r.champion.lower() == actual_champ.lower():
                reasoning = r.reasoning
                break

        # Record results
        action_result = ActionResult(
            action_count=action_num,
            action_type="pick" if is_pick else "ban",
            team=team,
            phase=phase,
            actual_champion=actual_champ,
            baseline_recommendations=baseline_champs[:5],
            baseline_in_recs=baseline_rank is not None,
            baseline_rank=baseline_rank,
            baseline_in_top3=baseline_rank is not None and baseline_rank <= 3,
            llm_recommendations=llm_champs[:5],
            llm_in_recs=llm_rank is not None,
            llm_rank=llm_rank,
            llm_in_top3=llm_rank is not None and llm_rank <= 3,
            llm_reasoning=reasoning,
            llm_additional_suggestions=[s.champion for s in llm_result.additional_suggestions],
            llm_draft_analysis=llm_result.draft_analysis,
            latency_ms=latency_ms,
            estimated_cost=estimated_cost,
            skipped=False,
        )
        results.actions.append(action_result)
        results.total_latency_ms += latency_ms
        results.total_cost += estimated_cost

        # Print result
        baseline_status = f"B:#{baseline_rank}" if baseline_rank else "B:miss"
        llm_status = f"L:#{llm_rank}" if llm_rank else "L:miss"
        if additional_hit:
            llm_status += "+sug"
            results.suggestions_hits += 1
        if not baseline_rank:
            results.suggestions_total += 1

        improvement = ""
        if llm_rank and baseline_rank and llm_rank < baseline_rank:
            improvement = f" ↑{baseline_rank - llm_rank}"
        elif llm_rank and not baseline_rank:
            improvement = " ★NEW"
        elif baseline_rank and llm_rank and llm_rank > baseline_rank:
            improvement = f" ↓{llm_rank - baseline_rank}"

        print(f"{baseline_status:8s} → {llm_status:10s}{improvement:8s} | {latency_ms:6.0f}ms")

    # Calculate aggregate metrics (only for non-skipped actions)
    pick_actions = [a for a in results.actions if a.action_type == "pick" and not a.skipped]
    ban_actions = [a for a in results.actions if a.action_type == "ban" and not a.skipped]

    if pick_actions:
        results.baseline_pick_accuracy = sum(1 for a in pick_actions if a.baseline_in_recs) / len(
            pick_actions
        )
        results.baseline_pick_top3 = sum(1 for a in pick_actions if a.baseline_in_top3) / len(
            pick_actions
        )
        results.llm_pick_accuracy = sum(1 for a in pick_actions if a.llm_in_recs) / len(pick_actions)
        results.llm_pick_top3 = sum(1 for a in pick_actions if a.llm_in_top3) / len(pick_actions)

    if ban_actions:
        results.baseline_ban_accuracy = sum(1 for a in ban_actions if a.baseline_in_recs) / len(
            ban_actions
        )
        results.baseline_ban_top3 = sum(1 for a in ban_actions if a.baseline_in_top3) / len(
            ban_actions
        )
        results.llm_ban_accuracy = sum(1 for a in ban_actions if a.llm_in_recs) / len(ban_actions)
        results.llm_ban_top3 = sum(1 for a in ban_actions if a.llm_in_top3) / len(ban_actions)

    return results


def print_results(results: ExperimentResults):
    """Print experiment results."""
    print(f"\n{'='*70}")
    print("EXPERIMENT RESULTS")
    print(f"{'='*70}")

    print(f"\n{'─'*50}")
    print("ACCURACY COMPARISON")
    print(f"{'─'*50}")
    print(f"{'Metric':<25} {'Baseline':>12} {'LLM':>12} {'Delta':>12}")
    print(f"{'─'*50}")

    pick_top3_delta = (results.llm_pick_top3 - results.baseline_pick_top3) * 100
    ban_top3_delta = (results.llm_ban_top3 - results.baseline_ban_top3) * 100

    print(
        f"{'Pick (in recommendations)':<25} "
        f"{results.baseline_pick_accuracy*100:>11.0f}% "
        f"{results.llm_pick_accuracy*100:>11.0f}% "
        f"{(results.llm_pick_accuracy-results.baseline_pick_accuracy)*100:>+11.0f}%"
    )
    print(
        f"{'Pick (top 3)':<25} "
        f"{results.baseline_pick_top3*100:>11.0f}% "
        f"{results.llm_pick_top3*100:>11.0f}% "
        f"{pick_top3_delta:>+11.0f}%"
    )
    print(
        f"{'Ban (in recommendations)':<25} "
        f"{results.baseline_ban_accuracy*100:>11.0f}% "
        f"{results.llm_ban_accuracy*100:>11.0f}% "
        f"{(results.llm_ban_accuracy-results.baseline_ban_accuracy)*100:>+11.0f}%"
    )
    print(
        f"{'Ban (top 3)':<25} "
        f"{results.baseline_ban_top3*100:>11.0f}% "
        f"{results.llm_ban_top3*100:>11.0f}% "
        f"{ban_top3_delta:>+11.0f}%"
    )

    if results.suggestions_total > 0:
        hit_rate = results.suggestions_hits / results.suggestions_total * 100
        print(
            f"\n{'Additional suggestions':<25} "
            f"{results.suggestions_hits}/{results.suggestions_total} hits ({hit_rate:.0f}%)"
        )

    print(f"\n{'─'*50}")
    print("OPERATIONAL METRICS")
    print(f"{'─'*50}")
    processed_actions = [a for a in results.actions if not a.skipped]
    num_processed = len(processed_actions)
    avg_latency = results.total_latency_ms / num_processed if num_processed else 0
    print(f"{'Total latency':<25} {results.total_latency_ms:>12.0f} ms")
    print(f"{'Average latency':<25} {avg_latency:>12.0f} ms")
    print(f"{'Estimated cost':<25} ${results.total_cost:>11.4f}")
    print(
        f"{'Cost per action':<25} ${results.total_cost/num_processed if num_processed else 0:>11.5f}"
    )

    # Phase filtering stats
    if results.skipped_phase1 > 0:
        print(f"\n{'─'*50}")
        print("PHASE FILTERING")
        print(f"{'─'*50}")
        print(f"{'Phase 1 skipped':<25} {results.skipped_phase1:>12}")
        print(f"{'Phase 2 processed':<25} {results.processed_phase2:>12}")
        savings_pct = (
            results.skipped_phase1 / (results.skipped_phase1 + results.processed_phase2) * 100
        )
        print(f"{'LLM call savings':<25} {savings_pct:>11.0f}%")

    # Show interesting cases
    print(f"\n{'─'*50}")
    print("NOTABLE INSIGHTS")
    print(f"{'─'*50}")

    # Cases where LLM improved ranking
    improved = [
        a
        for a in results.actions
        if a.llm_rank and a.baseline_rank and a.llm_rank < a.baseline_rank
    ]
    if improved:
        print(f"\n✓ LLM improved ranking for {len(improved)} actions:")
        for a in improved[:3]:
            print(f"  • {a.actual_champion}: #{a.baseline_rank} → #{a.llm_rank}")
            if a.llm_reasoning:
                print(f'    "{a.llm_reasoning[:80]}..."')

    # Cases where LLM found via additional suggestions
    found_via_suggestions = [
        a
        for a in results.actions
        if not a.baseline_in_recs and a.actual_champion in a.llm_additional_suggestions
    ]
    if found_via_suggestions:
        print(f"\n★ LLM suggested {len(found_via_suggestions)} champions not in baseline:")
        for a in found_via_suggestions:
            print(f"  • {a.actual_champion} (suggested for {a.action_type})")

    # Show sample draft analyses
    print(f"\n{'─'*50}")
    print("SAMPLE DRAFT ANALYSES")
    print(f"{'─'*50}")
    for a in results.actions[:3]:
        if a.llm_draft_analysis:
            print(f"\n[{a.action_count}] {a.phase}:")
            print(f"  {a.llm_draft_analysis}")


async def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Run LLM reranker experiment",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  uv run python scripts/llm_experiments.py logs/scoring/replay.json
  uv run python scripts/llm_experiments.py logs/scoring/replay.json --all-phases
  uv run python scripts/llm_experiments.py logs/scoring/replay.json --output results/exp.json
        """,
    )
    parser.add_argument("log_file", type=Path, help="Replay log file")
    parser.add_argument(
        "--model",
        choices=["deepseek", "deepseek-slow", "qwen3", "llama", "glm"],
        default="deepseek",
        help="LLM model to use (default: deepseek)",
    )
    parser.add_argument("--limit", type=int, help="Limit number of actions to process")
    parser.add_argument("--output", type=Path, help="Save results to JSON file")

    # Phase filtering options (mutually exclusive)
    phase_group = parser.add_mutually_exclusive_group()
    phase_group.add_argument(
        "--phase2-only",
        action="store_true",
        default=True,
        help="Only process Phase 2 actions with LLM (default)",
    )
    phase_group.add_argument(
        "--all-phases", action="store_true", help="Process all phases with LLM"
    )

    # Series context options
    parser.add_argument(
        "--include-series-context",
        action="store_true",
        help="Include series context in prompts (requires game_number > 1 in metadata)",
    )
    parser.add_argument(
        "--series-logs",
        type=Path,
        nargs="*",
        help="Previous game replay logs for series context (in order)",
    )

    args = parser.parse_args()

    # Load API keys
    nebius_key = os.environ.get("NEBIUS_API_KEY")

    if not nebius_key:
        print("ERROR: NEBIUS_API_KEY not found in environment")
        print("Make sure .env file exists with NEBIUS_API_KEY=...")
        sys.exit(1)

    # Initialize reranker (uses local knowledge data for context)
    reranker = LLMReranker(
        api_key=nebius_key,
        model=args.model,
        timeout=30.0,
    )

    print(f"Model: {reranker.model_id}")

    # Determine phase filtering mode
    phase2_only = not args.all_phases

    # Build series context if requested
    series_context: Optional[SeriesContext] = None
    if args.include_series_context:
        log_data = load_replay(args.log_file)
        metadata = log_data.get("metadata", {})
        game_number = metadata.get("game_number", 1)

        if game_number > 1 and args.series_logs:
            # Build from provided series logs
            replay_logs = [load_replay(p) for p in args.series_logs]
            # Determine our side from metadata
            our_side: Literal["blue", "red"] = "blue"  # Default, could be configurable
            series_context = SeriesContextBuilder.from_replay_logs(
                replay_logs=replay_logs,
                current_game_index=len(replay_logs),
                our_side=our_side,
            )
            print(f"Loaded series context from {len(args.series_logs)} previous game logs")
        elif game_number > 1:
            print(f"Warning: Game {game_number} but no --series-logs provided")
        else:
            print("Game 1 - no series context available")

    try:
        results = await run_experiment(
            args.log_file,
            reranker,
            limit=args.limit,
            phase2_only=phase2_only,
            series_context=series_context,
        )
        print_results(results)

        # Save results if requested
        if args.output:
            output_data = {
                "match_info": results.match_info,
                "metrics": {
                    "baseline_pick_top3": results.baseline_pick_top3,
                    "llm_pick_top3": results.llm_pick_top3,
                    "baseline_ban_top3": results.baseline_ban_top3,
                    "llm_ban_top3": results.llm_ban_top3,
                    "total_latency_ms": results.total_latency_ms,
                    "total_cost": results.total_cost,
                    "skipped_phase1": results.skipped_phase1,
                    "processed_phase2": results.processed_phase2,
                },
                "actions": [
                    {
                        "action_count": a.action_count,
                        "type": a.action_type,
                        "phase": a.phase,
                        "team": a.team,
                        "actual": a.actual_champion,
                        "baseline_recommendations": a.baseline_recommendations,
                        "baseline_rank": a.baseline_rank,
                        "llm_recommendations": a.llm_recommendations,
                        "llm_rank": a.llm_rank,
                        "llm_reasoning": a.llm_reasoning,
                        "llm_additional_suggestions": a.llm_additional_suggestions,
                        "llm_draft_analysis": a.llm_draft_analysis,
                        "latency_ms": a.latency_ms,
                        "skipped": a.skipped,
                    }
                    for a in results.actions
                ],
            }
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with open(args.output, "w") as f:
                json.dump(output_data, f, indent=2)
            print(f"\nResults saved to {args.output}")

    finally:
        await reranker.close()


if __name__ == "__main__":
    asyncio.run(main())
