"""Integration tests for the simulator backend.

These tests verify the full pipeline works end-to-end:
- Repository reads from DuckDB database (built from CSV files)
- Services integrate correctly
- Complete draft scenarios work
- API endpoints function with real service instances

Uses synthetic test fixtures to ensure deterministic behavior.
"""

import csv
import tempfile
from pathlib import Path

import duckdb
import httpx
import pytest

from ban_teemo.main import app
from ban_teemo.repositories.draft_repository import DraftRepository
from ban_teemo.services.enemy_simulator_service import EnemySimulatorService
from ban_teemo.services.pick_recommendation_engine import PickRecommendationEngine
from ban_teemo.services.ban_recommendation_service import BanRecommendationService
from ban_teemo.models.draft import DraftState


# =============================================================================
# Test Fixtures - Synthetic CSV Data
# =============================================================================


@pytest.fixture
def test_data_dir():
    """Create a temporary directory with synthetic CSV test data."""
    with tempfile.TemporaryDirectory() as tmpdir:
        data_path = Path(tmpdir)

        # teams.csv
        with open(data_path / "teams.csv", "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["id", "name", "acronym"])
            writer.writeheader()
            writer.writerows([
                {"id": "oe:team:t1", "name": "T1", "acronym": "T1"},
                {"id": "oe:team:geng", "name": "Gen.G", "acronym": "GEN"},
            ])

        # series.csv
        with open(data_path / "series.csv", "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "id", "match_date", "format", "blue_team_id", "red_team_id"
            ])
            writer.writeheader()
            writer.writerows([
                {
                    "id": "s:test1",
                    "match_date": "2026-01-15T14:00:00",
                    "format": "Bo3",
                    "blue_team_id": "oe:team:t1",
                    "red_team_id": "oe:team:geng",
                },
            ])

        # games.csv
        with open(data_path / "games.csv", "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "id", "series_id", "game_number", "patch_version",
                "winner_team_id", "duration_seconds"
            ])
            writer.writeheader()
            writer.writerows([
                {
                    "id": "g:test1",
                    "series_id": "s:test1",
                    "game_number": "1",
                    "patch_version": "14.24",
                    "winner_team_id": "oe:team:t1",
                    "duration_seconds": "1800",
                },
            ])

        # player_game_stats.csv - required for roster lookup
        with open(data_path / "player_game_stats.csv", "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "game_id", "team_id", "team_side", "player_id", "player_name", "role"
            ])
            writer.writeheader()
            # T1 players (blue side)
            writer.writerows([
                {"game_id": "g:test1", "team_id": "oe:team:t1", "team_side": "blue", "player_id": "p:zeus", "player_name": "Zeus", "role": "TOP"},
                {"game_id": "g:test1", "team_id": "oe:team:t1", "team_side": "blue", "player_id": "p:oner", "player_name": "Oner", "role": "JNG"},
                {"game_id": "g:test1", "team_id": "oe:team:t1", "team_side": "blue", "player_id": "p:faker", "player_name": "Faker", "role": "MID"},
                {"game_id": "g:test1", "team_id": "oe:team:t1", "team_side": "blue", "player_id": "p:guma", "player_name": "Gumayusi", "role": "ADC"},
                {"game_id": "g:test1", "team_id": "oe:team:t1", "team_side": "blue", "player_id": "p:keria", "player_name": "Keria", "role": "SUP"},
                # Gen.G players (red side)
                {"game_id": "g:test1", "team_id": "oe:team:geng", "team_side": "red", "player_id": "p:doran", "player_name": "Doran", "role": "TOP"},
                {"game_id": "g:test1", "team_id": "oe:team:geng", "team_side": "red", "player_id": "p:peanut", "player_name": "Peanut", "role": "JNG"},
                {"game_id": "g:test1", "team_id": "oe:team:geng", "team_side": "red", "player_id": "p:chovy", "player_name": "Chovy", "role": "MID"},
                {"game_id": "g:test1", "team_id": "oe:team:geng", "team_side": "red", "player_id": "p:peyz", "player_name": "Peyz", "role": "ADC"},
                {"game_id": "g:test1", "team_id": "oe:team:geng", "team_side": "red", "player_id": "p:lehends", "player_name": "Lehends", "role": "SUP"},
            ])

        # draft_actions.csv - complete draft from a real game
        # Columns: sequence_number, action_type, team_id, champion_id, champion_name, game_id
        with open(data_path / "draft_actions.csv", "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "id", "game_id", "sequence_number", "action_type", "team_id", "champion_id", "champion_name"
            ])
            writer.writeheader()
            # Standard draft order
            actions = [
                # Ban Phase 1
                {"id": "a:1", "game_id": "g:test1", "sequence_number": "1", "action_type": "ban", "team_id": "oe:team:t1", "champion_id": "c:aurora", "champion_name": "Aurora"},
                {"id": "a:2", "game_id": "g:test1", "sequence_number": "2", "action_type": "ban", "team_id": "oe:team:geng", "champion_id": "c:yone", "champion_name": "Yone"},
                {"id": "a:3", "game_id": "g:test1", "sequence_number": "3", "action_type": "ban", "team_id": "oe:team:t1", "champion_id": "c:ksante", "champion_name": "K'Sante"},
                {"id": "a:4", "game_id": "g:test1", "sequence_number": "4", "action_type": "ban", "team_id": "oe:team:geng", "champion_id": "c:azir", "champion_name": "Azir"},
                {"id": "a:5", "game_id": "g:test1", "sequence_number": "5", "action_type": "ban", "team_id": "oe:team:t1", "champion_id": "c:rumble", "champion_name": "Rumble"},
                {"id": "a:6", "game_id": "g:test1", "sequence_number": "6", "action_type": "ban", "team_id": "oe:team:geng", "champion_id": "c:taliyah", "champion_name": "Taliyah"},
                # Pick Phase 1
                {"id": "a:7", "game_id": "g:test1", "sequence_number": "7", "action_type": "pick", "team_id": "oe:team:t1", "champion_id": "c:jax", "champion_name": "Jax"},
                {"id": "a:8", "game_id": "g:test1", "sequence_number": "8", "action_type": "pick", "team_id": "oe:team:geng", "champion_id": "c:rell", "champion_name": "Rell"},
                {"id": "a:9", "game_id": "g:test1", "sequence_number": "9", "action_type": "pick", "team_id": "oe:team:geng", "champion_id": "c:varus", "champion_name": "Varus"},
                {"id": "a:10", "game_id": "g:test1", "sequence_number": "10", "action_type": "pick", "team_id": "oe:team:t1", "champion_id": "c:orianna", "champion_name": "Orianna"},
                {"id": "a:11", "game_id": "g:test1", "sequence_number": "11", "action_type": "pick", "team_id": "oe:team:t1", "champion_id": "c:vi", "champion_name": "Vi"},
                {"id": "a:12", "game_id": "g:test1", "sequence_number": "12", "action_type": "pick", "team_id": "oe:team:geng", "champion_id": "c:jayce", "champion_name": "Jayce"},
                # Ban Phase 2
                {"id": "a:13", "game_id": "g:test1", "sequence_number": "13", "action_type": "ban", "team_id": "oe:team:geng", "champion_id": "c:leona", "champion_name": "Leona"},
                {"id": "a:14", "game_id": "g:test1", "sequence_number": "14", "action_type": "ban", "team_id": "oe:team:t1", "champion_id": "c:nautilus", "champion_name": "Nautilus"},
                {"id": "a:15", "game_id": "g:test1", "sequence_number": "15", "action_type": "ban", "team_id": "oe:team:geng", "champion_id": "c:thresh", "champion_name": "Thresh"},
                {"id": "a:16", "game_id": "g:test1", "sequence_number": "16", "action_type": "ban", "team_id": "oe:team:t1", "champion_id": "c:rakan", "champion_name": "Rakan"},
                # Pick Phase 2
                {"id": "a:17", "game_id": "g:test1", "sequence_number": "17", "action_type": "pick", "team_id": "oe:team:geng", "champion_id": "c:sejuani", "champion_name": "Sejuani"},
                {"id": "a:18", "game_id": "g:test1", "sequence_number": "18", "action_type": "pick", "team_id": "oe:team:t1", "champion_id": "c:ashe", "champion_name": "Ashe"},
                {"id": "a:19", "game_id": "g:test1", "sequence_number": "19", "action_type": "pick", "team_id": "oe:team:t1", "champion_id": "c:renata", "champion_name": "Renata Glasc"},
                {"id": "a:20", "game_id": "g:test1", "sequence_number": "20", "action_type": "pick", "team_id": "oe:team:geng", "champion_id": "c:ahri", "champion_name": "Ahri"},
            ]
            writer.writerows(actions)

        # Build DuckDB file from CSVs (required by DraftRepository)
        db_path = data_path / "draft_data.duckdb"
        conn = duckdb.connect(str(db_path))
        for csv_file in data_path.glob("*.csv"):
            table_name = csv_file.stem.replace("-", "_")
            conn.execute(f"""
                CREATE TABLE {table_name} AS
                SELECT * FROM read_csv('{csv_file}', header=true, all_varchar=true)
            """)
        conn.close()

        yield str(data_path)


