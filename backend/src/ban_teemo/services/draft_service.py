"""Draft business logic service."""

from ban_teemo.models.draft import DraftAction, DraftPhase, DraftState
from ban_teemo.models.recommendations import (
    BanRecommendation,
    PickRecommendation,
    Recommendations,
)


class DraftService:
    """Core business logic for draft state and recommendations."""

    def __init__(self, data_path: str):
        """Initialize the draft service.

        Args:
            data_path: Path to CSV data directory (for future analytics)
        """
        self.data_path = data_path
        # Future: self.analytics = DraftAnalytics(data_path)

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

        STUB: Returns placeholder recommendations.
        Future: Use DraftAnalytics for real 4-layer analysis.

        Args:
            draft_state: Current state of the draft
            for_team: Which team to generate recommendations for ("blue" or "red")

        Returns:
            Recommendations with pick or ban suggestions
        """
        if draft_state.current_phase == DraftPhase.COMPLETE:
            return Recommendations(for_team=for_team, picks=[], bans=[])

        # Get unavailable champions (already picked or banned)
        unavailable = set(
            draft_state.blue_bans
            + draft_state.red_bans
            + draft_state.blue_picks
            + draft_state.red_picks
        )

        # Stub data - replace with real analytics later
        if draft_state.next_action == "pick":
            return Recommendations(
                for_team=for_team,
                picks=[
                    PickRecommendation(
                        champion_name="Azir",
                        confidence=0.78,
                        flag=None,
                        reasons=[
                            "High meta presence (25%)",
                            "Strong team fight potential",
                            "TODO: Implement analytics layer",
                        ],
                    ),
                    PickRecommendation(
                        champion_name="Vi",
                        confidence=0.72,
                        flag=None,
                        reasons=[
                            "S-tier jungler",
                            "Good engage synergy",
                            "TODO: Implement analytics layer",
                        ],
                    ),
                    PickRecommendation(
                        champion_name="Aurora",
                        confidence=0.55,
                        flag="SURPRISE_PICK",
                        reasons=[
                            "Low stage games (3)",
                            "Strong meta pick",
                            "TODO: Implement analytics layer",
                        ],
                    ),
                ],
                bans=[],
            )
        else:
            return Recommendations(
                for_team=for_team,
                picks=[],
                bans=[
                    BanRecommendation(
                        champion_name="Rumble",
                        priority=0.85,
                        target_player=None,
                        reasons=[
                            "Highest presence (31%)",
                            "TODO: Implement analytics layer",
                        ],
                    ),
                    BanRecommendation(
                        champion_name="Kalista",
                        priority=0.80,
                        target_player="Enemy ADC",
                        reasons=[
                            "Target ban",
                            "High comfort pick",
                            "TODO: Implement analytics layer",
                        ],
                    ),
                    BanRecommendation(
                        champion_name="Rell",
                        priority=0.70,
                        target_player=None,
                        reasons=[
                            "Strong engage support",
                            "TODO: Implement analytics layer",
                        ],
                    ),
                ],
            )
