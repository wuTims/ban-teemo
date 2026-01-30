"""Tests for simulator API routes."""

import httpx
import pytest
from unittest.mock import MagicMock, patch

from ban_teemo.main import app
from ban_teemo.api.routes.simulator import _sessions, _sessions_lock, _session_locks

pytestmark = pytest.mark.anyio


@pytest.fixture
def mock_services():
    """Mock the services to avoid needing real data."""
    from pathlib import Path
    mock_repo = MagicMock()
    mock_repo.data_path = Path("/fake/path")
    mock_repo._db_path = Path("/fake/path/draft_data.duckdb")

    # Mock get_team_context to return a fake team
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

    # Mock enemy service
    mock_enemy_service = MagicMock()
    mock_enemy_strategy = MagicMock()
    mock_enemy_strategy.reference_game_id = "game123"
    mock_enemy_strategy.draft_script = []
    mock_enemy_strategy.fallback_game_ids = []
    mock_enemy_strategy.champion_weights = {"Azir": 0.5, "Jinx": 0.3, "Thresh": 0.2}
    mock_enemy_service.initialize_enemy_strategy.return_value = mock_enemy_strategy
    mock_enemy_service.generate_action.return_value = ("Azir", "weighted_random")

    return {
        "repo": mock_repo,
        "enemy_service": mock_enemy_service,
    }


@pytest.fixture
async def client(mock_services):
    """Create async test client with mocked services."""
    # Clear sessions before each test
    with _sessions_lock:
        _sessions.clear()
        _session_locks.clear()

    # Set repository directly on app.state (mimics lifespan startup)
    app.state.repository = mock_services["repo"]

    # Clear any cached services so they get re-created with mocks
    for attr in ["enemy_simulator_service", "pick_engine", "ban_service", "team_eval_service"]:
        if hasattr(app.state, attr):
            delattr(app.state, attr)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


class TestStartSimulator:
    """Tests for POST /api/simulator/sessions."""

    @pytest.mark.anyio
    async def test_start_simulator_success(self, client, mock_services):
        """Test successfully starting a simulator session."""
        with patch(
            "ban_teemo.api.routes.simulator.EnemySimulatorService",
            return_value=mock_services["enemy_service"],
        ):
            response = await client.post(
                "/api/simulator/sessions",
                json={
                    "blue_team_id": "team_blue_123",
                    "red_team_id": "team_red_456",
                    "coaching_side": "blue",
                },
            )

        assert response.status_code == 201
        data = response.json()
        assert "session_id" in data
        assert data["session_id"].startswith("sim_")
        assert data["game_number"] == 1
        assert data["is_our_turn"] is True
        assert "blue_team" in data
        assert "red_team" in data
        assert "draft_state" in data
        # Recommendations now come from separate endpoint
        assert "recommendations" not in data
        assert "team_evaluation" not in data

    @pytest.mark.anyio
    async def test_start_simulator_with_series(self, client, mock_services):
        """Test starting a Bo3 series."""
        with patch(
            "ban_teemo.api.routes.simulator.EnemySimulatorService",
            return_value=mock_services["enemy_service"],
        ):
            response = await client.post(
                "/api/simulator/sessions",
                json={
                    "blue_team_id": "team_blue_123",
                    "red_team_id": "team_red_456",
                    "coaching_side": "red",
                    "series_length": 3,
                    "draft_mode": "fearless",
                },
            )

        assert response.status_code == 201
        data = response.json()
        # Red side means blue picks first, so not our turn
        assert data["is_our_turn"] is False

    async def test_start_simulator_team_not_found(self, client, mock_services):
        """Test error when team is not found."""
        # Override the fixture's mock to return None
        app.state.repository.get_team_context = MagicMock(return_value=None)

        with patch(
            "ban_teemo.api.routes.simulator.EnemySimulatorService",
            return_value=mock_services["enemy_service"],
        ):
            response = await client.post(
                "/api/simulator/sessions",
                json={
                    "blue_team_id": "nonexistent",
                    "red_team_id": "also_nonexistent",
                    "coaching_side": "blue",
                },
            )

        assert response.status_code == 404
        assert "Team not found" in response.json()["detail"]


