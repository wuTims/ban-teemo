#!/usr/bin/env python3
"""Scoring system experimentation framework.

This framework allows testing different scoring configurations against
historical pro play data to find optimal parameters.

Usage:
    # Run a single experiment
    uv run python scripts/scoring_experiments.py --config baseline

    # Compare multiple configs
    uv run python scripts/scoring_experiments.py --compare baseline meta_heavy archetype_mean

    # Run parameter sweep
    uv run python scripts/scoring_experiments.py --sweep archetype_weight 0.2 0.4 0.05

    # List available configs
    uv run python scripts/scoring_experiments.py --list-configs

Design:
    - Configs define all tunable parameters as a dict
    - The engine is monkey-patched with config values for each experiment
    - Results are compared against historical picks/bans
    - Metrics: top-5 accuracy, top-3 accuracy, MRR (mean reciprocal rank)
"""

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional
from copy import deepcopy

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend" / "src"))


@dataclass
class ExperimentConfig:
    """Configuration for a scoring experiment."""

    name: str
    description: str

    # Base weights (must sum to 1.0)
    weight_archetype: float = 0.30
    weight_meta: float = 0.30
    weight_matchup_counter: float = 0.25
    weight_proficiency: float = 0.15

    # Archetype calculation method
    # Options: "max", "mean", "weighted_mean", "capped_max"
    archetype_method: str = "max"
    archetype_cap: float = 1.0  # Only used if archetype_method == "capped_max"

    # Meta scoring method
    # Options: "default", "presence_only", "hybrid"
    meta_method: str = "default"

    # Synergy multiplier range (0.5 = 0.75-1.25 range)
    synergy_multiplier_range: float = 0.5

    # NO_DATA redistribution (when matchup data missing)
    # Keys: "archetype", "meta", "matchup_counter", "proficiency"
    # Values must sum to 1.0
    matchup_nodata_redistribution: dict = field(default_factory=lambda: {"meta": 1.0})
    prof_nodata_redistribution: dict = field(default_factory=lambda: {"meta": 0.6, "matchup_counter": 0.4})

    # First pick adjustments
    first_pick_meta_boost: float = 0.05
    first_pick_prof_reduction: float = 0.05
    first_pick_prof_cap: float = 0.70

    # Role flex bonus
    role_flex_bonus_multiplier: float = 0.15

    # Blind pick safety
    apply_blind_safety: bool = True

    def validate(self) -> bool:
        """Check that weights sum to 1.0."""
        total = (self.weight_archetype + self.weight_meta +
                 self.weight_matchup_counter + self.weight_proficiency)
        if abs(total - 1.0) > 0.001:
            raise ValueError(f"Weights must sum to 1.0, got {total}")
        return True


