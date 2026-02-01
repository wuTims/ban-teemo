"""LLM-based reranker for pick/ban recommendations.

Uses an LLM to rerank candidates from the deterministic scoring engine,
adding strategic reasoning and contextual awareness.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

import httpx

if TYPE_CHECKING:
    from ban_teemo.models.series_context import SeriesContext

logger = logging.getLogger(__name__)

# Archetype effectiveness matrix (from archetype_counters.json)
ARCHETYPE_COUNTERS = {
    "engage": {"vs_protect": 0.8, "vs_pick": 0.8, "vs_split": 1.2, "vs_teamfight": 1.2},
    "split": {"vs_engage": 0.8, "vs_pick": 0.8, "vs_teamfight": 1.2, "vs_protect": 1.2},
    "teamfight": {"vs_engage": 0.8, "vs_split": 0.8, "vs_protect": 1.2, "vs_pick": 1.2},
    "protect": {"vs_engage": 1.2, "vs_split": 0.8, "vs_teamfight": 0.8, "vs_pick": 1.2},
    "pick": {"vs_engage": 1.2, "vs_split": 1.2, "vs_teamfight": 0.8, "vs_protect": 0.8},
}

# Standard LoL pro draft order (who picks when)
# Format: (team, action_type) - Blue=0, Red=1
DRAFT_ORDER = [
    # Ban Phase 1: 6 bans alternating
    (0, "ban"), (1, "ban"), (0, "ban"), (1, "ban"), (0, "ban"), (1, "ban"),
    # Pick Phase 1: B1, R1-R2, B2-B3, R3
    (0, "pick"), (1, "pick"), (1, "pick"), (0, "pick"), (0, "pick"), (1, "pick"),
    # Ban Phase 2: 4 bans alternating (red first)
    (1, "ban"), (0, "ban"), (1, "ban"), (0, "ban"),
    # Pick Phase 2: R4-R5, B4-B5, R6
    (1, "pick"), (0, "pick"), (0, "pick"), (1, "pick"),
]


@dataclass
class RerankedRecommendation:
    """A recommendation that has been reranked by the LLM."""

    champion: str
    original_rank: int
    new_rank: int
    original_score: float
    confidence: float
    reasoning: str
    strategic_factors: list[str] = field(default_factory=list)


@dataclass
class AdditionalSuggestion:
    """A champion suggested by the LLM that wasn't in the original candidates."""

    champion: str
    reasoning: str
    confidence: float
    role: str = ""  # Role this champion fills (top/jungle/mid/adc/support)
    for_player: str = ""  # Player this recommendation is for


@dataclass
class RerankerResult:
    """Complete result from the LLM reranker."""

    reranked: list[RerankedRecommendation]
    additional_suggestions: list[AdditionalSuggestion]
    draft_analysis: str
    raw_llm_response: Optional[dict] = None


