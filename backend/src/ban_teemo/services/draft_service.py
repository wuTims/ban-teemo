"""Draft business logic service."""

from pathlib import Path
from typing import Optional

from ban_teemo.models.draft import DraftAction, DraftPhase, DraftState
from ban_teemo.models.recommendations import (
    BanRecommendation,
    PickRecommendation,
    Recommendations,
)
from ban_teemo.services.pick_recommendation_engine import PickRecommendationEngine
from ban_teemo.services.ban_recommendation_service import BanRecommendationService


class DraftService:
    """Core business logic for draft state and recommendations."""

    def __init__(
        self,
        database_path: str,
        knowledge_dir: Optional[Path] = None,
        tournament_data_file: Optional[str] = None,
    ):
        """Initialize the draft service.

        Args:
            database_path: Path to DuckDB database file
            knowledge_dir: Optional path to knowledge directory for recommendation engines
            tournament_data_file: Optional path to tournament-specific meta file for historical accuracy
        """
        self.database_path = database_path
        self.pick_engine = PickRecommendationEngine(knowledge_dir, tournament_data_file=tournament_data_file)
        self.ban_service = BanRecommendationService(knowledge_dir, tournament_data_file=tournament_data_file)

    def compute_phase(self, action_count: int) -> DraftPhase:
        """Compute draft phase from action count.

        Args:
            action_count: Number of actions completed (0-20)

        Returns:
            The current draft phase
        """
        if action_count >= 20:
            return DraftPhase.COMPLETE
        elif action_count < 6:
            return DraftPhase.BAN_PHASE_1
        elif action_count < 12:
            return DraftPhase.PICK_PHASE_1
        elif action_count < 16:
            return DraftPhase.BAN_PHASE_2
        else:
            return DraftPhase.PICK_PHASE_2

    def build_draft_state_at(
        self,
        base_state: DraftState,
        actions: list[DraftAction],
        up_to_index: int,
    ) -> DraftState:
        """Build draft state after N actions have occurred.

        Derives next_team and next_action from the actual game data,
        since draft order varies by tournament/game.

        Args:
            base_state: Initial draft state with team info
            actions: All draft actions for the game
            up_to_index: Include actions 0 through up_to_index-1

        Returns:
            New DraftState with actions applied and phase computed
        """
        actions_so_far = actions[:up_to_index]
        phase = self.compute_phase(len(actions_so_far))

        # Determine next action from the actual game sequence
        if up_to_index >= len(actions):
            next_team = None
            next_action = None
        else:
            next_act = actions[up_to_index]
            next_team = next_act.team_side
            next_action = next_act.action_type

        return DraftState(
            game_id=base_state.game_id,
            series_id=base_state.series_id,
            game_number=base_state.game_number,
            patch_version=base_state.patch_version,
            match_date=base_state.match_date,
            blue_team=base_state.blue_team,
            red_team=base_state.red_team,
            actions=actions_so_far,
            current_phase=phase,
            next_team=next_team,
            next_action=next_action,
        )

    def get_recommendations(
        self,
        draft_state: DraftState,
        for_team: str,
    ) -> Recommendations:
        """Generate pick/ban recommendations for a team.

        Args:
            draft_state: Current state of the draft
            for_team: Which team to generate recommendations for ("blue" or "red")

        Returns:
            Recommendations with pick or ban suggestions
        """
        if draft_state.current_phase == DraftPhase.COMPLETE:
            return Recommendations(for_team=for_team, picks=[], bans=[])

        # Determine our team and enemy team based on for_team
        if for_team == "blue":
            our_team = draft_state.blue_team
            enemy_team = draft_state.red_team
            our_picks = draft_state.blue_picks
            enemy_picks = draft_state.red_picks
        else:
            our_team = draft_state.red_team
            enemy_team = draft_state.blue_team
            our_picks = draft_state.red_picks
            enemy_picks = draft_state.blue_picks

        # Get all banned champions
        banned = draft_state.blue_bans + draft_state.red_bans

        # Format team players for recommendation engines
        team_players = [
            {"name": player.name, "role": player.role}
            for player in our_team.players
        ]
        enemy_players = [
            {"name": player.name, "role": player.role}
            for player in enemy_team.players
        ]

        if draft_state.next_action == "pick":
            # Get pick recommendations
            raw_picks = self.pick_engine.get_recommendations(
                team_players=team_players,
                our_picks=our_picks,
                enemy_picks=enemy_picks,
                banned=banned,
                limit=5,
            )

            # Convert to PickRecommendation model objects
            picks = [
                PickRecommendation(
                    champion_name=rec["champion_name"],
                    confidence=rec.get("confidence", rec.get("score", 0.5)),
                    suggested_role=rec.get("suggested_role"),
                    flag=rec.get("flag"),
                    reasons=rec.get("reasons", []),
                    score=rec.get("score", 0.0),
                    base_score=rec.get("base_score"),
                    synergy_multiplier=rec.get("synergy_multiplier"),
                    components=rec.get("components", {}),
                    weighted_components=rec.get("weighted_components", {}),
                    proficiency_source=rec.get("proficiency_source"),
                    proficiency_player=rec.get("proficiency_player"),
                )
                for rec in raw_picks
            ]

            return Recommendations(for_team=for_team, picks=picks, bans=[])
        else:
            # Get ban recommendations
            raw_bans = self.ban_service.get_ban_recommendations(
                enemy_team_id=enemy_team.id,
                our_picks=our_picks,
                enemy_picks=enemy_picks,
                banned=banned,
                phase=draft_state.current_phase.value,
                enemy_players=enemy_players,
                limit=5,
            )

            # Convert to BanRecommendation model objects
            bans = [
                BanRecommendation(
                    champion_name=rec["champion_name"],
                    priority=rec.get("priority", 0.5),
                    target_player=rec.get("target_player"),
                    reasons=rec.get("reasons", []),
                    components=rec.get("components", {}),
                )
                for rec in raw_bans
            ]

            return Recommendations(for_team=for_team, picks=[], bans=bans)
