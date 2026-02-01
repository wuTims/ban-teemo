#!/usr/bin/env python3
"""Test LLM response parsing with various formats.

This script tests the JSON extraction and parsing logic with
different response formats that LLMs might return.

Usage:
    uv run python scripts/test_llm_parsing.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "backend" / "src"))

from ban_teemo.services.llm_reranker import LLMReranker


# Test cases with various LLM response formats
TEST_CASES = [
    {
        "name": "Pure JSON",
        "content": """{
  "reranked": [
    {"champion": "Rumble", "original_rank": 2, "new_rank": 1, "confidence": 0.85, "reasoning": "Good synergy", "strategic_factors": ["synergy"]}
  ],
  "additional_suggestions": [],
  "draft_analysis": "Focus on engage"
}""",
        "expected_first_champ": "Rumble",
    },
    {
        "name": "Markdown code block",
        "content": """```json
{
  "reranked": [
    {"champion": "Poppy", "original_rank": 1, "new_rank": 1, "confidence": 0.8, "reasoning": "Meta strong", "strategic_factors": ["meta"]}
  ],
  "additional_suggestions": [],
  "draft_analysis": "Test"
}
```""",
        "expected_first_champ": "Poppy",
    },
    {
        "name": "Markdown without json tag",
        "content": """```
{
  "reranked": [
    {"champion": "Aurora", "original_rank": 3, "new_rank": 1, "confidence": 0.75, "reasoning": "Player comfort", "strategic_factors": []}
  ],
  "additional_suggestions": [],
  "draft_analysis": "Test"
}
```""",
        "expected_first_champ": "Aurora",
    },
    {
        "name": "DeepSeek thinking format",
        "content": """<think>
Let me analyze this draft situation...
The team has already picked Orianna, so they need engage.
Rumble would be good because...
</think>

{
  "reranked": [
    {"champion": "Rumble", "original_rank": 2, "new_rank": 1, "confidence": 0.9, "reasoning": "Orianna synergy with Rumble ult", "strategic_factors": ["orianna_combo", "teamfight"]}
  ],
  "additional_suggestions": [
    {"champion": "Malphite", "reasoning": "Another Orianna combo option", "confidence": 0.6}
  ],
  "draft_analysis": "Team needs engage for Orianna ball delivery"
}""",
        "expected_first_champ": "Rumble",
    },
    {
        "name": "JSON with leading text",
        "content": """Here is my analysis:

{
  "reranked": [
    {"champion": "Vi", "original_rank": 5, "new_rank": 1, "confidence": 0.8, "reasoning": "Strong engage", "strategic_factors": ["engage"]}
  ],
  "additional_suggestions": [],
  "draft_analysis": "Jungle priority"
}""",
        "expected_first_champ": "Vi",
    },
    {
        "name": "JSON with trailing text",
        "content": """{
  "reranked": [
    {"champion": "Rakan", "original_rank": 4, "new_rank": 1, "confidence": 0.85, "reasoning": "Engage support", "strategic_factors": ["engage"]}
  ],
  "additional_suggestions": [],
  "draft_analysis": "Support priority"
}

I hope this analysis helps!""",
        "expected_first_champ": "Rakan",
    },
    {
        "name": "Mixed markdown and text",
        "content": """Based on my analysis of the draft:

```json
{
  "reranked": [
    {"champion": "Camille", "original_rank": 3, "new_rank": 1, "confidence": 0.75, "reasoning": "Split push threat", "strategic_factors": ["split"]}
  ],
  "additional_suggestions": [],
  "draft_analysis": "Side lane pressure"
}
```

