#!/usr/bin/env python3
"""
Seed the SQLite database with data from CSV files.

Usage:
    python data/scripts/seed_database.py
"""

import sqlite3
from pathlib import Path


DATA_DIR = Path(__file__).parent.parent
DB_PATH = DATA_DIR / "draft_assistant.db"
CSV_DIR = DATA_DIR / "csv"


def create_tables(conn: sqlite3.Connection) -> None:
    """Create database schema."""
    conn.executescript("""
        -- Champions table
        CREATE TABLE IF NOT EXISTS champions (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            roles TEXT,  -- JSON array
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- Teams table
        CREATE TABLE IF NOT EXISTS teams (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            region TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- Games table
        CREATE TABLE IF NOT EXISTS games (
            id TEXT PRIMARY KEY,
            series_id TEXT,
            blue_team_id TEXT,
            red_team_id TEXT,
            winner TEXT,
            patch TEXT,
            game_date TIMESTAMP,
            FOREIGN KEY (blue_team_id) REFERENCES teams(id),
            FOREIGN KEY (red_team_id) REFERENCES teams(id)
        );

        -- Draft actions table
        CREATE TABLE IF NOT EXISTS draft_actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id TEXT NOT NULL,
            action_number INTEGER NOT NULL,
            phase TEXT NOT NULL,  -- 'ban' or 'pick'
            team TEXT NOT NULL,   -- 'blue' or 'red'
            champion_id TEXT,
            role TEXT,
            FOREIGN KEY (game_id) REFERENCES games(id),
            FOREIGN KEY (champion_id) REFERENCES champions(id),
            UNIQUE(game_id, action_number)
        );

        -- Create indexes
        CREATE INDEX IF NOT EXISTS idx_games_date ON games(game_date);
        CREATE INDEX IF NOT EXISTS idx_draft_game ON draft_actions(game_id);
    """)


def seed_from_csv(conn: sqlite3.Connection) -> None:
    """Load data from CSV files into database."""
    # TODO: Implement CSV loading logic
    # This will parse the CSV files from outputs/full_2024_2025/csv/
    # and insert them into the appropriate tables
    pass


def main() -> None:
    """Main entry point."""
    print(f"Creating database at {DB_PATH}")

    with sqlite3.connect(DB_PATH) as conn:
        create_tables(conn)
        print("Tables created successfully")

        seed_from_csv(conn)
        print("Database seeding complete")


if __name__ == "__main__":
    main()
