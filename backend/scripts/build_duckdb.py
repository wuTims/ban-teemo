#!/usr/bin/env python3
"""Build DuckDB database from CSV data files.

Run this once after updating CSV files, or in CI/CD.
The resulting .duckdb file is used by DraftRepository for fast queries.

Usage:
    uv run python scripts/build_duckdb.py [data_path]

Default data_path: outputs/full_2024_2025_v2/csv (relative to repo root)
"""
import duckdb
from pathlib import Path
import sys


def build_duckdb(data_path: Path, output_path: Path | None = None) -> Path:
    """Build DuckDB database from CSV files in data_path.

    Args:
        data_path: Directory containing CSV files
        output_path: Where to write the .duckdb file (default: data_path/draft_data.duckdb)

    Returns:
        Path to the created database file
    """
    if output_path is None:
        output_path = data_path / "draft_data.duckdb"

    # Remove old DB if exists
    if output_path.exists():
        output_path.unlink()
        print(f"Removed existing {output_path}")

    conn = duckdb.connect(str(output_path))

    csv_files = list(data_path.glob("*.csv"))
    if not csv_files:
        print(f"Warning: No CSV files found in {data_path}")
        conn.close()
        return output_path

    print(f"Building {output_path} from {len(csv_files)} CSV files...")

    for csv_file in sorted(csv_files):
        table_name = csv_file.stem
        # Sanitize table name (replace hyphens with underscores)
        table_name = table_name.replace("-", "_")

        try:
            # Use all_varchar=true to preserve string ID behavior
            # This matches the current behavior where all values are converted to strings
            conn.execute(f"""
                CREATE TABLE {table_name} AS
                SELECT * FROM read_csv('{csv_file}', header=true, all_varchar=true)
            """)
            row_count = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
            print(f"  ✓ {table_name}: {row_count:,} rows")
        except Exception as e:
            print(f"  ✗ {table_name}: {e}")

    # List all tables
    tables = conn.execute("SHOW TABLES").fetchall()
    print(f"\nCreated {len(tables)} tables in {output_path}")

    conn.close()
    return output_path


def main():
    # Default to outputs/full_2024_2025_v2/csv relative to repo root
    if len(sys.argv) > 1:
        data_path = Path(sys.argv[1])
    else:
        # Find data directory: backend/scripts -> backend -> ban-teemo -> outputs/...
        script_dir = Path(__file__).parent
        repo_root = script_dir.parent.parent  # backend/scripts -> backend -> ban-teemo
        data_path = repo_root / "outputs" / "full_2024_2025_v2" / "csv"

    if not data_path.exists():
        print(f"Error: Data path not found: {data_path}")
        print(f"Make sure CSV files exist at: {data_path}")
        sys.exit(1)

    db_path = build_duckdb(data_path)
    print(f"\nDone! Database ready at: {db_path}")


if __name__ == "__main__":
    main()
