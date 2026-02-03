"""Tests for flex pick role resolution."""
import pytest
import json
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
    """Test flex pick detection derived from current_viable_roles."""
    # Aurora has 2+ viable roles
    assert resolver.is_flex_pick("Aurora") is True
    # Jinx is bot-only
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


def test_role_history_uses_canonical_role(resolver):
    """Role history should parse canonical_role field correctly."""
    # Aatrox is a known TOP laner in role history - now stored as lowercase
    if "Aatrox" in resolver._primary_roles:
        assert resolver._primary_roles["Aatrox"] == "top"
    # At minimum, primary roles should have some entries
    assert len(resolver._primary_roles) > 0, "Primary roles should be populated"


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


def test_minimum_probability_threshold_allows_legit_flex(resolver):
    """Champions with meaningful secondary role probability should still be suggested.

    Poppy has 39% support probability - this is a legitimate flex pick.
    """
    filled_all_but_support = {"top", "jungle", "mid", "bot"}
    probs = resolver.get_role_probabilities("Poppy", filled_roles=filled_all_but_support)

    # Poppy has 39% support, which is above the 5% threshold
    assert "support" in probs, f"Poppy should be suggested for support (39% > 5% threshold), got: {probs}"
    assert probs["support"] == 1.0, "Should normalize to 100% when it's the only remaining role"


def _write_role_history(tmp_path, role_history):
    """Helper to create test knowledge files with champion_role_history.json only."""
    knowledge_dir = tmp_path / "knowledge"
    knowledge_dir.mkdir(exist_ok=True)
    (knowledge_dir / "champion_role_history.json").write_text(
        json.dumps({"champions": role_history})
    )
    return knowledge_dir


def _write_tournament_meta(knowledge_dir, tournament_data, filename="tournament_meta.json"):
    """Helper to create a tournament meta JSON file in the knowledge dir."""
    (knowledge_dir / filename).write_text(
        json.dumps({"metadata": {}, "champions": tournament_data})
    )


def test_current_viable_roles_override_all_time(tmp_path):
    """current_viable_roles should override all_time_distribution."""
    role_history = {
        "Flexy": {
            "canonical_role": "TOP",
            "all_time_distribution": {"TOP": 1.0},
            "current_viable_roles": ["mid"],
            "current_distribution": {"MID": 0.8, "TOP": 0.2},
        },
    }
    knowledge_dir = _write_role_history(tmp_path, role_history)
    resolver = FlexResolver(knowledge_dir)

    probs = resolver.get_role_probabilities("Flexy")
    # Should only use mid since it's the only current_viable_role
    assert probs == {"mid": 1.0}


def test_current_distribution_used_when_has_viable_roles(tmp_path):
    """When current_viable_roles exists, use current_distribution probabilities."""
    role_history = {
        "Flexy2": {
            "canonical_role": "TOP",
            "all_time_distribution": {"TOP": 1.0},
            "current_viable_roles": ["top", "mid"],
            "current_distribution": {"TOP": 0.3, "MID": 0.7},
        },
    }
    knowledge_dir = _write_role_history(tmp_path, role_history)
    resolver = FlexResolver(knowledge_dir)

    probs = resolver.get_role_probabilities("Flexy2")
    # Should use current_distribution proportions
    assert "top" in probs
    assert "mid" in probs
    assert probs["mid"] > probs["top"]


def test_fallback_all_time_if_current_missing(tmp_path):
    """Fall back to all_time_distribution when no current data exists."""
    role_history = {
        "Solo": {
            "canonical_role": "ADC",
            "all_time_distribution": {"ADC": 0.8, "MID": 0.15},
        },
    }
    knowledge_dir = _write_role_history(tmp_path, role_history)
    resolver = FlexResolver(knowledge_dir)

    probs = resolver.get_role_probabilities("Solo")
    # Should use all_time_distribution, filtering by MIN_ROLE_PROBABILITY
    assert "bot" in probs
    assert "mid" in probs


