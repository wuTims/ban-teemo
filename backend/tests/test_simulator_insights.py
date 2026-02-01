"""Tests for simulator LLM insights endpoint."""

import httpx
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from ban_teemo.main import app
from ban_teemo.api.routes.simulator import _sessions, _sessions_lock, _session_locks
from ban_teemo.services.llm_reranker import RerankerResult, RerankedRecommendation


pytestmark = pytest.mark.anyio


@pytest.fixture
def mock_services():
    """Mock the services to avoid needing real data."""
    from pathlib import Path
    mock_repo = MagicMock()
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


@pytest.fixture
def mock_reranker_result():
    """Create a mock LLM reranker result."""
    return RerankerResult(
        reranked=[
            RerankedRecommendation(
                champion="Orianna",
                original_rank=1,
                new_rank=1,
                original_score=0.85,
                confidence=0.9,
                reasoning="Strong control mage",
                strategic_factors=["safe_pick", "teamfight"],
            )
        ],
        additional_suggestions=[],
        draft_analysis="Enemy is building dive comp. Consider control mages.",
    )


class TestInsightsStaleRequestRejection:
    """Tests for stale request rejection in insights endpoint."""

    async def test_insights_returns_stale_for_wrong_action_count(
        self, client, mock_services, mock_reranker_result
    ):
        """Test that stale requests are rejected with status='stale'."""
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

            # Request insights with wrong action_count (session starts at 0)
            with patch("ban_teemo.api.routes.simulator.LLMReranker") as MockReranker:
                mock_instance = AsyncMock()
                mock_instance.rerank_bans = AsyncMock(return_value=mock_reranker_result)
                mock_instance.rerank_picks = AsyncMock(return_value=mock_reranker_result)
                mock_instance.close = AsyncMock()
                MockReranker.return_value = mock_instance

                response = await client.post(
                    f"/api/simulator/sessions/{session_id}/insights",
                    json={"api_key": "test-key", "action_count": 5},  # Wrong count
                )

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "stale"
            assert "Request for action 5" in data["message"]
            assert "current is 0" in data["message"]

    async def test_insights_returns_stale_when_action_count_behind(
        self, client, mock_services, mock_reranker_result
    ):
        """Test stale rejection when action_count is behind current state."""
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

            # Submit some actions to advance action_count
            await client.post(
                f"/api/simulator/sessions/{session_id}/actions",
                json={"champion": "Jinx"},
            )
            await client.post(f"/api/simulator/sessions/{session_id}/actions/enemy")

            # Request insights with outdated action_count (0 instead of 2)
            with patch("ban_teemo.api.routes.simulator.LLMReranker") as MockReranker:
                mock_instance = AsyncMock()
                mock_instance.rerank_bans = AsyncMock(return_value=mock_reranker_result)
                mock_instance.close = AsyncMock()
                MockReranker.return_value = mock_instance

                response = await client.post(
                    f"/api/simulator/sessions/{session_id}/insights",
                    json={"api_key": "test-key", "action_count": 0},  # Outdated
                )

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "stale"
            assert "current is 2" in data["message"]


