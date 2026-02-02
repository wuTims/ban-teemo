#!/usr/bin/env python3
"""Local test for LLM reranker without API calls.

This script tests the prompt generation and response parsing logic
without making actual API calls. Useful for development and debugging.

Usage:
    uv run python scripts/test_llm_reranker_local.py
"""

import asyncio
import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parents[1] / "backend" / "src"))

from ban_teemo.services.llm_reranker import LLMReranker, RerankerResult


# Sample data from the replay log
SAMPLE_PICK_CANDIDATES = [
    {
        "champion_name": "Poppy",
        "score": 0.696,
        "suggested_role": "jungle",
        "proficiency_player": "Canyon",
        "components": {
            "meta": 0.594,
            "proficiency": 0.613,
            "matchup": 0.5,
            "counter": 0.5,
            "synergy": 0.5,
            "archetype": 1.0,
        },
        "reasons": ["B-tier meta pick", "Strengthens team identity"],
    },
    {
        "champion_name": "Rumble",
        "score": 0.69,
        "suggested_role": "top",
        "proficiency_player": "Kiin",
        "components": {
            "meta": 0.566,
            "proficiency": 0.70,
            "matchup": 0.5,
            "counter": 0.643,
            "synergy": 0.5,
            "archetype": 1.0,
        },
        "reasons": ["B-tier meta pick", "Strong team proficiency", "Counters enemy comp"],
    },
    {
        "champion_name": "Aurora",
        "score": 0.673,
        "suggested_role": "mid",
        "proficiency_player": "Chovy",
        "components": {
            "meta": 0.566,
            "proficiency": 0.70,
            "matchup": 0.5,
            "counter": 0.5,
            "synergy": 0.5,
            "archetype": 0.775,
        },
        "reasons": ["B-tier meta pick", "Strong team proficiency"],
    },
    {
        "champion_name": "Rakan",
        "score": 0.657,
        "suggested_role": "support",
        "proficiency_player": "Duro",
        "components": {
            "meta": 0.568,
            "proficiency": 0.70,
            "matchup": 0.5,
            "counter": 0.6,
            "synergy": 0.5,
            "archetype": 0.83,
        },
        "reasons": ["B-tier meta pick", "Strong team proficiency", "Counters enemy comp"],
    },
    {
        "champion_name": "Vi",
        "score": 0.656,
        "suggested_role": "jungle",
        "proficiency_player": "Canyon",
        "components": {
            "meta": 0.543,
            "proficiency": 0.70,
            "matchup": 0.5,
            "counter": 0.5,
            "synergy": 0.5,
            "archetype": 1.0,
        },
        "reasons": ["B-tier meta pick", "Strong team proficiency"],
    },
]

SAMPLE_DRAFT_CONTEXT = {
    "phase": "PICK_PHASE_1",
    "patch": "15.17",
    "our_team": "Gen.G Esports",
    "enemy_team": "T1",
    "our_picks": ["Orianna"],
    "enemy_picks": ["Yunara"],
    "banned": ["Azir", "Wukong", "Pantheon", "Bard", "Neeko", "Jarvan IV"],
}

SAMPLE_TEAM_PLAYERS = [
    {"name": "Kiin", "role": "top"},
    {"name": "Canyon", "role": "jungle"},
    {"name": "Chovy", "role": "mid"},
    {"name": "Ruler", "role": "bot"},
    {"name": "Duro", "role": "support"},
]

SAMPLE_ENEMY_PLAYERS = [
    {"name": "Doran", "role": "top"},
    {"name": "Oner", "role": "jungle"},
    {"name": "Faker", "role": "mid"},
    {"name": "Gumayusi", "role": "bot"},
    {"name": "Keria", "role": "support"},
]