@pytest.fixture
def repository(test_data_dir):
    """Create a DraftRepository with test data."""
    return DraftRepository(test_data_dir)


# =============================================================================
# Test 1: Repository Integration - Verify Real Data Loads
# =============================================================================


class TestRepositoryIntegration:
    """Tests that verify the repository correctly reads CSV data."""

    def test_get_team_roster_returns_players(self, repository):
        """Repository should return actual player data from CSV."""
        roster = repository.get_team_roster("oe:team:t1")

        assert roster is not None
        assert len(roster) == 5

        # Verify player data
        player_names = {p["player_name"] for p in roster}
        assert "Faker" in player_names
        assert "Zeus" in player_names

    def test_get_team_context_builds_model(self, repository):
        """Repository should build TeamContext from CSV data."""
        context = repository.get_team_context("oe:team:t1", "blue")

        assert context is not None
        assert context.name == "T1"
        assert context.side == "blue"
        assert len(context.players) == 5

        # Verify players have correct roles (lowercase canonical)
        roles = {p.role for p in context.players}
        assert roles == {"top", "jungle", "mid", "bot", "support"}

    def test_get_team_games_returns_game_data(self, repository):
        """Repository should return games for a team."""
        games = repository.get_team_games("oe:team:t1", limit=10)

        assert len(games) >= 1
        assert games[0]["game_id"] == "g:test1"

    def test_get_draft_actions_returns_complete_draft(self, repository):
        """Repository should return all 20 draft actions for a game."""
        actions = repository.get_draft_actions("g:test1")

        assert len(actions) == 20

        # Verify action structure (returns dicts, not objects)
        bans = [a for a in actions if a["action_type"] == "ban"]
        picks = [a for a in actions if a["action_type"] == "pick"]
        assert len(bans) == 10
        assert len(picks) == 10

        # Verify first ban
        first_action = actions[0]
        assert first_action["champion_name"] == "Aurora"
        assert first_action["team_side"] == "blue"