Let me know if you need more details.""",
        "expected_first_champ": "Camille",
    },
    {
        "name": "Minimal valid response",
        "content": """{"reranked":[{"champion":"Azir","new_rank":1,"confidence":0.7,"reasoning":"test"}],"additional_suggestions":[],"draft_analysis":"ok"}""",
        "expected_first_champ": "Azir",
    },
    {
        "name": "Response with null values",
        "content": """{
  "reranked": [
    {"champion": "Syndra", "original_rank": null, "new_rank": 1, "confidence": 0.8, "reasoning": "Mid priority", "strategic_factors": null}
  ],
  "additional_suggestions": null,
  "draft_analysis": "Control mage"
}""",
        "expected_first_champ": "Syndra",
    },
    {
        "name": "Response with extra fields",
        "content": """{
  "thinking": "Internal reasoning here...",
  "reranked": [
    {"champion": "Orianna", "original_rank": 2, "new_rank": 1, "confidence": 0.9, "reasoning": "Ball delivery", "strategic_factors": ["teamfight"], "extra_field": "ignored"}
  ],
  "additional_suggestions": [],
  "draft_analysis": "Team fight comp",
  "meta_notes": "This should be ignored"
}""",
        "expected_first_champ": "Orianna",
    },
]

# Sample candidates for testing
SAMPLE_CANDIDATES = [
    {"champion_name": "Poppy", "score": 0.7},
    {"champion_name": "Rumble", "score": 0.69},
    {"champion_name": "Aurora", "score": 0.67},
    {"champion_name": "Rakan", "score": 0.65},
    {"champion_name": "Vi", "score": 0.64},
]


def test_json_extraction():
    """Test JSON extraction from various formats."""
    print("=" * 60)
    print("TESTING JSON EXTRACTION")
    print("=" * 60)

    reranker = LLMReranker(api_key="test")
    passed = 0
    failed = 0

    for case in TEST_CASES:
        name = case["name"]
        content = case["content"]
        expected = case["expected_first_champ"]

        try:
            data = reranker._extract_json_from_response(content)

            # Validate structure
            assert "reranked" in data, "Missing 'reranked' key"
            assert len(data["reranked"]) > 0, "Empty reranked list"
            assert data["reranked"][0]["champion"] == expected, f"Expected {expected}, got {data['reranked'][0]['champion']}"

            print(f"✓ {name}")
            passed += 1
        except Exception as e:
            print(f"✗ {name}: {e}")
            failed += 1

    print(f"\nResults: {passed}/{passed + failed} passed")
    return failed == 0


def test_full_parsing():
    """Test full response parsing pipeline."""
    print("\n" + "=" * 60)
    print("TESTING FULL PARSING PIPELINE")
    print("=" * 60)

    reranker = LLMReranker(api_key="test")
    passed = 0
    failed = 0

    for case in TEST_CASES:
        name = case["name"]
        content = case["content"]
        expected = case["expected_first_champ"]

        # Simulate LLM API response format
        response = {
            "choices": [
                {"message": {"content": content}}
            ]
        }

        try:
            result = reranker._parse_pick_response(response, SAMPLE_CANDIDATES, limit=5)

            # Validate result
            assert len(result.reranked) > 0, "No reranked items"
            assert result.reranked[0].champion == expected, f"Expected {expected}, got {result.reranked[0].champion}"
            assert result.reranked[0].confidence > 0, "Invalid confidence"
            assert result.draft_analysis, "Missing draft analysis"

            print(f"✓ {name}")
            print(f"  - First: {result.reranked[0].champion} (conf: {result.reranked[0].confidence})")
            print(f"  - Analysis: {result.draft_analysis[:50]}...")
            passed += 1
        except Exception as e:
            print(f"✗ {name}: {e}")
            failed += 1

    print(f"\nResults: {passed}/{passed + failed} passed")
    return failed == 0


def test_error_handling():
    """Test error handling for invalid responses."""
    print("\n" + "=" * 60)
    print("TESTING ERROR HANDLING")
    print("=" * 60)

    reranker = LLMReranker(api_key="test")

    error_cases = [
        {"name": "Empty response", "content": ""},
        {"name": "Plain text", "content": "This is not JSON at all"},
        {"name": "Invalid JSON", "content": "{invalid json}"},
        {"name": "Missing reranked", "content": '{"draft_analysis": "test"}'},
        {"name": "Empty reranked", "content": '{"reranked": [], "draft_analysis": "test"}'},
        {"name": "Null content", "content": "null"},
    ]

    passed = 0
    for case in error_cases:
        response = {"choices": [{"message": {"content": case["content"]}}]}

        result = reranker._parse_pick_response(response, SAMPLE_CANDIDATES, limit=5)

        # Should return fallback result, not crash
        if len(result.reranked) == len(SAMPLE_CANDIDATES[:5]):
            print(f"✓ {case['name']}: Graceful fallback")
            passed += 1
        else:
            print(f"✗ {case['name']}: Unexpected result")

    print(f"\nResults: {passed}/{len(error_cases)} handled gracefully")
    return passed == len(error_cases)


def test_candidate_mapping():
    """Test that original candidate data is preserved."""
    print("\n" + "=" * 60)
    print("TESTING CANDIDATE MAPPING")
    print("=" * 60)

    reranker = LLMReranker(api_key="test")

    # Response that reorders candidates
    content = """{
  "reranked": [
    {"champion": "Vi", "new_rank": 1, "confidence": 0.9, "reasoning": "Promoted", "strategic_factors": []},
    {"champion": "Poppy", "new_rank": 2, "confidence": 0.8, "reasoning": "Demoted", "strategic_factors": []},
    {"champion": "Rumble", "new_rank": 3, "confidence": 0.7, "reasoning": "Same", "strategic_factors": []}
  ],
  "additional_suggestions": [],
  "draft_analysis": "Reordered"
}"""

    response = {"choices": [{"message": {"content": content}}]}
    result = reranker._parse_pick_response(response, SAMPLE_CANDIDATES, limit=5)

    # Check that original ranks are correctly mapped
    vi = next(r for r in result.reranked if r.champion == "Vi")
    poppy = next(r for r in result.reranked if r.champion == "Poppy")

    tests_passed = True

    if vi.original_rank == 5 and vi.new_rank == 1:
        print(f"✓ Vi: rank 5 → 1 (promoted)")
    else:
        print(f"✗ Vi: expected 5→1, got {vi.original_rank}→{vi.new_rank}")
        tests_passed = False

    if poppy.original_rank == 1 and poppy.new_rank == 2:
        print(f"✓ Poppy: rank 1 → 2 (demoted)")
    else:
        print(f"✗ Poppy: expected 1→2, got {poppy.original_rank}→{poppy.new_rank}")
        tests_passed = False

    # Check original score is preserved
    if vi.original_score == 0.64:
        print(f"✓ Vi original score preserved: {vi.original_score}")
    else:
        print(f"✗ Vi original score: expected 0.64, got {vi.original_score}")
        tests_passed = False

    return tests_passed


def main():
    """Run all parsing tests."""
    print("=" * 60)
    print("LLM RESPONSE PARSING TESTS")
    print("=" * 60)
    print("Testing all response formats before using API credits\n")

    all_passed = True
    all_passed &= test_json_extraction()
    all_passed &= test_full_parsing()
    all_passed &= test_error_handling()
    all_passed &= test_candidate_mapping()

    print("\n" + "=" * 60)
    if all_passed:
        print("ALL TESTS PASSED ✓")
        print("Safe to run with real API")
    else:
        print("SOME TESTS FAILED ✗")
        print("Fix issues before using API credits")
    print("=" * 60)

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
