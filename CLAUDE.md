# Project Guidelines

## Development Commands

- **Always use `uv` for all Python-related commands** - do not use `pip`, `python`, or direct virtualenv commands
- Run pytest: `uv run pytest tests/test_file.py -v`
- Run Python scripts: `uv run python script.py`
- Install dependencies: `uv add package-name`
- Install dev dependencies: `uv add --dev package-name`
- Sync dependencies: `uv sync` or `uv sync --all-extras`

## Project Structure

- Backend code: `backend/src/ban_teemo/`
- Backend tests: `backend/tests/`
- Knowledge data files: `knowledge/`
- Frontend code: `frontend/`