class TestInsightsSuccessfulRequest:
    """Tests for successful insights requests."""

    async def test_insights_success_with_valid_action_count(
        self, client, mock_services, mock_reranker_result
    ):
        """Test successful insights request with matching action_count."""
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

            with patch("ban_teemo.api.routes.simulator.LLMReranker") as MockReranker:
                mock_instance = AsyncMock()
                mock_instance.rerank_bans = AsyncMock(return_value=mock_reranker_result)
                mock_instance.rerank_picks = AsyncMock(return_value=mock_reranker_result)
                mock_instance.close = AsyncMock()
                MockReranker.return_value = mock_instance

                response = await client.post(
                    f"/api/simulator/sessions/{session_id}/insights",
                    json={"api_key": "test-key", "action_count": 0},  # Correct count
                )

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ready"
            assert "draft_analysis" in data
            assert "reranked" in data
            assert data["action_count"] == 0
            assert data["for_team"] == "blue"

    async def test_insights_returns_complete_for_finished_draft(
        self, client, mock_services, mock_reranker_result
    ):
        """Test insights returns status='complete' when draft is finished.

        This test verifies the code path by directly manipulating session state,
        since completing a full 20-action draft with mocks is complex.
        """
        from ban_teemo.api.routes.simulator import _sessions, _sessions_lock
        from ban_teemo.models.draft import DraftPhase

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

            # Directly set draft phase to COMPLETE to simulate finished draft
            with _sessions_lock:
                session = _sessions[session_id]
                session.draft_state.current_phase = DraftPhase.COMPLETE
                session.draft_state.next_team = None
                session.draft_state.next_action = None

            # Request insights for completed draft
            with patch("ban_teemo.api.routes.simulator.LLMReranker") as MockReranker:
                mock_instance = AsyncMock()
                mock_instance.close = AsyncMock()
                MockReranker.return_value = mock_instance

                response = await client.post(
                    f"/api/simulator/sessions/{session_id}/insights",
                    json={"api_key": "test-key", "action_count": 0},
                )

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "complete"
            assert data.get("insights") is None


class TestInsightsFearlessContext:
    """Tests for fearless draft mode context in insights."""

    async def test_insights_includes_fearless_blocked_in_draft_context(
        self, client, mock_services, mock_reranker_result
    ):
        """Test that fearless blocked champions are passed to LLM via draft_context."""
        captured_draft_context = None

        async def capture_rerank_bans(candidates, draft_context, **kwargs):
            nonlocal captured_draft_context
            captured_draft_context = draft_context
            return mock_reranker_result

        with patch(
            "ban_teemo.api.routes.simulator.EnemySimulatorService",
            return_value=mock_services["enemy_service"],
        ):
            # Create fearless session
            start_response = await client.post(
                "/api/simulator/sessions",
                json={
                    "blue_team_id": "team_blue_123",
                    "red_team_id": "team_red_456",
                    "coaching_side": "blue",
                    "series_length": 3,  # Bo3
                    "draft_mode": "fearless",
                },
            )
            session_id = start_response.json()["session_id"]

            with patch("ban_teemo.api.routes.simulator.LLMReranker") as MockReranker:
                mock_instance = AsyncMock()
                mock_instance.rerank_bans = capture_rerank_bans
                mock_instance.rerank_picks = AsyncMock(return_value=mock_reranker_result)
                mock_instance.close = AsyncMock()
                MockReranker.return_value = mock_instance

                response = await client.post(
                    f"/api/simulator/sessions/{session_id}/insights",
                    json={"api_key": "test-key", "action_count": 0},
                )

            assert response.status_code == 200
            # Verify draft_context includes fearless mode info
            assert captured_draft_context is not None
            assert captured_draft_context.get("draft_mode") == "fearless"
            # At game 1, fearless_blocked should be empty
            assert captured_draft_context.get("fearless_blocked") == []

    async def test_insights_fearless_blocked_contains_previous_game_champs(
        self, client, mock_services, mock_reranker_result
    ):
        """Test that after game 1, fearless_blocked contains used champions."""
        captured_draft_context = None

        async def capture_context(candidates, draft_context, **kwargs):
            nonlocal captured_draft_context
            captured_draft_context = draft_context
            return mock_reranker_result

        with patch(
            "ban_teemo.api.routes.simulator.EnemySimulatorService",
            return_value=mock_services["enemy_service"],
        ):
            # Create fearless session
            start_response = await client.post(
                "/api/simulator/sessions",
                json={
                    "blue_team_id": "team_blue_123",
                    "red_team_id": "team_red_456",
                    "coaching_side": "blue",
                    "series_length": 3,
                    "draft_mode": "fearless",
                },
            )
            session_id = start_response.json()["session_id"]

            # Complete game 1 draft (do all 20 actions)
            champ_pool = [
                "Aatrox", "Ahri", "Akali", "Alistar", "Amumu",
                "Anivia", "Annie", "Aphelios", "Ashe", "Azir",
                "Bard", "Blitzcrank", "Brand", "Braum", "Caitlyn",
                "Camille", "Corki", "Darius", "Diana", "Draven",
            ]
            champ_idx = 0

            for _ in range(20):
                session_resp = await client.get(f"/api/simulator/sessions/{session_id}")
                session_data = session_resp.json()

                if session_data["draft_state"]["next_team"] == "blue":
                    await client.post(
                        f"/api/simulator/sessions/{session_id}/actions",
                        json={"champion": champ_pool[champ_idx]},
                    )
                else:
                    await client.post(f"/api/simulator/sessions/{session_id}/actions/enemy")
                champ_idx += 1

            # Complete game 1
            complete_resp = await client.post(
                f"/api/simulator/sessions/{session_id}/games/complete",
                json={"winner": "blue"},
            )

            # Get fearless blocked count from complete response
            fearless_blocked_after_g1 = complete_resp.json().get("fearless_blocked", {})

            # Start game 2
            await client.post(f"/api/simulator/sessions/{session_id}/games/next")

            # Now request insights for game 2
            with patch("ban_teemo.api.routes.simulator.LLMReranker") as MockReranker:
                mock_instance = AsyncMock()
                mock_instance.rerank_bans = capture_context
                mock_instance.rerank_picks = AsyncMock(return_value=mock_reranker_result)
                mock_instance.close = AsyncMock()
                MockReranker.return_value = mock_instance

                response = await client.post(
                    f"/api/simulator/sessions/{session_id}/insights",
                    json={"api_key": "test-key", "action_count": 0},
                )

            assert response.status_code == 200
            assert captured_draft_context is not None
            assert captured_draft_context.get("draft_mode") == "fearless"
            # fearless_blocked should contain champions from game 1
            fearless_blocked = captured_draft_context.get("fearless_blocked", [])
            # Should have 10 champions (5 blue + 5 red picks from game 1)
            assert len(fearless_blocked) == len(fearless_blocked_after_g1)


