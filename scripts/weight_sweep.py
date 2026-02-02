#!/usr/bin/env python3
"""Weight sweep for pick/ban accuracy on current recommendation engines.

Focus: maximize pick/ban accuracy (top-5/top-3) against historical drafts.
Uses per-tournament replay_meta for era-appropriate tournament scoring.

Usage:
  UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/weight_sweep.py --recent 30
"""

import argparse
import json
import sys
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
import types

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend" / "src"))

from ban_teemo.models.draft import DraftAction, DraftPhase, DraftState
from ban_teemo.models.team import Player, TeamContext
from ban_teemo.repositories.draft_repository import DraftRepository
from ban_teemo.services.draft_service import DraftService
from ban_teemo.services.pick_recommendation_engine import PickRecommendationEngine
from ban_teemo.services.ban_recommendation_service import BanRecommendationService


# Baseline weights (current production)
PICK_BASE_WEIGHTS = {
    "tournament_priority": 0.25,
    "tournament_performance": 0.20,
    "matchup_counter": 0.25,
    "archetype": 0.15,
    "proficiency": 0.15,
}

BAN_PHASE1_BASE = {
    "tournament_priority": 0.40,
    "meta": 0.20,
    "flex": 0.25,
    "proficiency": 0.15,
}

BAN_PHASE2_BASE = {
    "tournament_priority": 0.30,
    "meta": 0.20,
    "proficiency": 0.25,
    "comfort": 0.15,
    "confidence": 0.10,
}


@dataclass
class EvalResult:
    label: str
    pick_top5_hits: int = 0
    pick_top5_total: int = 0
    pick_top3_hits: int = 0
    pick_top3_total: int = 0
    ban_top5_hits: int = 0
    ban_top5_total: int = 0
    ban_top3_hits: int = 0
    ban_top3_total: int = 0

    @property
    def pick_top5_pct(self) -> float:
        return self.pick_top5_hits / self.pick_top5_total * 100 if self.pick_top5_total else 0.0

    @property
    def pick_top3_pct(self) -> float:
        return self.pick_top3_hits / self.pick_top3_total * 100 if self.pick_top3_total else 0.0

    @property
    def ban_top5_pct(self) -> float:
        return self.ban_top5_hits / self.ban_top5_total * 100 if self.ban_top5_total else 0.0

    @property
    def ban_top3_pct(self) -> float:
        return self.ban_top3_hits / self.ban_top3_total * 100 if self.ban_top3_total else 0.0


def normalize_weights(base: dict[str, float], key: str, new_value: float) -> dict[str, float]:
    """Adjust one weight and scale others proportionally to keep sum=1."""
    if new_value <= 0.0 or new_value >= 1.0:
        raise ValueError("Weight must be between 0 and 1")

    others = {k: v for k, v in base.items() if k != key}
    total_others = sum(others.values())
    remaining = 1.0 - new_value
    if total_others <= 0:
        raise ValueError("Invalid base weights")

    scaled = {k: (v / total_others) * remaining for k, v in others.items()}
    result = {key: new_value, **scaled}
    # Normalize tiny float drift
    total = sum(result.values())
    if abs(total - 1.0) > 1e-6:
        # Adjust the target weight to fix drift
        result[key] += 1.0 - total
    return result


def patch_pick_engine(engine: PickRecommendationEngine, weights: dict[str, float]) -> None:
    engine.BASE_WEIGHTS = dict(weights)


