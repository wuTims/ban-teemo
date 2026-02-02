"""Test draft quality analysis endpoint."""
import pytest
from unittest.mock import MagicMock, patch
import httpx

from ban_teemo.main import app
from ban_teemo.api.routes.simulator import _sessions, _sessions_lock, _session_locks
from ban_teemo.models.draft import DraftPhase

pytestmark = pytest.mark.anyio


@pytest.fixture
def mock_services():
    """Mock the services to avoid needing real data."""
    from pathlib import Path
    mock_repo = MagicMock()
    mock_repo._db_path = Path("/fake/path/draft_data.duckdb")

    def mock_get_team_context(team_id, side):
        from ban_teemo.models.team import TeamContext, Player
        return TeamContext(
            id=team_id,
            name=f"Team {team_id[:8]}",
            side=side,
            players=[
                Player(id=f"p{i}", name=f"Player{i}", role=role)
                for i, role in enumerate(["TOP", "JNG", "MID", "ADC", "SUP"])
            ],
        )

    mock_repo.get_team_context = mock_get_team_context

    mock_enemy_service = MagicMock()
    mock_enemy_strategy = MagicMock()
    mock_enemy_strategy.reference_game_id = "game123"
    mock_enemy_strategy.draft_script = []
    mock_enemy_strategy.fallback_game_ids = []
    mock_enemy_strategy.champion_weights = {"Azir": 0.5, "Jinx": 0.3, "Thresh": 0.2}
    mock_enemy_service.initialize_enemy_strategy.return_value = mock_enemy_strategy
    mock_enemy_service.generate_action.return_value = ("Azir", "weighted_random")
    mock_enemy_service.generate_smart_action.return_value = ("Jinx", "smart_recommendation")

    return {
        "repo": mock_repo,
        "enemy_service": mock_enemy_service,
    }


@pytest.fixture
async def client(mock_services):
    """Create async test client with mocked services."""
    with _sessions_lock:
        _sessions.clear()
        _session_locks.clear()

    app.state.repository = mock_services["repo"]

    for attr in ["enemy_simulator_service", "pick_engine", "ban_service", "team_eval_service", "draft_quality_analyzer"]:
        if hasattr(app.state, attr):
            delattr(app.state, attr)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


class TestDraftQualityEndpoint:
    """Tests for GET /api/simulator/sessions/{session_id}/draft-quality."""

    async def test_draft_quality_requires_complete_draft(self, client, mock_services):
        """Endpoint returns 400 if draft not complete."""
        with patch(
            "ban_teemo.api.routes.simulator.EnemySimulatorService",
            return_value=mock_services["enemy_service"],
        ):
            # Create a session
            start_response = await client.post(
                "/api/simulator/sessions",
                json={
                    "blue_team_id": "team_blue_123",
                    "red_team_id": "team_red_456",
                    "coaching_side": "blue",
                },
            )
            session_id = start_response.json()["session_id"]

            # Try to get draft quality before draft is complete
            response = await client.get(f"/api/simulator/sessions/{session_id}/draft-quality")

        assert response.status_code == 400
        assert "draft is complete" in response.json()["detail"].lower()

    async def test_draft_quality_session_not_found(self, client, mock_services):
        """Endpoint returns 404 for unknown session."""
        response = await client.get("/api/simulator/sessions/nonexistent/draft-quality")
        assert response.status_code == 404

    async def test_draft_quality_endpoint_returns_analysis(self, client, mock_services):
        """GET /sessions/{id}/draft-quality returns analysis at draft end."""
        with patch(
            "ban_teemo.api.routes.simulator.EnemySimulatorService",
            return_value=mock_services["enemy_service"],
        ):
            # Create a session
            start_response = await client.post(
                "/api/simulator/sessions",
                json={
                    "blue_team_id": "team_blue_123",
                    "red_team_id": "team_red_456",
                    "coaching_side": "blue",
                },
            )
            session_id = start_response.json()["session_id"]

            # Complete the entire draft (20 actions)
            # Draft order: 6 bans, 6 picks, 4 bans, 4 picks
            champions = [
                # Ban Phase 1: B-R-B-R-B-R
                "Ban1", "Ban2", "Ban3", "Ban4", "Ban5", "Ban6",
                # Pick Phase 1: B-R-R-B-B-R
                "Pick1", "Pick2", "Pick3", "Pick4", "Pick5", "Pick6",
                # Ban Phase 2: R-B-R-B
                "Ban7", "Ban8", "Ban9", "Ban10",
                # Pick Phase 2: R-B-B-R
                "Pick7", "Pick8", "Pick9", "Pick10",
            ]

            draft_order = [
                ("blue", "ban"), ("red", "ban"), ("blue", "ban"), ("red", "ban"),
                ("blue", "ban"), ("red", "ban"),  # 6 bans
                ("blue", "pick"), ("red", "pick"), ("red", "pick"), ("blue", "pick"),
                ("blue", "pick"), ("red", "pick"),  # 6 picks
                ("red", "ban"), ("blue", "ban"), ("red", "ban"), ("blue", "ban"),  # 4 bans
                ("red", "pick"), ("blue", "pick"), ("blue", "pick"), ("red", "pick"),  # 4 picks
            ]

            for i, (team, action) in enumerate(draft_order):
                if team == "blue":
                    # Our action (we're blue)
                    await client.post(
                        f"/api/simulator/sessions/{session_id}/actions?include_recommendations=true",
                        json={"champion": champions[i]},
                    )
                else:
                    # Enemy action
                    # Override the mock to return unique champions
                    mock_services["enemy_service"].generate_smart_action.return_value = (
                        champions[i], "smart_recommendation"
                    )
                    await client.post(f"/api/simulator/sessions/{session_id}/actions/enemy")

            # Now draft should be complete, get quality analysis
            response = await client.get(f"/api/simulator/sessions/{session_id}/draft-quality")

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "session_id" in data
        assert data["session_id"] == session_id
        assert "game_number" in data
        assert "coaching_side" in data
        assert data["coaching_side"] == "blue"

        # Verify analysis structure from DraftQualityAnalyzer
        assert "actual_draft" in data
        assert "recommended_draft" in data
        assert "comparison" in data

        # Verify actual_draft structure
        assert "picks" in data["actual_draft"]
        assert "archetype" in data["actual_draft"]
        assert "composition_score" in data["actual_draft"]

        # Verify comparison structure
        assert "score_delta" in data["comparison"]
        assert "picks_matched" in data["comparison"]