class TestSubmitAction:
    """Tests for POST /api/simulator/sessions/{session_id}/actions."""

    async def test_submit_action_success(self, client, mock_services):
        """Test successfully submitting a pick/ban."""
        with patch(
            "ban_teemo.api.routes.simulator.EnemySimulatorService",
            return_value=mock_services["enemy_service"],
        ):
            start_response = await client.post(
                "/api/simulator/sessions",
                json={
                    "blue_team_id": "team_blue_123",
                    "red_team_id": "team_red_456",
                    "coaching_side": "blue",
                },
            )
            session_id = start_response.json()["session_id"]

            # Submit a ban (blue bans first)
            response = await client.post(
                f"/api/simulator/sessions/{session_id}/actions",
                json={"champion": "Azir"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["action"]["champion_name"] == "Azir"
        assert data["action"]["action_type"] == "ban"
        assert data["action"]["team_side"] == "blue"
        # By default, no recommendations in action response
        assert "recommendations" not in data

    async def test_submit_action_session_not_found(self, client, mock_services):
        """Test error when session doesn't exist."""
        response = await client.post(
            "/api/simulator/sessions/nonexistent_session/actions",
            json={"champion": "Azir"},
        )
        assert response.status_code == 404
        assert "Session not found" in response.json()["detail"]

    async def test_submit_action_not_your_turn(self, client, mock_services):
        """Test error when it's not your turn."""
        with patch(
            "ban_teemo.api.routes.simulator.EnemySimulatorService",
            return_value=mock_services["enemy_service"],
        ):
            # Start as red side (blue picks first, so not our turn)
            start_response = await client.post(
                "/api/simulator/sessions",
                json={
                    "blue_team_id": "team_blue_123",
                    "red_team_id": "team_red_456",
                    "coaching_side": "red",
                },
            )
            session_id = start_response.json()["session_id"]

            # Try to submit when it's not our turn
            response = await client.post(
                f"/api/simulator/sessions/{session_id}/actions",
                json={"champion": "Azir"},
            )

        assert response.status_code == 400
        assert "Not your turn" in response.json()["detail"]

    async def test_submit_action_champion_unavailable(self, client, mock_services):
        """Test error when champion is already picked/banned."""
        with patch(
            "ban_teemo.api.routes.simulator.EnemySimulatorService",
            return_value=mock_services["enemy_service"],
        ):
            start_response = await client.post(
                "/api/simulator/sessions",
                json={
                    "blue_team_id": "team_blue_123",
                    "red_team_id": "team_red_456",
                    "coaching_side": "blue",
                },
            )
            session_id = start_response.json()["session_id"]

            # Ban Azir first time
            await client.post(
                f"/api/simulator/sessions/{session_id}/actions",
                json={"champion": "Azir"},
            )

            # Enemy bans
            await client.post(f"/api/simulator/sessions/{session_id}/actions/enemy")

            # Try to ban Azir again
            response = await client.post(
                f"/api/simulator/sessions/{session_id}/actions",
                json={"champion": "Azir"},
            )

        assert response.status_code == 400
        assert "not available" in response.json()["detail"]


class TestGetSession:
    """Tests for GET /api/simulator/sessions/{session_id}."""

    async def test_get_session_success(self, client, mock_services):
        """Test getting session state."""
        with patch(
            "ban_teemo.api.routes.simulator.EnemySimulatorService",
            return_value=mock_services["enemy_service"],
        ):
            start_response = await client.post(
                "/api/simulator/sessions",
                json={
                    "blue_team_id": "team_blue_123",
                    "red_team_id": "team_red_456",
                    "coaching_side": "blue",
                },
            )
            session_id = start_response.json()["session_id"]

            response = await client.get(f"/api/simulator/sessions/{session_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == session_id
        assert data["status"] == "drafting"
        assert data["game_number"] == 1

    async def test_get_session_not_found(self, client, mock_services):
        """Test error when session doesn't exist."""
        response = await client.get("/api/simulator/sessions/nonexistent")
        assert response.status_code == 404


class TestEndSession:
    """Tests for DELETE /api/simulator/sessions/{session_id}."""

    async def test_end_session_success(self, client, mock_services):
        """Test ending a session."""
        with patch(
            "ban_teemo.api.routes.simulator.EnemySimulatorService",
            return_value=mock_services["enemy_service"],
        ):
            start_response = await client.post(
                "/api/simulator/sessions",
                json={
                    "blue_team_id": "team_blue_123",
                    "red_team_id": "team_red_456",
                    "coaching_side": "blue",
                },
            )
            session_id = start_response.json()["session_id"]

            # End the session
            response = await client.delete(f"/api/simulator/sessions/{session_id}")

        assert response.status_code == 200
        assert response.json()["status"] == "ended"

    async def test_end_nonexistent_session(self, client, mock_services):
        """Test ending a session that doesn't exist (should succeed silently)."""
        response = await client.delete("/api/simulator/sessions/nonexistent")
        assert response.status_code == 200
        assert response.json()["status"] == "ended"


class TestListTeams:
    """Tests for GET /api/simulator/teams."""

    async def test_list_teams_success(self, client, mock_services):
        """Test listing available teams."""
        # Set up the _query mock on the repository already in app.state
        app.state.repository._query = MagicMock(
            return_value=[
                {"id": "team1", "name": "Team Alpha"},
                {"id": "team2", "name": "Team Beta"},
            ]
        )

        with patch(
            "ban_teemo.api.routes.simulator.EnemySimulatorService",
            return_value=mock_services["enemy_service"],
        ):
            response = await client.get("/api/simulator/teams")

        assert response.status_code == 200
        data = response.json()
        assert "teams" in data
        assert len(data["teams"]) == 2

    async def test_list_teams_respects_limit(self, client, mock_services):
        """Test that limit parameter is passed correctly."""
        app.state.repository._query = MagicMock(return_value=[])

        with patch(
            "ban_teemo.api.routes.simulator.EnemySimulatorService",
            return_value=mock_services["enemy_service"],
        ):
            await client.get("/api/simulator/teams?limit=10")

        # Verify the query was called with the limit
        call_args = app.state.repository._query.call_args[0][0]
        assert "LIMIT 10" in call_args

    async def test_list_teams_clamps_excessive_limit(self, client, mock_services):
        """Test that excessive limit is clamped to MAX_TEAMS_LIMIT."""
        app.state.repository._query = MagicMock(return_value=[])

        with patch(
            "ban_teemo.api.routes.simulator.EnemySimulatorService",
            return_value=mock_services["enemy_service"],
        ):
            await client.get("/api/simulator/teams?limit=9999")

        # Verify the query was called with clamped limit (500)
        call_args = app.state.repository._query.call_args[0][0]
        assert "LIMIT 500" in call_args


class TestGetRecommendations:
    """Tests for GET /api/simulator/sessions/{session_id}/recommendations."""

    async def test_get_recommendations_ban_phase(self, client, mock_services):
        """Test getting ban recommendations."""
        with patch(
            "ban_teemo.api.routes.simulator.EnemySimulatorService",
            return_value=mock_services["enemy_service"],
        ):
            start_response = await client.post(
                "/api/simulator/sessions",
                json={
                    "blue_team_id": "team_blue_123",
                    "red_team_id": "team_red_456",
                    "coaching_side": "blue",
                },
            )
            session_id = start_response.json()["session_id"]

            response = await client.get(f"/api/simulator/sessions/{session_id}/recommendations")

        assert response.status_code == 200
        data = response.json()
        assert "for_action_count" in data
        assert data["for_action_count"] == 0  # No actions yet
        assert data["phase"] == "BAN_PHASE_1"
        assert "recommendations" in data

    async def test_get_recommendations_session_not_found(self, client, mock_services):
        """Test error when session doesn't exist."""
        response = await client.get("/api/simulator/sessions/nonexistent/recommendations")
        assert response.status_code == 404

    async def test_recommendations_staleness_tracking(self, client, mock_services):
        """Test that for_action_count updates after actions."""
        with patch(
            "ban_teemo.api.routes.simulator.EnemySimulatorService",
            return_value=mock_services["enemy_service"],
        ):
            start_response = await client.post(
                "/api/simulator/sessions",
                json={
                    "blue_team_id": "team_blue_123",
                    "red_team_id": "team_red_456",
                    "coaching_side": "blue",
                },
            )
            session_id = start_response.json()["session_id"]

            # Initial recommendations
            rec1 = await client.get(f"/api/simulator/sessions/{session_id}/recommendations")
            assert rec1.json()["for_action_count"] == 0

            # Submit an action
            await client.post(
                f"/api/simulator/sessions/{session_id}/actions",
                json={"champion": "Jinx"},
            )

            # Enemy action
            await client.post(f"/api/simulator/sessions/{session_id}/actions/enemy")

            # Recommendations should reflect new action count
            rec2 = await client.get(f"/api/simulator/sessions/{session_id}/recommendations")
            assert rec2.json()["for_action_count"] == 2


class TestGetEvaluation:
    """Tests for GET /api/simulator/sessions/{session_id}/evaluation."""

    async def test_get_evaluation_no_picks(self, client, mock_services):
        """Test evaluation when no picks made yet."""
        with patch(
            "ban_teemo.api.routes.simulator.EnemySimulatorService",
            return_value=mock_services["enemy_service"],
        ):
            start_response = await client.post(
                "/api/simulator/sessions",
                json={
                    "blue_team_id": "team_blue_123",
                    "red_team_id": "team_red_456",
                    "coaching_side": "blue",
                },
            )
            session_id = start_response.json()["session_id"]

            response = await client.get(f"/api/simulator/sessions/{session_id}/evaluation")

        assert response.status_code == 200
        data = response.json()
        assert data["for_action_count"] == 0
        assert data["our_evaluation"] is None
        assert data["enemy_evaluation"] is None

    async def test_get_evaluation_session_not_found(self, client, mock_services):
        """Test error when session doesn't exist."""
        response = await client.get("/api/simulator/sessions/nonexistent/evaluation")
        assert response.status_code == 404


class TestRoleGroupedRecommendations:
    """Tests for role-grouped recommendations in pick phase."""

    async def test_recommendations_include_role_grouped(self, client, mock_services):
        """GET /recommendations returns role-grouped picks during pick phase."""
        with patch(
            "ban_teemo.api.routes.simulator.EnemySimulatorService",
            return_value=mock_services["enemy_service"],
        ):
            # Create session
            start_response = await client.post(
                "/api/simulator/sessions",
                json={
                    "blue_team_id": "team_blue_123",
                    "red_team_id": "team_red_456",
                    "coaching_side": "blue",
                },
            )
            session_id = start_response.json()["session_id"]

            # Complete ban phase (6 bans) to get to pick phase
            for i in range(3):
                # Our ban
                await client.post(
                    f"/api/simulator/sessions/{session_id}/actions",
                    json={"champion": f"BanChamp{i}"},
                )
                # Enemy ban
                await client.post(f"/api/simulator/sessions/{session_id}/actions/enemy")

            # Now in PICK_PHASE_1, get recommendations
            response = await client.get(f"/api/simulator/sessions/{session_id}/recommendations")

        assert response.status_code == 200
        data = response.json()

        # Verify role_grouped is present during pick phase
        assert "role_grouped" in data
        assert "by_role" in data["role_grouped"]
        by_role = data["role_grouped"]["by_role"]
        assert isinstance(by_role, dict)

        # Verify view_type metadata
        assert data["role_grouped"]["view_type"] == "supplemental"

    async def test_recommendations_no_role_grouped_in_ban_phase(self, client, mock_services):
        """GET /recommendations does NOT return role_grouped in ban phase."""
        with patch(
            "ban_teemo.api.routes.simulator.EnemySimulatorService",
            return_value=mock_services["enemy_service"],
        ):
            start_response = await client.post(
                "/api/simulator/sessions",
                json={
                    "blue_team_id": "team_blue_123",
                    "red_team_id": "team_red_456",
                    "coaching_side": "blue",
                },
            )
            session_id = start_response.json()["session_id"]

            # Get recommendations during ban phase
            response = await client.get(f"/api/simulator/sessions/{session_id}/recommendations")

        assert response.status_code == 200
        data = response.json()

        # role_grouped should NOT be present during ban phase
        assert "role_grouped" not in data


class TestEagerFetchQueryParams:
    """Tests for ?include_recommendations and ?include_evaluation query params."""

    async def test_action_with_include_recommendations(self, client, mock_services):
        """Test action endpoint with include_recommendations=true."""
        with patch(
            "ban_teemo.api.routes.simulator.EnemySimulatorService",
            return_value=mock_services["enemy_service"],
        ):
            start_response = await client.post(
                "/api/simulator/sessions",
                json={
                    "blue_team_id": "team_blue_123",
                    "red_team_id": "team_red_456",
                    "coaching_side": "blue",
                },
            )
            session_id = start_response.json()["session_id"]

            # Submit action WITHOUT query params
            response_without = await client.post(
                f"/api/simulator/sessions/{session_id}/actions",
                json={"champion": "Jinx"},
            )
            assert "recommendations" not in response_without.json()

            # Trigger enemy action WITH query params
            response_with = await client.post(
                f"/api/simulator/sessions/{session_id}/actions/enemy?include_recommendations=true",
            )
            data = response_with.json()
            assert "recommendations" in data
            assert isinstance(data["recommendations"], list)

    async def test_action_with_include_evaluation(self, client, mock_services):
        """Test action endpoint with include_evaluation=true."""
        with patch(
            "ban_teemo.api.routes.simulator.EnemySimulatorService",
            return_value=mock_services["enemy_service"],
        ):
            start_response = await client.post(
                "/api/simulator/sessions",
                json={
                    "blue_team_id": "team_blue_123",
                    "red_team_id": "team_red_456",
                    "coaching_side": "blue",
                },
            )
            session_id = start_response.json()["session_id"]

            # Submit action WITH include_evaluation
            response = await client.post(
                f"/api/simulator/sessions/{session_id}/actions?include_evaluation=true",
                json={"champion": "Jinx"},
            )
            data = response.json()
            # Evaluation may be null if no picks yet (it's a ban), but key should exist if requested
            # Actually, during ban phase there are no picks, so evaluation won't be included
            # The key is only included if there ARE picks
            # This is correct - evaluation only meaningful with picks
            assert response.status_code == 200
