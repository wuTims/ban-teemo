"""Diagnostic logging for scoring system analysis.

This module provides a way to capture detailed scoring information
during replay and simulation runs for debugging and analysis.

Usage:
    from ban_teemo.services.scoring_logger import ScoringLogger

    # In your service that generates recommendations:
    logger = ScoringLogger()
    logger.start_session("session-123", "simulator", {...metadata})

    # Log recommendation requests and outputs
    logger.log_pick_recommendations(action_count, recommendations, ...)
    logger.log_actual_action(action_count, "pick", "blue", "Azir", was_rec, rank)

    # Save when done
    logger.save()
"""
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

# Configure module logger
module_logger = logging.getLogger("ban_teemo.scoring_diagnostics")


class ScoringLogger:
    """Captures detailed scoring diagnostics for analysis."""

    def __init__(self, output_dir: Optional[Path] = None, enabled: bool = True):
        """Initialize scoring logger.

        Args:
            output_dir: Directory to save diagnostic files. Defaults to logs/scoring/
            enabled: Whether logging is active. Can be controlled via SCORING_DIAGNOSTICS env var.
        """
        # Check environment variable for override
        env_enabled = os.environ.get("SCORING_DIAGNOSTICS", "").lower()
        if env_enabled == "true":
            enabled = True
        elif env_enabled == "false":
            enabled = False

        self.enabled = enabled
        self.output_dir = output_dir or Path(__file__).parents[4] / "logs" / "scoring"
        self.entries: list[dict] = []
        self.session_id: str = ""
        self.mode: str = ""
        self._metadata: dict = {}

        if self.enabled:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            module_logger.info(f"Scoring diagnostics enabled, output dir: {self.output_dir}")

    def start_session(
        self,
        session_id: str,
        mode: str,
        blue_team: str,
        red_team: str,
        coaching_side: Optional[str] = None,
        series_id: Optional[str] = None,
        game_number: Optional[int] = None,
        extra_metadata: Optional[dict] = None,
    ):
        """Initialize a new diagnostic session.

        Args:
            session_id: Unique session identifier
            mode: "replay" or "simulator"
            blue_team: Blue team name
            red_team: Red team name
            coaching_side: Which side we're coaching (simulator only)
            series_id: Series identifier (replay only)
            game_number: Game number in series
            extra_metadata: Any additional metadata to capture
        """
        if not self.enabled:
            return

        self.session_id = session_id
        self.mode = mode
        self.entries = []
        self._metadata = {
            "session_id": session_id,
            "mode": mode,
            "blue_team": blue_team,
            "red_team": red_team,
            "coaching_side": coaching_side,
            "series_id": series_id,
            "game_number": game_number,
            "started_at": datetime.now().isoformat(),
            **(extra_metadata or {})
        }

        self.entries.append({
            "event": "session_start",
            "timestamp": datetime.now().isoformat(),
            **self._metadata
        })

    def log_draft_state(
        self,
        action_count: int,
        phase: str,
        blue_picks: list[str],
        red_picks: list[str],
        blue_bans: list[str],
        red_bans: list[str],
    ):
        """Log current draft state."""
        if not self.enabled:
            return

        self.entries.append({
            "event": "draft_state",
            "timestamp": datetime.now().isoformat(),
            "action_count": action_count,
            "phase": phase,
            "blue_picks": blue_picks,
            "red_picks": red_picks,
            "blue_bans": blue_bans,
            "red_bans": red_bans,
        })

    def log_pick_recommendations(
        self,
        action_count: int,
        phase: str,
        for_team: str,
        our_picks: list[str],
        enemy_picks: list[str],
        banned: list[str],
        team_players: list[dict],
        candidates_count: int,
        filled_roles: list[str],
        unfilled_roles: list[str],
        recommendations: list[dict],
    ):
        """Log pick recommendation request and output with full details.

        Args:
            action_count: Current action number in draft
            phase: Draft phase (PICK_PHASE_1, etc.)
            for_team: Team receiving recommendations ("blue" or "red")
            our_picks: Champions already picked by our team
            enemy_picks: Champions already picked by enemy
            banned: All banned champions
            team_players: Player roster with name/role
            candidates_count: Number of candidates evaluated
            filled_roles: Roles already filled
            unfilled_roles: Roles still needing picks
            recommendations: Full recommendation output from engine
        """
        if not self.enabled:
            return

        self.entries.append({
            "event": "pick_recommendations",
            "timestamp": datetime.now().isoformat(),
            "action_count": action_count,
            "phase": phase,
            "for_team": for_team,
            "context": {
                "our_picks": our_picks,
                "enemy_picks": enemy_picks,
                "banned": banned,
                "team_players": [{"name": p["name"], "role": p["role"]} for p in team_players],
            },
            "analysis": {
                "candidates_evaluated": candidates_count,
                "filled_roles": filled_roles,
                "unfilled_roles": unfilled_roles,
            },
            "recommendations": [
                {
                    "rank": i + 1,
                    "champion": rec.get("champion_name"),
                    "role": rec.get("suggested_role"),
                    "score": rec.get("score") or rec.get("confidence"),
                    "base_score": rec.get("base_score"),
                    "synergy_multiplier": rec.get("synergy_multiplier"),
                    "confidence": rec.get("confidence"),
                    "components": rec.get("components", {}),
                    "flag": rec.get("flag"),
                    "reasons": rec.get("reasons", []),
                }
                for i, rec in enumerate(recommendations[:10])  # Top 10 only
            ]
        })

    def log_ban_recommendations(
        self,
        action_count: int,
        phase: str,
        for_team: str,
        our_picks: list[str],
        enemy_picks: list[str],
        banned: list[str],
        enemy_players: list[dict],
        recommendations: list[dict],
    ):
        """Log ban recommendation output.

        Args:
            action_count: Current action number
            phase: Draft phase
            for_team: Team receiving recommendations
            our_picks: Our current picks
            enemy_picks: Enemy current picks
            banned: Already banned champions
            enemy_players: Enemy roster
            recommendations: Ban recommendations from service
        """
        if not self.enabled:
            return

        self.entries.append({
            "event": "ban_recommendations",
            "timestamp": datetime.now().isoformat(),
            "action_count": action_count,
            "phase": phase,
            "for_team": for_team,
            "context": {
                "our_picks": our_picks,
                "enemy_picks": enemy_picks,
                "banned": banned,
                "enemy_players": [{"name": p.get("name"), "role": p.get("role")} for p in (enemy_players or [])],
            },
            "recommendations": [
                {
                    "rank": i + 1,
                    "champion": rec["champion_name"],
                    "priority": rec["priority"],
                    "target_player": rec.get("target_player"),
                    "target_role": rec.get("target_role"),
                    "reasons": rec.get("reasons", []),
                    "components": rec.get("components", {}),
                }
                for i, rec in enumerate(recommendations[:10])
            ]
        })

    def log_actual_action(
        self,
        action_count: int,
        action_type: str,
        team: str,
        champion: str,
        recommendations: list[dict],
    ):
        """Log what actually happened vs what was recommended.

        Args:
            action_count: Action sequence number
            action_type: "pick" or "ban"
            team: "blue" or "red"
            champion: Champion that was actually picked/banned
            recommendations: The recommendations that were active for this action
        """
        if not self.enabled:
            return

        # Find if actual champion was in recommendations
        was_recommended = False
        recommendation_rank = None
        recommendation_score = None

        for i, rec in enumerate(recommendations):
            rec_champ = rec.get("champion_name") or rec.get("champion")
            if rec_champ == champion:
                was_recommended = True
                recommendation_rank = i + 1
                recommendation_score = rec.get("score") or rec.get("priority")
                break

        self.entries.append({
            "event": "actual_action",
            "timestamp": datetime.now().isoformat(),
            "action_count": action_count,
            "action_type": action_type,
            "team": team,
            "champion": champion,
            "was_recommended": was_recommended,
            "recommendation_rank": recommendation_rank,
            "recommendation_score": recommendation_score,
            "top3_recommended": [
                rec.get("champion_name") or rec.get("champion")
                for rec in recommendations[:3]
            ]
        })

    def log_evaluation(
        self,
        action_count: int,
        our_evaluation: Optional[dict],
        enemy_evaluation: Optional[dict],
        matchup_advantage: Optional[float],
        matchup_description: Optional[str],
    ):
        """Log team evaluation data."""
        if not self.enabled:
            return

        self.entries.append({
            "event": "evaluation",
            "timestamp": datetime.now().isoformat(),
            "action_count": action_count,
            "our_evaluation": our_evaluation,
            "enemy_evaluation": enemy_evaluation,
            "matchup_advantage": matchup_advantage,
            "matchup_description": matchup_description,
        })

    def log_error(self, error_message: str):
        """Log an error that occurred during processing.

        Args:
            error_message: Full error message with traceback
        """
        if not self.enabled:
            return

        self.entries.append({
            "event": "error",
            "timestamp": datetime.now().isoformat(),
            "error": error_message,
        })
        module_logger.error(f"Scoring error logged: {error_message[:200]}...")

    def save(self, suffix: str = "") -> Optional[Path]:
        """Save diagnostics to JSON file.

        Returns:
            Path to saved file, or None if disabled/empty
        """
        if not self.enabled or not self.entries:
            return None

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        session_short = self.session_id[:8] if self.session_id else "unknown"
        filename = f"{self.mode}_{session_short}_{timestamp}{suffix}.json"
        output_path = self.output_dir / filename

        summary = self._compute_summary()

        with open(output_path, "w") as f:
            json.dump({
                "metadata": self._metadata,
                "summary": summary,
                "entries": self.entries,
            }, f, indent=2)

        module_logger.info(f"Scoring diagnostics saved: {output_path}")
        return output_path

    def _compute_summary(self) -> dict:
        """Compute summary statistics from logged entries."""
        pick_events = [e for e in self.entries if e["event"] == "pick_recommendations"]
        ban_events = [e for e in self.entries if e["event"] == "ban_recommendations"]
        actual_events = [e for e in self.entries if e["event"] == "actual_action"]

        # Analyze component distributions for picks
        component_stats: dict[str, dict] = {}
        for comp in ["meta", "proficiency", "matchup", "counter", "synergy"]:
            component_stats[comp] = {"values": [], "at_05_count": 0}

        for event in pick_events:
            for rec in event.get("recommendations", []):
                components = rec.get("components", {})
                for comp, val in components.items():
                    if comp in component_stats:
                        component_stats[comp]["values"].append(val)
                        if abs(val - 0.5) < 0.01:
                            component_stats[comp]["at_05_count"] += 1

        # Calculate component averages and 0.5 percentages
        for comp, stats in component_stats.items():
            vals = stats["values"]
            if vals:
                stats["avg"] = round(sum(vals) / len(vals), 3)
                stats["min"] = round(min(vals), 3)
                stats["max"] = round(max(vals), 3)
                stats["pct_at_05"] = round(stats["at_05_count"] / len(vals) * 100, 1)
            del stats["values"]  # Don't include raw values in summary

        # Analyze recommendation accuracy
        pick_matches = 0
        pick_top3 = 0
        ban_matches = 0
        ban_top3 = 0

        for actual in actual_events:
            if actual["was_recommended"]:
                if actual["action_type"] == "pick":
                    pick_matches += 1
                    if actual["recommendation_rank"] and actual["recommendation_rank"] <= 3:
                        pick_top3 += 1
                else:
                    ban_matches += 1
                    if actual["recommendation_rank"] and actual["recommendation_rank"] <= 3:
                        ban_top3 += 1

        pick_actuals = [e for e in actual_events if e["action_type"] == "pick"]
        ban_actuals = [e for e in actual_events if e["action_type"] == "ban"]

        return {
            "total_pick_recommendation_events": len(pick_events),
            "total_ban_recommendation_events": len(ban_events),
            "total_actual_picks": len(pick_actuals),
            "total_actual_bans": len(ban_actuals),
            "pick_accuracy": {
                "in_recommendations": pick_matches,
                "in_top_3": pick_top3,
                "accuracy_pct": round(pick_matches / len(pick_actuals) * 100, 1) if pick_actuals else 0,
                "top3_pct": round(pick_top3 / len(pick_actuals) * 100, 1) if pick_actuals else 0,
            },
            "ban_accuracy": {
                "in_recommendations": ban_matches,
                "in_top_3": ban_top3,
                "accuracy_pct": round(ban_matches / len(ban_actuals) * 100, 1) if ban_actuals else 0,
                "top3_pct": round(ban_top3 / len(ban_actuals) * 100, 1) if ban_actuals else 0,
            },
            "component_stats": component_stats,
        }


# Singleton instance for easy access across the application
_global_logger: Optional[ScoringLogger] = None


def get_scoring_logger() -> ScoringLogger:
    """Get the global scoring logger instance.

    The logger is enabled by default. Set SCORING_DIAGNOSTICS=false to disable.
    """
    global _global_logger
    if _global_logger is None:
        _global_logger = ScoringLogger()
    return _global_logger


def reset_scoring_logger():
    """Reset the global logger (e.g., between tests)."""
    global _global_logger
    _global_logger = None
