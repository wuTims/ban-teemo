"""Ban recommendation service targeting enemy player pools."""
from pathlib import Path
from typing import Optional

from ban_teemo.services.scorers import MetaScorer, ProficiencyScorer


class BanRecommendationService:
    """Generates ban recommendations based on enemy team analysis."""

    def __init__(self, knowledge_dir: Optional[Path] = None):
        if knowledge_dir is None:
            knowledge_dir = Path(__file__).parents[4] / "knowledge"

        self.meta_scorer = MetaScorer(knowledge_dir)
        self.proficiency_scorer = ProficiencyScorer(knowledge_dir)

    def get_ban_recommendations(
        self,
        enemy_team_id: str,
        our_picks: list[str],
        enemy_picks: list[str],
        banned: list[str],
        phase: str,
        enemy_players: Optional[list[dict]] = None,
        limit: int = 5
    ) -> list[dict]:
        """Generate ban recommendations targeting enemy team.

        Args:
            enemy_team_id: ID of enemy team (used for future roster lookup)
            our_picks: Champions already picked by our team
            enemy_picks: Champions already picked by enemy team
            banned: Champions already banned
            phase: Current draft phase (BAN_PHASE_1, BAN_PHASE_2, etc.)
            enemy_players: Optional list of enemy players with 'name' and 'role' keys
            limit: Maximum recommendations to return

        Returns:
            List of ban recommendations with priority scores
        """
        unavailable = set(banned) | set(our_picks) | set(enemy_picks)
        is_phase_1 = "1" in phase

        ban_candidates = []

        # If enemy players provided, target their champion pools
        if enemy_players:
            for player in enemy_players:
                player_pool = self.proficiency_scorer.get_player_champion_pool(
                    player["name"], min_games=2
                )

                for entry in player_pool[:5]:  # Top 5 per player
                    champ = entry["champion"]
                    if champ in unavailable:
                        continue

                    priority = self._calculate_ban_priority(
                        champion=champ,
                        player=player,
                        proficiency=entry,
                        is_phase_1=is_phase_1,
                        our_picks=our_picks
                    )

                    ban_candidates.append({
                        "champion_name": champ,
                        "priority": priority,
                        "target_player": player["name"],
                        "target_role": player.get("role"),
                        "reasons": self._generate_reasons(champ, player, entry, priority)
                    })

        # Add high meta picks
        for champ in self.meta_scorer.get_top_meta_champions(limit=15):
            if champ in unavailable:
                continue
            if any(c["champion_name"] == champ for c in ban_candidates):
                continue

            meta_score = self.meta_scorer.get_meta_score(champ)
            if meta_score >= 0.5:
                ban_candidates.append({
                    "champion_name": champ,
                    "priority": meta_score * 0.8,  # Slightly lower than targeted bans
                    "target_player": None,
                    "target_role": None,
                    "reasons": [f"{self.meta_scorer.get_meta_tier(champ) or 'High'}-tier meta pick"]
                })

        # Sort by priority
        ban_candidates.sort(key=lambda x: -x["priority"])
        return ban_candidates[:limit]

    def _calculate_ban_priority(
        self,
        champion: str,
        player: dict,
        proficiency: dict,
        is_phase_1: bool,
        our_picks: list[str]
    ) -> float:
        """Calculate ban priority score."""
        # Base: player proficiency on champion
        priority = proficiency["score"] * 0.4

        # Meta strength
        meta_score = self.meta_scorer.get_meta_score(champion)
        priority += meta_score * 0.3

        # Games played (comfort factor)
        games = proficiency.get("games", 0)
        comfort = min(1.0, games / 10)
        priority += comfort * 0.2

        # Confidence bonus
        conf = proficiency.get("confidence", "LOW")
        conf_bonus = {"HIGH": 0.1, "MEDIUM": 0.05, "LOW": 0.0}.get(conf, 0)
        priority += conf_bonus

        return round(min(1.0, priority), 3)

    def _generate_reasons(
        self,
        champion: str,
        player: dict,
        proficiency: dict,
        priority: float
    ) -> list[str]:
        """Generate human-readable ban reasons."""
        reasons = []

        games = proficiency.get("games", 0)
        if games >= 5:
            reasons.append(f"{player['name']}'s comfort pick ({games} games)")
        elif games >= 2:
            reasons.append(f"In {player['name']}'s pool")

        tier = self.meta_scorer.get_meta_tier(champion)
        if tier in ["S", "A"]:
            reasons.append(f"{tier}-tier meta champion")

        if priority >= 0.8:
            reasons.append("High priority target")

        return reasons if reasons else ["General ban recommendation"]