class TestInsightsSeriesContext:
    """Tests for series context building in insights."""

    async def test_insights_builds_series_context_from_previous_games(
        self, client, mock_services, mock_reranker_result
    ):
        """Test that series context is built from completed games."""
        captured_series_context = None

        async def capture_series(candidates, draft_context, series_context=None, **kwargs):
            nonlocal captured_series_context
            captured_series_context = series_context
            return mock_reranker_result

        with patch(
            "ban_teemo.api.routes.simulator.EnemySimulatorService",
            return_value=mock_services["enemy_service"],
        ):
            # Create Bo3 session
            start_response = await client.post(
                "/api/simulator/sessions",
                json={
                    "blue_team_id": "team_blue_123",
                    "red_team_id": "team_red_456",
                    "coaching_side": "blue",
                    "series_length": 3,
                    "draft_mode": "normal",
                },
            )
            session_id = start_response.json()["session_id"]

            # Complete game 1
            champ_pool = [
                "Aatrox", "Ahri", "Akali", "Alistar", "Amumu",
                "Anivia", "Annie", "Aphelios", "Ashe", "Azir",
                "Bard", "Blitzcrank", "Brand", "Braum", "Caitlyn",
                "Camille", "Corki", "Darius", "Diana", "Draven",
            ]
            champ_idx = 0

            for _ in range(20):
                session_resp = await client.get(f"/api/simulator/sessions/{session_id}")
                session_data = session_resp.json()

                if session_data["draft_state"]["next_team"] == "blue":
                    await client.post(
                        f"/api/simulator/sessions/{session_id}/actions",
                        json={"champion": champ_pool[champ_idx]},
                    )
                else:
                    await client.post(f"/api/simulator/sessions/{session_id}/actions/enemy")
                champ_idx += 1

            await client.post(
                f"/api/simulator/sessions/{session_id}/games/complete",
                json={"winner": "blue"},
            )
            await client.post(f"/api/simulator/sessions/{session_id}/games/next")

            # Request insights for game 2
            with patch("ban_teemo.api.routes.simulator.LLMReranker") as MockReranker:
                mock_instance = AsyncMock()
                mock_instance.rerank_bans = capture_series
                mock_instance.rerank_picks = AsyncMock(return_value=mock_reranker_result)
                mock_instance.close = AsyncMock()
                MockReranker.return_value = mock_instance

                response = await client.post(
                    f"/api/simulator/sessions/{session_id}/insights",
                    json={"api_key": "test-key", "action_count": 0},
                )

            assert response.status_code == 200
            # Verify series context was passed to reranker
            assert captured_series_context is not None
            assert captured_series_context.game_number == 2
            assert len(captured_series_context.previous_games) == 1
            assert captured_series_context.previous_games[0].winner == "blue"

    async def test_insights_no_series_context_for_game_1(
        self, client, mock_services, mock_reranker_result
    ):
        """Test that game 1 has no series context (None)."""
        captured_series_context = "NOT_CALLED"

        async def capture_series(candidates, draft_context, series_context=None, **kwargs):
            nonlocal captured_series_context
            captured_series_context = series_context
            return mock_reranker_result

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
                    "series_length": 3,
                },
            )
            session_id = start_response.json()["session_id"]

            with patch("ban_teemo.api.routes.simulator.LLMReranker") as MockReranker:
                mock_instance = AsyncMock()
                mock_instance.rerank_bans = capture_series
                mock_instance.close = AsyncMock()
                MockReranker.return_value = mock_instance

                response = await client.post(
                    f"/api/simulator/sessions/{session_id}/insights",
                    json={"api_key": "test-key", "action_count": 0},
                )

            assert response.status_code == 200
            # Series context should be None for game 1
            assert captured_series_context is None