# Pre-defined experiment configurations
EXPERIMENT_CONFIGS = {
    "baseline": ExperimentConfig(
        name="baseline",
        description="Current production configuration",
        weight_archetype=0.30,
        weight_meta=0.30,
        weight_matchup_counter=0.25,
        weight_proficiency=0.15,
        archetype_method="max",
        matchup_nodata_redistribution={"meta": 1.0},
    ),

    "meta_heavy": ExperimentConfig(
        name="meta_heavy",
        description="Emphasize meta/power level over team composition",
        weight_archetype=0.20,
        weight_meta=0.40,
        weight_matchup_counter=0.25,
        weight_proficiency=0.15,
        archetype_method="max",
    ),

    "archetype_heavy": ExperimentConfig(
        name="archetype_heavy",
        description="Emphasize team composition over meta",
        weight_archetype=0.40,
        weight_meta=0.20,
        weight_matchup_counter=0.25,
        weight_proficiency=0.15,
        archetype_method="max",
    ),

    "archetype_mean": ExperimentConfig(
        name="archetype_mean",
        description="Use mean of archetype scores instead of max (reduces specialist bias)",
        weight_archetype=0.30,
        weight_meta=0.30,
        weight_matchup_counter=0.25,
        weight_proficiency=0.15,
        archetype_method="mean",
    ),

    "archetype_capped": ExperimentConfig(
        name="archetype_capped",
        description="Cap archetype max at 0.8 to reduce specialist advantage",
        weight_archetype=0.30,
        weight_meta=0.30,
        weight_matchup_counter=0.25,
        weight_proficiency=0.15,
        archetype_method="capped_max",
        archetype_cap=0.80,
    ),

    "matchup_focus": ExperimentConfig(
        name="matchup_focus",
        description="Higher weight on matchup/counter data",
        weight_archetype=0.25,
        weight_meta=0.25,
        weight_matchup_counter=0.35,
        weight_proficiency=0.15,
        archetype_method="max",
    ),

    "proficiency_boost": ExperimentConfig(
        name="proficiency_boost",
        description="Higher weight on player proficiency",
        weight_archetype=0.25,
        weight_meta=0.25,
        weight_matchup_counter=0.25,
        weight_proficiency=0.25,
        archetype_method="max",
    ),

    "balanced_redistribution": ExperimentConfig(
        name="balanced_redistribution",
        description="Split NO_DATA redistribution evenly between meta and archetype",
        weight_archetype=0.30,
        weight_meta=0.30,
        weight_matchup_counter=0.25,
        weight_proficiency=0.15,
        archetype_method="max",
        matchup_nodata_redistribution={"meta": 0.5, "archetype": 0.5},
    ),

    "no_synergy_boost": ExperimentConfig(
        name="no_synergy_boost",
        description="Disable synergy multiplier (synergy still tracked but no score impact)",
        weight_archetype=0.30,
        weight_meta=0.30,
        weight_matchup_counter=0.25,
        weight_proficiency=0.15,
        synergy_multiplier_range=0.0,  # No synergy effect
    ),

    "high_synergy": ExperimentConfig(
        name="high_synergy",
        description="Stronger synergy multiplier effect (0.6-1.4 range)",
        weight_archetype=0.30,
        weight_meta=0.30,
        weight_matchup_counter=0.25,
        weight_proficiency=0.15,
        synergy_multiplier_range=0.8,  # 0.6-1.4 range
    ),

    # Optimal configs based on experiments
    "optimal_capped": ExperimentConfig(
        name="optimal_capped",
        description="Optimal: cap archetype at 0.60 (reduces specialist bias)",
        weight_archetype=0.30,
        weight_meta=0.30,
        weight_matchup_counter=0.25,
        weight_proficiency=0.15,
        archetype_method="capped_max",
        archetype_cap=0.60,
    ),

    "optimal_low_arch": ExperimentConfig(
        name="optimal_low_arch",
        description="Optimal: lower archetype weight (0.15), higher meta (0.45)",
        weight_archetype=0.15,
        weight_meta=0.45,
        weight_matchup_counter=0.25,
        weight_proficiency=0.15,
        archetype_method="max",
    ),

    "optimal_combined": ExperimentConfig(
        name="optimal_combined",
        description="Optimal: low archetype (0.20) + capped at 0.65 + higher meta (0.40)",
        weight_archetype=0.20,
        weight_meta=0.40,
        weight_matchup_counter=0.25,
        weight_proficiency=0.15,
        archetype_method="capped_max",
        archetype_cap=0.65,
    ),

    # Meta scoring experiments
    "presence_meta": ExperimentConfig(
        name="presence_meta",
        description="Use presence-only meta score (ignores win rate penalty)",
        weight_archetype=0.15,
        weight_meta=0.45,
        weight_matchup_counter=0.25,
        weight_proficiency=0.15,
        archetype_method="max",
        meta_method="presence_only",
    ),

    "hybrid_meta": ExperimentConfig(
        name="hybrid_meta",
        description="Average of original and presence-based meta score",
        weight_archetype=0.15,
        weight_meta=0.45,
        weight_matchup_counter=0.25,
        weight_proficiency=0.15,
        archetype_method="max",
        meta_method="hybrid",
    ),

    "presence_capped_arch": ExperimentConfig(
        name="presence_capped_arch",
        description="Presence meta + capped archetype (best combo attempt)",
        weight_archetype=0.20,
        weight_meta=0.40,
        weight_matchup_counter=0.25,
        weight_proficiency=0.15,
        archetype_method="capped_max",
        archetype_cap=0.65,
        meta_method="presence_only",
    ),

    "hybrid_capped": ExperimentConfig(
        name="hybrid_capped",
        description="Hybrid meta + capped archetype",
        weight_archetype=0.20,
        weight_meta=0.40,
        weight_matchup_counter=0.25,
        weight_proficiency=0.15,
        archetype_method="capped_max",
        archetype_cap=0.65,
        meta_method="hybrid",
    ),
}