class LLMReranker:
    """Reranks pick/ban recommendations using LLM reasoning."""

    # Nebius Token Factory API endpoint
    NEBIUS_API_URL = "https://api.tokenfactory.us-central1.nebius.com/v1/chat/completions"

    # Model options (in preference order)
    MODELS = {
        "deepseek": "deepseek-ai/DeepSeek-V3-0324-fast",  # Fast variant: ~2s latency
        "deepseek-slow": "deepseek-ai/DeepSeek-V3.2",  # Full model: ~25s latency
        "qwen3": "Qwen/Qwen3-235B-A22B-Instruct-2507",
        "llama": "meta-llama/Llama-3.3-70B-Instruct",
        "glm": "zai-org/GLM-4.5",
    }

    DEFAULT_MODEL = "deepseek"

    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_MODEL,
        timeout: float = 15.0,
    ):
        """Initialize the LLM reranker.

        Args:
            api_key: Nebius API key
            model: Model to use (deepseek, qwen3, llama, glm)
            timeout: Request timeout in seconds
        """
        self.api_key = api_key
        self.model_id = self.MODELS.get(model, self.MODELS[self.DEFAULT_MODEL])
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def close(self):
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def rerank_picks(
        self,
        candidates: list[dict],
        draft_context: dict,
        team_players: list[dict],
        enemy_players: list[dict],
        limit: int = 5,
        series_context: Optional[SeriesContext] = None,
    ) -> RerankerResult:
        """Rerank pick candidates with LLM reasoning.

        Args:
            candidates: List of candidates from PickRecommendationEngine
            draft_context: Current draft state (phase, picks, bans, etc.)
            team_players: Our team's players with name and role
            enemy_players: Enemy team's players with name and role
            limit: Number of recommendations to return
            series_context: Optional context about previous games in the series

        Returns:
            RerankerResult with reranked recommendations and analysis
        """
        # Pre-filter candidates to remove champions for already-filled OUR roles
        our_picks = draft_context.get("our_picks", [])
        filtered_candidates = self._filter_candidates_by_role(candidates, our_picks, is_ban=False)

        # Build strategic context (archetypes, synergies, counters)
        strategic_context = self._build_strategic_context(
            draft_context, team_players=team_players, enemy_players=enemy_players
        )

        # Build series context section if available
        series_section = self._build_series_context_section(series_context)

        # Build prompt
        prompt = self._build_pick_rerank_prompt(
            candidates=filtered_candidates,
            draft_context=draft_context,
            team_players=team_players,
            enemy_players=enemy_players,
            web_context=strategic_context,
            limit=limit,
            series_section=series_section,
        )

        # Call LLM
        try:
            response = await self._call_llm(prompt)
            return self._parse_pick_response(response, filtered_candidates, limit)
        except Exception as e:
            logger.error(f"LLM reranking failed: {e}")
            # Fallback: return original order
            return self._fallback_result(candidates, limit, str(e))

    def _get_champion_viable_roles(self, champ: str) -> set[str]:
        """Get all viable roles for a champion (flex-aware).

        Returns normalized role names (top, jungle, mid, adc, support).
        """
        champion_roles = self._get_champion_role_data()
        champ_data = champion_roles.get(champ, {})

        if not isinstance(champ_data, dict):
            return set()

        role_map = {
            "TOP": "top",
            "JNG": "jungle",
            "JUNGLE": "jungle",
            "MID": "mid",
            "ADC": "adc",
            "BOT": "adc",
            "SUP": "support",
            "SUPPORT": "support",
        }

        # Use current_viable_roles if available (most accurate)
        viable = champ_data.get("current_viable_roles", [])
        if viable:
            return {role_map.get(r.upper(), r.lower()) for r in viable}

        # Fall back to canonical_all
        canonical_all = champ_data.get("canonical_all", [])
        if canonical_all:
            return {role_map.get(r.upper(), r.lower()) for r in canonical_all}

        # Fall back to primary role only
        primary = self._get_champion_primary_role(champ_data)
        if primary:
            return {role_map.get(primary, primary.lower())}

        return set()

    def _filter_candidates_by_role(
        self,
        candidates: list[dict],
        picks: list[str],
        is_ban: bool = True,
    ) -> list[dict]:
        """Filter candidates to remove champions that can't fill needed roles.

        For bans: remove champions that can ONLY play roles enemy has filled
        For picks: remove champions that can ONLY play roles we have filled

        Flex champions are kept if they can play ANY unfilled role.
        """
        if not picks:
            return candidates

        roles_info = self._infer_roles_filled(picks)
        filled_roles = set(roles_info["filled"].keys())
        unfilled_roles = set(roles_info["unfilled"])

        if not filled_roles:
            return candidates

        # Filter candidates - keep if champion can play ANY unfilled role
        filtered = []
        removed = []
        for c in candidates:
            champ_name = c.get("champion_name", c.get("champion", ""))
            champ_roles = self._get_champion_viable_roles(champ_name)

            # Keep if champion can play at least one unfilled role
            can_fill_needed = bool(champ_roles & unfilled_roles)

            if can_fill_needed or not champ_roles:  # Keep if no role data
                filtered.append(c)
            else:
                removed.append(f"{champ_name} ({', '.join(champ_roles)})")

        action_type = "ban" if is_ban else "pick"
        if removed:
            logger.info(
                f"Filtered {len(removed)} {action_type} candidates (can only play filled roles): "
                f"{removed[:5]}"
            )

        return filtered if filtered else candidates  # Fallback to original if all filtered

    async def rerank_bans(
        self,
        candidates: list[dict],
        draft_context: dict,
        our_players: list[dict],
        enemy_players: list[dict],
        limit: int = 5,
        series_context: Optional[SeriesContext] = None,
    ) -> RerankerResult:
        """Rerank ban candidates with LLM reasoning.

        Args:
            candidates: List of candidates from BanRecommendationService
            draft_context: Current draft state
            our_players: Our team's players
            enemy_players: Enemy team's players
            limit: Number of recommendations to return
            series_context: Optional context about previous games in the series

        Returns:
            RerankerResult with reranked ban recommendations
        """
        # Pre-filter candidates to remove champions for already-filled enemy roles
        enemy_picks = draft_context.get("enemy_picks", [])
        filtered_candidates = self._filter_candidates_by_role(candidates, enemy_picks, is_ban=True)

        # Build strategic context (archetypes, synergies, disruption targets)
        strategic_context = self._build_strategic_context(
            draft_context, team_players=our_players, enemy_players=enemy_players
        )

        # Build series context section if available
        series_section = self._build_series_context_section(series_context)

        prompt = self._build_ban_rerank_prompt(
            candidates=filtered_candidates,
            draft_context=draft_context,
            our_players=our_players,
            enemy_players=enemy_players,
            web_context=strategic_context,
            limit=limit,
            series_section=series_section,
        )

        try:
            response = await self._call_llm(prompt)
            return self._parse_ban_response(response, filtered_candidates, limit)
        except Exception as e:
            logger.error(f"LLM ban reranking failed: {e}")
            return self._fallback_result(candidates, limit, str(e))

    def _is_phase_1(self, phase: str) -> bool:
        """Check if we're in phase 1 (early draft)."""
        return "1" in phase or "BAN_PHASE_1" in phase or "PICK_PHASE_1" in phase

    def _get_pick_context_type(self, draft_context: dict) -> str:
        """Determine the pick context: 'first_pick', 'responding', or 'late_draft'.

        Returns context based on:
        - Number of our picks vs enemy picks
        - Phase of draft
        - Team side
        """
        our_picks = draft_context.get("our_picks", [])
        enemy_picks = draft_context.get("enemy_picks", [])
        phase = draft_context.get("phase", "")

        # Phase 2 is always "late_draft" with full information
        if "2" in phase:
            return "late_draft"

        # In Phase 1, check if we're picking blind or responding
        if len(enemy_picks) == 0:
            return "first_pick"  # No enemy picks yet - true blind pick
        elif len(our_picks) == 0:
            return "responding"  # Enemy picked, we haven't - can counter
        elif len(enemy_picks) > len(our_picks):
            return "responding"  # Enemy has more picks - can counter their latest
        else:
            return "first_pick"  # We're picking blind relative to enemy's next pick

    def _build_phase1_pick_prompt(
        self,
        candidates: list[dict],
        draft_context: dict,
        team_players: list[dict],
        enemy_players: list[dict],
        web_context: str,
        limit: int,
        series_section: str = "",
    ) -> str:
        """Build prompt for Phase 1 picks - focused on blind pick safety and meta power."""
        our_picks = draft_context.get('our_picks', [])
        enemy_picks = draft_context.get('enemy_picks', [])
        pick_type = self._get_pick_context_type(draft_context)

        # Add fearless mode context
        fearless_section = ""
        fearless_blocked = draft_context.get('fearless_blocked', [])
        if fearless_blocked:
            fearless_section = f"""
## FEARLESS DRAFT MODE
Champions permanently unavailable (picked in previous games): {', '.join(fearless_blocked)}
These champions CANNOT be picked or banned - do not suggest them."""

        # Determine pick context based on situation
        if pick_type == "first_pick":
            pick_context = """
## Pick Context: BLIND PICK / FIRST PICK
No enemy picks to counter yet. You MUST prioritize:

1. **HARD TO COUNTER** - Champions with no hard counters in pro play
2. **FLEX VALUE** - Can go multiple roles (hides information)
3. **META POWER** - Must-pick champions dominating current patch
4. **SAFE LANING** - Wins or goes even in most matchups

Avoid: Easily counterable champions, niche picks, late-game scaling without safety"""

        elif pick_type == "responding":
            pick_context = f"""
## Pick Context: RESPONDING TO ENEMY PICKS
Enemy has picked: {enemy_picks}

You CAN consider counter-picks to their revealed champions:
1. **COUNTER POTENTIAL** - Champions that beat their picks
2. **DENY SYNERGIES** - Pick champions that break their emerging comp
3. **META POWER** - Still prioritize strong meta picks
4. **FLEX VALUE** - Hide your composition direction

Balance countering with not being counterable yourself."""

        else:  # late_draft
            pick_context = f"""
## Pick Context: LATE DRAFT
Our picks: {our_picks}
Enemy picks: {enemy_picks}

Full information available. Focus on:
1. **COMPLETE OUR COMPOSITION** - Fill missing roles/archetypes
2. **COUNTER ENEMY COMP** - Direct counters to their strategy
3. **SYNERGY COMPLETION** - Finish our team's combos"""

        series_block = f"\n{series_section}\n" if series_section else ""

        # Build available picks section for unfilled roles
        available_picks_section = self._build_available_picks_section(draft_context, team_players)
        available_block = f"\n{available_picks_section}\n" if available_picks_section else ""

        return f"""You are an expert League of Legends professional draft analyst. This is PHASE 1 - early draft where information is limited.

## Current Draft State
- Phase: {draft_context.get('phase', 'PICK_PHASE_1')}
- Patch: {draft_context.get('patch', 'Unknown')}
- Our Team: {draft_context.get('our_team', 'Unknown')}
- Enemy Team: {draft_context.get('enemy_team', 'Unknown')}
- Our Picks: {our_picks}
- Enemy Picks: {enemy_picks}
- Banned: {draft_context.get('banned', [])}
{fearless_section}
{pick_context}
{series_block}
## Player & Meta Context
{web_context}
{available_block}
## Algorithm Recommendations
{self._format_pick_candidates(candidates)}

## PHASE 1 PICK PRIORITIES (in order):

1. **META POWER** (highest priority in Phase 1)
   - Must-pick champions dominating current patch
   - High priority contested picks
   - Champions with >55% presence in pro play

2. **BLIND PICK SAFETY**
   - Champions with few hard counters
   - Safe laning in most matchups
   - Example: Orianna mid is safe, Kassadin is risky blind

3. **FLEX VALUE**
   - Champions that can go multiple roles
   - Hides information from enemy
   - Forces enemy to respect multiple positions

4. **PLAYER COMFORT** (important in Phase 1)
   - High win-rate comfort picks for our players
   - Signature champions

5. **COUNTER POTENTIAL** (only if enemy has picked)
   - Champions that counter revealed enemy picks

## CRITICAL RULES:
1. **"reranked" MUST only contain champions from the Algorithm Recommendations above**
   - You are REORDERING the existing candidates, not replacing them
   - Do NOT add new champions to "reranked" - only reorder the ones provided
2. **"additional_suggestions" is for champions NOT in the Algorithm Recommendations**
   - Suggest strong meta picks for unfilled roles from the Available Champions section
   - These are bonus suggestions beyond the algorithm's candidates

## Output (respond ONLY with valid JSON, no markdown)
{{
  "reranked": [
    {{
      "champion": "ChampionName (MUST be from Algorithm Recommendations)",
      "original_rank": 1,
      "new_rank": 1,
      "confidence": 0.85,
      "reasoning": "Why this is a strong Phase 1 pick - meta power, safety, flex value",
      "strategic_factors": ["meta_power", "blind_safe", "flex_pick", "player_comfort"]
    }}
  ],
  "additional_suggestions": [
    {{
      "champion": "ChampionName (NOT in Algorithm Recommendations)",
      "role": "mid/top/jungle/adc/support",
      "reasoning": "Why this champion is strong for Phase 1 and this role",
      "confidence": 0.6
    }}
  ],
  "draft_analysis": "Phase 1 priority assessment - what we should secure early"
}}"""

    def _build_phase1_ban_prompt(
        self,
        candidates: list[dict],
        draft_context: dict,
        our_players: list[dict],
        enemy_players: list[dict],
        web_context: str,
        limit: int,
        series_section: str = "",
    ) -> str:
        """Build prompt for Phase 1 bans - meta power, flex threats, player targeting."""
        series_block = f"\n{series_section}\n" if series_section else ""

        # Add fearless mode context
        fearless_section = ""
        fearless_blocked = draft_context.get('fearless_blocked', [])
        if fearless_blocked:
            fearless_section = f"""
## FEARLESS DRAFT MODE
Champions permanently unavailable (picked in previous games): {', '.join(fearless_blocked)}
These champions CANNOT be picked or banned - do not suggest them."""

        return f"""You are an expert League of Legends professional draft analyst. This is BAN PHASE 1 - early bans before any picks.

## Current Draft State
- Phase: {draft_context.get('phase', 'BAN_PHASE_1')}
- Patch: {draft_context.get('patch', 'Unknown')}
- Our Team: {draft_context.get('our_team', 'Unknown')}
- Enemy Team: {draft_context.get('enemy_team', 'Unknown')}
- Already Banned: {draft_context.get('banned', [])}
{fearless_section}
{series_block}
## Player & Meta Context
{web_context}

## Algorithm Ban Recommendations
{self._format_ban_candidates(candidates)}

## PHASE 1 BAN PRIORITIES (in order):

1. **META POWER BANS** (highest priority)
   - OP champions dominating current patch
   - >60% presence/ban rate in pro play
   - Champions that warp draft if left open

2. **FLEX THREAT BANS**
   - Champions with strong multi-role flex
   - Hard to draft around (Aurora, Pantheon, etc.)
   - Denies enemy draft flexibility

3. **ENEMY PLAYER TARGETING**
   - High win-rate comfort picks for enemy players
   - Signature champions of star players
   - One-tricks or pocket picks

4. **DENY STRONG BLIND PICKS**
   - Champions enemy might first-pick
   - Safe laners that are hard to punish

## Output (respond ONLY with valid JSON, no markdown)
{{
  "reranked": [
    {{
      "champion": "ChampionName",
      "original_rank": 1,
      "new_rank": 1,
      "confidence": 0.85,
      "reasoning": "Why ban this in Phase 1 - meta power, flex threat, or player target",
      "strategic_factors": ["meta_power", "flex_threat", "targets_player", "deny_blind"]
    }}
  ],
  "additional_suggestions": [
    {{
      "champion": "ChampionName",
      "reasoning": "Why this ban makes sense in Phase 1",
      "confidence": 0.6
    }}
  ],
  "draft_analysis": "Phase 1 ban strategy - what threats to remove early"
}}"""

    def _build_pick_rerank_prompt(
        self,
        candidates: list[dict],
        draft_context: dict,
        team_players: list[dict],
        enemy_players: list[dict],
        web_context: str,
        limit: int,
        series_section: str = "",
    ) -> str:
        """Build the prompt for pick reranking with strategic focus."""
        # Check if this is Phase 1 - use different prompt
        phase = draft_context.get('phase', '')
        if self._is_phase_1(phase):
            return self._build_phase1_pick_prompt(
                candidates, draft_context, team_players, enemy_players,
                web_context, limit, series_section
            )

        # Phase 2 prompt (existing logic)
        # Infer which roles we've filled and still need
        our_picks = draft_context.get('our_picks', [])
        our_roles = self._infer_roles_filled(our_picks)
        enemy_picks = draft_context.get('enemy_picks', [])

        # Add fearless mode context
        fearless_section = ""
        fearless_blocked = draft_context.get('fearless_blocked', [])
        if fearless_blocked:
            fearless_section = f"""
## FEARLESS DRAFT MODE
Champions permanently unavailable (picked in previous games): {', '.join(fearless_blocked)}
These champions CANNOT be picked or banned - do not suggest them."""

        role_context = ""
        if our_roles["unfilled"]:
            filled_str = ", ".join(f"{r}: {c}" for r, c in our_roles["filled"].items()) if our_roles["filled"] else "none"
            unfilled_str = ", ".join(our_roles["unfilled"])
            role_context = f"""
## Our Role Status (CRITICAL - prioritize picks for unfilled roles!)
- Filled roles: {filled_str}
- NEED TO FILL: {unfilled_str}
- Focus recommendations on champions that fill these unfilled roles"""

        series_block = f"\n{series_section}\n" if series_section else ""

        # Build available picks section for unfilled roles
        available_picks_section = self._build_available_picks_section(draft_context, team_players)
        available_block = f"\n{available_picks_section}\n" if available_picks_section else ""

        # Build player-role mapping for output format
        player_roles = []
        for p in team_players:
            role = p.get("role", "").lower()
            name = p.get("name", "Unknown")
            if role in our_roles.get("unfilled", []):
                player_roles.append(f"{name} ({role.upper()})")
        players_needing_picks = ", ".join(player_roles) if player_roles else "None"

        return f"""You are an expert League of Legends professional draft analyst. Your PRIMARY goal is to identify picks that COUNTER the enemy's draft strategy or COMPLETE powerful team compositions.

## Current Draft State
- Phase: {draft_context.get('phase', 'UNKNOWN')}
- Patch: {draft_context.get('patch', 'Unknown')}
- Our Team: {draft_context.get('our_team', 'Unknown')}
- Enemy Team: {draft_context.get('enemy_team', 'Unknown')}
- Our Picks: {our_picks}
- Enemy Picks: {enemy_picks}
- All Bans: {draft_context.get('banned', [])}
{fearless_section}
- **Players Still Needing Picks**: {players_needing_picks}
{role_context}
{series_block}
## Strategic Analysis
{web_context}
{available_block}
## Algorithm Recommendations
{self._format_pick_candidates(candidates)}

## PRIORITY RANKING (in order of importance):

1. **COUNTER ENEMY STRATEGY** (highest priority)
   - What archetype are they building? (engage, split, teamfight, protect, pick)
   - What champions HARD COUNTER that strategy?
   - Example: Enemy building dive? Consider Janna, Poppy, Lulu. Enemy has no engage? Go scaling.

2. **COMPLETE SYNERGIES**
   - What combos can we complete with our existing picks?
   - Orianna + ball delivery (Nocturne, J4, Vi, Rell)
   - Yasuo + knockup enablers
   - Protect comp with hypercarry

3. **DISRUPT ENEMY WIN CONDITION**
   - What pick denies their key champion or combo?
   - First-pick contested power picks

4. **META POWER** (secondary)
   - Currently strong pro play champions

5. **Player Comfort** (tertiary, tiebreaker only)
   - Only matters if multiple options are strategically equal

## CRITICAL RULES:
1. **"reranked" MUST only contain champions from the Algorithm Recommendations above**
   - You are REORDERING the existing candidates, not replacing them
   - Do NOT add new champions to "reranked" - only reorder the ones provided
2. **"additional_suggestions" is for champions NOT in the Algorithm Recommendations**
   - Suggest strategic picks for unfilled roles from the Available Champions section
   - These are bonus suggestions beyond the algorithm's candidates

## Output (respond ONLY with valid JSON, no markdown)
{{
  "reranked": [
    {{
      "champion": "ChampionName (MUST be from Algorithm Recommendations)",
      "original_rank": 1,
      "new_rank": 1,
      "confidence": 0.85,
      "reasoning": "WHY this counters enemy or completes our comp - be specific",
      "strategic_factors": ["counters_dive", "completes_orianna_combo", "denies_enemy_synergy"]
    }}
  ],
  "additional_suggestions": [
    {{
      "champion": "ChampionName (NOT in Algorithm Recommendations)",
      "role": "mid/top/jungle/adc/support",
      "for_player": "PlayerName",
      "reasoning": "Strategic reason this DISRUPTS enemy or ENABLES our win condition",
      "confidence": 0.6
    }}
  ],
  "draft_analysis": "Enemy strategy: [what they're building]. Counter picks: [specific champions] for [player/role] because [reason]."
}}"""

    def _get_champion_role_data(self) -> dict:
        """Load and cache champion role data from champion_role_history.json."""
        if not hasattr(self, "_champion_role_cache"):
            try:
                from pathlib import Path

                possible_paths = [
                    Path("knowledge/champion_role_history.json"),
                    Path(__file__).parent.parent.parent.parent.parent / "knowledge" / "champion_role_history.json",
                ]

                for path in possible_paths:
                    if path.exists():
                        with open(path) as f:
                            data = json.load(f)
                            self._champion_role_cache = data.get("champions", {})
                            logger.info(f"Loaded {len(self._champion_role_cache)} champion role mappings")
                            return self._champion_role_cache

                logger.warning("champion_role_history.json not found")
                self._champion_role_cache = {}
            except Exception as e:
                logger.error(f"Failed to load champion role data: {e}")
                self._champion_role_cache = {}

        return self._champion_role_cache

    def _get_champion_primary_role(self, champ_data: dict) -> str | None:
        """Get the primary role for a champion, using fallbacks."""
        # Try canonical_role first
        role = champ_data.get("canonical_role")
        if role:
            return role.upper()

        # Fall back to pro_play_primary_role
        role = champ_data.get("pro_play_primary_role")
        if role:
            return role.upper()

        # Fall back to highest distribution role
        distribution = champ_data.get("all_time_distribution", {})
        if distribution:
            return max(distribution.items(), key=lambda x: x[1])[0].upper()

        return None

    def _infer_roles_filled(self, picks: list[str]) -> dict:
        """Infer which roles are filled based on picks.

        Uses champion_role_history.json for accurate role data.

        Returns dict with 'filled' roles and 'unfilled' roles.
        """
        champion_roles = self._get_champion_role_data()

        # Normalize role names (TOP -> top, SUP/SUPPORT -> support, etc.)
        role_map = {
            "TOP": "top",
            "JNG": "jungle",
            "JUNGLE": "jungle",
            "MID": "mid",
            "ADC": "adc",
            "BOT": "adc",
            "SUP": "support",
            "SUPPORT": "support",
        }

        all_roles = {"top", "jungle", "mid", "adc", "support"}
        filled_roles = set()
        role_picks = {}

        for champ in picks:
            champ_data = champion_roles.get(champ, {})
            if not isinstance(champ_data, dict):
                continue
            primary_role = self._get_champion_primary_role(champ_data)
            if primary_role:
                normalized_role = role_map.get(primary_role, primary_role.lower())
                if normalized_role in all_roles:
                    filled_roles.add(normalized_role)
                    role_picks[normalized_role] = champ

        unfilled = all_roles - filled_roles

        return {
            "filled": role_picks,
            "unfilled": list(unfilled),
        }

    def _get_champions_by_role(self, role: str) -> list[str]:
        """Get all champions that play a given role."""
        champion_roles = self._get_champion_role_data()

        role_map = {
            "top": ["TOP"],
            "jungle": ["JNG", "JUNGLE"],
            "mid": ["MID"],
            "adc": ["ADC", "BOT"],
            "support": ["SUP", "SUPPORT"],
        }

        target_roles = role_map.get(role.lower(), [])
        champions = []

        for champ, data in champion_roles.items():
            if not isinstance(data, dict):
                continue
            primary_role = self._get_champion_primary_role(data)
            if primary_role and primary_role in target_roles:
                champions.append(champ)

        return champions

    def _get_available_champions_by_role(
        self,
        role: str,
        banned: list[str],
        picked: list[str],
        limit: int = 10,
    ) -> list[str]:
        """Get available champions for a role, sorted by meta strength.

        Returns champions that are:
        - Not banned
        - Not already picked
        - Viable for the given role
        - Sorted by pro play presence/strength
        """
        champion_roles = self._get_champion_role_data()
        unavailable = set(c.lower() for c in banned + picked)

        role_map = {
            "top": ["TOP"],
            "jungle": ["JNG", "JUNGLE"],
            "mid": ["MID"],
            "adc": ["ADC", "BOT"],
            "support": ["SUP", "SUPPORT"],
        }
        target_roles = role_map.get(role.lower(), [])

        candidates = []
        for champ, data in champion_roles.items():
            if not isinstance(data, dict):
                continue
            if champ.lower() in unavailable:
                continue

            # Check if champion can play this role (primary or viable)
            primary_role = self._get_champion_primary_role(data)
            viable_roles = data.get("current_viable_roles", [])

            can_play = False
            if primary_role and primary_role in target_roles:
                can_play = True
            elif any(r.upper() in target_roles for r in viable_roles):
                can_play = True

            if can_play:
                # Use pro play presence as strength indicator
                presence = data.get("pro_play_presence", 0)
                win_rate = data.get("pro_play_win_rate", 0.5)
                # Simple scoring: presence * win_rate adjustment
                score = presence * (0.5 + win_rate)
                candidates.append((champ, score))

        # Sort by score descending
        candidates.sort(key=lambda x: -x[1])
        return [c[0] for c in candidates[:limit]]

    def _build_available_picks_section(
        self,
        draft_context: dict,
        team_players: list[dict],
    ) -> str:
        """Build a section showing available strong picks per unfilled role.

        This gives the LLM visibility into the full champion pool beyond
        the baseline candidates.
        """
        our_picks = draft_context.get("our_picks", [])
        banned = draft_context.get("banned", [])
        all_picked = our_picks + draft_context.get("enemy_picks", [])

        roles_info = self._infer_roles_filled(our_picks)
        unfilled_roles = roles_info.get("unfilled", [])

        if not unfilled_roles:
            return ""

        lines = ["## Available Champions by Role (Top Meta Picks)"]
        lines.append("These champions are available and strong in the current meta:")

        # Map players to roles
        player_role_map = {}
        for p in team_players:
            role = p.get("role", "").lower()
            player_role_map[role] = p.get("name", "Unknown")

        for role in unfilled_roles:
            available = self._get_available_champions_by_role(
                role, banned, all_picked, limit=8
            )
            if available:
                player = player_role_map.get(role, "TBD")
                lines.append(f"\n**{role.upper()}** (for {player}):")
                lines.append(f"  {', '.join(available)}")

        return "\n".join(lines) if len(lines) > 2 else ""

    def _build_ban_rerank_prompt(
        self,
        candidates: list[dict],
        draft_context: dict,
        our_players: list[dict],
        enemy_players: list[dict],
        web_context: str,
        limit: int,
        series_section: str = "",
    ) -> str:
        """Build the prompt for ban reranking with strategic disruption focus."""
        phase = draft_context.get("phase", "")

        # Use Phase 1 specific prompt for early bans
        if self._is_phase_1(phase):
            return self._build_phase1_ban_prompt(
                candidates, draft_context, our_players, enemy_players,
                web_context, limit, series_section
            )

        # Phase 2 ban prompt (existing logic for synergy disruption)
        phase_guidance = "Phase 2: Target SYNERGY COMPLETERS and COUNTERS to our composition."

        # Infer which roles enemy has filled
        enemy_picks = draft_context.get('enemy_picks', [])
        enemy_roles = self._infer_roles_filled(enemy_picks)
        our_picks = draft_context.get('our_picks', [])
        our_roles = self._infer_roles_filled(our_picks)

        role_context = ""
        if enemy_roles["filled"]:
            filled_str = ", ".join(f"{r}: {c}" for r, c in enemy_roles["filled"].items())
            unfilled_str = ", ".join(enemy_roles["unfilled"]) if enemy_roles["unfilled"] else "none"

            # Build per-role invalid examples
            role_invalid_examples = {}
            for role in enemy_roles["filled"].keys():
                role_champs = self._get_champions_by_role(role)[:8]  # Get more to show variety
                role_invalid_examples[role] = role_champs

            role_context = f"""
## ⚠️ CRITICAL: Enemy Role Status ⚠️
Enemy has ALREADY picked:
{filled_str}

Enemy still NEEDS: **{unfilled_str}**

**ROLE-BASED FILTERING (REQUIRED):**"""
            for role, champs in role_invalid_examples.items():
                picked_champ = enemy_roles["filled"].get(role, "?")
                role_context += f"\n- {role.upper()} is FILLED by {picked_champ}. DO NOT BAN: {', '.join(champs)}"

            role_context += f"""

**ONLY recommend bans for champions that can play: {unfilled_str}**
Any ban of a {', '.join(enemy_roles['filled'].keys())} champion is WASTED."""

        # Add fearless mode context
        fearless_section = ""
        fearless_blocked = draft_context.get('fearless_blocked', [])
        if fearless_blocked:
            fearless_section = f"""
## FEARLESS DRAFT MODE
Champions permanently unavailable (picked in previous games): {', '.join(fearless_blocked)}
These champions CANNOT be picked or banned - do not suggest them."""

        series_block = f"\n{series_section}\n" if series_section else ""
        return f"""You are an expert League of Legends professional draft analyst. Your PRIMARY goal is to DISRUPT the enemy's draft strategy and DENY their win conditions.

## Current Draft State
- Phase: {draft_context.get('phase', 'UNKNOWN')}
- Patch: {draft_context.get('patch', 'Unknown')}
- Our Team: {draft_context.get('our_team', 'Unknown')}
- Enemy Team: {draft_context.get('enemy_team', 'Unknown')}
- Our Picks: {our_picks}
- Enemy Picks: {enemy_picks}
- Already Banned: {draft_context.get('banned', [])}
{fearless_section}
{role_context}
{series_block}
## Strategic Analysis
{web_context}

## Algorithm Ban Recommendations
{self._format_ban_candidates(candidates)}

## Phase Context
{phase_guidance}

## PRIORITY RANKING (in order of importance):

1. **BREAK ENEMY SYNERGIES** (highest priority)
   - What combo are they building? (Orianna+ball carrier, Yasuo+knockup, protect comp)
   - Ban the MISSING PIECE that completes their combo
   - Example: They have Orianna → ban Nocturne/J4/Rell to deny ball delivery

2. **DENY COUNTER TO OUR COMP**
   - What champions HARD COUNTER what we're building?
   - If we're building engage → ban Janna/Poppy
   - If we're building protect → ban assassins/dive

3. **REMOVE ARCHETYPE ENABLERS**
   - What single champion enables their entire strategy?
   - Ban the keystone pick, not comfort picks

4. **DENY FLEX/POWER PICKS** (Phase 1 priority)
   - Champions that can go multiple roles
   - Must-pick meta staples

5. **Player Pools** (tertiary, tiebreaker only)
   - Only if multiple bans are strategically equal
   - Don't just ban "comfort picks" without strategic reason

## CRITICAL: Look for UNEXPECTED but high-impact bans
Champions NOT in the candidate list that:
- Complete a powerful synergy they're building
- Hard counter our composition
- Are the keystone of their strategy

## Output (respond ONLY with valid JSON, no markdown)
{{
  "reranked": [
    {{
      "champion": "ChampionName",
      "original_rank": 1,
      "new_rank": 1,
      "confidence": 0.85,
      "reasoning": "WHY this disrupts enemy strategy - be specific about what combo/synergy it breaks",
      "strategic_factors": ["breaks_synergy", "denies_counter", "removes_archetype"]
    }}
  ],
  "additional_suggestions": [
    {{
      "champion": "ChampionName",
      "reasoning": "What enemy synergy/strategy this disrupts",
      "confidence": 0.6
    }}
  ],
  "draft_analysis": "What enemy is building + what ban breaks it"
}}"""

    def _format_players(self, players: list[dict]) -> str:
        """Format player list for prompt."""
        if not players:
            return "No player data available"
        lines = []
        for p in players:
            lines.append(f"- {p.get('name', 'Unknown')} ({p.get('role', 'unknown')})")
        return "\n".join(lines)

    def _format_pick_candidates(self, candidates: list[dict]) -> str:
        """Format pick candidates for prompt."""
        lines = []
        for i, c in enumerate(candidates[:15], 1):
            components = c.get("components", {})
            comp_str = ", ".join(f"{k}:{v:.2f}" for k, v in components.items() if isinstance(v, (int, float)))
            lines.append(
                f"{i}. {c.get('champion_name', c.get('champion', 'Unknown'))} "
                f"(role: {c.get('suggested_role', c.get('role', '?'))}, "
                f"score: {c.get('score', 0):.3f}, "
                f"player: {c.get('proficiency_player', 'unknown')})\n"
                f"   Components: {comp_str}\n"
                f"   Reasons: {', '.join(c.get('reasons', []))}"
            )
        return "\n".join(lines)

    def _format_ban_candidates(self, candidates: list[dict]) -> str:
        """Format ban candidates for prompt."""
        lines = []
        for i, c in enumerate(candidates[:15], 1):
            components = c.get("components", {})
            comp_str = ", ".join(f"{k}:{v:.2f}" for k, v in components.items() if isinstance(v, (int, float)))
            # Support both 'champion_name' and 'champion' keys
            champ_name = c.get("champion_name", c.get("champion", "Unknown"))
            lines.append(
                f"{i}. {champ_name} "
                f"(priority: {c.get('priority', 0):.3f}, "
                f"target: {c.get('target_player', 'general')})\n"
                f"   Components: {comp_str}\n"
                f"   Reasons: {', '.join(c.get('reasons', []))}"
            )
        return "\n".join(lines)

    def _build_series_context_section(
        self, series_context: Optional[SeriesContext]
    ) -> str:
        """Build prompt section with series history and tendencies.

        Args:
            series_context: Context about previous games in the series

        Returns:
            Formatted string section for the prompt, or empty string if no context
        """
        if series_context is None or not series_context.is_series_context_available:
            return ""

        lines = ["## Series Context"]
        lines.append(
            f"- Game {series_context.game_number} of series"
        )
        lines.append(
            f"- Series Score: Blue {series_context.series_score[0]} - "
            f"{series_context.series_score[1]} Red"
        )

        # Previous game summaries
        lines.append("\n### Previous Games")
        for game in series_context.previous_games:
            winner_text = "Blue won" if game.winner == "blue" else "Red won"
            lines.append(f"\n**Game {game.game_number}** ({winner_text}):")
            lines.append(f"  - Blue comp: {', '.join(game.blue_comp)}")
            lines.append(f"  - Red comp: {', '.join(game.red_comp)}")
            lines.append(f"  - Blue bans: {', '.join(game.blue_bans)}")
            lines.append(f"  - Red bans: {', '.join(game.red_bans)}")

        # Team tendencies
        if series_context.our_tendencies:
            tendencies = series_context.our_tendencies
            lines.append("\n### Our Tendencies (observed in series)")
            if tendencies.prioritized_champions:
                lines.append(
                    f"  - Priority picks: {', '.join(tendencies.prioritized_champions)}"
                )
            if tendencies.first_pick_patterns:
                lines.append(
                    f"  - First pick patterns: {', '.join(tendencies.first_pick_patterns)}"
                )
            if tendencies.banned_against_them:
                lines.append(
                    f"  - Opponents have banned: {', '.join(tendencies.banned_against_them)}"
                )

        if series_context.enemy_tendencies:
            tendencies = series_context.enemy_tendencies
            lines.append("\n### Enemy Tendencies (observed in series)")
            if tendencies.prioritized_champions:
                lines.append(
                    f"  - Priority picks: {', '.join(tendencies.prioritized_champions)}"
                )
            if tendencies.first_pick_patterns:
                lines.append(
                    f"  - First pick patterns: {', '.join(tendencies.first_pick_patterns)}"
                )
            if tendencies.banned_against_them:
                lines.append(
                    f"  - We have banned: {', '.join(tendencies.banned_against_them)}"
                )

        return "\n".join(lines)

    def _build_player_context(
        self,
        draft_context: dict,
        team_players: list[dict] | None = None,
        enemy_players: list[dict] | None = None,
    ) -> str:
        """Build context from local player proficiency data.

        Uses structured data from knowledge/player_proficiency.json to provide
        accurate player champion pools, win rates, and comfort picks.
        """
        lines = []

        # Load proficiency data (cached after first load)
        proficiency_data = self._get_proficiency_data()
        if not proficiency_data:
            return self._get_fallback_meta_context(draft_context)

        # Format enemy player pools (for ban targeting)
        if enemy_players:
            lines.append("## Enemy Player Champion Pools (ban targets)")
            for player in enemy_players:
                player_name = player.get("name", "")
                role = player.get("role", "")
                player_stats = proficiency_data.get(player_name, {})

                if player_stats:
                    # Get top 5 champions by games weighted
                    champs = sorted(
                        player_stats.items(),
                        key=lambda x: x[1].get("games_weighted", 0),
                        reverse=True,
                    )[:5]

                    if champs:
                        champ_strs = []
                        for champ, stats in champs:
                            games = stats.get("games_raw", 0)
                            wr = stats.get("win_rate", 0) * 100
                            conf = stats.get("confidence", "LOW")
                            champ_strs.append(f"{champ} ({games}g, {wr:.0f}% WR, {conf})")
                        lines.append(f"- **{player_name}** ({role}): {', '.join(champ_strs)}")
                    else:
                        lines.append(f"- **{player_name}** ({role}): No recent data")
                else:
                    lines.append(f"- **{player_name}** ({role}): No proficiency data")

        # Format our team player pools (for pick recommendations)
        if team_players:
            lines.append("\n## Our Player Champion Pools (pick options)")
            for player in team_players:
                player_name = player.get("name", "")
                role = player.get("role", "")
                player_stats = proficiency_data.get(player_name, {})

                if player_stats:
                    champs = sorted(
                        player_stats.items(),
                        key=lambda x: x[1].get("games_weighted", 0),
                        reverse=True,
                    )[:5]

                    if champs:
                        champ_strs = []
                        for champ, stats in champs:
                            games = stats.get("games_raw", 0)
                            wr = stats.get("win_rate", 0) * 100
                            champ_strs.append(f"{champ} ({games}g, {wr:.0f}%)")
                        lines.append(f"- **{player_name}** ({role}): {', '.join(champ_strs)}")

        return "\n".join(lines) if lines else self._get_fallback_meta_context(draft_context)

    def _get_proficiency_data(self) -> dict:
        """Load and cache player proficiency data."""
        if not hasattr(self, "_proficiency_cache"):
            try:
                import json
                from pathlib import Path

                # Try multiple possible paths
                possible_paths = [
                    Path("knowledge/player_proficiency.json"),
                    Path(__file__).parent.parent.parent.parent.parent / "knowledge" / "player_proficiency.json",
                ]

                for path in possible_paths:
                    if path.exists():
                        with open(path) as f:
                            data = json.load(f)
                            self._proficiency_cache = data.get("proficiencies", {})
                            logger.info(f"Loaded {len(self._proficiency_cache)} player profiles")
                            return self._proficiency_cache

                logger.warning("player_proficiency.json not found")
                self._proficiency_cache = {}
            except Exception as e:
                logger.error(f"Failed to load proficiency data: {e}")
                self._proficiency_cache = {}

        return self._proficiency_cache

    def _get_fallback_meta_context(self, draft_context: dict) -> str:
        """Provide fallback meta context when web search is unavailable."""
        patch = draft_context.get("patch", "15.17")
        return f"""Meta context for patch {patch} (from training data):
- High priority picks: Engage supports, scaling ADCs, flex champions
- Common ban targets: Strong blind picks, player comfort picks
- Pro play trends: Early game junglers, team fight compositions
Note: This is general guidance. Use your knowledge of current pro meta."""

    def _get_archetype_data(self) -> dict:
        """Load and cache champion archetype data."""
        if not hasattr(self, "_archetype_cache"):
            try:
                from pathlib import Path

                possible_paths = [
                    Path("knowledge/archetype_counters.json"),
                    Path(__file__).parent.parent.parent.parent.parent / "knowledge" / "archetype_counters.json",
                ]

                for path in possible_paths:
                    if path.exists():
                        with open(path) as f:
                            data = json.load(f)
                            self._archetype_cache = data.get("champion_archetypes", {})
                            logger.info(f"Loaded {len(self._archetype_cache)} champion archetypes")
                            return self._archetype_cache

                logger.warning("archetype_counters.json not found")
                self._archetype_cache = {}
            except Exception as e:
                logger.error(f"Failed to load archetype data: {e}")
                self._archetype_cache = {}

        return self._archetype_cache

    def _get_synergy_data(self) -> list:
        """Load and cache synergy data."""
        if not hasattr(self, "_synergy_cache"):
            try:
                from pathlib import Path

                possible_paths = [
                    Path("knowledge/synergies.json"),
                    Path(__file__).parent.parent.parent.parent.parent / "knowledge" / "synergies.json",
                ]

                for path in possible_paths:
                    if path.exists():
                        with open(path) as f:
                            self._synergy_cache = json.load(f)
                            logger.info(f"Loaded {len(self._synergy_cache)} synergies")
                            return self._synergy_cache

                logger.warning("synergies.json not found")
                self._synergy_cache = []
            except Exception as e:
                logger.error(f"Failed to load synergy data: {e}")
                self._synergy_cache = []

        return self._synergy_cache

    def _analyze_draft_archetype(self, picks: list[str]) -> dict:
        """Analyze the archetype direction of a team's picks.

        Returns:
            Dict with 'primary_archetype', 'secondary_archetype', 'archetype_scores',
            and 'detected_strategy'
        """
        archetype_data = self._get_archetype_data()
        if not archetype_data or not picks:
            return {"primary_archetype": None, "archetype_scores": {}, "detected_strategy": "Unknown"}

        # Aggregate archetype weights from all picks
        archetype_totals = {"engage": 0, "split": 0, "teamfight": 0, "protect": 0, "pick": 0}

        for champ in picks:
            champ_archetypes = archetype_data.get(champ, {})
            for archetype, weight in champ_archetypes.items():
                if archetype in archetype_totals:
                    archetype_totals[archetype] += weight

        # Normalize by number of picks
        num_picks = len(picks)
        archetype_scores = {k: round(v / num_picks, 2) for k, v in archetype_totals.items()}

        # Find primary and secondary archetypes
        sorted_archetypes = sorted(archetype_scores.items(), key=lambda x: x[1], reverse=True)
        primary = sorted_archetypes[0][0] if sorted_archetypes[0][1] > 0 else None
        secondary = sorted_archetypes[1][0] if len(sorted_archetypes) > 1 and sorted_archetypes[1][1] > 0.2 else None

        # Detect strategy based on archetype combination
        strategy = self._detect_strategy(primary, secondary, archetype_scores)

        return {
            "primary_archetype": primary,
            "secondary_archetype": secondary,
            "archetype_scores": archetype_scores,
            "detected_strategy": strategy,
        }

    def _detect_strategy(self, primary: str, secondary: str, scores: dict) -> str:
        """Detect the team strategy based on archetype combination."""
        if not primary:
            return "Unclear direction"

        strategy_map = {
            ("engage", "teamfight"): "Wombo combo / hard engage teamfight",
            ("engage", "pick"): "Aggressive dive / assassination",
            ("teamfight", "protect"): "Front-to-back teamfight with carry",
            ("protect", "teamfight"): "Protect-the-carry / scaling",
            ("split", "pick"): "1-3-1 split with pick threat",
            ("split", "teamfight"): "Flexible scaling with split option",
            ("pick", "engage"): "Pick into engage / snowball comp",
            ("teamfight", "engage"): "Teamfight focused with engage tools",
        }

        key = (primary, secondary) if secondary else (primary, None)
        return strategy_map.get(key, f"{primary.capitalize()}-focused composition")

    def _find_synergies(self, picks: list[str], available_pool: list[str] = None) -> list[dict]:
        """Find synergies that could be completed with our picks.

        Args:
            picks: Champions already picked by our team
            available_pool: Champions we could still pick (optional filter)

        Returns:
            List of synergy opportunities with enabling champion and description
        """
        synergy_data = self._get_synergy_data()
        if not synergy_data or not picks:
            return []

        opportunities = []
        picks_set = set(picks)
        available_set = set(available_pool) if available_pool else None

        for synergy in synergy_data:
            champs = set(synergy.get("champions", []))

            # Check if we have partial overlap (can complete the synergy)
            have = champs & picks_set
            need = champs - picks_set

            if len(have) >= 1 and len(need) >= 1:
                # We have some pieces, could complete with others
                for needed_champ in need:
                    if available_set is None or needed_champ in available_set:
                        opportunities.append({
                            "synergy_id": synergy.get("id"),
                            "have": list(have),
                            "need": needed_champ,
                            "strength": synergy.get("strength", "B"),
                            "description": synergy.get("description", ""),
                            "comp_archetypes": synergy.get("comp_archetypes", []),
                        })

        # Sort by synergy strength (S > A > B > C)
        strength_order = {"S": 0, "A": 1, "B": 2, "C": 3}
        opportunities.sort(key=lambda x: strength_order.get(x["strength"], 4))

        return opportunities[:10]  # Top 10 opportunities

    def _find_enemy_synergies_to_disrupt(self, enemy_picks: list[str]) -> list[dict]:
        """Find synergies the enemy is building that we could disrupt with bans.

        Returns:
            List of disruption targets with impact explanation
        """
        synergy_data = self._get_synergy_data()
        if not synergy_data or not enemy_picks:
            return []

        disruptions = []
        enemy_set = set(enemy_picks)

        for synergy in synergy_data:
            champs = set(synergy.get("champions", []))

            # Check if enemy has partial synergy we could block
            have = champs & enemy_set
            need = champs - enemy_set

            if len(have) >= 1 and len(need) >= 1:
                # Enemy is building toward this synergy
                for block_target in need:
                    disruptions.append({
                        "synergy_id": synergy.get("id"),
                        "enemy_has": list(have),
                        "ban_target": block_target,
                        "strength": synergy.get("strength", "B"),
                        "impact": f"Blocks {synergy.get('description', 'synergy combo')}",
                        "countered_by": synergy.get("countered_by", []),
                    })

        # Sort by synergy strength
        strength_order = {"S": 0, "A": 1, "B": 2, "C": 3}
        disruptions.sort(key=lambda x: strength_order.get(x["strength"], 4))

        return disruptions[:5]  # Top 5 disruption opportunities

    def _get_counter_archetypes(self, enemy_archetype: str) -> list[str]:
        """Get archetypes that counter the enemy's strategy."""
        if not enemy_archetype or enemy_archetype not in ARCHETYPE_COUNTERS:
            return []

        # Find archetypes with positive matchup (>1.0 effectiveness)
        counters = []
        for archetype, matchups in ARCHETYPE_COUNTERS.items():
            vs_key = f"vs_{enemy_archetype}"
            if matchups.get(vs_key, 1.0) > 1.0:
                counters.append(archetype)
        return counters

    def _build_strategic_context(
        self,
        draft_context: dict,
        team_players: list[dict] | None = None,
        enemy_players: list[dict] | None = None,
    ) -> str:
        """Build strategic draft analysis context for LLM.

        This focuses on draft strategy, archetypes, and synergies rather than
        just player comfort picks.
        """
        lines = []

        our_picks = draft_context.get("our_picks", [])
        enemy_picks = draft_context.get("enemy_picks", [])

        # 1. ENEMY DRAFT DIRECTION ANALYSIS
        if enemy_picks:
            enemy_analysis = self._analyze_draft_archetype(enemy_picks)
            lines.append("## Enemy Draft Analysis")
            lines.append(f"**Detected Strategy**: {enemy_analysis['detected_strategy']}")
            if enemy_analysis['primary_archetype']:
                lines.append(f"**Primary Archetype**: {enemy_analysis['primary_archetype'].upper()}")
                scores = enemy_analysis['archetype_scores']
                score_str = ", ".join(f"{k}: {v:.2f}" for k, v in sorted(scores.items(), key=lambda x: -x[1]) if v > 0)
                lines.append(f"**Archetype Breakdown**: {score_str}")

                # Counter suggestions
                counters = self._get_counter_archetypes(enemy_analysis['primary_archetype'])
                if counters:
                    lines.append(f"**Counter Archetypes**: {', '.join(c.upper() for c in counters)}")

        # 2. SYNERGY DISRUPTION TARGETS (for bans)
        if enemy_picks:
            disruptions = self._find_enemy_synergies_to_disrupt(enemy_picks)
            if disruptions:
                lines.append("\n## Enemy Synergies to Disrupt (ban targets)")
                for d in disruptions[:3]:
                    lines.append(f"- **{d['ban_target']}** (strength: {d['strength']}): {d['impact']}")
                    if d.get('countered_by'):
                        lines.append(f"  Or counter with: {', '.join(d['countered_by'][:2])}")

        # 3. OUR SYNERGY OPPORTUNITIES (for picks)
        if our_picks:
            our_analysis = self._analyze_draft_archetype(our_picks)
            lines.append("\n## Our Draft Direction")
            lines.append(f"**Current Strategy**: {our_analysis['detected_strategy']}")

            opportunities = self._find_synergies(our_picks)
            if opportunities:
                lines.append("\n## Synergy Completion Opportunities")
                for opp in opportunities[:4]:
                    lines.append(
                        f"- **{opp['need']}** (strength: {opp['strength']}): "
                        f"Completes {opp['synergy_id'].replace('_', ' ')} with {', '.join(opp['have'])}"
                    )
                    if opp.get('comp_archetypes'):
                        lines.append(f"  Enables: {', '.join(opp['comp_archetypes'])}")

        # 4. ARCHETYPE-BASED CHAMPION SUGGESTIONS
        archetype_data = self._get_archetype_data()
        if enemy_picks and archetype_data:
            enemy_analysis = self._analyze_draft_archetype(enemy_picks)
            if enemy_analysis['primary_archetype']:
                counters = self._get_counter_archetypes(enemy_analysis['primary_archetype'])
                if counters:
                    lines.append(f"\n## Counter-Archetype Champions")
                    for counter_arch in counters[:2]:
                        # Find strong champions in this archetype
                        arch_champs = [
                            (champ, data.get(counter_arch, 0))
                            for champ, data in archetype_data.items()
                            if data.get(counter_arch, 0) >= 0.7
                        ]
                        arch_champs.sort(key=lambda x: -x[1])
                        top_champs = [c[0] for c in arch_champs[:5]]
                        if top_champs:
                            lines.append(f"- **{counter_arch.upper()}** counters enemy: {', '.join(top_champs)}")

        # 5. PLAYER PROFICIENCY (secondary consideration)
        proficiency_context = self._build_player_context(draft_context, team_players, enemy_players)
        if proficiency_context and "No proficiency data" not in proficiency_context:
            lines.append(f"\n## Player Pools (secondary consideration)")
            # Truncate to avoid overwhelming strategy focus
            prof_lines = proficiency_context.split('\n')[:8]
            lines.extend(prof_lines)

        return "\n".join(lines) if lines else self._get_fallback_meta_context(draft_context)

    async def _call_llm(self, prompt: str) -> dict:
        """Call the Nebius LLM API."""
        client = await self._get_client()

        response = await client.post(
            self.NEBIUS_API_URL,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model_id,
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a League of Legends esports draft analyst. Respond only with valid JSON.",
                    },
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.3,
                "max_tokens": 2500,
            },
        )

        response.raise_for_status()
        return response.json()

    def _extract_json_from_response(self, content: str) -> dict:
        """Extract JSON from LLM response, handling various formats.

        Handles:
        - Pure JSON
        - JSON wrapped in ```json ... ``` markdown
        - JSON with <think>...</think> reasoning blocks (DeepSeek)
        - JSON with leading/trailing text
        """
        content = content.strip()

        # Remove DeepSeek thinking blocks
        if "<think>" in content:
            # Find the last </think> and take everything after
            think_end = content.rfind("</think>")
            if think_end != -1:
                content = content[think_end + 8:].strip()

        # Handle markdown code blocks
        if "```" in content:
            # Find JSON block - could be ```json or just ```
            parts = content.split("```")
            for part in parts:
                part = part.strip()
                if part.startswith("json"):
                    part = part[4:].strip()
                if part.startswith("{"):
                    content = part
                    break

        # Try to find JSON object boundaries with proper brace matching
        if not content.startswith("{"):
            start = content.find("{")
            if start == -1:
                raise ValueError("No JSON object found in response")
            content = content[start:]

        # Find matching closing brace by counting braces
        brace_count = 0
        end_pos = -1
        in_string = False
        escape_next = False

        for i, char in enumerate(content):
            if escape_next:
                escape_next = False
                continue
            if char == '\\':
                escape_next = True
                continue
            if char == '"' and not escape_next:
                in_string = not in_string
                continue
            if in_string:
                continue
            if char == '{':
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0:
                    end_pos = i
                    break

        if end_pos == -1:
            raise ValueError("No matching closing brace found")

        content = content[:end_pos + 1]
        return json.loads(content)

    def _parse_pick_response(
        self, response: dict, original_candidates: list[dict], limit: int
    ) -> RerankerResult:
        """Parse the LLM response for picks."""
        try:
            content = response["choices"][0]["message"]["content"]
            data = self._extract_json_from_response(content)

            # Debug: log raw parsed data
            logger.debug(f"Parsed LLM response keys: {data.keys() if isinstance(data, dict) else type(data)}")
            if isinstance(data, dict) and "reranked" in data:
                logger.debug(f"Reranked count: {len(data.get('reranked', []))}")
                if data.get("reranked"):
                    logger.debug(f"First reranked item: {data['reranked'][0]}")

            # Validate response structure
            if not isinstance(data, dict):
                raise ValueError(f"Expected dict, got {type(data)}")
            if "reranked" not in data:
                raise ValueError("Missing 'reranked' key in response")

            # Build champion -> original data mapping
            orig_map = {}
            for i, c in enumerate(original_candidates):
                name = c.get("champion_name", c.get("champion", ""))
                orig_map[name.lower()] = (i + 1, c.get("score", c.get("priority", 0)))

            reranked = []
            for idx, item in enumerate(data.get("reranked", [])[:limit]):
                if not isinstance(item, dict):
                    continue
                champ = item.get("champion", "")
                if not champ:
                    continue
                orig_rank, orig_score = orig_map.get(champ.lower(), (99, 0))
                reranked.append(
                    RerankedRecommendation(
                        champion=champ,
                        original_rank=orig_rank,
                        new_rank=item.get("new_rank", idx + 1),
                        original_score=orig_score,
                        confidence=float(item.get("confidence", 0.5)),
                        reasoning=str(item.get("reasoning", "")),
                        strategic_factors=item.get("strategic_factors", []) or [],
                    )
                )

            additional = []
            for item in data.get("additional_suggestions", []) or []:
                if not isinstance(item, dict):
                    continue
                champ = item.get("champion", "")
                if not champ:
                    continue
                additional.append(
                    AdditionalSuggestion(
                        champion=champ,
                        reasoning=str(item.get("reasoning", "")),
                        confidence=float(item.get("confidence", 0.5)),
                        role=str(item.get("role", "")),
                        for_player=str(item.get("for_player", "")),
                    )
                )

            # If no reranked items were parsed, fall back
            if not reranked:
                raise ValueError("No valid reranked items in response")

            return RerankerResult(
                reranked=reranked,
                additional_suggestions=additional,
                draft_analysis=str(data.get("draft_analysis", "")),
                raw_llm_response=data,
            )
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}")
            return self._fallback_result(original_candidates, limit, "JSON parse error")
        except Exception as e:
            logger.error(f"Failed to parse LLM response: {e}")
            # Truncate error message for cleaner output
            error_msg = str(e)[:100] if len(str(e)) > 100 else str(e)
            return self._fallback_result(original_candidates, limit, error_msg)

    def _parse_ban_response(
        self, response: dict, original_candidates: list[dict], limit: int
    ) -> RerankerResult:
        """Parse the LLM response for bans (same structure as picks)."""
        return self._parse_pick_response(response, original_candidates, limit)

    def _fallback_result(
        self, candidates: list[dict], limit: int, error: str
    ) -> RerankerResult:
        """Create fallback result preserving original order."""
        reranked = []
        for i, c in enumerate(candidates[:limit]):
            champ = c.get("champion_name", c.get("champion", "Unknown"))
            reranked.append(
                RerankedRecommendation(
                    champion=champ,
                    original_rank=i + 1,
                    new_rank=i + 1,
                    original_score=c.get("score", c.get("priority", 0)),
                    confidence=0.5,
                    reasoning="(using algorithm ranking)",
                    strategic_factors=[],
                )
            )
        return RerankerResult(
            reranked=reranked,
            additional_suggestions=[],
            draft_analysis=f"LLM unavailable ({error[:50]}). Using algorithm rankings.",
        )