def make_ban_priority_calculator(phase1_weights: dict[str, float], phase2_weights: dict[str, float]):
    """Create patched _calculate_ban_priority using provided weights."""

    def _calculate_ban_priority(self: BanRecommendationService, champion: str, player: dict,
                                proficiency: dict, is_phase_1: bool = True):
        components: dict[str, float] = {}

        if is_phase_1:
            meta_score = self.meta_scorer.get_meta_score(champion)
            flex = self._get_flex_value(champion)
            prof_score = proficiency["score"]
            conf = proficiency.get("confidence", "LOW")

            is_high_proficiency = prof_score >= 0.7 and conf in {"HIGH", "MEDIUM"}
            is_in_pool = proficiency.get("games", 0) >= 2

            tournament_priority = self.tournament_scorer.get_priority(champion)

            w_t = phase1_weights["tournament_priority"]
            w_m = phase1_weights["meta"]
            w_f = phase1_weights["flex"]
            w_p = phase1_weights["proficiency"]

            components["tournament_priority"] = round(tournament_priority * w_t, 3)
            components["meta"] = round(meta_score * w_m, 3)
            components["flex"] = round(flex * w_f, 3)
            components["proficiency"] = round(prof_score * w_p, 3)

            base_priority = (
                tournament_priority * w_t
                + meta_score * w_m
                + flex * w_f
                + prof_score * w_p
            )

            is_high_tournament = tournament_priority >= 0.50
            tier_bonus = 0.0
            tier_high_meta = is_high_tournament or self._get_presence_score(champion) >= 0.25

            if is_high_proficiency and tier_high_meta and is_in_pool:
                tier_bonus = 0.10
                components["tier"] = "T1_SIGNATURE_POWER"
            elif tier_high_meta:
                tier_bonus = 0.05
                components["tier"] = "T2_META_POWER"
            elif is_high_proficiency and is_in_pool:
                tier_bonus = 0.03
                components["tier"] = "T3_COMFORT_PICK"
            else:
                tier_bonus = 0.0
                components["tier"] = "T4_GENERAL"

            components["tier_bonus"] = round(tier_bonus, 3)
            priority = base_priority + tier_bonus
        else:
            prof_score = proficiency["score"]
            meta_score = self.meta_scorer.get_meta_score(champion)
            tournament_priority = self.tournament_scorer.get_priority(champion)

            games = proficiency.get("games", 0)
            comfort = min(1.0, games / 10)

            conf = proficiency.get("confidence", "LOW")
            conf_value = {"HIGH": 1.0, "MEDIUM": 0.5, "LOW": 0.0}.get(conf, 0)

            w_t = phase2_weights["tournament_priority"]
            w_m = phase2_weights["meta"]
            w_p = phase2_weights["proficiency"]
            w_c = phase2_weights["comfort"]
            w_conf = phase2_weights["confidence"]

            components["tournament_priority"] = round(tournament_priority * w_t, 3)
            components["meta"] = round(meta_score * w_m, 3)
            components["proficiency"] = round(prof_score * w_p, 3)
            components["comfort"] = round(comfort * w_c, 3)
            components["confidence"] = round(conf_value * w_conf, 3)

            priority = (
                tournament_priority * w_t
                + meta_score * w_m
                + prof_score * w_p
                + comfort * w_c
                + conf_value * w_conf
            )

        return (round(min(1.0, priority), 3), components)

    return _calculate_ban_priority


def patch_ban_service(ban_service: BanRecommendationService,
                      phase1_weights: dict[str, float],
                      phase2_weights: dict[str, float]) -> None:
    patched = make_ban_priority_calculator(phase1_weights, phase2_weights)
    ban_service._calculate_ban_priority = types.MethodType(patched, ban_service)


def load_game_data(repo: DraftRepository, series_id: str, game_number: int):
    game_info = repo.get_game_info(series_id, game_number)
    if not game_info:
        raise ValueError(f"Game not found: {series_id} game {game_number}")

    game_id = game_info["game_id"]
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