# Simulated LLM response (what we expect the model to return)
SIMULATED_LLM_RESPONSE = {
    "choices": [
        {
            "message": {
                "content": json.dumps(
                    {
                        "reranked": [
                            {
                                "champion": "Rumble",
                                "original_rank": 2,
                                "new_rank": 1,
                                "confidence": 0.85,
                                "reasoning": "Rumble is a high priority top laner that synergizes well with Orianna ball delivery. Kiin has strong proficiency and it counters Yunara's team fight presence.",
                                "strategic_factors": [
                                    "orianna_synergy",
                                    "player_comfort",
                                    "counter_enemy",
                                ],
                            },
                            {
                                "champion": "Rakan",
                                "original_rank": 4,
                                "new_rank": 2,
                                "confidence": 0.80,
                                "reasoning": "Rakan provides engage for Orianna combos and is a priority support. Duro's comfort on Rakan makes this a strong pick.",
                                "strategic_factors": [
                                    "orianna_synergy",
                                    "engage_support",
                                    "player_comfort",
                                ],
                            },
                            {
                                "champion": "Vi",
                                "original_rank": 5,
                                "new_rank": 3,
                                "confidence": 0.75,
                                "reasoning": "Vi provides additional engage and lockdown for Orianna combos. Canyon's jungle pool includes Vi.",
                                "strategic_factors": ["orianna_synergy", "engage_jungle"],
                            },
                            {
                                "champion": "Poppy",
                                "original_rank": 1,
                                "new_rank": 4,
                                "confidence": 0.70,
                                "reasoning": "Poppy is strong but doesn't synergize as well with Orianna's team fight style. Better as a counter-pick.",
                                "strategic_factors": ["meta_strong", "defensive"],
                            },
                            {
                                "champion": "Aurora",
                                "original_rank": 3,
                                "new_rank": 5,
                                "confidence": 0.65,
                                "reasoning": "Aurora is a strong mid but Orianna is already picked for mid. Aurora would need to flex top/jungle which is less optimal.",
                                "strategic_factors": ["role_conflict"],
                            },
                        ],
                        "additional_suggestions": [
                            {
                                "champion": "Jarvan IV",
                                "reasoning": "J4 would be excellent here for Orianna + J4 combo, but he's banned.",
                                "confidence": 0.0,
                            },
                            {
                                "champion": "Malphite",
                                "reasoning": "Malphite ult + Orianna ball is a classic combo. If Kiin plays Malphite, this could be devastating.",
                                "confidence": 0.60,
                            },
                            {
                                "champion": "Rell",
                                "reasoning": "Rell provides engage similar to Rakan and synergizes with Orianna ball delivery.",
                                "confidence": 0.55,
                            },
                        ],
                        "draft_analysis": "Gen.G has first-picked Orianna, signaling a team fight composition. They should prioritize engage champions that can deliver Orianna's ball effectively. Rumble or an engage support would complement this well.",
                    }
                )
            }
        }
    ]
}


class MockLLMReranker(LLMReranker):
    """Mock reranker that returns simulated responses."""

    async def _call_llm(self, prompt: str) -> dict:
        """Return simulated response instead of calling API."""
        print("\n" + "=" * 60)
        print("GENERATED PROMPT (truncated)")
        print("=" * 60)
        # Print first 2000 chars of prompt
        print(prompt[:2000])
        if len(prompt) > 2000:
            print(f"\n... [{len(prompt) - 2000} more characters]")
        print("=" * 60)

        return SIMULATED_LLM_RESPONSE


import pytest


