"""DuckDB-based data access for draft data."""

import duckdb
import pandas as pd
from pathlib import Path

from ban_teemo.models.team import Player, TeamContext


class DraftRepository:
    """Data access layer - DuckDB queries against pre-built database file."""

    def __init__(self, data_path: str):
        """Initialize with path to DuckDB database.

        Args:
            data_path: Path to directory containing draft_data.duckdb
                      (built from CSV files by scripts/build_duckdb.py)

        Raises:
            FileNotFoundError: If draft_data.duckdb doesn't exist
        """
        self.data_path = Path(data_path) if isinstance(data_path, str) else data_path
        self._db_path = self.data_path / "draft_data.duckdb"

        if not self._db_path.exists():
            raise FileNotFoundError(
                f"DuckDB database not found: {self._db_path}\n"
                f"Run: cd backend && uv run python scripts/build_duckdb.py"
            )

        # Verify we can connect
        with duckdb.connect(str(self._db_path), read_only=True) as conn:
            tables = conn.execute("SHOW TABLES").fetchall()
        print(f"DraftRepository: Using {self._db_path} ({len(tables)} tables)")

    def _query(self, sql: str) -> list[dict]:
        """Execute query and return list of dicts with proper type conversion."""
        # Read-only connection per query - no locks needed, thread-safe
        with duckdb.connect(str(self._db_path), read_only=True) as conn:
            df = conn.execute(sql).df()

        # Convert all columns to JSON-serializable types (preserve existing behavior)
        for col in df.columns:
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                # Convert datetime to ISO string
                df[col] = df[col].dt.strftime("%Y-%m-%dT%H:%M:%S")
            elif df[col].dtype == "object":
                # Keep strings as-is
                pass
            else:
                # Convert numeric types to native Python types
                df[col] = df[col].astype(str)

        return df.to_dict(orient="records")

    def get_series_list(self, limit: int = 50) -> list[dict]:
        """Get recent series for replay selection.

        Returns list of dicts with: id, match_date, format,
        blue_team_id, blue_team_name, red_team_id, red_team_name
        """
        return self._query(f"""
            SELECT
                s.id,
                s.match_date,
                s.format,
                s.blue_team_id,
                t1.name as blue_team_name,
                s.red_team_id,
                t2.name as red_team_name
            FROM series s
            JOIN teams t1 ON s.blue_team_id = t1.id
            JOIN teams t2 ON s.red_team_id = t2.id
            ORDER BY s.match_date DESC
            LIMIT {limit}
        """)

    def get_games_for_series(self, series_id: str) -> list[dict]:
        """Get all games in a series.

        Returns list of dicts with: id, game_number, patch_version, winner_team_id
        """
        return self._query(f"""
            SELECT
                id,
                game_number,
                patch_version,
                winner_team_id,
                duration_seconds
            FROM games
            WHERE series_id = '{series_id}'
            ORDER BY CAST(game_number AS INTEGER)
        """)

    def get_game_info(self, series_id: str, game_number: int) -> dict | None:
        """Get game metadata including team IDs.

        Returns dict with: game_id, series_id, game_number, patch_version,
        winner_team_id, match_date, blue_team_id, red_team_id
        """
        results = self._query(f"""
            SELECT
                g.id as game_id,
                g.series_id,
                g.game_number,
                g.patch_version,
                g.winner_team_id,
                s.match_date,
                s.blue_team_id,
                s.red_team_id
            FROM games g
            JOIN series s ON g.series_id = s.id
            WHERE g.series_id = '{series_id}'
              AND CAST(g.game_number AS INTEGER) = {game_number}
        """)
        return results[0] if results else None

    def get_team_with_name(self, team_id: str) -> dict | None:
        """Get team info by ID.

        Returns dict with: id, name
        """
        results = self._query(f"""
            SELECT id, name
            FROM teams
            WHERE id = '{team_id}'
        """)
        return results[0] if results else None

    def get_players_for_game(self, game_id: str, team_id: str) -> list[dict]:
        """Get players who played in a specific game for a team.

        Returns list of dicts with: id, name, role, team_side
        Ordered by role (TOP, JNG, MID, ADC, SUP)
        """
        return self._query(f"""
            SELECT DISTINCT
                player_id as id,
                player_name as name,
                role,
                team_side
            FROM player_game_stats
            WHERE game_id = '{game_id}'
              AND team_id = '{team_id}'
            ORDER BY
                CASE role
                    WHEN 'TOP' THEN 1
                    WHEN 'JNG' THEN 2
                    WHEN 'MID' THEN 3
                    WHEN 'ADC' THEN 4
                    WHEN 'SUP' THEN 5
                    ELSE 6
                END
        """)

    def get_players_for_game_by_side(self, game_id: str, team_side: str) -> list[dict]:
        """Get players who played on a specific side in a game.

        Args:
            game_id: The game ID
            team_side: "blue" or "red"

        Returns list of dicts with: id, name, role, team_id
        Ordered by role (TOP, JNG, MID, ADC, SUP)
        """
        return self._query(f"""
            SELECT DISTINCT
                player_id as id,
                player_name as name,
                role,
                team_id
            FROM player_game_stats
            WHERE game_id = '{game_id}'
              AND team_side = '{team_side}'
            ORDER BY
                CASE role
                    WHEN 'TOP' THEN 1
                    WHEN 'JNG' THEN 2
                    WHEN 'MID' THEN 3
                    WHEN 'ADC' THEN 4
                    WHEN 'SUP' THEN 5
                    ELSE 6
                END
        """)

    def get_team_for_game_side(self, game_id: str, team_side: str) -> dict | None:
        """Get team info for who played on a specific side in a game.

        Args:
            game_id: The game ID
            team_side: "blue" or "red"

        Returns dict with: id, name, or None if not found
        """
        results = self._query(f"""
            SELECT DISTINCT
                pgs.team_id as id,
                t.name
            FROM player_game_stats pgs
            JOIN teams t ON pgs.team_id = t.id
            WHERE pgs.game_id = '{game_id}'
              AND pgs.team_side = '{team_side}'
            LIMIT 1
        """)
        return results[0] if results else None

    def get_draft_actions(self, game_id: str) -> list[dict]:
        """Get all draft actions for a game in order.

        Returns list of dicts with: sequence, action_type, team_id,
        champion_id, champion_name, team_side
        """
        return self._query(f"""
            SELECT
                da.sequence_number as sequence,
                da.action_type,
                da.team_id,
                da.champion_id,
                da.champion_name,
                CASE
                    WHEN da.team_id = s.blue_team_id THEN 'blue'
                    ELSE 'red'
                END as team_side
            FROM draft_actions da
            JOIN games g ON da.game_id = g.id
            JOIN series s ON g.series_id = s.id
            WHERE da.game_id = '{game_id}'
            ORDER BY CAST(da.sequence_number AS INTEGER)
        """)

    def get_team_games(self, team_id: str, limit: int = 10) -> list[dict]:
        """Get recent games for a team.

        Returns list of dicts with: game_id, series_id, game_number, match_date,
        team_side, opponent_team_id, opponent_team_name, winner_team_id
        """
        return self._query(f"""
            WITH team_games AS (
                SELECT DISTINCT
                    pgs.game_id,
                    g.series_id,
                    CAST(g.game_number AS INTEGER) as game_number,
                    s.match_date,
                    pgs.team_side,
                    g.winner_team_id,
                    CASE
                        WHEN pgs.team_side = 'blue' THEN s.red_team_id
                        ELSE s.blue_team_id
                    END as opponent_team_id
                FROM player_game_stats pgs
                JOIN games g ON pgs.game_id = g.id
                JOIN series s ON g.series_id = s.id
                WHERE pgs.team_id = '{team_id}'
            )
            SELECT
                tg.game_id,
                tg.series_id,
                tg.game_number,
                tg.match_date,
                tg.team_side,
                tg.opponent_team_id,
                t.name as opponent_team_name,
                tg.winner_team_id
            FROM team_games tg
            JOIN teams t ON tg.opponent_team_id = t.id
            ORDER BY tg.match_date DESC, tg.game_number DESC
            LIMIT {limit}
        """)

    def get_team_roster(self, team_id: str) -> list[dict]:
        """Get current roster for a team based on most recent game.

        Returns list of dicts with: player_id, player_name, role
        Ordered by role (TOP, JNG, MID, ADC, SUP)
        """
        # Get the most recent game for the team
        recent_games = self.get_team_games(team_id, limit=1)
        if not recent_games:
            return []

        game_id = recent_games[0]["game_id"]
        return self._query(f"""
            SELECT DISTINCT
                player_id,
                player_name,
                role
            FROM player_game_stats
            WHERE game_id = '{game_id}'
              AND team_id = '{team_id}'
            ORDER BY
                CASE role
                    WHEN 'TOP' THEN 1
                    WHEN 'JNG' THEN 2
                    WHEN 'MID' THEN 3
                    WHEN 'ADC' THEN 4
                    WHEN 'SUP' THEN 5
                    ELSE 6
                END
        """)

    def get_team_context(self, team_id: str, side: str) -> TeamContext | None:
        """Build TeamContext for a team with its current roster.

        Args:
            team_id: The team ID
            side: "blue" or "red" - the side the team will play on

        Returns:
            TeamContext with team info and players, or None if team not found
        """
        team_info = self.get_team_with_name(team_id)
        if not team_info:
            return None

        roster = self.get_team_roster(team_id)
        players = [
            Player(
                id=p["player_id"],
                name=p["player_name"],
                role=p["role"],
            )
            for p in roster
        ]

        return TeamContext(
            id=team_id,
            name=team_info["name"],
            side=side,
            players=players,
        )
