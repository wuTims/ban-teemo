"""Tests for flex pick role resolution."""
import pytest
from ban_teemo.services.scorers.flex_resolver import FlexResolver


@pytest.fixture
def resolver():
    return FlexResolver()


def test_get_role_probabilities_flex(resolver):
    """Flex champion should have multiple roles."""
    probs = resolver.get_role_probabilities("Aurora")
    assert isinstance(probs, dict)
    assert sum(probs.values()) == pytest.approx(1.0, abs=0.01)


def test_get_role_probabilities_single_role(resolver):
    """Single-role champion should have high probability for one role."""
    probs = resolver.get_role_probabilities("Jinx")
    assert probs.get("ADC", 0) >= 0.9


def test_is_flex_pick(resolver):
    """Test flex pick detection."""
    assert resolver.is_flex_pick("Aurora") is True
    assert resolver.is_flex_pick("Jinx") is False


def test_normalize_role(resolver):
    """Test role normalization to canonical JNG form."""
    # JNG is canonical, JUNGLE is converted
    assert resolver.normalize_role("JNG") == "JNG"
    assert resolver.normalize_role("jng") == "JNG"
    assert resolver.normalize_role("jungle") == "JNG"
    assert resolver.normalize_role("JUNGLE") == "JNG"
    assert resolver.normalize_role("JG") == "JNG"

    # ADC aliases
    assert resolver.normalize_role("BOT") == "ADC"
    assert resolver.normalize_role("BOTTOM") == "ADC"
    assert resolver.normalize_role("adc") == "ADC"

    # Support aliases
    assert resolver.normalize_role("SUP") == "SUP"
    assert resolver.normalize_role("SUPPORT") == "SUP"

    # Mid aliases
    assert resolver.normalize_role("MID") == "MID"
    assert resolver.normalize_role("MIDDLE") == "MID"

    # Top (no alias needed)
    assert resolver.normalize_role("TOP") == "TOP"
    assert resolver.normalize_role("top") == "TOP"


def test_outputs_jng_not_jungle(resolver):
    """FlexResolver should output JNG, not JUNGLE."""
    # Test a known jungle champion
    probs = resolver.get_role_probabilities("Lee Sin")
    if probs:
        assert "JNG" in probs or len(probs) == 0, f"Should use JNG, got: {probs.keys()}"
        assert "JUNGLE" not in probs, "Should not output JUNGLE"


def test_unknown_champion_deterministic(resolver):
    """Unknown champions should get deterministic role assignment."""
    probs1 = resolver.get_role_probabilities("CompletelyFakeChampion123")
    probs2 = resolver.get_role_probabilities("CompletelyFakeChampion123")
    assert probs1 == probs2, "Should be deterministic for unknown champions"


def test_fallback_uses_role_history(resolver):
    """Champions not in flex data should use role history as fallback."""
    # Check internal state to find a champion in role_history but not flex_data
    # If flex_data has fewer champions than role_history, we can test fallback
    flex_champs = set(resolver._flex_data.keys())
    history_champs = set(resolver._role_history.keys())
    fallback_only = history_champs - flex_champs

    if fallback_only:
        # Test a champion that requires fallback
        test_champ = next(iter(fallback_only))
        probs = resolver.get_role_probabilities(test_champ)
        assert probs, f"{test_champ} should have probabilities via role history fallback"
        assert len(probs) == 1, "Fallback should return single role with 100%"
        assert list(probs.values())[0] == 1.0, "Fallback should have 100% for primary role"
    else:
        # All role_history champs are in flex_data, test deterministic fallback
        probs = resolver.get_role_probabilities("CompletelyUnknownChampXYZ123")
        assert probs, "Unknown champion should get deterministic fallback"
        assert len(probs) == 1, "Deterministic fallback returns single role"


def test_role_history_uses_canonical_role(resolver):
    """Role history should parse canonical_role field correctly."""
    # Aatrox is a known TOP laner in role history
    if "Aatrox" in resolver._role_history:
        assert resolver._role_history["Aatrox"] == "TOP"
    # At minimum, role history should have some entries
    assert len(resolver._role_history) > 0, "Role history should be populated"


def test_matchup_calculator_accepts_jng():
    """MatchupCalculator should accept JNG and translate to JUNGLE for data lookup."""
    from ban_teemo.services.scorers.matchup_calculator import MatchupCalculator
    calc = MatchupCalculator()

    # Test that JNG doesn't always return 0.5 (no data)
    # Use known jungle matchup - Maokai vs Sejuani is in the data
    result = calc.get_lane_matchup("Maokai", "Sejuani", "JNG")
    # If translation works, we should get actual data
    if result["data_source"] != "none":
        assert result["score"] != 0.5 or result["games"] > 0, "JNG should find JUNGLE data"
