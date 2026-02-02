"""Tests for tournament meta scoring."""
import json
import pytest
from ban_teemo.services.scorers.tournament_scorer import TournamentScorer


def _write_tournament_data(tmp_path, champions, defaults=None):
    """Helper to create test tournament meta file."""
    knowledge_dir = tmp_path / "knowledge"
    knowledge_dir.mkdir(exist_ok=True)

    if defaults is None:
        defaults = {
            "missing_champion_priority": 0.05,
            "missing_champion_performance": 0.35,
            "note": "Test defaults",
        }

    data = {
        "metadata": {
            "source": "test.csv",
            "generated_at": "2026-02-01T00:00:00Z",
            "patch": "26.1",
            "champion_count": len(champions),
        },
        "champions": champions,
        "defaults": defaults,
    }

    (knowledge_dir / "tournament_meta.json").write_text(json.dumps(data))
    return knowledge_dir


# ======================================================================
# Priority Score Tests (Role-Agnostic)
# ======================================================================


def test_get_priority_returns_champion_priority(tmp_path):
    """Priority returns the stored priority value."""
    knowledge_dir = _write_tournament_data(
        tmp_path,
        {
            "Jayce": {"priority": 0.86, "roles": {}},
            "Rumble": {"priority": 0.70, "roles": {}},
        },
    )
    scorer = TournamentScorer(knowledge_dir=knowledge_dir)

    assert scorer.get_priority("Jayce") == 0.86
    assert scorer.get_priority("Rumble") == 0.70


def test_get_priority_missing_champion_returns_penalty(tmp_path):
    """Missing champion returns the penalty value from defaults."""
    knowledge_dir = _write_tournament_data(
        tmp_path,
        {"Jayce": {"priority": 0.86, "roles": {}}},
        defaults={
            "missing_champion_priority": 0.05,
            "missing_champion_performance": 0.35,
        },
    )
    scorer = TournamentScorer(knowledge_dir=knowledge_dir)

    assert scorer.get_priority("Teemo") == 0.05


def test_priority_is_role_agnostic(tmp_path):
    """Priority is the same regardless of what role is queried."""
    knowledge_dir = _write_tournament_data(
        tmp_path,
        {
            "Jayce": {
                "priority": 0.86,
                "roles": {
                    "top": {"winrate": 1.0, "picks": 1, "adjusted_performance": 0.55},
                    "mid": {"winrate": 0.5, "picks": 10, "adjusted_performance": 0.5},
                },
            }
        },
    )
    scorer = TournamentScorer(knowledge_dir=knowledge_dir)

    # Priority should be the same for any role query
    scores_top = scorer.get_tournament_scores("Jayce", "top")
    scores_mid = scorer.get_tournament_scores("Jayce", "mid")

    assert scores_top["priority"] == scores_mid["priority"] == 0.86


# ======================================================================
# Performance Score Tests (Role-Specific)
# ======================================================================


def test_get_performance_returns_role_specific_value(tmp_path):
    """Performance returns the adjusted_performance for the specific role."""
    knowledge_dir = _write_tournament_data(
        tmp_path,
        {
            "Jayce": {
                "priority": 0.86,
                "roles": {
                    "top": {"winrate": 1.0, "picks": 1, "adjusted_performance": 0.55},
                    "jungle": {
                        "winrate": 0.47,
                        "picks": 19,
                        "adjusted_performance": 0.47,
                    },
                    "mid": {"winrate": 1.0, "picks": 1, "adjusted_performance": 0.55},
                },
            }
        },
    )
    scorer = TournamentScorer(knowledge_dir=knowledge_dir)

    assert scorer.get_performance("Jayce", "top") == 0.55
    assert scorer.get_performance("Jayce", "jungle") == 0.47
    assert scorer.get_performance("Jayce", "mid") == 0.55