def evaluate_config(
    repo: DraftRepository,
    series_list: list[dict],
    pick_weights: dict[str, float],
    ban_phase1_weights: dict[str, float],
    ban_phase2_weights: dict[str, float],
    target: str = "both",
) -> EvalResult:
    """Evaluate a config over recent series. target: pick|ban|both."""
    project_root = Path(__file__).parent.parent
    knowledge_dir = project_root / "knowledge"
    db_path = project_root / "data" / "draft_data.duckdb"

    result = EvalResult(label="config")

    service_cache: dict[str, DraftService] = {}

    def get_service(game_id: str) -> DraftService:
        tournament_id = repo.get_tournament_id_for_game(game_id)
        cache_key = tournament_id or "default"
        if cache_key in service_cache:
            return service_cache[cache_key]

        tournament_data_file = f"replay_meta/{tournament_id}.json" if tournament_id else None
        service = DraftService(
            str(db_path),
            knowledge_dir=knowledge_dir,
            tournament_data_file=tournament_data_file,
        )
        patch_pick_engine(service.pick_engine, pick_weights)
        patch_ban_service(service.ban_service, ban_phase1_weights, ban_phase2_weights)
        service_cache[cache_key] = service
        return service

    for series in series_list:
        series_id = series["id"]
        games = repo.get_games_for_series(series_id)
        for game in games:
            game_num = int(game["game_number"])
            initial_state, actions = load_game_data(repo, series_id, game_num)
            service = get_service(initial_state.game_id)

            for i, action in enumerate(actions):
                current_state = service.build_draft_state_at(initial_state, actions, i)
                if current_state.next_team is None:
                    continue

                # Only evaluate requested target
                if target == "pick" and action.action_type != "pick":
                    # still need to advance state, but no recs
                    continue
                if target == "ban" and action.action_type != "ban":
                    continue

                recs = service.get_recommendations(current_state, current_state.next_team)

                if action.action_type == "pick":
                    picks = recs.picks
                    names = [p.champion_name for p in picks]
                    result.pick_top5_total += 1
                    result.pick_top3_total += 1
                    if action.champion_name in names[:5]:
                        result.pick_top5_hits += 1
                    if action.champion_name in names[:3]:
                        result.pick_top3_hits += 1
                else:
                    bans = recs.bans
                    names = [b.champion_name for b in bans]
                    result.ban_top5_total += 1
                    result.ban_top3_total += 1
                    if action.champion_name in names[:5]:
                        result.ban_top5_hits += 1
                    if action.champion_name in names[:3]:
                        result.ban_top3_hits += 1

    return result


def run_weight_sweep(
    repo: DraftRepository,
    series_list: list[dict],
    group_name: str,
    base_weights: dict[str, float],
    target: str,
    pick_weights: dict[str, float],
    ban_phase1_weights: dict[str, float],
    ban_phase2_weights: dict[str, float],
    delta: float,
    step: float,
) -> list[dict]:
    """Run a sweep over all weights in a group."""
    results = []

    for key, base_val in base_weights.items():
        start = max(0.05, base_val - delta)
        end = min(0.60, base_val + delta)
        value = start
        while value <= end + 1e-6:
            sweep_weights = normalize_weights(base_weights, key, value)

            # Apply to appropriate group
            if group_name == "pick":
                pick_w = sweep_weights
                ban1_w = ban_phase1_weights
                ban2_w = ban_phase2_weights
            elif group_name == "ban_phase1":
                pick_w = pick_weights
                ban1_w = sweep_weights
                ban2_w = ban_phase2_weights
            else:
                pick_w = pick_weights
                ban1_w = ban_phase1_weights
                ban2_w = sweep_weights

            label = f"{group_name}:{key}={value:.2f}"
            eval_result = evaluate_config(
                repo, series_list, pick_w, ban1_w, ban2_w, target=target
            )

            results.append({
                "label": label,
                "group": group_name,
                "weight_key": key,
                "weight_value": round(value, 3),
                "weights": sweep_weights,
                "pick_top5_pct": round(eval_result.pick_top5_pct, 2),
                "pick_top3_pct": round(eval_result.pick_top3_pct, 2),
                "ban_top5_pct": round(eval_result.ban_top5_pct, 2),
                "ban_top3_pct": round(eval_result.ban_top3_pct, 2),
            })

            print(
                f"{label:28} "
                f"pick@5={eval_result.pick_top5_pct:.1f}% "
                f"ban@5={eval_result.ban_top5_pct:.1f}%"
            )

            value += step

    return results