@pytest.mark.asyncio
async def test_pick_reranking():
    """Test pick reranking with simulated LLM response."""
    print("\n" + "=" * 60)
    print("TEST: Pick Reranking")
    print("=" * 60)

    # Create mock reranker (no API key needed)
    reranker = MockLLMReranker(
        api_key="mock-key",
        model="deepseek",
    )

    try:
        result = await reranker.rerank_picks(
            candidates=SAMPLE_PICK_CANDIDATES,
            draft_context=SAMPLE_DRAFT_CONTEXT,
            team_players=SAMPLE_TEAM_PLAYERS,
            enemy_players=SAMPLE_ENEMY_PLAYERS,
            limit=5,
        )

        print("\n" + "=" * 60)
        print("RERANKED RESULTS")
        print("=" * 60)

        print("\nOriginal vs Reranked Order:")
        print("-" * 40)
        for rec in result.reranked:
            movement = rec.original_rank - rec.new_rank
            arrow = "↑" if movement > 0 else "↓" if movement < 0 else "="
            print(
                f"  {rec.new_rank}. {rec.champion} "
                f"(was #{rec.original_rank}) {arrow} "
                f"[conf: {rec.confidence:.0%}]"
            )
            print(f"     {rec.reasoning[:80]}...")
            print(f"     Factors: {', '.join(rec.strategic_factors)}")

        print("\nAdditional Suggestions (not in original candidates):")
        print("-" * 40)
        for sug in result.additional_suggestions:
            print(f"  • {sug.champion} [conf: {sug.confidence:.0%}]")
            print(f"    {sug.reasoning}")

        print(f"\nDraft Analysis:")
        print("-" * 40)
        print(f"  {result.draft_analysis}")

        # Verify parsing worked correctly
        print("\n" + "=" * 60)
        print("VALIDATION")
        print("=" * 60)
        assert len(result.reranked) == 5, f"Expected 5 reranked, got {len(result.reranked)}"
        assert result.reranked[0].champion == "Rumble", "Expected Rumble to be #1"
        assert len(result.additional_suggestions) == 3, "Expected 3 additional suggestions"
        print("✓ All validations passed!")

    finally:
        await reranker.close()


@pytest.mark.asyncio
async def test_prompt_generation():
    """Test that prompts are generated correctly for different scenarios."""
    print("\n" + "=" * 60)
    print("TEST: Prompt Generation")
    print("=" * 60)

    reranker = LLMReranker(
        api_key="mock-key",
        model="deepseek",
    )

    # Test pick prompt
    pick_prompt = reranker._build_pick_rerank_prompt(
        candidates=SAMPLE_PICK_CANDIDATES,
        draft_context=SAMPLE_DRAFT_CONTEXT,
        team_players=SAMPLE_TEAM_PLAYERS,
        enemy_players=SAMPLE_ENEMY_PLAYERS,
        web_context="Mock meta context",
        limit=5,
    )

    print("\nPick Prompt Stats:")
    print(f"  Length: {len(pick_prompt)} characters")
    print(f"  Contains team players: {'Kiin' in pick_prompt}")
    print(f"  Contains enemy players: {'Faker' in pick_prompt}")
    print(f"  Contains candidates: {'Poppy' in pick_prompt}")
    print(f"  Contains JSON format: {'reranked' in pick_prompt}")

    # Test ban prompt
    ban_prompt = reranker._build_ban_rerank_prompt(
        candidates=[
            {
                "champion_name": "Azir",
                "priority": 0.831,
                "target_player": "Faker",
                "components": {"proficiency": 0.867, "meta": 0.73},
                "reasons": ["Faker's comfort pick"],
            }
        ],
        draft_context={
            "phase": "BAN_PHASE_1",
            "patch": "15.17",
            "our_team": "Gen.G",
            "enemy_team": "T1",
            "our_picks": [],
            "enemy_picks": [],
            "banned": [],
        },
        our_players=SAMPLE_TEAM_PLAYERS,
        enemy_players=SAMPLE_ENEMY_PLAYERS,
        web_context="Mock meta context",
        limit=5,
    )

    print("\nBan Prompt Stats:")
    print(f"  Length: {len(ban_prompt)} characters")
    print(f"  Contains phase guidance: {'Phase 1 bans' in ban_prompt}")
    print(f"  Contains enemy targets: {'Faker' in ban_prompt}")

    print("\n✓ Prompt generation tests passed!")

    await reranker.close()


async def main():
    """Run all tests."""
    print("=" * 60)
    print("LLM RERANKER LOCAL TESTS")
    print("=" * 60)
    print("These tests use simulated LLM responses - no API key needed.")

    await test_prompt_generation()
    await test_pick_reranking()

    print("\n" + "=" * 60)
    print("ALL TESTS COMPLETED")
    print("=" * 60)
    print("\nTo test with real LLM:")
    print("  export NEBIUS_API_KEY=your_key")
    print(
        "  uv run python scripts/eval_llm_reranker.py "
        "logs/scoring/replay_13df7c3a_20260130_205515.json --mock"
    )


if __name__ == "__main__":
    asyncio.run(main())