# =============================================================================
# Test 2: Service Integration - Verify Services Work Together
# =============================================================================


class TestServiceIntegration:
    """Tests that verify services integrate correctly without mocks."""

    def test_enemy_simulator_uses_real_draft_data(self, repository):
        """EnemySimulatorService should load strategy from real game data."""
        service = EnemySimulatorService(data_path=repository.data_path)

        strategy = service.initialize_enemy_strategy("oe:team:geng")

        assert strategy is not None
        assert strategy.reference_game_id == "g:test1"
        assert len(strategy.draft_script) > 0
        assert len(strategy.champion_weights) > 0

    def test_enemy_simulator_generates_valid_actions(self, repository):
        """Enemy simulator should generate picks from historical data."""
        service = EnemySimulatorService(data_path=repository.data_path)
        strategy = service.initialize_enemy_strategy("oe:team:geng")

        # Generate an action (enemy's first ban)
        champion, source = service.generate_action(
            strategy,
            sequence=2,  # Red's first action in the draft
            unavailable={"Aurora"}  # Blue already banned Aurora
        )

        assert champion is not None
        assert champion != "Aurora"  # Should not pick unavailable
        assert source in ["reference_game", "fallback_game", "weighted_random"]

    def test_pick_engine_with_real_knowledge_data(self):
        """Pick engine should generate recommendations using knowledge files."""
        engine = PickRecommendationEngine()

        team_players = [
            {"name": "Faker", "role": "MID"},
            {"name": "Zeus", "role": "TOP"},
        ]

        recs = engine.get_recommendations(
            team_players=team_players,
            our_picks=["Jax"],  # TOP filled
            enemy_picks=["Rell", "Varus"],
            banned=["Aurora", "Yone"],
            limit=5
        )

        assert len(recs) >= 1
        # Recommendations should exclude unavailable
        rec_names = {r["champion_name"] for r in recs}
        assert "Jax" not in rec_names
        assert "Aurora" not in rec_names
        # Should have valid structure
        assert all("suggested_role" in r for r in recs)
        assert all("score" in r for r in recs)

    def test_ban_service_with_repository_lookup(self, repository):
        """Ban service should auto-lookup roster from repository."""
        service = BanRecommendationService(draft_repository=repository)

        recs = service.get_ban_recommendations(
            enemy_team_id="oe:team:geng",
            our_picks=[],
            enemy_picks=[],
            banned=[],
            phase="BAN_PHASE_1",
            limit=5
        )

        assert len(recs) >= 1
        # Should have valid structure
        assert all("champion_name" in r for r in recs)
        assert all("priority" in r for r in recs)