def summarize_sweep(results: list[dict], metric: str) -> dict:
    grouped = {}
    for r in results:
        key = r["weight_key"]
        grouped.setdefault(key, []).append(r[metric])
    summary = {}
    for key, vals in grouped.items():
        summary[key] = {
            "min": round(min(vals), 3),
            "max": round(max(vals), 3),
            "range": round(max(vals) - min(vals), 3),
        }
    return summary


def main():
    parser = argparse.ArgumentParser(description="Weight sweep for pick/ban accuracy")
    parser.add_argument("--recent", type=int, default=30, help="Number of recent series to evaluate")
    parser.add_argument("--delta", type=float, default=0.10, help="Sweep +/- delta around baseline")
    parser.add_argument("--step", type=float, default=0.05, help="Sweep step size")
    parser.add_argument("--output", type=str, default="", help="Output JSON path")
    args = parser.parse_args()

    project_root = Path(__file__).parent.parent
    knowledge_dir = project_root / "knowledge"

    db_path = project_root / "data" / "draft_data.duckdb"
    repo = DraftRepository(str(db_path), knowledge_dir=knowledge_dir)

    series_list = repo.get_series_list(limit=args.recent)

    all_results = []

    # Pick sweep (evaluate picks only to save time)
    print("\n=== PICK WEIGHT SWEEP ===")
    pick_results = run_weight_sweep(
        repo,
        series_list,
        group_name="pick",
        base_weights=PICK_BASE_WEIGHTS,
        target="pick",
        pick_weights=PICK_BASE_WEIGHTS,
        ban_phase1_weights=BAN_PHASE1_BASE,
        ban_phase2_weights=BAN_PHASE2_BASE,
        delta=args.delta,
        step=args.step,
    )
    all_results.extend(pick_results)

    # Ban phase 1 sweep (evaluate bans only)
    print("\n=== BAN PHASE 1 WEIGHT SWEEP ===")
    ban1_results = run_weight_sweep(
        repo,
        series_list,
        group_name="ban_phase1",
        base_weights=BAN_PHASE1_BASE,
        target="ban",
        pick_weights=PICK_BASE_WEIGHTS,
        ban_phase1_weights=BAN_PHASE1_BASE,
        ban_phase2_weights=BAN_PHASE2_BASE,
        delta=args.delta,
        step=args.step,
    )
    all_results.extend(ban1_results)

    # Ban phase 2 sweep (evaluate bans only)
    print("\n=== BAN PHASE 2 WEIGHT SWEEP ===")
    ban2_results = run_weight_sweep(
        repo,
        series_list,
        group_name="ban_phase2",
        base_weights=BAN_PHASE2_BASE,
        target="ban",
        pick_weights=PICK_BASE_WEIGHTS,
        ban_phase1_weights=BAN_PHASE1_BASE,
        ban_phase2_weights=BAN_PHASE2_BASE,
        delta=args.delta,
        step=args.step,
    )
    all_results.extend(ban2_results)

    # Summaries
    pick_summary = summarize_sweep(pick_results, "pick_top5_pct")
    ban1_summary = summarize_sweep(ban1_results, "ban_top5_pct")
    ban2_summary = summarize_sweep(ban2_results, "ban_top5_pct")

    summary = {
        "pick_top5_sensitivity": pick_summary,
        "ban_phase1_top5_sensitivity": ban1_summary,
        "ban_phase2_top5_sensitivity": ban2_summary,
    }

    output = {
        "metadata": {
            "generated_at": datetime.now().isoformat(),
            "recent_series": args.recent,
            "delta": args.delta,
            "step": args.step,
        },
        "results": all_results,
        "summary": summary,
    }

    output_path = args.output or str(
        project_root / "outputs" / f"weight_sweep_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nResults saved to: {output_path}")


if __name__ == "__main__":
    main()
