"""DuckDB-based data access for draft data."""

import duckdb
import pandas as pd


class DraftRepository:
    """Data access layer - DuckDB queries against CSV files."""

    def __init__(self, data_path: str):
        """Initialize with path to CSV directory.

        Args:
            data_path: Path to directory containing CSV files
                      (teams.csv, players.csv, series.csv, etc.)
        """
        self.data_path = data_path

    def _query(self, sql: str) -> list[dict]:
        """Execute query and return list of dicts with proper type conversion."""
        # Use a fresh connection per query to avoid race conditions
        conn = duckdb.connect(":memory:")
        df = conn.execute(sql).df()
        conn.close()

        # Convert all columns to JSON-serializable types
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
            FROM '{self.data_path}/series.csv' s
            JOIN '{self.data_path}/teams.csv' t1 ON s.blue_team_id = t1.id
            JOIN '{self.data_path}/teams.csv' t2 ON s.red_team_id = t2.id
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
            FROM '{self.data_path}/games.csv'
            WHERE series_id = '{series_id}'
            ORDER BY game_number
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
            FROM read_csv('{self.data_path}/games.csv', all_varchar=true) g
            JOIN read_csv('{self.data_path}/series.csv', all_varchar=true) s ON g.series_id = s.id
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
            FROM '{self.data_path}/teams.csv'
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
                CAST(player_id AS VARCHAR) as id,
                player_name as name,
                role,
                team_side
            FROM read_csv('{self.data_path}/player_game_stats.csv', all_varchar=true)
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
                CAST(player_id AS VARCHAR) as id,
                player_name as name,
                role,
                team_id
            FROM read_csv('{self.data_path}/player_game_stats.csv', all_varchar=true)
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
            FROM read_csv('{self.data_path}/player_game_stats.csv', all_varchar=true) pgs
            JOIN read_csv('{self.data_path}/teams.csv', all_varchar=true) t ON pgs.team_id = t.id
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
            FROM read_csv('{self.data_path}/draft_actions.csv', all_varchar=true) da
            JOIN read_csv('{self.data_path}/games.csv', all_varchar=true) g ON da.game_id = g.id
            JOIN read_csv('{self.data_path}/series.csv', all_varchar=true) s ON g.series_id = s.id
            WHERE da.game_id = '{game_id}'
            ORDER BY CAST(da.sequence_number AS INTEGER)
        """)
