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
    # Canonical role is now lowercase "bot"
    assert probs.get("bot", 0) >= 0.9


def test_is_flex_pick(resolver):
    """Test flex pick detection."""
    assert resolver.is_flex_pick("Aurora") is True
    assert resolver.is_flex_pick("Jinx") is False


def test_normalize_role(resolver):
    """Test role normalization to canonical lowercase form."""
    # All variants should normalize to lowercase canonical form
    assert resolver.normalize_role("JNG") == "jungle"
    assert resolver.normalize_role("jng") == "jungle"
    assert resolver.normalize_role("jungle") == "jungle"
    assert resolver.normalize_role("JUNGLE") == "jungle"
    assert resolver.normalize_role("JG") == "jungle"

    # ADC/bot aliases -> "bot"
    assert resolver.normalize_role("BOT") == "bot"
    assert resolver.normalize_role("BOTTOM") == "bot"
    assert resolver.normalize_role("adc") == "bot"
    assert resolver.normalize_role("ADC") == "bot"

    # Support aliases -> "support"
    assert resolver.normalize_role("SUP") == "support"
    assert resolver.normalize_role("SUPPORT") == "support"
    assert resolver.normalize_role("support") == "support"

    # Mid aliases -> "mid"
    assert resolver.normalize_role("MID") == "mid"
    assert resolver.normalize_role("MIDDLE") == "mid"
    assert resolver.normalize_role("mid") == "mid"

    # Top -> "top"
    assert resolver.normalize_role("TOP") == "top"
    assert resolver.normalize_role("top") == "top"


def test_outputs_lowercase_roles(resolver):
    """FlexResolver should output lowercase canonical roles."""
    # Test a known jungle champion
    probs = resolver.get_role_probabilities("Lee Sin")
    if probs:
        assert "jungle" in probs or len(probs) == 0, f"Should use 'jungle', got: {probs.keys()}"
        assert "JNG" not in probs, "Should not output JNG (uppercase)"
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
    # Aatrox is a known TOP laner in role history - now stored as lowercase
    if "Aatrox" in resolver._role_history:
        assert resolver._role_history["Aatrox"] == "top"
    # At minimum, role history should have some entries
    assert len(resolver._role_history) > 0, "Role history should be populated"


def test_matchup_calculator_accepts_role_variants():
    """MatchupCalculator should accept various role formats."""
    from ban_teemo.services.scorers.matchup_calculator import MatchupCalculator
    calc = MatchupCalculator()

    # Test that both uppercase and lowercase roles work
    # Use known jungle matchup - Maokai vs Sejuani is in the data
    result1 = calc.get_lane_matchup("Maokai", "Sejuani", "JNG")
    result2 = calc.get_lane_matchup("Maokai", "Sejuani", "jungle")

    # Both should find the same data
    assert result1["score"] == result2["score"], "JNG and jungle should find same data"


def test_minimum_probability_threshold_filters_noise(resolver):
    """Champions with very low role probability should not be suggested for that role.

    Viego has 2% support probability in the data - this is noise and should be filtered.
    When all other roles are filled, Viego should return empty dict, not support.
    """
    # Viego is primarily jungle (96.5%), with tiny MID (1.6%) and SUP (2%) probabilities
    # When jungle is filled, the remaining probabilities are below threshold
    filled_all_but_support = {"top", "jungle", "mid", "bot"}
    probs = resolver.get_role_probabilities("Viego", filled_roles=filled_all_but_support)

    # Should return empty dict because 2% support is below 5% threshold
    assert probs == {}, f"Viego should not be suggested for support (2% < 5% threshold), got: {probs}"


def test_minimum_probability_threshold_filters_exact_boundary(resolver):
    """Champions at exactly 5% should be filtered (we use >5% not >=5%).

    Nocturne has exactly 5% support probability - this should be filtered.
    """
    filled_all_but_support = {"top", "jungle", "mid", "bot"}
    probs = resolver.get_role_probabilities("Nocturne", filled_roles=filled_all_but_support)

    # Should return empty dict because 5% support is at the boundary (we filter >= threshold)
    assert probs == {}, f"Nocturne should not be suggested for support (5% at boundary), got: {probs}"


def test_minimum_probability_threshold_allows_legit_flex(resolver):
    """Champions with meaningful secondary role probability should still be suggested.

    Poppy has 39% support probability - this is a legitimate flex pick.
    """
    filled_all_but_support = {"top", "jungle", "mid", "bot"}
    probs = resolver.get_role_probabilities("Poppy", filled_roles=filled_all_but_support)

    # Poppy has 39% support, which is above the 5% threshold
    assert "support" in probs, f"Poppy should be suggested for support (39% > 5% threshold), got: {probs}"
    assert probs["support"] == 1.0, "Should normalize to 100% when it's the only remaining role"
