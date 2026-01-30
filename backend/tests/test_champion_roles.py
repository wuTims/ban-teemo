"""Tests for champion role lookup."""
import json
import pytest
from ban_teemo.utils.champion_roles import get_champion_primary_role, ChampionRoleLookup


@pytest.fixture
def mock_role_history(tmp_path):
    """Create mock champion role history."""
    data = {
        "champions": {
            "Aatrox": {
                "canonical_role": "TOP",
                "current_viable_roles": ["TOP"],
            },
            "Aurora": {
                "canonical_role": "MID",
                "current_viable_roles": ["MID", "TOP"],
                "current_distribution": {"MID": 0.7, "TOP": 0.3},
            },
            "Jinx": {
                "canonical_role": "BOT",
            },
            "FlexChamp": {
                "current_distribution": {"MID": 0.5, "TOP": 0.5},
            },
        }
    }
    path = tmp_path / "champion_role_history.json"
    path.write_text(json.dumps(data))
    return tmp_path


def test_get_primary_role_from_canonical(mock_role_history):
    """Returns canonical_role when available."""
    lookup = ChampionRoleLookup(mock_role_history)
    assert lookup.get_primary_role("Aatrox") == "top"
    assert lookup.get_primary_role("Jinx") == "bot"


def test_get_primary_role_single_current_viable(mock_role_history):
    """Returns single current_viable_role."""
    lookup = ChampionRoleLookup(mock_role_history)
    assert lookup.get_primary_role("Aatrox") == "top"


def test_get_primary_role_flex_uses_distribution_over_canonical(mock_role_history):
    """Flex champ uses distribution over canonical when both exist."""
    lookup = ChampionRoleLookup(mock_role_history)
    # Aurora has canonical_role=MID and current_distribution={MID: 0.7, TOP: 0.3}
    # Distribution takes priority, highest is MID (0.7)
    assert lookup.get_primary_role("Aurora") == "mid"


def test_get_primary_role_distribution_overrides_canonical(mock_role_history):
    """When distribution disagrees with canonical, distribution wins."""
    # Add a champ where distribution disagrees with canonical
    mock_role_history_data = {
        "champions": {
            "ConflictChamp": {
                "canonical_role": "TOP",
                "current_distribution": {"MID": 0.8, "TOP": 0.2},
            },
        }
    }
    import json
    path = mock_role_history / "champion_role_history.json"
    path.write_text(json.dumps(mock_role_history_data))
    lookup = ChampionRoleLookup(mock_role_history)
    # Distribution says MID (0.8), canonical says TOP - distribution wins
    assert lookup.get_primary_role("ConflictChamp") == "mid"


def test_get_primary_role_flex_no_canonical_uses_distribution(mock_role_history):
    """Flex champ without canonical uses highest distribution."""
    lookup = ChampionRoleLookup(mock_role_history)
    # FlexChamp has no canonical, equal distribution - should pick one deterministically
    role = lookup.get_primary_role("FlexChamp")
    assert role in {"mid", "top"}


def test_get_primary_role_unknown_champion(mock_role_history):
    """Unknown champion returns None."""
    lookup = ChampionRoleLookup(mock_role_history)
    assert lookup.get_primary_role("UnknownChamp") is None


def test_get_primary_role_normalizes_output(mock_role_history):
    """Output is always lowercase canonical."""
    lookup = ChampionRoleLookup(mock_role_history)
    role = lookup.get_primary_role("Aatrox")
    assert role == "top"
    assert role.islower()