@dataclass
class ExperimentResult:
    """Results from running an experiment."""

    config_name: str
    games_analyzed: int

    # Pick accuracy
    pick_top5_hits: int
    pick_top5_total: int
    pick_top3_hits: int
    pick_top3_total: int
    pick_mrr: float  # Mean reciprocal rank

    # Ban accuracy
    ban_top5_hits: int
    ban_top5_total: int
    ban_top3_hits: int
    ban_top3_total: int
    ban_mrr: float

    @property
    def pick_top5_pct(self) -> float:
        return self.pick_top5_hits / self.pick_top5_total * 100 if self.pick_top5_total else 0

    @property
    def pick_top3_pct(self) -> float:
        return self.pick_top3_hits / self.pick_top3_total * 100 if self.pick_top3_total else 0

    @property
    def ban_top5_pct(self) -> float:
        return self.ban_top5_hits / self.ban_top5_total * 100 if self.ban_top5_total else 0

    @property
    def ban_top3_pct(self) -> float:
        return self.ban_top3_hits / self.ban_top3_total * 100 if self.ban_top3_total else 0


class ExperimentRunner:
    """Runs scoring experiments against historical data."""

    def __init__(self, num_games: int = 50):
        self.num_games = num_games
        self._original_engine = None

    def run_experiment(self, config: ExperimentConfig) -> ExperimentResult:
        """Run a single experiment with the given configuration."""
        from ban_teemo.services.pick_recommendation_engine import PickRecommendationEngine
        from ban_teemo.services.archetype_service import ArchetypeService

        # Apply configuration to engine
        engine = self._create_patched_engine(config)

        # Run evaluation
        result = self._evaluate_engine(engine, config.name)

        return result

    def _create_patched_engine(self, config: ExperimentConfig) -> Any:
        """Create an engine instance with patched parameters."""
        from ban_teemo.services.pick_recommendation_engine import PickRecommendationEngine

        engine = PickRecommendationEngine()

        # Patch base weights
        engine.BASE_WEIGHTS = {
            "archetype": config.weight_archetype,
            "meta": config.weight_meta,
            "matchup_counter": config.weight_matchup_counter,
            "proficiency": config.weight_proficiency,
        }

        # Patch synergy multiplier range
        engine.SYNERGY_MULTIPLIER_RANGE = config.synergy_multiplier_range

        # Patch archetype calculation if needed
        if config.archetype_method != "max":
            original_calc = engine._calculate_archetype_score
            engine._calculate_archetype_score = self._make_archetype_calculator(
                engine, config.archetype_method, config.archetype_cap
            )

        # Patch meta scoring if needed
        if config.meta_method != "default":
            engine.meta_scorer.get_meta_score = self._make_meta_scorer(
                engine.meta_scorer, config.meta_method
            )

        # Patch weight redistribution
        original_get_weights = engine._get_effective_weights
        engine._get_effective_weights = self._make_weight_getter(
            engine, config, original_get_weights
        )

        return engine

    def _make_meta_scorer(self, meta_scorer: Any, method: str) -> Callable:
        """Create a patched meta scorer based on method."""
        original_stats = meta_scorer._meta_stats

        def presence_only_score(champion_name: str) -> float:
            if champion_name not in original_stats:
                return 0.5
            presence = original_stats[champion_name].get("presence", 0)
            # Scale presence (0-1) to meta score (0.3-1.0)
            return 0.3 + presence * 0.7

        def hybrid_score(champion_name: str) -> float:
            if champion_name not in original_stats:
                return 0.5
            stats = original_stats[champion_name]
            presence = stats.get("presence", 0)
            original_score = stats.get("meta_score")
            if original_score is None:
                original_score = 0.5
            # Average of original score and presence-based score
            presence_score = 0.3 + presence * 0.7
            return (original_score + presence_score) / 2

        if method == "presence_only":
            return presence_only_score
        elif method == "hybrid":
            return hybrid_score
        else:
            raise ValueError(f"Unknown meta method: {method}")

    def _make_archetype_calculator(
        self, engine: Any, method: str, cap: float
    ) -> Callable:
        """Create a patched archetype calculator based on method."""
        original_service = engine.archetype_service

        def patched_calculate(champion: str, our_picks: list, enemy_picks: list) -> float:
            pick_count = len(our_picks)

            if method == "mean":
                # Use mean of all archetype scores instead of max
                if champion not in original_service._champion_archetypes:
                    return 0.5
                scores = original_service._champion_archetypes[champion]
                if not scores:
                    return 0.5
                raw_strength = sum(scores.values()) / len(scores)
            elif method == "capped_max":
                # Use max but cap it
                raw_strength = min(cap, original_service.get_raw_strength(champion))
            else:
                raw_strength = original_service.get_raw_strength(champion)

            versatility = original_service.get_versatility_score(champion)

            # Early draft: value versatility
            if pick_count <= 1:
                versatility_bonus = versatility * 0.15
                return min(1.0, raw_strength + versatility_bonus)

            # Mid-late draft: value alignment
            team_arch = original_service.calculate_team_archetype(our_picks)
            team_primary = team_arch.get("primary")

            if not team_primary:
                return raw_strength

            contribution = original_service.get_contribution_to_archetype(champion, team_primary)
            alignment_weight = min(0.7, pick_count * 0.15)
            base_score = contribution * alignment_weight + raw_strength * (1 - alignment_weight)

            # Late draft: factor in counter-effectiveness
            if enemy_picks and pick_count >= 3:
                advantage = original_service.calculate_comp_advantage(
                    our_picks + [champion], enemy_picks
                )
                effectiveness = advantage.get("advantage", 1.0)
                effectiveness_normalized = max(0.0, min(1.0, (effectiveness - 0.8) / 0.4))
                eff_weight = min(0.4, (pick_count - 2) * 0.1)
                base_score = base_score * (1 - eff_weight) + effectiveness_normalized * eff_weight

            return round(base_score, 3)

        return patched_calculate

    def _make_weight_getter(
        self, engine: Any, config: ExperimentConfig, original_fn: Callable
    ) -> Callable:
        """Create a patched weight getter with custom redistribution."""

        def patched_get_weights(
            prof_conf: str,
            pick_count: int = 0,
            has_enemy_picks: bool = False,
            matchup_conf: str = "FULL"
        ) -> dict:
            weights = dict(engine.BASE_WEIGHTS)

            # First pick adjustments
            if pick_count == 0 and not has_enemy_picks:
                weights["meta"] += config.first_pick_meta_boost
                weights["proficiency"] -= config.first_pick_prof_reduction

            # Late draft: boost matchup_counter
            elif has_enemy_picks and pick_count >= 3:
                weights["matchup_counter"] += 0.05
                weights["meta"] -= 0.05

            # Handle NO_DATA matchup with custom redistribution
            if matchup_conf == "NO_DATA":
                redistribute = weights["matchup_counter"] * 0.5
                weights["matchup_counter"] *= 0.5
                for component, fraction in config.matchup_nodata_redistribution.items():
                    weights[component] += redistribute * fraction
            elif matchup_conf == "PARTIAL":
                redistribute = weights["matchup_counter"] * 0.25
                weights["matchup_counter"] *= 0.75
                for component, fraction in config.matchup_nodata_redistribution.items():
                    weights[component] += redistribute * fraction

            # Handle NO_DATA proficiency
            if prof_conf == "NO_DATA":
                redistribute = weights["proficiency"] * 0.8
                weights["proficiency"] *= 0.2
                for component, fraction in config.prof_nodata_redistribution.items():
                    weights[component] += redistribute * fraction

            return weights

        return patched_get_weights

    def _evaluate_engine(self, engine: Any, config_name: str) -> ExperimentResult:
        """Evaluate engine against historical games."""
        import duckdb

        # Find the database
        project_root = Path(__file__).parent.parent
        db_paths = [
            project_root / "outputs" / "full_2024_2025_v2" / "csv" / "draft_data.duckdb",
            project_root / "outputs" / "data" / "draft_data.duckdb",
            project_root / "pro_games.duckdb",
        ]
        db_path = None
        for p in db_paths:
            if p.exists():
                db_path = p
                break

        if not db_path:
            raise FileNotFoundError(f"Database not found. Tried: {db_paths}")

        conn = duckdb.connect(str(db_path), read_only=True)

        # Get recent games with team info
        games = conn.execute(f"""
            SELECT DISTINCT
                g.id as game_id,
                g.series_id,
                CAST(g.game_number AS INTEGER) as game_number,
                s.blue_team_id,
                s.red_team_id
            FROM games g
            JOIN series s ON g.series_id = s.id
            ORDER BY s.match_date DESC, g.game_number
            LIMIT {self.num_games}
        """).fetchall()

        pick_top5_hits = 0
        pick_top5_total = 0
        pick_top3_hits = 0
        pick_top3_total = 0
        pick_reciprocal_ranks = []

        ban_top5_hits = 0
        ban_top5_total = 0
        ban_top3_hits = 0
        ban_top3_total = 0
        ban_reciprocal_ranks = []

        from ban_teemo.services.ban_recommendation_service import BanRecommendationService

        ban_service = BanRecommendationService()

        for game_id, series_id, game_number, blue_team_id, red_team_id in games:
            # Get draft actions for this game
            actions = conn.execute("""
                SELECT action_type, team_id, champion_name, CAST(sequence_number AS INTEGER) as seq
                FROM draft_actions
                WHERE game_id = ?
                ORDER BY seq
            """, [game_id]).fetchall()

            # Get team rosters
            blue_players = self._get_team_roster(conn, game_id, blue_team_id)
            red_players = self._get_team_roster(conn, game_id, red_team_id)

            # Simulate draft step by step
            blue_picks, red_picks = [], []
            blue_bans, red_bans = [], []

            for action_type, team_id, champion, seq in actions:
                # Determine side based on team_id
                is_blue = (team_id == blue_team_id)

                # Get recommendations BEFORE this action
                if action_type == "pick":
                    if is_blue:
                        our_picks = blue_picks
                        enemy_picks = red_picks
                        team_players = blue_players
                    else:
                        our_picks = red_picks
                        enemy_picks = blue_picks
                        team_players = red_players

                    banned = blue_bans + red_bans

                    try:
                        recs = engine.get_recommendations(
                            team_players=team_players,
                            our_picks=our_picks,
                            enemy_picks=enemy_picks,
                            banned=banned,
                            limit=10
                        )

                        # Check if actual pick was recommended
                        rec_names = [r["champion_name"] for r in recs]
                        pick_top5_total += 1
                        pick_top3_total += 1

                        if champion in rec_names[:5]:
                            pick_top5_hits += 1
                        if champion in rec_names[:3]:
                            pick_top3_hits += 1

                        # Calculate reciprocal rank
                        if champion in rec_names:
                            rank = rec_names.index(champion) + 1
                            pick_reciprocal_ranks.append(1.0 / rank)
                        else:
                            pick_reciprocal_ranks.append(0.0)

                    except Exception as e:
                        # Log first error for debugging
                        if pick_top5_total == 0:
                            import traceback
                            print(f"ERROR in pick recommendations: {e}")
                            traceback.print_exc()

                    # Update state
                    if is_blue:
                        blue_picks.append(champion)
                    else:
                        red_picks.append(champion)

                elif action_type == "ban":
                    # Note: Ban recommendations require complex setup (enemy_team_id, phase)
                    # For now, just track the ban state for pick recommendations
                    if is_blue:
                        blue_bans.append(champion)
                    else:
                        red_bans.append(champion)

        conn.close()

        return ExperimentResult(
            config_name=config_name,
            games_analyzed=len(games),
            pick_top5_hits=pick_top5_hits,
            pick_top5_total=pick_top5_total,
            pick_top3_hits=pick_top3_hits,
            pick_top3_total=pick_top3_total,
            pick_mrr=sum(pick_reciprocal_ranks) / len(pick_reciprocal_ranks) if pick_reciprocal_ranks else 0,
            ban_top5_hits=ban_top5_hits,
            ban_top5_total=ban_top5_total,
            ban_top3_hits=ban_top3_hits,
            ban_top3_total=ban_top3_total,
            ban_mrr=sum(ban_reciprocal_ranks) / len(ban_reciprocal_ranks) if ban_reciprocal_ranks else 0,
        )

    def _get_team_roster(self, conn: Any, game_id: str, team_id: str) -> list:
        """Get team roster from database."""
        rows = conn.execute("""
            SELECT player_name, role
            FROM player_game_stats
            WHERE game_id = ? AND team_id = ?
        """, [game_id, team_id]).fetchall()

        return [{"name": name, "role": role} for name, role in rows]