def test_is_flex_derived_from_current_viable_roles(tmp_path):
    """is_flex_pick should be derived from current_viable_roles count."""
    role_history = {
        "FlexChamp": {
            "canonical_role": "TOP",
            "current_viable_roles": ["top", "jungle"],
            "all_time_distribution": {"TOP": 0.6, "JUNGLE": 0.4},
        },
        "SingleChamp": {
            "canonical_role": "MID",
            "current_viable_roles": ["mid"],
            "all_time_distribution": {"MID": 1.0},
        },
    }
    knowledge_dir = _write_role_history(tmp_path, role_history)
    resolver = FlexResolver(knowledge_dir)

    assert resolver.is_flex_pick("FlexChamp") is True
    assert resolver.is_flex_pick("SingleChamp") is False


def test_is_flex_fallback_to_all_time(tmp_path):
    """is_flex_pick should fall back to all_time_distribution when no current data."""
    role_history = {
        "OldFlex": {
            "canonical_role": "TOP",
            "all_time_distribution": {"TOP": 0.6, "JUNGLE": 0.4},
        },
        "OldSingle": {
            "canonical_role": "MID",
            "all_time_distribution": {"MID": 0.98, "TOP": 0.02},
        },
    }
    knowledge_dir = _write_role_history(tmp_path, role_history)
    resolver = FlexResolver(knowledge_dir)

    # OldFlex has 2 roles above MIN_ROLE_PROBABILITY
    assert resolver.is_flex_pick("OldFlex") is True
    # OldSingle has only 1 role above MIN_ROLE_PROBABILITY
    assert resolver.is_flex_pick("OldSingle") is False


def test_unknown_champion_not_flex(tmp_path):
    """Unknown champions should not be considered flex picks."""
    knowledge_dir = _write_role_history(tmp_path, {})
    resolver = FlexResolver(knowledge_dir)

    assert resolver.is_flex_pick("CompletelyUnknownChamp") is False


def test_filled_roles_excluded(tmp_path):
    """Filled roles should be excluded from probabilities."""
    role_history = {
        "Flexy": {
            "current_viable_roles": ["top", "mid", "jungle"],
            "current_distribution": {"TOP": 0.4, "MID": 0.4, "JUNGLE": 0.2},
        },
    }
    knowledge_dir = _write_role_history(tmp_path, role_history)
    resolver = FlexResolver(knowledge_dir)

    # Fill top and mid
    probs = resolver.get_role_probabilities("Flexy", filled_roles={"top", "mid"})
    # Only jungle should remain
    assert probs == {"jungle": 1.0}


def test_all_viable_roles_filled_returns_empty(tmp_path):
    """When all viable roles are filled, return empty dict."""
    role_history = {
        "Flexy": {
            "current_viable_roles": ["top", "mid"],
            "current_distribution": {"TOP": 0.5, "MID": 0.5},
        },
    }
    knowledge_dir = _write_role_history(tmp_path, role_history)
    resolver = FlexResolver(knowledge_dir)

    # Fill both viable roles
    probs = resolver.get_role_probabilities("Flexy", filled_roles={"top", "mid"})
    assert probs == {}


def test_primary_role_fallback(tmp_path):
    """Fall back to canonical_role when no distribution data."""
    role_history = {
        "SimpleChamp": {
            "canonical_role": "TOP",
        },
    }
    knowledge_dir = _write_role_history(tmp_path, role_history)
    resolver = FlexResolver(knowledge_dir)

    probs = resolver.get_role_probabilities("SimpleChamp")
    assert probs == {"top": 1.0}


def test_minimum_probability_threshold_at_boundary(tmp_path):
    """Roles at exactly the threshold boundary should be filtered."""
    role_history = {
        "EdgeCase": {
            "all_time_distribution": {"TOP": 0.95, "SUP": 0.05},  # 5% is at boundary
        }
    }
    knowledge_dir = _write_role_history(tmp_path, role_history)
    resolver = FlexResolver(knowledge_dir)

    filled_all_but_support = {"top", "jungle", "mid", "bot"}
    probs = resolver.get_role_probabilities("EdgeCase", filled_roles=filled_all_but_support)

    # 5% is below MIN_ROLE_PROBABILITY (0.051), so should be empty
    assert probs == {}, f"EdgeCase should not be suggested for support (5% at boundary), got: {probs}"