class TestInsightsErrorHandling:
    """Tests for error handling in insights endpoint."""

    async def test_insights_session_not_found(self, client, mock_services):
        """Test error when session doesn't exist."""
        response = await client.post(
            "/api/simulator/sessions/nonexistent_session/insights",
            json={"api_key": "test-key", "action_count": 0},
        )
        assert response.status_code == 404
        assert "Session not found" in response.json()["detail"]

    async def test_insights_returns_error_on_llm_failure(
        self, client, mock_services
    ):
        """Test that LLM errors are caught and returned gracefully."""
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

            with patch("ban_teemo.api.routes.simulator.LLMReranker") as MockReranker:
                mock_instance = AsyncMock()
                mock_instance.rerank_bans = AsyncMock(
                    side_effect=Exception("LLM API timeout")
                )
                mock_instance.close = AsyncMock()
                MockReranker.return_value = mock_instance

                response = await client.post(
                    f"/api/simulator/sessions/{session_id}/insights",
                    json={"api_key": "test-key", "action_count": 0},
                )

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "error"
            assert "LLM API timeout" in data["message"]


class TestInsightsPickPhase:
    """Tests for insights during pick phase."""

    async def test_insights_calls_rerank_picks_during_pick_phase(
        self, client, mock_services, mock_reranker_result
    ):
        """Test that rerank_picks is called during pick phase."""
        rerank_picks_called = False

        async def track_rerank_picks(candidates, draft_context, **kwargs):
            nonlocal rerank_picks_called
            rerank_picks_called = True
            return mock_reranker_result

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

            # Complete ban phase (6 bans)
            for i in range(3):
                await client.post(
                    f"/api/simulator/sessions/{session_id}/actions",
                    json={"champion": f"BanChamp{i}"},
                )
                await client.post(f"/api/simulator/sessions/{session_id}/actions/enemy")

            # Now in pick phase
            with patch("ban_teemo.api.routes.simulator.LLMReranker") as MockReranker:
                mock_instance = AsyncMock()
                mock_instance.rerank_bans = AsyncMock(return_value=mock_reranker_result)
                mock_instance.rerank_picks = track_rerank_picks
                mock_instance.close = AsyncMock()
                MockReranker.return_value = mock_instance

                response = await client.post(
                    f"/api/simulator/sessions/{session_id}/insights",
                    json={"api_key": "test-key", "action_count": 6},
                )

            assert response.status_code == 200
            assert rerank_picks_called is True