def print_result(result: ExperimentResult, show_detail: bool = True):
    """Print experiment result."""
    print(f"\n{'='*60}")
    print(f"Config: {result.config_name}")
    print(f"Games analyzed: {result.games_analyzed}")
    print(f"{'='*60}")

    print(f"\n  PICKS:")
    print(f"    Top-5 accuracy: {result.pick_top5_pct:.1f}% ({result.pick_top5_hits}/{result.pick_top5_total})")
    print(f"    Top-3 accuracy: {result.pick_top3_pct:.1f}% ({result.pick_top3_hits}/{result.pick_top3_total})")
    print(f"    MRR: {result.pick_mrr:.3f}")

    print(f"\n  BANS:")
    print(f"    Top-5 accuracy: {result.ban_top5_pct:.1f}% ({result.ban_top5_hits}/{result.ban_top5_total})")
    print(f"    Top-3 accuracy: {result.ban_top3_pct:.1f}% ({result.ban_top3_hits}/{result.ban_top3_total})")
    print(f"    MRR: {result.ban_mrr:.3f}")


def print_comparison(results: list[ExperimentResult]):
    """Print comparison table of multiple results."""
    print(f"\n{'='*80}")
    print("EXPERIMENT COMPARISON")
    print(f"{'='*80}")

    # Header
    print(f"\n{'Config':<25} {'Pick Top-5':>10} {'Pick Top-3':>10} {'Pick MRR':>10}")
    print("-" * 60)

    # Sort by pick top-5 accuracy
    sorted_results = sorted(results, key=lambda r: r.pick_top5_pct, reverse=True)

    for r in sorted_results:
        print(f"{r.config_name:<25} {r.pick_top5_pct:>9.1f}% {r.pick_top3_pct:>9.1f}% {r.pick_mrr:>10.3f}")

    # Best config
    best = sorted_results[0]
    baseline = next((r for r in results if r.config_name == "baseline"), None)

    print(f"\n🏆 Best config: {best.config_name} (Pick Top-5: {best.pick_top5_pct:.1f}%)")
    if baseline and best.config_name != "baseline":
        improvement = best.pick_top5_pct - baseline.pick_top5_pct
        print(f"   Improvement over baseline: +{improvement:.1f}%")


