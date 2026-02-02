"""Tests for role-phase prior scoring."""
import json
import pytest
from ban_teemo.services.scorers.role_phase_scorer import RolePhaseScorer


def _write_role_phase_data(tmp_path, distribution):
    """Helper to create test knowledge files."""
    knowledge_dir = tmp_path / "knowledge"
    knowledge_dir.mkdir(exist_ok=True)
    (knowledge_dir / "role_pick_phase.json").write_text(json.dumps(distribution))
    return knowledge_dir


@pytest.fixture
def scorer():
    """Use actual knowledge data for integration tests."""
    return RolePhaseScorer()


# ======================================================================
# Basic Multiplier Tests
# ======================================================================


def test_support_early_p1_penalty(scorer):
    """Support gets significant penalty in early phase 1."""
    mult = scorer.get_multiplier("support", total_picks=0)
    # With 8% empirical vs 20% uniform: 0.08/0.20 = 0.40
    assert 0.35 <= mult <= 0.45


def test_support_late_p1_penalty(scorer):
    """Support gets moderate penalty in late phase 1."""
    mult = scorer.get_multiplier("support", total_picks=4)
    # With 16.8% empirical vs 20% uniform: 0.168/0.20 = 0.84
    assert 0.80 <= mult <= 0.90


def test_support_p2_no_penalty(scorer):
    """Support gets no penalty in phase 2 (common pick phase)."""
    mult = scorer.get_multiplier("support", total_picks=7)
    # With 32% empirical vs 20% uniform: 1.0 (capped, no boost)
    assert mult == 1.0


def test_jungle_early_p1_no_penalty(scorer):
    """Jungle gets no penalty in early phase 1 (common pick phase)."""
    mult = scorer.get_multiplier("jungle", total_picks=0)
    # With 27.3% empirical vs 20% uniform: capped at 1.0
    assert mult == 1.0


def test_jungle_p2_penalty(scorer):
    """Jungle gets penalty in phase 2."""
    mult = scorer.get_multiplier("jungle", total_picks=7)
    # With 12.6% empirical vs 20% uniform: 0.126/0.20 = 0.63
    assert 0.60 <= mult <= 0.70


def test_mid_p2_penalty(scorer):
    """Mid gets penalty in phase 2."""
    mult = scorer.get_multiplier("mid", total_picks=7)
    # With 13.8% empirical vs 20% uniform: 0.138/0.20 = 0.69
    assert 0.65 <= mult <= 0.75


def test_bot_late_p1_penalty(scorer):
    """Bot gets slight penalty in late phase 1."""
    mult = scorer.get_multiplier("bot", total_picks=4)
    # With 16.4% empirical vs 20% uniform: 0.164/0.20 = 0.82
    assert 0.78 <= mult <= 0.86


def test_top_early_p1_slight_penalty(scorer):
    """Top gets slight penalty in early phase 1."""
    mult = scorer.get_multiplier("top", total_picks=0)
    # With 18.3% empirical vs 20% uniform: 0.183/0.20 = 0.915
    assert 0.88 <= mult <= 0.96


# ======================================================================
# Edge Cases
# ======================================================================


def test_unknown_role_no_penalty(scorer):
    """Unknown role returns 1.0 (no penalty)."""
    mult = scorer.get_multiplier("unknown_role", total_picks=0)
    assert mult == 1.0


def test_empty_role_no_penalty(scorer):
    """Empty role returns 1.0 (no penalty)."""
    mult = scorer.get_multiplier("", total_picks=0)
    assert mult == 1.0


def test_none_role_no_penalty(scorer):
    """None role returns 1.0 (no penalty)."""
    mult = scorer.get_multiplier(None, total_picks=0)
    assert mult == 1.0


def test_missing_knowledge_file_no_penalty(tmp_path):
    """Missing knowledge file returns 1.0 (no penalty)."""
    knowledge_dir = tmp_path / "knowledge"
    knowledge_dir.mkdir(exist_ok=True)
    # No role_pick_phase.json created
    scorer = RolePhaseScorer(knowledge_dir)
    mult = scorer.get_multiplier("support", total_picks=0)
    assert mult == 1.0


def test_role_case_insensitive(scorer):
    """Role lookup is case-insensitive."""
    mult_lower = scorer.get_multiplier("support", total_picks=0)
    mult_upper = scorer.get_multiplier("SUPPORT", total_picks=0)
    mult_mixed = scorer.get_multiplier("Support", total_picks=0)
    assert mult_lower == mult_upper == mult_mixed


# ======================================================================
# Phase Mapping Tests
# ======================================================================


def test_phase_mapping_early_p1(scorer):
    """Picks 0-2 map to early_p1."""
    for picks in [0, 1, 2]:
        assert scorer._get_phase(picks) == "early_p1"


def test_phase_mapping_late_p1(scorer):
    """Picks 3-5 map to late_p1."""
    for picks in [3, 4, 5]:
        assert scorer._get_phase(picks) == "late_p1"


def test_phase_mapping_p2(scorer):
    """Picks 6-9 map to p2."""
    for picks in [6, 7, 8, 9]:
        assert scorer._get_phase(picks) == "p2"


# ======================================================================
# Custom Distribution Tests
# ======================================================================


def test_custom_distribution(tmp_path):
    """Test with custom distribution data."""
    knowledge_dir = _write_role_phase_data(
        tmp_path,
        {
            "support": {"early_p1": 0.05, "late_p1": 0.10, "p2": 0.40},
            "jungle": {"early_p1": 0.30, "late_p1": 0.25, "p2": 0.10},
        },
    )
    scorer = RolePhaseScorer(knowledge_dir)

    # Support early: 0.05/0.20 = 0.25
    assert scorer.get_multiplier("support", total_picks=0) == 0.25

    # Jungle early: 0.30/0.20 = 1.5, but capped at 1.0
    assert scorer.get_multiplier("jungle", total_picks=0) == 1.0


def test_get_distribution(scorer):
    """Test get_distribution returns role data."""
    dist = scorer.get_distribution("support")
    assert "early_p1" in dist
    assert "late_p1" in dist
    assert "p2" in dist
    assert all(0 < v < 1 for v in dist.values())


def test_get_distribution_unknown_role(scorer):
    """Unknown role returns empty distribution."""
    dist = scorer.get_distribution("unknown_role")
    assert dist == {}


# ======================================================================
# Multiplier Never Exceeds 1.0 (Penalty-Only)
# ======================================================================


def test_multiplier_never_exceeds_one(scorer):
    """Multiplier is capped at 1.0 (no boost, only penalty)."""
    for role in ["top", "jungle", "mid", "bot", "support"]:
        for picks in range(10):
            mult = scorer.get_multiplier(role, picks)
            assert mult <= 1.0, f"Role {role} at picks {picks} exceeded 1.0"
            assert mult >= 0.0, f"Role {role} at picks {picks} below 0.0"