def test_get_performance_missing_role_returns_penalty(tmp_path):
    """Champion exists but role doesn't - returns penalty."""
    knowledge_dir = _write_tournament_data(
        tmp_path,
        {
            "Rumble": {
                "priority": 0.70,
                "roles": {
                    "top": {"winrate": 0.56, "picks": 64, "adjusted_performance": 0.56}
                },
            }
        },
        defaults={
            "missing_champion_priority": 0.05,
            "missing_champion_performance": 0.35,
        },
    )
    scorer = TournamentScorer(knowledge_dir=knowledge_dir)

    # Rumble has top data but not mid
    assert scorer.get_performance("Rumble", "top") == 0.56
    assert scorer.get_performance("Rumble", "mid") == 0.35  # Penalty


def test_get_performance_missing_champion_returns_penalty(tmp_path):
    """Missing champion entirely returns penalty."""
    knowledge_dir = _write_tournament_data(
        tmp_path,
        {"Jayce": {"priority": 0.86, "roles": {}}},
        defaults={
            "missing_champion_priority": 0.05,
            "missing_champion_performance": 0.35,
        },
    )
    scorer = TournamentScorer(knowledge_dir=knowledge_dir)

    assert scorer.get_performance("Teemo", "top") == 0.35


# ======================================================================
# Asymmetric Blending Tests (verified through build script output)
# ======================================================================


def test_performance_high_wr_low_sample_is_blended(tmp_path):
    """High winrate + low sample should be blended toward 0.5."""
    # This tests the data that was already blended by build script
    # Jayce top: 100% WR, 1 pick -> should be blended to ~0.55
    knowledge_dir = _write_tournament_data(
        tmp_path,
        {
            "Jayce": {
                "priority": 0.86,
                "roles": {
                    "top": {
                        "winrate": 1.0,
                        "picks": 1,
                        "adjusted_performance": 0.55,  # Blended: 0.1*1.0 + 0.9*0.5
                    }
                },
            }
        },
    )
    scorer = TournamentScorer(knowledge_dir=knowledge_dir)

    # The blending happened in build script, scorer just returns stored value
    assert scorer.get_performance("Jayce", "top") == 0.55


def test_performance_low_wr_preserved_as_warning(tmp_path):
    """Low winrate should be preserved regardless of sample size."""
    # Mordekaiser: 11% WR, 9 picks -> should stay at 0.11
    knowledge_dir = _write_tournament_data(
        tmp_path,
        {
            "Mordekaiser": {
                "priority": 0.01,
                "roles": {
                    "top": {
                        "winrate": 0.11,
                        "picks": 9,
                        "adjusted_performance": 0.11,  # Preserved warning
                    }
                },
            }
        },
    )
    scorer = TournamentScorer(knowledge_dir=knowledge_dir)

    assert scorer.get_performance("Mordekaiser", "top") == 0.11


def test_performance_high_sample_not_blended(tmp_path):
    """High sample (>=10) should not be blended."""
    knowledge_dir = _write_tournament_data(
        tmp_path,
        {
            "Azir": {
                "priority": 0.53,
                "roles": {
                    "mid": {
                        "winrate": 0.49,
                        "picks": 82,
                        "adjusted_performance": 0.49,  # Not blended - enough sample
                    }
                },
            }
        },
    )
    scorer = TournamentScorer(knowledge_dir=knowledge_dir)

    assert scorer.get_performance("Azir", "mid") == 0.49


# ======================================================================
# Full Scores Tests
# ======================================================================


def test_get_tournament_scores_returns_all_fields(tmp_path):
    """get_tournament_scores returns complete data for UI."""
    knowledge_dir = _write_tournament_data(
        tmp_path,
        {
            "Rumble": {
                "priority": 0.70,
                "roles": {
                    "top": {"winrate": 0.56, "picks": 64, "adjusted_performance": 0.56}
                },
            }
        },
    )
    scorer = TournamentScorer(knowledge_dir=knowledge_dir)

    scores = scorer.get_tournament_scores("Rumble", "top")

    assert scores["priority"] == 0.70
    assert scores["performance"] == 0.56
    assert scores["has_data"] is True
    assert scores["role_has_data"] is True
    assert scores["picks"] == 64


