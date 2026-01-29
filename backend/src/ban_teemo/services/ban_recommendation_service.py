"""Ban recommendation service targeting enemy player pools."""
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from ban_teemo.services.scorers import MatchupCalculator, MetaScorer, ProficiencyScorer
from ban_teemo.utils.role_normalizer import normalize_role

if TYPE_CHECKING:
    from ban_teemo.repositories.draft_repository import DraftRepository


class BanRecommendationService:
    """Generates ban recommendations based on enemy team analysis."""

    def __init__(
        self,
        knowledge_dir: Optional[Path] = None,
        draft_repository: Optional["DraftRepository"] = None
    ):
        if knowledge_dir is None:
            knowledge_dir = Path(__file__).parents[4] / "knowledge"

        self.meta_scorer = MetaScorer(knowledge_dir)
        self.proficiency_scorer = ProficiencyScorer(knowledge_dir)
        self.matchup_calculator = MatchupCalculator(knowledge_dir)
        self._draft_repository = draft_repository

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

        # Auto-lookup roster if not provided but repository is available
        if enemy_players is None and self._draft_repository and enemy_team_id:
            enemy_players = self._lookup_enemy_roster(enemy_team_id)

        # If enemy players provided (or looked up), target their champion pools
        if enemy_players:
            for player in enemy_players:
                player_pool = self.proficiency_scorer.get_player_champion_pool(
                    player["name"], min_games=2
                )
                pool_size = len(player_pool)  # Pre-compute once per player for efficiency

                for entry in player_pool[:5]:  # Top 5 per player
                    champ = entry["champion"]
                    if champ in unavailable:
                        continue

                    priority, components = self._calculate_ban_priority(
                        champion=champ,
                        player=player,
                        proficiency=entry,
                        pool_size=pool_size,
                    )

                    ban_candidates.append({
                        "champion_name": champ,
                        "priority": priority,
                        "target_player": player["name"],
                        "target_role": player.get("role"),
                        "reasons": self._generate_reasons(champ, player, entry, priority),
                        "components": components,
                    })

        # Phase 2: Add counter-pick bans (champions that counter our picks)
        if not is_phase_1 and our_picks:
            counter_bans = self._get_counter_pick_bans(our_picks, unavailable)
            for counter_ban in counter_bans:
                # Check if already in candidates and boost priority if so
                existing = next(
                    (c for c in ban_candidates if c["champion_name"] == counter_ban["champion_name"]),
                    None
                )
                if existing:
                    # Boost priority for counter picks that are also in player pools
                    existing["priority"] = min(1.0, existing["priority"] + 0.15)
                    existing["reasons"].append(counter_ban["reasons"][0])
                else:
                    ban_candidates.append(counter_ban)

        # Add high meta picks
        for champ in self.meta_scorer.get_top_meta_champions(limit=15):
            if champ in unavailable:
                continue
            if any(c["champion_name"] == champ for c in ban_candidates):
                continue

            meta_score = self.meta_scorer.get_meta_score(champ)
            if meta_score >= 0.5:
                priority = meta_score * 0.8  # Slightly lower than targeted bans
                ban_candidates.append({
                    "champion_name": champ,
                    "priority": round(priority, 3),
                    "target_player": None,
                    "target_role": None,
                    "reasons": [f"{self.meta_scorer.get_meta_tier(champ) or 'High'}-tier meta pick"],
                    "components": {"meta": round(priority, 3)},
                })

        # Sort by priority
        ban_candidates.sort(key=lambda x: -x["priority"])
        return ban_candidates[:limit]

    def _calculate_ban_priority(
        self,
        champion: str,
        player: dict,
        proficiency: dict,
        pool_size: int = 0,
    ) -> tuple[float, dict[str, float]]:
        """Calculate ban priority score for a player's champion pool entry.

        Args:
            champion: Champion name being considered for ban
            player: Player dict with 'name' and 'role'
            proficiency: Proficiency entry with 'score', 'games', 'confidence'
            pool_size: Pre-computed size of player's champion pool (min_games=2)

        Returns:
            Tuple of (priority_score, components_dict)
        """
        components: dict[str, float] = {}

        # Base: player proficiency on champion
        proficiency_component = proficiency["score"] * 0.4
        components["proficiency"] = round(proficiency_component, 3)

        # Meta strength
        meta_score = self.meta_scorer.get_meta_score(champion)
        meta_component = meta_score * 0.3
        components["meta"] = round(meta_component, 3)

        # Games played (comfort factor)
        games = proficiency.get("games", 0)
        comfort = min(1.0, games / 10)
        comfort_component = comfort * 0.2
        components["comfort"] = round(comfort_component, 3)

        # Confidence bonus
        conf = proficiency.get("confidence", "LOW")
        conf_bonus = {"HIGH": 0.1, "MEDIUM": 0.05, "LOW": 0.0}.get(conf, 0)
        components["confidence_bonus"] = round(conf_bonus, 3)

        # Pool depth exploitation - bans hurt more against shallow pools
        pool_bonus = 0.0
        if pool_size >= 1:  # Only boost if we have actual data
            if pool_size <= 3:
                pool_bonus = 0.20  # High impact - shallow pool
            elif pool_size <= 5:
                pool_bonus = 0.10  # Medium impact
            # Deep pools (6+) get no bonus
        components["pool_depth_bonus"] = round(pool_bonus, 3)

        priority = (
            proficiency_component
            + meta_component
            + comfort_component
            + conf_bonus
            + pool_bonus
        )

        return (round(min(1.0, priority), 3), components)

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

    def _get_counter_pick_bans(
        self,
        our_picks: list[str],
        unavailable: set[str]
    ) -> list[dict]:
        """Find champions that counter our picks for Phase 2 bans.

        Uses MatchupCalculator to identify champions with favorable matchups
        against our picks.
        """
        counter_candidates: dict[str, dict] = {}

        # Get top meta champions as potential counters
        meta_champs = self.meta_scorer.get_top_meta_champions(limit=30)

        for our_champ in our_picks:
            for potential_counter in meta_champs:
                if potential_counter in unavailable:
                    continue
                if potential_counter in our_picks:
                    continue

                # Check if this champion counters our pick
                # We use team matchup since we may not know exact roles
                matchup = self.matchup_calculator.get_team_matchup(
                    our_champion=our_champ,
                    enemy_champion=potential_counter
                )

                # If our champion has < 0.45 win rate against this counter,
                # it's a strong counter we should consider banning
                if matchup["score"] < 0.45 and matchup["data_source"] != "none":
                    counter_score = 1.0 - matchup["score"]  # Higher score = better counter

                    if potential_counter not in counter_candidates:
                        counter_candidates[potential_counter] = {
                            "champion_name": potential_counter,
                            "priority": 0.0,
                            "target_player": None,
                            "target_role": None,
                            "counters": [],
                            "reasons": []
                        }

                    counter_candidates[potential_counter]["counters"].append({
                        "vs": our_champ,
                        "score": counter_score
                    })

        # Calculate final priority for counter bans
        result = []
        for champ, data in counter_candidates.items():
            # Average counter score * meta score
            avg_counter = sum(c["score"] for c in data["counters"]) / len(data["counters"])
            meta_score = self.meta_scorer.get_meta_score(champ)

            counter_component = avg_counter * 0.6
            meta_component = meta_score * 0.4
            priority = counter_component + meta_component
            countered_champs = [c["vs"] for c in data["counters"]]

            result.append({
                "champion_name": champ,
                "priority": round(priority, 3),
                "target_player": None,
                "target_role": None,
                "reasons": [f"Counters {', '.join(countered_champs)}"],
                "components": {
                    "counter": round(counter_component, 3),
                    "meta": round(meta_component, 3),
                },
            })

        return sorted(result, key=lambda x: -x["priority"])[:5]

    def _lookup_enemy_roster(self, enemy_team_id: str) -> list[dict]:
        """Lookup enemy roster from repository.

        Converts repository format to expected player format.

        Args:
            enemy_team_id: The enemy team's ID

        Returns:
            List of player dicts with 'name' and 'role' keys
        """
        if not self._draft_repository:
            return []

        roster = self._draft_repository.get_team_roster(enemy_team_id)
        if not roster:
            return []

        players = []
        for player in roster:
            # Role is already normalized by repository, but ensure consistency
            role = normalize_role(player.get("role"))

            players.append({
                "name": player.get("player_name", ""),
                "role": role,
                "player_id": player.get("player_id")
            })

        return players
