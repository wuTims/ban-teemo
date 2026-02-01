"""Skill transfer service for suggesting similar champions."""
import json
from pathlib import Path
from typing import Optional


class SkillTransferService:
    """Access skill transfer data for similar champion suggestions."""

    def __init__(self, knowledge_dir: Optional[Path] = None):
        if knowledge_dir is None:
            knowledge_dir = Path(__file__).parents[5] / "knowledge"
        self.knowledge_dir = knowledge_dir
        self._transfers: dict = {}
        self._load_data()

    def _load_data(self):
        """Load skill transfer data."""
        path = self.knowledge_dir / "skill_transfers.json"
        if path.exists():
            with open(path) as f:
                data = json.load(f)
                self._transfers = data.get("transfers", {})

    def get_similar_champions(self, champion_name: str, limit: Optional[int] = None) -> list[dict]:
        """Return similar champions sorted by co_play_rate descending."""
        entry = self._transfers.get(champion_name, {})
        similar = entry.get("similar_champions", [])
        if not isinstance(similar, list):
            return []

        ranked = sorted(similar, key=lambda x: x.get("co_play_rate", 0), reverse=True)
        if limit is not None:
            return ranked[:limit]
        return ranked

    def get_best_transfer(self, champion_name: str, available_champions: set[str]) -> Optional[dict]:
        """Return best transfer candidate within available champions."""
        if not available_champions:
            return None
        for entry in self.get_similar_champions(champion_name):
            target = entry.get("champion")
            if target in available_champions:
                return entry
        return None