# =============================================================================
# Test 3: Complete Draft Scenario - Full 20-Action Draft
# =============================================================================


class TestCompleteDraftScenario:
    """Tests that verify a complete draft works end-to-end."""

    def test_full_draft_sequence_via_actions(self, repository):
        """Simulate a complete 20-action draft using DraftAction model."""
        from datetime import datetime
        from ban_teemo.models.draft import DraftAction

        # Get team contexts for the draft state
        blue_team = repository.get_team_context("oe:team:t1", "blue")
        red_team = repository.get_team_context("oe:team:geng", "red")

        draft = DraftState(
            game_id="g:test1",
            series_id="s:test1",
            game_number=1,
            patch_version="14.24",
            match_date=datetime(2026, 1, 15, 14, 0),
            blue_team=blue_team,
            red_team=red_team,
        )

        # Standard draft order
        draft_actions = [
            # Ban Phase 1
            (1, "ban", "blue", "Aurora"),
            (2, "ban", "red", "Yone"),
            (3, "ban", "blue", "K'Sante"),
            (4, "ban", "red", "Azir"),
            (5, "ban", "blue", "Rumble"),
            (6, "ban", "red", "Taliyah"),
            # Pick Phase 1
            (7, "pick", "blue", "Jax"),
            (8, "pick", "red", "Rell"),
            (9, "pick", "red", "Varus"),
            (10, "pick", "blue", "Orianna"),
            (11, "pick", "blue", "Vi"),
            (12, "pick", "red", "Jayce"),
            # Ban Phase 2
            (13, "ban", "red", "Leona"),
            (14, "ban", "blue", "Nautilus"),
            (15, "ban", "red", "Thresh"),
            (16, "ban", "blue", "Rakan"),
            # Pick Phase 2
            (17, "pick", "red", "Sejuani"),
            (18, "pick", "blue", "Ashe"),
            (19, "pick", "blue", "Renata Glasc"),
            (20, "pick", "red", "Ahri"),
        ]

        for seq, action_type, side, champion in draft_actions:
            action = DraftAction(
                sequence=seq,
                action_type=action_type,
                team_side=side,
                champion_id=f"c:{champion.lower()}",
                champion_name=champion,
            )
            draft.actions.append(action)

        # Verify final state
        assert len(draft.blue_bans) == 5
        assert len(draft.red_bans) == 5
        assert len(draft.blue_picks) == 5
        assert len(draft.red_picks) == 5

        # Verify specific picks
        assert "Faker" in [p.name for p in draft.blue_team.players]  # Mid player
        assert "Orianna" in draft.blue_picks  # Mid champion

        # Verify no duplicates
        all_champions = (
            draft.blue_bans + draft.red_bans +
            draft.blue_picks + draft.red_picks
        )
        assert len(all_champions) == len(set(all_champions))

    def test_draft_state_computes_bans_picks_from_actions(self, repository):
        """DraftState should correctly compute bans/picks from actions list."""
        from datetime import datetime
        from ban_teemo.models.draft import DraftAction

        blue_team = repository.get_team_context("oe:team:t1", "blue")
        red_team = repository.get_team_context("oe:team:geng", "red")

        draft = DraftState(
            game_id="g:test1",
            series_id="s:test1",
            game_number=1,
            patch_version="14.24",
            match_date=datetime(2026, 1, 15, 14, 0),
            blue_team=blue_team,
            red_team=red_team,
        )

        # Add some actions
        draft.actions = [
            DraftAction(1, "ban", "blue", "c:aurora", "Aurora"),
            DraftAction(2, "ban", "red", "c:yone", "Yone"),
            DraftAction(3, "ban", "blue", "c:ksante", "K'Sante"),
            DraftAction(4, "ban", "red", "c:azir", "Azir"),
            DraftAction(7, "pick", "blue", "c:jax", "Jax"),
            DraftAction(8, "pick", "red", "c:rell", "Rell"),
            DraftAction(10, "pick", "blue", "c:orianna", "Orianna"),
        ]

        # Verify properties compute correctly
        assert draft.blue_bans == ["Aurora", "K'Sante"]
        assert draft.red_bans == ["Yone", "Azir"]
        assert draft.blue_picks == ["Jax", "Orianna"]
        assert draft.red_picks == ["Rell"]

    def test_recommendation_engine_respects_draft_progression(self):
        """Engine should adapt recommendations as draft progresses."""
        engine = PickRecommendationEngine()
        team_players = [
            {"name": "Zeus", "role": "top"},
            {"name": "Oner", "role": "jungle"},
            {"name": "Faker", "role": "mid"},
            {"name": "Gumayusi", "role": "bot"},
            {"name": "Keria", "role": "support"},
        ]

        # Early draft - all roles open
        early_recs = engine.get_recommendations(
            team_players=team_players,
            our_picks=[],
            enemy_picks=[],
            banned=["Aurora"],
            limit=10
        )
        early_roles = {r["suggested_role"] for r in early_recs}
        # Should suggest multiple roles
        assert len(early_roles) >= 2

        # Mid draft - some roles filled
        # Use pure role champions (not flex) so soft role fill closes roles completely
        mid_recs = engine.get_recommendations(
            team_players=team_players,
            our_picks=["Gnar", "Vi", "Orianna"],  # top, jungle, mid filled (non-flex)
            enemy_picks=["Rell", "Varus"],
            banned=["Aurora", "Yone"],
            limit=10
        )
        mid_roles = {r["suggested_role"] for r in mid_recs}
        # Should only suggest bot and support (lowercase canonical)
        assert mid_roles.issubset({"bot", "support"})

        # Late draft - only one role left
        # Use Jinx (pure ADC) instead of Ashe (flex ADC/SUP) for complete role fill
        late_recs = engine.get_recommendations(
            team_players=team_players,
            our_picks=["Gnar", "Vi", "Orianna", "Jinx"],  # Only support open
            enemy_picks=["Rell", "Varus", "Jayce", "Sejuani"],
            banned=["Aurora", "Yone", "K'Sante", "Azir", "Rumble"],
            limit=5
        )
        late_roles = {r["suggested_role"] for r in late_recs}
        # Should only suggest support (lowercase canonical)
        assert late_roles == {"support"}


