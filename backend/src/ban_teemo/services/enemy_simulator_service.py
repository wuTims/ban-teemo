"""Generates enemy picks/bans from historical data."""

import random
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from ban_teemo.models.simulator import EnemyStrategy
from ban_teemo.models.draft import DraftAction
from ban_teemo.repositories.draft_repository import DraftRepository

if TYPE_CHECKING:
    from ban_teemo.services.ban_recommendation_service import BanRecommendationService
    from ban_teemo.services.pick_recommendation_engine import PickRecommendationEngine


class EnemySimulatorService:
    """Generates enemy picks/bans from historical data."""

    def __init__(
        self,
        database_path: Optional[str] = None,
        ban_service: Optional["BanRecommendationService"] = None,
        pick_engine: Optional["PickRecommendationEngine"] = None,
    ):
        if database_path is None:
            database_path = str(Path(__file__).parents[4] / "data" / "draft_data.duckdb")
        self.repo = DraftRepository(database_path)

        # Lazy-load recommendation services if not provided
        self._ban_service = ban_service
        self._pick_engine = pick_engine

    @property
    def ban_service(self) -> "BanRecommendationService":
        """Lazy-load ban recommendation service."""
        if self._ban_service is None:
            from ban_teemo.services.ban_recommendation_service import BanRecommendationService
            self._ban_service = BanRecommendationService(
                draft_repository=self.repo,
            )
        return self._ban_service

    @property
    def pick_engine(self) -> "PickRecommendationEngine":
        """Lazy-load pick recommendation engine."""
        if self._pick_engine is None:
            from ban_teemo.services.pick_recommendation_engine import PickRecommendationEngine
            self._pick_engine = PickRecommendationEngine()
        return self._pick_engine

    def initialize_enemy_strategy(self, enemy_team_id: str) -> EnemyStrategy:
        """Load reference game, fallbacks, and champion weights."""
        games = self.repo.get_team_games(enemy_team_id, limit=20)
        if not games:
            raise ValueError(f"No games found for team {enemy_team_id}")

        reference = random.choice(games)
        fallbacks = [g for g in games if g["game_id"] != reference["game_id"]]

        # Load draft actions for reference game
        draft_actions_raw = self.repo.get_draft_actions(reference["game_id"])

        # Convert dict results to DraftAction if needed
        draft_actions = []
        for a in draft_actions_raw:
            if isinstance(a, DraftAction):
                draft_actions.append(a)
            else:
                draft_actions.append(
                    DraftAction(
                        sequence=int(a["sequence"]),
                        action_type=a["action_type"],
                        team_side=a["team_side"],
                        champion_id=a["champion_id"],
                        champion_name=a["champion_name"],
                    )
                )

        # Determine which side the enemy team was on in this game
        team_side = reference.get("team_side")
        if not team_side:
            # Fallback: check if team is blue_team_id
            if reference.get("blue_team_id") == enemy_team_id:
                team_side = "blue"
            else:
                team_side = "red"

        # Filter to enemy team's actions only
        enemy_actions = [a for a in draft_actions if a.team_side == team_side]

        # Build champion weights from all games
        weights = self._build_champion_weights(enemy_team_id, games)

        # Build game_id -> team_side mapping for all games (needed for fallback filtering)
        game_team_sides = {}
        for game in games:
            game_side = game.get("team_side")
            if not game_side:
                if game.get("blue_team_id") == enemy_team_id:
                    game_side = "blue"
                else:
                    game_side = "red"
            game_team_sides[game["game_id"]] = game_side

        # Load team info and roster for smart recommendations
        team_info = self.repo.get_team_with_name(enemy_team_id)
        team_name = team_info["name"] if team_info else ""

        roster = self.repo.get_team_roster(enemy_team_id)
        players = [
            {"name": p["player_name"], "role": p["role"]}
            for p in roster
        ] if roster else []

        return EnemyStrategy(
            reference_game_id=reference["game_id"],
            draft_script=enemy_actions,
            fallback_game_ids=[g["game_id"] for g in fallbacks],
            champion_weights=weights,
            game_team_sides=game_team_sides,
            team_id=enemy_team_id,
            team_name=team_name,
            players=players,
        )

    def _build_champion_weights(self, team_id: str, games: list[dict]) -> dict[str, float]:
        """Build champion pick frequency weights."""
        pick_counts: dict[str, int] = {}
        total = 0

        for game in games:
            actions_raw = self.repo.get_draft_actions(game["game_id"])

            # Determine team side for this game
            team_side = game.get("team_side")
            if not team_side:
                if game.get("blue_team_id") == team_id:
                    team_side = "blue"
                else:
                    team_side = "red"

            for action in actions_raw:
                # Handle both DraftAction objects and dicts
                if isinstance(action, DraftAction):
                    action_side = action.team_side
                    action_type = action.action_type
                    champion_name = action.champion_name
                else:
                    action_side = action["team_side"]
                    action_type = action["action_type"]
                    champion_name = action["champion_name"]

                if action_side == team_side and action_type == "pick":
                    pick_counts[champion_name] = pick_counts.get(champion_name, 0) + 1
                    total += 1

        if total == 0:
            return {}
        return {champ: count / total for champ, count in pick_counts.items()}

    def generate_action(
        self, strategy: EnemyStrategy, sequence: int, unavailable: set[str]
    ) -> tuple[str, str]:
        """Generate enemy's next pick/ban."""
        # Step 1: Try reference script - find next valid action at or after sequence
        for action in strategy.draft_script:
            if action.sequence >= sequence and action.champion_name not in unavailable:
                return action.champion_name, "reference_game"

        # Step 2: Try fallback games - find next valid action at or after sequence
        # Filter to only actions from the enemy team's side in each fallback game
        for fallback_id in strategy.fallback_game_ids:
            enemy_side_in_fallback = strategy.game_team_sides.get(fallback_id)
            if not enemy_side_in_fallback:
                continue

            actions_raw = self.repo.get_draft_actions(fallback_id)
            for action_raw in actions_raw:
                # Handle both DraftAction objects and dicts
                if isinstance(action_raw, DraftAction):
                    action_seq = action_raw.sequence
                    action_side = action_raw.team_side
                    champion = action_raw.champion_name
                else:
                    action_seq = int(action_raw["sequence"])
                    action_side = action_raw["team_side"]
                    champion = action_raw["champion_name"]

                # Only consider actions from the enemy team's side
                if action_side != enemy_side_in_fallback:
                    continue

                if action_seq >= sequence and champion not in unavailable:
                    return champion, "fallback_game"

        # Step 3: Weighted random
        available_weights = {
            champ: weight
            for champ, weight in strategy.champion_weights.items()
            if champ not in unavailable
        }

        if available_weights:
            champs = list(available_weights.keys())
            weights = list(available_weights.values())
            chosen = random.choices(champs, weights=weights, k=1)[0]
            return chosen, "weighted_random"

        # Ultimate fallback: any available champion from weights
        all_champs = list(strategy.champion_weights.keys())
        available = [c for c in all_champs if c not in unavailable]
        if available:
            return random.choice(available), "weighted_random"

        raise ValueError("No available champions for enemy action")

    def generate_smart_action(
        self,
        strategy: EnemyStrategy,
        action_type: str,  # "ban" or "pick"
        our_picks: list[str],
        enemy_picks: list[str],
        banned: list[str],
        unavailable: set[str],
    ) -> tuple[str, str]:
        """Generate enemy action using recommendation services filtered by champion pool.

        Uses the same scoring logic as user recommendations, but filtered to champions
        the enemy team has historically played. Selects randomly from top 3 overlapping
        recommendations for variety.

        Falls back to legacy generate_action if no recommendations overlap with pool.

        Args:
            strategy: Enemy's draft strategy with champion pool
            action_type: "ban" or "pick"
            our_picks: Enemy's picks so far (from their perspective)
            enemy_picks: User's picks (enemy to them)
            banned: All banned champions
            unavailable: Set of unavailable champions (picked, banned, fearless)

        Returns:
            Tuple of (champion_name, source) where source indicates selection method
        """
        pool = strategy.champion_pool - unavailable

        if not pool:
            # No champions in pool available, fall back to legacy
            return self.generate_action(strategy, sequence=1, unavailable=unavailable)

        if action_type == "ban":
            recommendations = self._get_smart_ban_recommendations(
                strategy, our_picks, enemy_picks, banned
            )
        else:
            recommendations = self._get_smart_pick_recommendations(
                strategy, our_picks, enemy_picks, banned
            )

        # Filter recommendations to champions in pool and available
        pool_recommendations = [
            r for r in recommendations
            if r["champion_name"] in pool
        ]

        if not pool_recommendations:
            # No overlap with pool, fall back to legacy generation
            # Calculate sequence based on action count
            sequence = len(banned) + len(our_picks) + len(enemy_picks) + 1
            return self.generate_action(strategy, sequence=sequence, unavailable=unavailable)

        # Select randomly from top 3 for variety (avoid being too predictable)
        top_n = min(3, len(pool_recommendations))
        selected = random.choice(pool_recommendations[:top_n])

        return selected["champion_name"], "smart_recommendation"

    def _get_smart_ban_recommendations(
        self,
        strategy: EnemyStrategy,
        our_picks: list[str],
        enemy_picks: list[str],
        banned: list[str],
    ) -> list[dict]:
        """Get ban recommendations from enemy's perspective."""
        # Determine phase based on ban count
        ban_count = len(banned)
        phase = "BAN_PHASE_1" if ban_count < 6 else "BAN_PHASE_2"

        # Get recommendations - note: from enemy's perspective:
        # - "our_picks" = enemy team's picks (the simulator's team)
        # - "enemy_picks" = user's team's picks (enemy to the simulator)
        # - enemy_team_id = user's team (who enemy wants to target)
        # But we don't have user's team_id easily, so we pass empty and rely on meta
        return self.ban_service.get_ban_recommendations(
            enemy_team_id="",  # Will use global meta bans
            our_picks=our_picks,
            enemy_picks=enemy_picks,
            banned=banned,
            phase=phase,
            enemy_players=None,  # Will use global meta
            limit=10,
        )

    def _get_smart_pick_recommendations(
        self,
        strategy: EnemyStrategy,
        our_picks: list[str],
        enemy_picks: list[str],
        banned: list[str],
    ) -> list[dict]:
        """Get pick recommendations from enemy's perspective."""
        return self.pick_engine.get_recommendations(
            team_players=strategy.players,
            our_picks=our_picks,
            enemy_picks=enemy_picks,
            banned=banned,
            limit=10,
        )
