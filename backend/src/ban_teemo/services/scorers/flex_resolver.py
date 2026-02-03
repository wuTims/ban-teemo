"""Flex pick role resolution with probability estimation.

This module uses champion_role_history.json as the single source of truth
for role data. Previous versions used flex_champions.json, which has been
deprecated to eliminate data conflicts.
"""
import json
from pathlib import Path
from typing import Optional

from ban_teemo.utils.role_normalizer import (
    normalize_role as util_normalize_role,
    CANONICAL_ROLES,
    ROLE_ORDER,
)
from ban_teemo.utils.role_viability import (
    extract_current_role_viability,
    CURRENT_ROLE_THRESHOLD,
)


class FlexResolver:
    """Resolves flex pick role probabilities.

    Uses champion_role_history.json as the single source of truth for:
    - Role probability distributions (current_distribution, all_time_distribution)
    - Flex detection (derived from current_viable_roles)
    - Primary role fallback (canonical_role, pro_play_primary_role)
    """

    # Canonical output roles - lowercase: top, jungle, mid, bot, support
    VALID_ROLES = CANONICAL_ROLES

    # Minimum probability threshold to consider a role viable (>5%)
    # Filters out noise like Viego's 2% support or Rumble's 2% support
    # Using 0.051 to ensure exact 5% (like Nocturne SUP) is filtered out
    MIN_ROLE_PROBABILITY = 0.051

    # Minimum roles to be considered a flex pick
    MIN_FLEX_ROLES = 2

    # Map data file formats (from knowledge files) to canonical lowercase format
    DATA_TO_CANONICAL = {
        "JUNGLE": "jungle",
        "jungle": "jungle",
        "JNG": "jungle",
        "TOP": "top",
        "top": "top",
        "MID": "mid",
        "mid": "mid",
        "MIDDLE": "mid",
        "ADC": "bot",
        "adc": "bot",
        "BOT": "bot",
        "bot": "bot",
        "BOTTOM": "bot",
        "SUP": "support",
        "sup": "support",
        "SUPPORT": "support",
        "support": "support",
    }

    # Default role order for deterministic fallback (most common roles first)
    DEFAULT_ROLE_ORDER = ["mid", "bot", "top", "jungle", "support"]

    CURRENT_ROLE_THRESHOLD = CURRENT_ROLE_THRESHOLD

    def __init__(self, knowledge_dir: Optional[Path] = None, tournament_data_file: Optional[str] = None):
        if knowledge_dir is None:
            knowledge_dir = Path(__file__).parents[5] / "knowledge"
        self.knowledge_dir = knowledge_dir
        self._role_history_data: dict = {}
        self._primary_roles: dict[str, str] = {}  # Cached primary role lookups
        self._tournament_role_data: dict[str, dict[str, float]] = {}  # champion -> role probs
        self._load_data()
        self._load_tournament_data(tournament_data_file)

    def _load_data(self):
        """Load champion role history data (single source of truth)."""
        history_path = self.knowledge_dir / "champion_role_history.json"
        if history_path.exists():
            with open(history_path) as f:
                data = json.load(f)
                self._role_history_data = data.get("champions", {})
                # Build primary role cache for fast lookups
                for champ, champ_data in self._role_history_data.items():
                    if isinstance(champ_data, dict):
                        role = champ_data.get("canonical_role") or champ_data.get(
                            "pro_play_primary_role"
                        )
                        if role:
                            canonical = self.DATA_TO_CANONICAL.get(role, role)
                            if canonical in self.VALID_ROLES:
                                self._primary_roles[champ] = canonical

    def _load_tournament_data(self, tournament_data_file: Optional[str] = None):
        """Load tournament/replay meta and extract role distributions.

        Only stores data for champions NOT already in champion_role_history,
        since role_history is the richer, more authoritative source.
        """
        if tournament_data_file is None:
            tournament_data_file = "tournament_meta.json"
        meta_path = self.knowledge_dir / tournament_data_file
        if not meta_path.exists():
            return

        with open(meta_path) as f:
            data = json.load(f)

        champions = data.get("champions", {})
        for champ_name, champ_data in champions.items():
            if champ_name in self._role_history_data:
                continue  # role_history takes precedence
            roles = champ_data.get("roles", {})
            if not roles:
                continue
            distribution = self._tournament_meta_to_distribution(roles)
            if distribution:
                self._tournament_role_data[champ_name] = distribution

    def _tournament_meta_to_distribution(self, roles: dict) -> dict[str, float]:
        """Convert tournament meta role pick counts to a probability distribution.

        Args:
            roles: Dict like {"top": {"picks": 27, ...}, "support": {"picks": 1, ...}}

        Returns:
            Normalized probability dict with MIN_ROLE_PROBABILITY filter applied,
            e.g. {"top": 0.964, "support": 0.036} -> {"top": 1.0} after filtering.
        """
        pick_counts: dict[str, int] = {}
        for role_key, role_data in roles.items():
            normalized = util_normalize_role(role_key)
            if not normalized:
                continue
            picks = role_data.get("picks", 0)
            if picks > 0:
                pick_counts[normalized] = pick_counts.get(normalized, 0) + picks

        if not pick_counts:
            return {}

        total = sum(pick_counts.values())
        raw_probs = {role: count / total for role, count in pick_counts.items()}

        # Filter by MIN_ROLE_PROBABILITY
        filtered = {
            role: prob for role, prob in raw_probs.items()
            if prob >= self.MIN_ROLE_PROBABILITY
        }

        # Re-normalize
        total_filtered = sum(filtered.values())
        if total_filtered > 0:
            return {role: prob / total_filtered for role, prob in filtered.items()}
        return {}

    def get_role_probabilities(
        self, champion_name: str, filled_roles: Optional[set[str]] = None
    ) -> dict[str, float]:
        """Get role probability distribution for a champion.

        Returns probabilities using canonical role names (top, jungle, mid, bot, support).
        Uses champion_role_history.json as the single source of truth.

        FALLBACK STRATEGY:
        Each level addresses a different data availability scenario, from best data
        (recent meta) to worst (unknown champion). Earlier levels are more accurate
        because they reflect current professional play patterns.

        Level 1: current_viable_roles + current_distribution
            - WHY: Recent split data reflects current meta. Pantheon might be
              viable mid now but wasn't historically. Current data catches this.
            - WHEN: Champion has current split data with sufficient sample size.

        Level 2: all_time_distribution
            - WHY: Historical data provides reasonable estimates when current
              split data is missing (e.g., champion wasn't picked this split).
            - WHEN: Champion has historical data but no current split data.
            - NOTE: Uses MIN_ROLE_PROBABILITY threshold to filter noise roles.

        Level 3: canonical_role / pro_play_primary_role
            - WHY: Some champions are one-tricks (Yuumi support, Karthus jungle).
              If we only know their primary role, assign 100% probability there.
            - WHEN: Champion has role data but no distribution data available.

        Level 4: DEFAULT_ROLE_ORDER (unknown champions)
            - WHY: New champions or those never seen in pro play need a fallback.
              Default order prioritizes solo lanes where new picks are most common.
            - WHEN: Champion has no data at all in our knowledge base.
        """
        # Normalize filled_roles to canonical lowercase
        filled = set()
        if filled_roles:
            for role in filled_roles:
                normalized = util_normalize_role(role)
                if normalized:
                    filled.add(normalized)

        champ_data = self._role_history_data.get(champion_name)
        if isinstance(champ_data, dict):
            # ═══════════════════════════════════════════════════════════════════
            # LEVEL 1: Current viable roles + current distribution (BEST DATA)
            # Use recent split data - most accurate for current meta
            # ═══════════════════════════════════════════════════════════════════
            current_roles, has_current = extract_current_role_viability(
                champ_data, threshold=self.CURRENT_ROLE_THRESHOLD
            )

            if has_current:
                # Use current_viable_roles as the definitive role set
                if not current_roles:
                    return {}

                # Get distribution probabilities, filtered to current viable roles
                current_dist = champ_data.get("current_distribution") or {}
                probs = self._distribution_to_probs(
                    current_dist,
                    filled,
                    threshold=0.0,  # Already filtered by current_viable_roles
                    allowed_roles=current_roles,
                )
                if probs:
                    return probs

                # If current_distribution is missing/empty, use uniform over viable roles
                # (rare edge case - we have viable roles but no percentage breakdown)
                available_roles = {role for role in current_roles if role not in filled}
                if available_roles:
                    prob = 1.0 / len(available_roles)
                    return {role: prob for role in available_roles}
                return {}

            # ═══════════════════════════════════════════════════════════════════
            # LEVEL 2: All-time distribution (HISTORICAL DATA)
            # Use when no current split data - less accurate but still informed
            # ═══════════════════════════════════════════════════════════════════
            all_time_dist = champ_data.get("all_time_distribution") or {}
            probs = self._distribution_to_probs(
                all_time_dist,
                filled,
                threshold=self.MIN_ROLE_PROBABILITY,  # Filter noise (e.g., 2% support Viego)
            )
            if probs:
                return probs

            # Champion has data but all roles filtered out - return empty
            # (don't fall through to unknown champion fallback)
            if all_time_dist:
                return {}

        # ═══════════════════════════════════════════════════════════════════════
        # LEVEL 3: Primary role only (MINIMAL DATA)
        # Champion has a known primary role but no distribution data
        # ═══════════════════════════════════════════════════════════════════════
        if champion_name in self._primary_roles:
            primary_role = self._primary_roles[champion_name]
            if primary_role not in filled:
                return {primary_role: 1.0}
            # Primary role is filled - champion can't play other roles reliably
            return {}

        # ═══════════════════════════════════════════════════════════════════════
        # LEVEL 0 RESCUE: Tournament/replay meta (MISSING FROM ROLE HISTORY)
        # Champion exists in tournament data but not in champion_role_history.
        # Derive probabilities from tournament pick counts.
        # ═══════════════════════════════════════════════════════════════════════
        if champion_name in self._tournament_role_data:
            tournament_probs = self._tournament_role_data[champion_name]
            available = {
                role: prob for role, prob in tournament_probs.items()
                if role not in filled
            }
            total = sum(available.values())
            if total > 0:
                return {role: prob / total for role, prob in available.items()}
            return {}

        # ═══════════════════════════════════════════════════════════════════════
        # LEVEL 4: Default role order (NO DATA - unknown champion)
        # New or never-picked champion - assign to first available role
        # ═══════════════════════════════════════════════════════════════════════
        for role in self.DEFAULT_ROLE_ORDER:
            if role not in filled:
                return {role: 1.0}
        return {}

    def is_flex_pick(self, champion_name: str) -> bool:
        """Check if champion is a flex pick.

        A champion is flex if they have 2+ current viable roles.
        Derived from current_viable_roles in champion_role_history.json,
        with tournament meta fallback for missing champions.
        """
        champ_data = self._role_history_data.get(champion_name)
        if not isinstance(champ_data, dict):
            # Not in role history — check tournament meta
            if champion_name in self._tournament_role_data:
                return len(self._tournament_role_data[champion_name]) >= self.MIN_FLEX_ROLES
            return False

        current_roles, has_current = extract_current_role_viability(
            champ_data, threshold=self.CURRENT_ROLE_THRESHOLD
        )

        if has_current:
            return len(current_roles) >= self.MIN_FLEX_ROLES

        # Fall back to all_time_distribution for champions without current data
        all_time_dist = champ_data.get("all_time_distribution") or {}
        viable_roles = [
            role
            for role, pct in all_time_dist.items()
            if pct >= self.MIN_ROLE_PROBABILITY
        ]
        return len(viable_roles) >= self.MIN_FLEX_ROLES

    def normalize_role(self, role: str) -> str:
        """Normalize role name to canonical form (top, jungle, mid, bot, support)."""
        return util_normalize_role(role) or role.lower()

    def _distribution_to_probs(
        self,
        distribution: dict,
        filled_roles: set[str],
        threshold: float,
        allowed_roles: Optional[set[str]] = None,
    ) -> dict[str, float]:
        """Convert a role distribution to normalized probabilities.

        Args:
            distribution: Role -> percentage mapping (e.g., {"TOP": 0.8, "MID": 0.2})
            filled_roles: Roles already filled on the team
            threshold: Minimum percentage to include a role
            allowed_roles: If provided, only include these roles

        Returns:
            Normalized probability dict (sums to 1.0) or empty dict
        """
        probs: dict[str, float] = {}
        for role, pct in distribution.items():
            normalized = util_normalize_role(role)
            if not normalized or normalized in filled_roles:
                continue
            if allowed_roles and normalized not in allowed_roles:
                continue
            try:
                pct_val = float(pct)
            except (TypeError, ValueError):
                continue
            if pct_val >= threshold:
                probs[normalized] = pct_val

        total = sum(probs.values())
        if total > 0:
            return {role: p / total for role, p in probs.items()}
        return {}

    def finalize_role_assignments(
        self, champions: list[str]
    ) -> list[dict[str, str]]:
        """Assign champions to roles at draft end.

        Uses greedy assignment based on role probabilities. Each champion is
        assigned to its highest-probability available role.

        Args:
            champions: List of 5 champion names in pick order

        Returns:
            List of dicts with 'champion' and 'role' keys, ordered by role
            (top, jungle, mid, bot, support)
        """
        if len(champions) != 5:
            # Return as-is if not exactly 5 picks
            return [
                {"champion": champ, "role": self.DEFAULT_ROLE_ORDER[i] if i < 5 else "unknown"}
                for i, champ in enumerate(champions)
            ]

        # Build assignment matrix: for each champion, get role probabilities
        role_order = ["top", "jungle", "mid", "bot", "support"]
        assigned: dict[str, str] = {}  # role -> champion
        filled_roles: set[str] = set()

        # Get all role probabilities for each champion
        champ_probs: list[tuple[str, dict[str, float]]] = []
        for champ in champions:
            probs = self.get_role_probabilities(champ, filled_roles=set())
            champ_probs.append((champ, probs))

        # Greedy assignment: repeatedly assign the most confident (champion, role) pair
        # Tie-breaking: prefer champion with fewer viable remaining roles (less flexible
        # champions should get their sole role before flexible ones can adapt)
        remaining_champs = set(champions)
        remaining_roles = set(role_order)

        while remaining_champs and remaining_roles:
            best_score = -1.0
            best_champ = None
            best_role = None
            best_alternatives = float("inf")

            for champ in remaining_champs:
                probs = dict(champ_probs[champions.index(champ)][1])
                for role in remaining_roles:
                    score = probs.get(role, 0.0)
                    champ_alternatives = sum(
                        1 for r in remaining_roles if probs.get(r, 0.0) > 0
                    )
                    if score > best_score or (
                        score == best_score
                        and score >= 0
                        and champ_alternatives < best_alternatives
                    ):
                        best_score = score
                        best_champ = champ
                        best_role = role
                        best_alternatives = champ_alternatives

            if best_champ and best_role:
                assigned[best_role] = best_champ
                remaining_champs.remove(best_champ)
                remaining_roles.remove(best_role)
            else:
                # No valid assignment found - assign remaining arbitrarily
                for champ, role in zip(remaining_champs, remaining_roles):
                    assigned[role] = champ
                break

        # Build result in role order
        result = []
        for role in role_order:
            if role in assigned:
                result.append({"champion": assigned[role], "role": role})

        return result