def test_get_tournament_scores_missing_champion(tmp_path):
    """Missing champion shows appropriate flags."""
    knowledge_dir = _write_tournament_data(
        tmp_path,
        {"Jayce": {"priority": 0.86, "roles": {}}},
        defaults={
            "missing_champion_priority": 0.05,
            "missing_champion_performance": 0.35,
        },
    )
    scorer = TournamentScorer(knowledge_dir=knowledge_dir)

    scores = scorer.get_tournament_scores("Teemo", "top")

    assert scores["priority"] == 0.05
    assert scores["performance"] == 0.35
    assert scores["has_data"] is False
    assert scores["role_has_data"] is False
    assert scores["picks"] == 0


def test_get_tournament_scores_missing_role(tmp_path):
    """Champion exists but role missing shows appropriate flags."""
    knowledge_dir = _write_tournament_data(
        tmp_path,
        {
            "Rumble": {
                "priority": 0.70,
                "roles": {
                    "top": {"winrate": 0.56, "picks": 64, "adjusted_performance": 0.56}
                },
            }
        },
        defaults={
            "missing_champion_priority": 0.05,
            "missing_champion_performance": 0.35,
        },
    )
    scorer = TournamentScorer(knowledge_dir=knowledge_dir)

    scores = scorer.get_tournament_scores("Rumble", "mid")

    assert scores["priority"] == 0.70  # Champion exists, so priority is known
    assert scores["performance"] == 0.35  # Role missing, use penalty
    assert scores["has_data"] is True
    assert scores["role_has_data"] is False
    assert scores["picks"] == 0


# ======================================================================
# Role Normalization Tests
# ======================================================================


def test_role_normalization(tmp_path):
    """Role names are normalized (case-insensitive)."""
    knowledge_dir = _write_tournament_data(
        tmp_path,
        {
            "Jayce": {
                "priority": 0.86,
                "roles": {
                    "jungle": {
                        "winrate": 0.47,
                        "picks": 19,
                        "adjusted_performance": 0.47,
                    }
                },
            }
        },
    )
    scorer = TournamentScorer(knowledge_dir=knowledge_dir)

    # All these should work
    assert scorer.get_performance("Jayce", "jungle") == 0.47
    assert scorer.get_performance("Jayce", "Jungle") == 0.47
    assert scorer.get_performance("Jayce", "JUNGLE") == 0.47


# ======================================================================
# Integration with Real Data
# ======================================================================


@pytest.fixture
def real_scorer():
    """Scorer using real tournament_meta.json if available."""
    return TournamentScorer()


def test_real_data_jayce_priority(real_scorer):
    """Verify Jayce priority from real data."""
    priority = real_scorer.get_priority("Jayce")
    assert priority == 0.86


def test_real_data_jayce_jungle_performance(real_scorer):
    """Verify Jayce jungle performance from real data."""
    performance = real_scorer.get_performance("Jayce", "jungle")
    assert performance == 0.47


def test_real_data_missing_champion_penalty(real_scorer):
    """Verify missing champion gets penalty."""
    priority = real_scorer.get_priority("Teemo")
    performance = real_scorer.get_performance("Teemo", "top")

    assert priority == 0.05
    assert performance == 0.35


# ======================================================================
# Custom Data File Tests
# ======================================================================


def test_custom_data_file_path(tmp_path):
    """TournamentScorer can load data from a custom file path."""
    knowledge_dir = tmp_path / "knowledge"
    knowledge_dir.mkdir(exist_ok=True)
    replay_meta_dir = knowledge_dir / "replay_meta"
    replay_meta_dir.mkdir(exist_ok=True)

    # Write custom meta file
    custom_data = {
        "metadata": {
            "tournament_id": "756908",
            "tournament_name": "LCK - Spring 2024 (Playoffs)",
            "window_start": "2024-02-01",
            "window_end": "2024-03-30",
            "games_analyzed": 150,
        },
        "champions": {
            "Azir": {"priority": 0.75, "roles": {"mid": {"adjusted_performance": 0.55, "picks": 20}}}
        },
        "defaults": {"missing_champion_priority": 0.05, "missing_champion_performance": 0.35},
    }
    (replay_meta_dir / "756908.json").write_text(json.dumps(custom_data))

    scorer = TournamentScorer(knowledge_dir=knowledge_dir, data_file="replay_meta/756908.json")

    assert scorer.get_priority("Azir") == 0.75
    assert scorer.get_performance("Azir", "mid") == 0.55