# =============================================================================
# Test 4: API Integration - Test Endpoints with Real Services
# =============================================================================


class TestAPIIntegration:
    """Tests for API endpoints with real (non-mocked) services."""

    @pytest.fixture
    async def integration_client(self, test_data_dir):
        """Create async test client with real services pointing to test data."""
        # Clear any cached state
        if hasattr(app.state, "repository"):
            delattr(app.state, "repository")
        for attr in ["enemy_simulator_service", "pick_engine", "ban_service", "team_eval_service"]:
            if hasattr(app.state, attr):
                delattr(app.state, attr)

        # Set up real repository with test data
        app.state.repository = DraftRepository(test_data_dir)

        # Clear sessions
        from ban_teemo.api.routes.simulator import _sessions, _sessions_lock, _session_locks
        with _sessions_lock:
            _sessions.clear()
            _session_locks.clear()

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            yield client

    @pytest.mark.anyio
    async def test_start_session_with_real_teams(self, integration_client):
        """API should start session with real team data from CSV."""
        response = await integration_client.post(
            "/api/simulator/sessions",
            json={
                "blue_team_id": "oe:team:t1",
                "red_team_id": "oe:team:geng",
                "coaching_side": "blue",
            }
        )

        assert response.status_code == 201
        data = response.json()

        # Verify real team data loaded
        assert data["blue_team"]["name"] == "T1"
        assert data["red_team"]["name"] == "Gen.G"

        # Verify players loaded
        assert len(data["blue_team"]["players"]) == 5
        blue_player_names = {p["name"] for p in data["blue_team"]["players"]}
        assert "Faker" in blue_player_names

    @pytest.mark.anyio
    async def test_submit_action_updates_state(self, integration_client):
        """Submitting actions should correctly update draft state."""
        # Start session
        start_resp = await integration_client.post(
            "/api/simulator/sessions",
            json={
                "blue_team_id": "oe:team:t1",
                "red_team_id": "oe:team:geng",
                "coaching_side": "blue",
            }
        )
        session_id = start_resp.json()["session_id"]

        # Submit a ban
        action_resp = await integration_client.post(
            f"/api/simulator/sessions/{session_id}/actions",
            json={"champion": "Aurora"}
        )

        assert action_resp.status_code == 200
        data = action_resp.json()
        assert data["action"]["champion_name"] == "Aurora"
        assert data["action"]["action_type"] == "ban"
        assert "Aurora" in data["draft_state"]["blue_bans"]

    @pytest.mark.anyio
    async def test_get_recommendations_during_draft(self, integration_client):
        """API should return pick recommendations during draft."""
        # Start session
        start_resp = await integration_client.post(
            "/api/simulator/sessions",
            json={
                "blue_team_id": "oe:team:t1",
                "red_team_id": "oe:team:geng",
                "coaching_side": "blue",
            }
        )
        session_id = start_resp.json()["session_id"]

        # Fetch recommendations separately (CQRS refactor)
        recs_resp = await integration_client.get(
            f"/api/simulator/sessions/{session_id}/recommendations"
        )
        data = recs_resp.json()
        assert "recommendations" in data
        assert "for_action_count" in data

    @pytest.mark.anyio
    async def test_list_teams_returns_real_data(self, integration_client):
        """Teams list endpoint should return real team data."""
        response = await integration_client.get("/api/simulator/teams")

        assert response.status_code == 200
        data = response.json()
        assert "teams" in data

        team_names = {t["name"] for t in data["teams"]}
        assert "T1" in team_names
        assert "Gen.G" in team_names
