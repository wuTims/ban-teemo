"""Ban recommendation service targeting enemy player pools."""
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from ban_teemo.services.archetype_service import ArchetypeService
from ban_teemo.services.scorers import FlexResolver, MatchupCalculator, MetaScorer, ProficiencyScorer
from ban_teemo.services.synergy_service import SynergyService
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
        self.flex_resolver = FlexResolver(knowledge_dir)
        self.archetype_service = ArchetypeService(knowledge_dir)
        self.synergy_service = SynergyService(knowledge_dir)
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
                        is_phase_1=is_phase_1,
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
        is_phase_1: bool = True,
    ) -> tuple[float, dict[str, float]]:
        """Calculate ban priority score using explicit tiered priority.

        TIERED PRIORITY SYSTEM (Phase 1):
            Tier 1 (Highest): High proficiency + high presence (in pool + meta power)
            Tier 2 (High):    High proficiency only (pool targeting)
            Tier 3 (Medium):  High presence only (global power)
            Tier 4 (Lower):   General meta bans

        Base weights: proficiency(30%), meta(25%), presence(25%), flex(20%)
        Tier bonuses applied on top for combined conditions.
        """
        components: dict[str, float] = {}

        if is_phase_1:
            # Phase 1: Tiered power pick priority

            # Calculate base components
            meta_score = self.meta_scorer.get_meta_score(champion)
            presence = self._get_presence_score(champion)
            flex = self._get_flex_value(champion)
            prof_score = proficiency["score"]
            conf = proficiency.get("confidence", "LOW")

            # Determine tier conditions
            is_high_proficiency = prof_score >= 0.7 and conf in {"HIGH", "MEDIUM"}
            is_high_presence = presence >= 0.25
            is_in_pool = proficiency.get("games", 0) >= 2

            # Base score (weights: prof 30%, meta 25%, presence 25%, flex 20%)
            proficiency_component = prof_score * 0.30
            meta_component = meta_score * 0.25
            presence_component = presence * 0.25
            flex_component = flex * 0.20

            components["proficiency"] = round(proficiency_component, 3)
            components["meta"] = round(meta_component, 3)
            components["presence"] = round(presence_component, 3)
            components["flex"] = round(flex_component, 3)

            base_priority = (
                proficiency_component
                + meta_component
                + presence_component
                + flex_component
            )

            # Apply tier bonuses
            tier_bonus = 0.0
            if is_high_proficiency and is_high_presence and is_in_pool:
                # TIER 1: High proficiency + high presence + in pool
                tier_bonus = 0.15
                components["tier"] = "T1_POOL_AND_POWER"
            elif is_high_proficiency and is_in_pool:
                # TIER 2: High proficiency, in pool (comfort pick targeting)
                tier_bonus = 0.10
                components["tier"] = "T2_POOL_TARGET"
            elif is_high_presence:
                # TIER 3: High presence only (global power ban)
                tier_bonus = 0.05
                components["tier"] = "T3_GLOBAL_POWER"
            else:
                # TIER 4: General meta ban
                tier_bonus = 0.0
                components["tier"] = "T4_GENERAL"

            components["tier_bonus"] = round(tier_bonus, 3)

            # Pool depth exploitation (additive - shallow pools = higher impact)
            pool_bonus = 0.0
            if pool_size >= 1:
                if pool_size <= 3:
                    pool_bonus = 0.08
                elif pool_size <= 5:
                    pool_bonus = 0.04
            components["pool_depth_bonus"] = round(pool_bonus, 3)

            priority = base_priority + tier_bonus + pool_bonus
        else:
            # Phase 2: Keep original calculation for now (Task 14 will update)
            proficiency_component = proficiency["score"] * 0.4
            components["proficiency"] = round(proficiency_component, 3)

            meta_score = self.meta_scorer.get_meta_score(champion)
            meta_component = meta_score * 0.3
            components["meta"] = round(meta_component, 3)

            games = proficiency.get("games", 0)
            comfort = min(1.0, games / 10)
            comfort_component = comfort * 0.2
            components["comfort"] = round(comfort_component, 3)

            conf = proficiency.get("confidence", "LOW")
            conf_bonus = {"HIGH": 0.1, "MEDIUM": 0.05, "LOW": 0.0}.get(conf, 0)
            components["confidence_bonus"] = round(conf_bonus, 3)

            pool_bonus = 0.0
            if pool_size >= 1:
                if pool_size <= 3:
                    pool_bonus = 0.20
                elif pool_size <= 5:
                    pool_bonus = 0.10
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

    def _get_presence_score(self, champion: str) -> float:
        """Get champion's presence rate as a score.

        Presence = pick_rate + ban_rate (how contested is this pick?)

        Returns:
            Float 0.0-1.0 representing presence
        """
        meta_data = self.meta_scorer._meta_stats.get(champion, {})
        presence = meta_data.get("presence", 0)
        return presence  # Already 0-1 scale

    def _get_flex_value(self, champion: str) -> float:
        """Get champion's flex pick value based on role versatility.

        Champions that can play multiple roles are harder to plan against
        and more valuable to ban.

        Returns:
            Float 0.0-0.8 representing flex value
        """
        probs = self.flex_resolver.get_role_probabilities(champion)
        if not probs:
            return 0.2  # Unknown - assume single role

        # Count roles with >= 15% probability (viable roles)
        viable_roles = [r for r, p in probs.items() if p >= 0.15]

        if len(viable_roles) >= 3:
            return 0.8  # True flex (3+ roles)
        elif len(viable_roles) >= 2:
            return 0.5  # Dual flex
        return 0.2  # Single role

    def _get_archetype_counter_score(self, champion: str, enemy_picks: list[str]) -> float:
        """Calculate how much banning this champion disrupts enemy's archetype.

        Args:
            champion: Champion to potentially ban
            enemy_picks: Champions enemy has already picked

        Returns:
            Float 0.0-1.0 representing archetype disruption value
        """
        if not enemy_picks:
            return 0.0

        # Get enemy's emerging archetype
        enemy_arch = self.archetype_service.calculate_team_archetype(enemy_picks)
        enemy_primary = enemy_arch.get("primary")

        if not enemy_primary:
            return 0.0

        # How much does this champion contribute to enemy's direction?
        contribution = self.archetype_service.get_contribution_to_archetype(
            champion, enemy_primary
        )

        # Also check alignment boost - would adding this champion increase enemy's alignment?
        current_alignment = enemy_arch.get("alignment", 0)
        with_champ = self.archetype_service.calculate_team_archetype(
            enemy_picks + [champion]
        )
        new_alignment = with_champ.get("alignment", 0)
        alignment_boost = max(0, new_alignment - current_alignment)

        # Combine contribution and alignment boost
        return round(contribution * 0.6 + alignment_boost * 0.4, 3)

    def _get_synergy_denial_score(self, champion: str, enemy_picks: list[str]) -> float:
        """Calculate synergy denial value of banning this champion.

        Would this champion complete a strong synergy with enemy picks?

        Args:
            champion: Champion to potentially ban
            enemy_picks: Champions enemy has already picked

        Returns:
            Float 0.0-1.0 representing synergy denial value
        """
        if not enemy_picks:
            return 0.0

        # Calculate synergy gain if enemy added this champion
        synergy_with = self.synergy_service.calculate_team_synergy(
            enemy_picks + [champion]
        )
        synergy_without = self.synergy_service.calculate_team_synergy(enemy_picks)

        synergy_gain = synergy_with["total_score"] - synergy_without["total_score"]

        # Scale the gain (typical range is 0.0-0.2) to 0-1
        return round(max(0, min(1.0, synergy_gain * 3)), 3)

    def _get_role_denial_score(
        self,
        champion: str,
        enemy_picks: list[str],
        enemy_players: list[dict]
    ) -> float:
        """Calculate role denial value of banning this champion.

        Does banning this deny a role the enemy still needs to fill?

        Args:
            champion: Champion to potentially ban
            enemy_picks: Champions enemy has already picked
            enemy_players: Enemy player info with 'name' and 'role'

        Returns:
            Float 0.0-0.8 representing role denial value
        """
        if not enemy_players:
            return 0.0

        # Infer which roles enemy has filled
        filled_roles = set()
        for pick in enemy_picks:
            probs = self.flex_resolver.get_role_probabilities(pick)
            if probs:
                primary_role = max(probs, key=probs.get)
                filled_roles.add(primary_role)

        unfilled_roles = {"top", "jungle", "mid", "bot", "support"} - filled_roles

        if not unfilled_roles:
            return 0.0

        # Can this champion fill an unfilled role?
        champ_probs = self.flex_resolver.get_role_probabilities(champion)
        if not champ_probs:
            return 0.0

        for role in unfilled_roles:
            if champ_probs.get(role, 0) >= 0.25:  # Viable in this role
                # Check if any enemy player in this role has this in their pool
                player = next(
                    (p for p in enemy_players if p.get("role") == role),
                    None
                )
                if player:
                    pool = self.proficiency_scorer.get_player_champion_pool(
                        player["name"], min_games=2
                    )
                    pool_champs = [e["champion"] for e in pool[:10]]
                    if champion in pool_champs:
                        return 0.8  # High denial - in player's pool for unfilled role
                return 0.4  # General denial - fills unfilled role

        return 0.0