def run_parameter_sweep(
    base_config: ExperimentConfig,
    param_name: str,
    start: float,
    end: float,
    step: float,
    runner: ExperimentRunner
) -> list[ExperimentResult]:
    """Sweep a single parameter across a range of values."""
    results = []

    value = start
    while value <= end + 0.001:  # Small epsilon for float comparison
        config = deepcopy(base_config)
        config.name = f"{param_name}={value:.2f}"

        # Set the parameter
        if param_name == "weight_archetype":
            # Adjust meta to compensate
            delta = value - config.weight_archetype
            config.weight_archetype = value
            config.weight_meta -= delta
        elif param_name == "weight_meta":
            delta = value - config.weight_meta
            config.weight_meta = value
            config.weight_archetype -= delta
        elif param_name == "weight_matchup_counter":
            delta = value - config.weight_matchup_counter
            config.weight_matchup_counter = value
            config.weight_meta -= delta
        elif param_name == "weight_proficiency":
            delta = value - config.weight_proficiency
            config.weight_proficiency = value
            config.weight_meta -= delta
        elif param_name == "synergy_multiplier_range":
            config.synergy_multiplier_range = value
        elif param_name == "archetype_cap":
            config.archetype_method = "capped_max"
            config.archetype_cap = value
        else:
            raise ValueError(f"Unknown parameter: {param_name}")

        try:
            config.validate()
            result = runner.run_experiment(config)
            results.append(result)
            print(f"  {config.name}: Pick Top-5 = {result.pick_top5_pct:.1f}%")
        except ValueError as e:
            print(f"  {config.name}: SKIPPED ({e})")

        value += step

    return results


