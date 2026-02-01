.PHONY: install install-backend install-frontend dev dev-backend dev-frontend \
       setup-data download-data build-db build-knowledge \
       test lint clean help

# Install all dependencies
install: install-backend install-frontend

install-backend:
	cd backend && uv sync

install-frontend:
	cd frontend && npm install

# Development servers
dev:
	@echo "Run 'make dev-backend' and 'make dev-frontend' in separate terminals"

dev-backend:
	cd backend && uv run fastapi dev src/ban_teemo/main.py

dev-frontend:
	cd frontend && npm run dev

# =============================================================================
# Data Setup
# =============================================================================
#
# Data Flow:
#   1. download-data  → CSVs in outputs/full_2024_2025_v2/csv/
#   2. build-db       → Creates draft_data.duckdb from CSVs
#   3. build-knowledge (optional) → Regenerates knowledge/*.json from CSVs
#
# The knowledge/*.json files are pre-committed to the repo, so step 3 is only
# needed when refreshing analytics from new CSV data.
#
# =============================================================================

# Full data setup: download CSVs + build DuckDB (standard first-time setup)
setup-data: download-data build-db
	@echo ""
	@echo "✓ Data setup complete!"
	@echo ""
	@echo "  CSV data:  outputs/full_2024_2025_v2/csv/"
	@echo "  Database:  outputs/full_2024_2025_v2/csv/draft_data.duckdb"
	@echo "  Knowledge: knowledge/*.json (pre-committed, no rebuild needed)"
	@echo ""
	@echo "Run 'make dev-backend' to start the server."

# Download CSV data from GitHub releases (requires gh CLI)
download-data:
	@echo "==> Downloading data from GitHub releases..."
	@if ! command -v gh >/dev/null 2>&1; then \
		echo "Error: GitHub CLI (gh) is required. Install from https://cli.github.com/"; \
		exit 1; \
	fi
	./scripts/download-data.sh

# Build DuckDB database from CSV files
build-db:
	@echo "==> Building DuckDB database from CSVs..."
	cd backend && uv run python scripts/build_duckdb.py

# Regenerate knowledge files from CSV data (optional - only for data refresh)
build-knowledge:
	@echo "==> Regenerating knowledge files from CSV data..."
	@if [ ! -d "outputs/full_2024_2025_v2/csv" ]; then \
		echo "Error: CSV data not found. Run 'make download-data' first."; \
		exit 1; \
	fi
	uv run python scripts/build_computed_datasets.py
	@echo ""
	@echo "✓ Knowledge files regenerated in knowledge/"

# Testing
test: test-backend test-frontend

test-backend:
	cd backend && uv run pytest

test-frontend:
	cd frontend && npm test

# Linting
lint: lint-backend lint-frontend

lint-backend:
	cd backend && uv run ruff check src/

lint-frontend:
	cd frontend && npm run lint

# Build
build: build-backend build-frontend

build-backend:
	cd backend && uv build

build-frontend:
	cd frontend && npm run build

# Clean
clean:
	rm -rf backend/.venv
	rm -rf frontend/node_modules
	rm -rf frontend/dist

# Help
help:
	@echo "Available commands:"
	@echo ""
	@echo "  First-time setup:"
	@echo "    make install       - Install all dependencies (Python + Node)"
	@echo "    make setup-data    - Download CSVs + build DuckDB (requires gh CLI)"
	@echo ""
	@echo "  Development:"
	@echo "    make dev-backend   - Start FastAPI dev server (port 8000)"
	@echo "    make dev-frontend  - Start Vite dev server (port 5173)"
	@echo ""
	@echo "  Data commands:"
	@echo "    make download-data   - Download CSVs from GitHub releases"
	@echo "    make build-db        - Build DuckDB from CSV files"
	@echo "    make build-knowledge - Regenerate knowledge/*.json from CSVs"
	@echo ""
	@echo "  Testing & quality:"
	@echo "    make test          - Run all tests"
	@echo "    make lint          - Run linters"
	@echo "    make build         - Build for production"
	@echo "    make clean         - Remove build artifacts"
	@echo ""
	@echo "  Data flow:"
	@echo "    CSVs (download-data) → DuckDB (build-db) → ready to run"
	@echo "    Knowledge files are pre-committed; rebuild only when refreshing data"