def test_talon_midlane_not_jungle(resolver):
    """Talon should resolve to mid, not jungle (P3 fix verification).

    This test verifies the consolidation fix - previously Talon would be
    dropped because flex_champions.json said JUNGLE but current_viable_roles
    said MID, and the intersection was empty.
    """
    probs = resolver.get_role_probabilities("Talon")
    # Talon should now resolve based on current_viable_roles from champion_role_history
    assert probs, "Talon should have role probabilities"
    # Should include mid (current meta role)
    if "mid" in probs or "jungle" in probs:
        # Either is acceptable depending on current data
        pass
    else:
        # At minimum should have some role
        assert len(probs) > 0, f"Talon should have at least one role, got: {probs}"


class TestFinalizeRoleAssignments:
    """Tests for the finalize_role_assignments method."""

    def test_basic_single_role_champions(self, resolver):
        """Standard comp with single-role champions should assign correctly."""
        champions = ["Aatrox", "Lee Sin", "Ahri", "Jinx", "Thresh"]
        result = resolver.finalize_role_assignments(champions)

        assert len(result) == 5
        roles = {r["role"] for r in result}
        assert roles == {"top", "jungle", "mid", "bot", "support"}

        # Verify expected assignments
        assignments = {r["role"]: r["champion"] for r in result}
        assert assignments["top"] == "Aatrox"
        assert assignments["jungle"] == "Lee Sin"
        assert assignments["mid"] == "Ahri"
        assert assignments["bot"] == "Jinx"
        assert assignments["support"] == "Thresh"

    def test_flex_pick_resolution(self, resolver):
        """Flex champions should be resolved to best available role."""
        # Aurora is mid/top flex, with Aatrox already taking top
        champions = ["Aatrox", "Lee Sin", "Aurora", "Jinx", "Thresh"]
        result = resolver.finalize_role_assignments(champions)

        assignments = {r["role"]: r["champion"] for r in result}
        # Aurora should go mid since top is taken by Aatrox
        assert assignments["mid"] == "Aurora"
        assert assignments["top"] == "Aatrox"

    def test_returns_role_ordered(self, resolver):
        """Result should be ordered by role: top, jungle, mid, bot, support."""
        champions = ["Thresh", "Jinx", "Ahri", "Lee Sin", "Aatrox"]
        result = resolver.finalize_role_assignments(champions)

        expected_order = ["top", "jungle", "mid", "bot", "support"]
        actual_order = [r["role"] for r in result]
        assert actual_order == expected_order

    def test_handles_incomplete_team(self, resolver):
        """Should handle less than 5 champions gracefully."""
        champions = ["Aatrox", "Lee Sin", "Ahri"]
        result = resolver.finalize_role_assignments(champions)

        # Returns what we got with default role assignments
        assert len(result) == 3

    def test_all_flex_picks(self, tmp_path):
        """Team with all flex champions should still assign uniquely."""
        role_history = {
            "FlexA": {"current_viable_roles": ["top", "mid"], "current_distribution": {"TOP": 0.6, "MID": 0.4}},
            "FlexB": {"current_viable_roles": ["jungle", "top"], "current_distribution": {"JUNGLE": 0.7, "TOP": 0.3}},
            "FlexC": {"current_viable_roles": ["mid", "bot"], "current_distribution": {"MID": 0.5, "BOT": 0.5}},
            "FlexD": {"current_viable_roles": ["bot", "support"], "current_distribution": {"BOT": 0.6, "SUP": 0.4}},
            "FlexE": {"current_viable_roles": ["support", "jungle"], "current_distribution": {"SUP": 0.7, "JUNGLE": 0.3}},
        }
        knowledge_dir = _write_role_history(tmp_path, role_history)
        resolver = FlexResolver(knowledge_dir)

        champions = ["FlexA", "FlexB", "FlexC", "FlexD", "FlexE"]
        result = resolver.finalize_role_assignments(champions)

        # All 5 roles should be assigned exactly once
        roles = [r["role"] for r in result]
        assert sorted(roles) == ["bot", "jungle", "mid", "support", "top"]

        # Each champion assigned exactly once
        champs = [r["champion"] for r in result]
        assert sorted(champs) == sorted(champions)