def main():
    parser = argparse.ArgumentParser(description="Run scoring experiments")
    parser.add_argument("--config", type=str, help="Run a single config by name")
    parser.add_argument("--compare", nargs="+", help="Compare multiple configs")
    parser.add_argument("--sweep", nargs=4, metavar=("PARAM", "START", "END", "STEP"),
                       help="Sweep a parameter (e.g., --sweep weight_archetype 0.2 0.4 0.05)")
    parser.add_argument("--list-configs", action="store_true", help="List available configs")
    parser.add_argument("--games", type=int, default=50, help="Number of games to evaluate")
    parser.add_argument("--all", action="store_true", help="Run all pre-defined configs")

    args = parser.parse_args()

    if args.list_configs:
        print("\nAvailable experiment configurations:")
        print("-" * 60)
        for name, config in EXPERIMENT_CONFIGS.items():
            print(f"  {name:<25} {config.description}")
        return

    runner = ExperimentRunner(num_games=args.games)

    if args.config:
        if args.config not in EXPERIMENT_CONFIGS:
            print(f"Unknown config: {args.config}")
            print(f"Available: {list(EXPERIMENT_CONFIGS.keys())}")
            return

        print(f"Running experiment: {args.config}")
        config = EXPERIMENT_CONFIGS[args.config]
        result = runner.run_experiment(config)
        print_result(result)

    elif args.compare:
        results = []
        for name in args.compare:
            if name not in EXPERIMENT_CONFIGS:
                print(f"Unknown config: {name}")
                continue

            print(f"Running experiment: {name}...")
            config = EXPERIMENT_CONFIGS[name]
            result = runner.run_experiment(config)
            results.append(result)

        if results:
            print_comparison(results)

    elif args.sweep:
        param_name, start, end, step = args.sweep
        start, end, step = float(start), float(end), float(step)

        print(f"Sweeping {param_name} from {start} to {end} (step={step})")
        base_config = EXPERIMENT_CONFIGS["baseline"]
        results = run_parameter_sweep(base_config, param_name, start, end, step, runner)

        if results:
            print_comparison(results)

    elif args.all:
        results = []
        for name, config in EXPERIMENT_CONFIGS.items():
            print(f"Running experiment: {name}...")
            result = runner.run_experiment(config)
            results.append(result)

        print_comparison(results)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
