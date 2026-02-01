"""Tests for SkillTransferService."""
import json

from ban_teemo.services.scorers.skill_transfer_service import SkillTransferService


def _write_skill_transfer(tmp_path, transfers):
    knowledge_dir = tmp_path / "knowledge"
    knowledge_dir.mkdir()
    (knowledge_dir / "skill_transfers.json").write_text(
        json.dumps({"transfers": transfers})
    )
    return knowledge_dir


def test_get_similar_champions_returns_sorted(tmp_path):
    transfers = {
        "TestChamp": {
            "similar_champions": [
                {"champion": "A", "co_play_rate": 0.2},
                {"champion": "B", "co_play_rate": 0.9},
                {"champion": "C", "co_play_rate": 0.5},
            ]
        }
    }
    knowledge_dir = _write_skill_transfer(tmp_path, transfers)
    service = SkillTransferService(knowledge_dir)

    results = service.get_similar_champions("TestChamp")
    assert [entry["champion"] for entry in results] == ["B", "C", "A"]


def test_get_best_transfer_respects_available_pool(tmp_path):
    transfers = {
        "TestChamp": {
            "similar_champions": [
                {"champion": "A", "co_play_rate": 0.9},
                {"champion": "B", "co_play_rate": 0.8},
            ]
        }
    }
    knowledge_dir = _write_skill_transfer(tmp_path, transfers)
    service = SkillTransferService(knowledge_dir)

    best = service.get_best_transfer("TestChamp", {"B"})
    assert best["champion"] == "B"