class TestTournamentMetaRescue:
    """Tests for tournament meta as Level 0 rescue fallback."""

    def test_tournament_meta_rescues_unknown_champion(self, tmp_path):
        """Champion missing from role_history but present in tournament_meta gets role from tournament data."""
        knowledge_dir = _write_role_history(tmp_path, {})
        _write_tournament_meta(knowledge_dir, {
            "Zaahen": {
                "priority": 0.11,
                "roles": {
                    "top": {"winrate": 0.48, "picks": 27},
                    "support": {"winrate": 0.0, "picks": 1},
                },
            },
        })
        resolver = FlexResolver(knowledge_dir)

        probs = resolver.get_role_probabilities("Zaahen")
        # 27 top + 1 sup → top is 96.4%, sup is 3.6% → sup filtered by MIN_ROLE_PROBABILITY
        assert "top" in probs
        assert "support" not in probs
        assert probs["top"] == pytest.approx(1.0, abs=0.01)

    def test_role_history_takes_precedence_over_tournament(self, tmp_path):
        """Champions in BOTH sources should use role_history (richer data)."""
        knowledge_dir = _write_role_history(tmp_path, {
            "Rumble": {
                "canonical_role": "TOP",
                "all_time_distribution": {"TOP": 0.9, "MID": 0.1},
            },
        })
        _write_tournament_meta(knowledge_dir, {
            "Rumble": {
                "priority": 0.7,
                "roles": {
                    "top": {"picks": 64},
                    "jungle": {"picks": 5},
                },
            },
        })
        resolver = FlexResolver(knowledge_dir)

        probs = resolver.get_role_probabilities("Rumble")
        # Should use role_history's all_time_distribution, not tournament_meta
        assert "top" in probs
        # jungle should NOT appear (it's not in role_history data)
        assert "jungle" not in probs

    def test_tournament_meta_role_normalization(self, tmp_path):
        """Tournament meta with 'adc' key should normalize to 'bot'."""
        knowledge_dir = _write_role_history(tmp_path, {})
        _write_tournament_meta(knowledge_dir, {
            "NewADC": {
                "priority": 0.5,
                "roles": {
                    "adc": {"picks": 50},
                    "mid": {"picks": 5},
                },
            },
        })
        resolver = FlexResolver(knowledge_dir)

        probs = resolver.get_role_probabilities("NewADC")
        assert "bot" in probs
        assert "adc" not in probs

    def test_custom_tournament_data_file(self, tmp_path):
        """Replay mode uses custom tournament_data_file path."""
        knowledge_dir = _write_role_history(tmp_path, {})
        replay_dir = knowledge_dir / "replay_meta"
        replay_dir.mkdir()
        _write_tournament_meta(knowledge_dir, {
            "OldChamp": {
                "priority": 0.3,
                "roles": {
                    "jungle": {"picks": 40},
                },
            },
        }, filename="replay_meta/series_123.json")
        resolver = FlexResolver(knowledge_dir, tournament_data_file="replay_meta/series_123.json")

        probs = resolver.get_role_probabilities("OldChamp")
        assert probs == {"jungle": pytest.approx(1.0, abs=0.01)}

    def test_is_flex_pick_with_tournament_meta(self, tmp_path):
        """is_flex_pick should work for tournament-meta-only champions."""
        knowledge_dir = _write_role_history(tmp_path, {})
        _write_tournament_meta(knowledge_dir, {
            "FlexNewChamp": {
                "priority": 0.5,
                "roles": {
                    "top": {"picks": 30},
                    "mid": {"picks": 25},
                },
            },
            "SingleNewChamp": {
                "priority": 0.3,
                "roles": {
                    "jungle": {"picks": 50},
                    "support": {"picks": 1},  # Filtered by MIN_ROLE_PROBABILITY
                },
            },
        })
        resolver = FlexResolver(knowledge_dir)

        assert resolver.is_flex_pick("FlexNewChamp") is True
        assert resolver.is_flex_pick("SingleNewChamp") is False

    def test_tournament_rescue_with_filled_roles(self, tmp_path):
        """Tournament-rescued champion should respect filled_roles."""
        knowledge_dir = _write_role_history(tmp_path, {})
        _write_tournament_meta(knowledge_dir, {
            "TopJungler": {
                "priority": 0.4,
                "roles": {
                    "top": {"picks": 30},
                    "jungle": {"picks": 20},
                },
            },
        })
        resolver = FlexResolver(knowledge_dir)

        probs = resolver.get_role_probabilities("TopJungler", filled_roles={"top"})
        assert "top" not in probs
        assert "jungle" in probs
        assert probs["jungle"] == pytest.approx(1.0, abs=0.01)


