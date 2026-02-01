"""Player proficiency scoring with confidence tracking."""
import json
from pathlib import Path
from typing import Optional

from ban_teemo.services.scorers.skill_transfer_service import SkillTransferService
from ban_teemo.utils.champion_roles import ChampionRoleLookup
from ban_teemo.utils.role_normalizer import normalize_role


class ProficiencyScorer:
    """Scores player proficiency on champions."""

    CONFIDENCE_THRESHOLDS = {"HIGH": 8, "MEDIUM": 4, "LOW": 1}
    TRANSFER_MAX_WEIGHT = 0.5

    # Champion Comfort + Role Strength constants
    COMFORT_BASELINE = 0.5  # Starting comfort for all unplayed champions
    G_FULL = 10  # Games for full comfort scaling
    # Raised from 0.95 to 1.0 for better score differentiation
    PROFICIENCY_CAP = 1.0
    ROLE_STRENGTH_BONUS = 0.3  # Max bonus from role strength

    def __init__(self, knowledge_dir: Optional[Path] = None):
        if knowledge_dir is None:
            knowledge_dir = Path(__file__).parents[5] / "knowledge"
        self.knowledge_dir = knowledge_dir
        self._proficiency_data: dict = {}
        self.skill_transfer = SkillTransferService(knowledge_dir)
        self.champion_roles = ChampionRoleLookup(knowledge_dir)
        self._load_data()

    def _load_data(self):
        """Load player proficiency data."""
        prof_path = self.knowledge_dir / "player_proficiency.json"
        if prof_path.exists():
            with open(prof_path) as f:
                data = json.load(f)
                self._proficiency_data = data.get("proficiencies", {})

    def get_proficiency_score(self, player_name: str, champion_name: str) -> tuple[float, str]:
        """Get proficiency score and confidence for player-champion pair."""
        if player_name not in self._proficiency_data:
            return 0.5, "NO_DATA"

        player_data = self._proficiency_data[player_name]
        if champion_name not in player_data:
            return 0.5, "NO_DATA"

        champ_data = player_data[champion_name]
        games = champ_data.get("games_raw", champ_data.get("games_weighted", 0))
        win_rate = champ_data.get("win_rate_weighted", champ_data.get("win_rate", 0.5))

        games_factor = min(1.0, games / 10)
        score = win_rate * 0.6 + games_factor * 0.4
        confidence = champ_data.get("confidence") or self._games_to_confidence(int(games))

        return round(score, 3), confidence

    def get_role_proficiency(
        self,
        champion_name: str,
        role: str,
        team_players: list[dict],
    ) -> tuple[float, str, Optional[str]]:
        """Return proficiency for the player assigned to a role."""
        normalized_role = normalize_role(role)
        if not normalized_role:
            return 0.5, "NO_DATA", None

        player = next(
            (p for p in team_players if normalize_role(p.get("role")) == normalized_role),
            None,
        )
        if not player:
            return 0.5, "NO_DATA", None

        score, conf = self.get_proficiency_score(player["name"], champion_name)
        return score, conf, player["name"]

    def calculate_role_strength(self, player_name: str, role: str) -> Optional[float]:
        """Calculate player's role strength using win_rate-weighted average.

        Role strength measures "how strong is this player in this role generally?"
        This is separate from champion-specific comfort.

        Returns:
            Weighted average win_rate, or None if no data for this role.

        Invariants:
            - Only considers champions the player has actually played
            - Only includes champions whose primary role matches requested role
            - Weights by games_weighted (more played = more influence)
            - Uses win_rate_weighted as the skill signal (avoids double-counting games)
            - Returns None if player has no relevant data
        """
        normalized_role = normalize_role(role)
        if not normalized_role:
            return None

        if player_name not in self._proficiency_data:
            return None

        player_data = self._proficiency_data[player_name]
        role_champions: list[tuple[float, float]] = []  # (win_rate, games)

        for champ, data in player_data.items():
            champ_role = self.champion_roles.get_primary_role(champ)
            if champ_role != normalized_role:
                continue

            games = data.get("games_weighted", data.get("games_raw", 0))
            if games <= 0:
                continue

            win_rate = data.get("win_rate_weighted", data.get("win_rate"))
            if win_rate is None:
                continue
            role_champions.append((float(win_rate), games))

        if not role_champions:
            return None

        total_weight = sum(games for _, games in role_champions)
        weighted_sum = sum(win_rate * games for win_rate, games in role_champions)
        return round(weighted_sum / total_weight, 3)

    def get_champion_proficiency(
        self,
        champion_name: str,
        role: str,
        team_players: list[dict],
    ) -> tuple[float, str, Optional[str], str]:
        """Calculate proficiency using champion comfort + role strength.

        Formula:
            comfort = COMFORT_BASELINE + (1 - COMFORT_BASELINE) * min(1.0, games / G_FULL)
            proficiency = comfort * (1 + role_strength * ROLE_STRENGTH_BONUS)
            proficiency = min(PROFICIENCY_CAP, proficiency)

        Returns:
            (score, confidence, player_name, source)
            source: "direct" | "comfort_only" | "none"

        Invariants:
            - Comfort starts at 0.5 for unplayed champions
            - More games -> higher comfort (monotonic)
            - Role strength provides additive bonus
            - Result capped at PROFICIENCY_CAP
            - NO_DATA only when player is unknown
        """
        normalized_role = normalize_role(role)
        if not normalized_role:
            return 0.5, "NO_DATA", None, "none"

        # Find player assigned to this role
        player = next(
            (p for p in team_players if normalize_role(p.get("role")) == normalized_role),
            None,
        )
        if not player:
            return 0.5, "NO_DATA", None, "none"

        player_name = player["name"]

        # Check if player exists in data
        if player_name not in self._proficiency_data:
            return 0.5, "NO_DATA", player_name, "none"

        # Calculate champion comfort (0.5 baseline + games scaling)
        player_data = self._proficiency_data.get(player_name, {})
        champ_data = player_data.get(champion_name, {})
        games = champ_data.get("games_weighted", champ_data.get("games_raw", 0))

        scalar = min(1.0, games / self.G_FULL) if games > 0 else 0.0
        comfort = self.COMFORT_BASELINE + (1 - self.COMFORT_BASELINE) * scalar

        # Calculate role strength (may be None if no role data)
        role_strength = self.calculate_role_strength(player_name, normalized_role)

        if role_strength is None:
            # No role data -> comfort only, no bonus (still capped)
            comfort = min(self.PROFICIENCY_CAP, comfort)
            confidence = self._games_to_confidence(int(games)) if games > 0 else "LOW"
            return round(comfort, 3), confidence, player_name, "comfort_only"

        # Apply role strength bonus
        proficiency = comfort * (1 + role_strength * self.ROLE_STRENGTH_BONUS)
        proficiency = min(self.PROFICIENCY_CAP, proficiency)

        confidence = self._games_to_confidence(int(games)) if games > 0 else "LOW"
        source = "direct" if games > 0 else "comfort_only"
        return round(proficiency, 3), confidence, player_name, source

    def get_role_proficiency_with_transfer(
        self,
        champion_name: str,
        role: str,
        team_players: list[dict],
        min_games: int = 4,
    ) -> tuple[float, str, Optional[str], str]:
        """Return role proficiency with skill transfer fallback.

        DEPRECATED: Use get_champion_proficiency instead.
        This method is kept for backward compatibility but should not be used
        for new code. The comfort + role strength approach provides more stable
        and predictable proficiency scores.

        Returns:
            (score, confidence, player_name, source)
            source: direct | transfer | none
        """
        score, conf, player_name = self.get_role_proficiency(
            champion_name, role, team_players
        )
        if not player_name:
            return 0.5, "NO_DATA", None, "none"

        if conf in {"HIGH", "MEDIUM"}:
            return score, conf, player_name, "direct"

        if conf not in {"LOW", "NO_DATA"}:
            return score, conf, player_name, "direct"

        pool = self.get_player_champion_pool(player_name, min_games=min_games)
        available = {
            entry["champion"]
            for entry in pool
            if entry.get("confidence") in {"HIGH", "MEDIUM"}
        }
        transfer = self.skill_transfer.get_best_transfer(champion_name, available)
        if not transfer:
            source = "direct" if conf != "NO_DATA" else "none"
            return score, conf, player_name, source

        co_play_rate = transfer.get("co_play_rate", 0)
        if not co_play_rate:
            source = "direct" if conf != "NO_DATA" else "none"
            return score, conf, player_name, source

        transfer_champ = transfer.get("champion")
        if not transfer_champ:
            source = "direct" if conf != "NO_DATA" else "none"
            return score, conf, player_name, source

        transfer_score, _ = self.get_proficiency_score(player_name, transfer_champ)
        transfer_weight = min(self.TRANSFER_MAX_WEIGHT, self.TRANSFER_MAX_WEIGHT * co_play_rate)
        blended = (score * (1 - transfer_weight)) + (transfer_score * transfer_weight)
        blended = max(0.0, min(1.0, blended))
        transfer_conf = conf if conf != "NO_DATA" else "LOW"
        return round(blended, 3), transfer_conf, player_name, "transfer"

    def _games_to_confidence(self, games: int) -> str:
        """Convert game count to confidence level."""
        if games >= self.CONFIDENCE_THRESHOLDS["HIGH"]:
            return "HIGH"
        elif games >= self.CONFIDENCE_THRESHOLDS["MEDIUM"]:
            return "MEDIUM"
        elif games >= self.CONFIDENCE_THRESHOLDS["LOW"]:
            return "LOW"
        return "NO_DATA"

    def get_player_champion_pool(self, player_name: str, min_games: int = 1) -> list[dict]:
        """Get a player's champion pool sorted by proficiency."""
        if player_name not in self._proficiency_data:
            return []

        pool = []
        for champ, data in self._proficiency_data[player_name].items():
            games = data.get("games_raw", 0)
            if games >= min_games:
                score, conf = self.get_proficiency_score(player_name, champ)
                pool.append({"champion": champ, "score": score, "games": games, "confidence": conf})

        return sorted(pool, key=lambda x: -x["score"])
