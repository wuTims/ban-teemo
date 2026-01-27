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