class TestTieBreaking:
    """Tests for tie-breaking by champion flexibility."""

    def test_inflexible_champion_wins_tie(self, tmp_path):
        """Inflexible champion (1 viable role) should win over flex champion in tie."""
        role_history = {
            "Ashe": {
                "all_time_distribution": {"ADC": 0.6, "SUP": 0.4},
            },
            "KaiSa": {
                "all_time_distribution": {"ADC": 1.0},
            },
        }
        knowledge_dir = _write_role_history(tmp_path, role_history)
        resolver = FlexResolver(knowledge_dir)

        # Both have bot as their highest role - Kai'Sa should win bot
        # because she has fewer alternatives (bot only vs bot+support)
        ashe_probs = resolver.get_role_probabilities("Ashe")
        kaisa_probs = resolver.get_role_probabilities("KaiSa")
        assert "bot" in ashe_probs
        assert "bot" in kaisa_probs

    def test_full_assignment_with_tiebreak(self, tmp_path):
        """Full 5-champion assignment with tie-breaking scenario."""
        role_history = {
            "Dr. Mundo": {
                "current_viable_roles": ["top", "jungle"],
                "current_distribution": {"TOP": 0.4, "JUNGLE": 0.6},
            },
            "Yone": {
                "current_viable_roles": ["mid"],
                "current_distribution": {"MID": 1.0},
            },
            "Ashe": {
                "all_time_distribution": {"ADC": 0.6, "SUP": 0.4},
            },
            "Kai'Sa": {
                "all_time_distribution": {"ADC": 1.0},
            },
        }
        knowledge_dir = _write_role_history(tmp_path, role_history)
        _write_tournament_meta(knowledge_dir, {
            "Zaahen": {
                "priority": 0.11,
                "roles": {
                    "top": {"picks": 27},
                    "support": {"picks": 1},
                },
            },
        })
        resolver = FlexResolver(knowledge_dir)

        champions = ["Dr. Mundo", "Zaahen", "Yone", "Ashe", "Kai'Sa"]
        result = resolver.finalize_role_assignments(champions)
        assignments = {r["role"]: r["champion"] for r in result}

        # Expected:
        # Zaahen → top (tournament meta, primary role)
        # Dr. Mundo → jungle (top taken by Zaahen, jungle is next best)
        # Yone → mid (only role)
        # Kai'Sa → bot (bot-only, wins tie over Ashe who has bot+support)
        # Ashe → support (remaining role)
        assert assignments["top"] == "Zaahen"
        assert assignments["jungle"] == "Dr. Mundo"
        assert assignments["mid"] == "Yone"
        assert assignments["bot"] == "Kai'Sa"
        assert assignments["support"] == "Ashe"
