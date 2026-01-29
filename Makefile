.PHONY: install install-backend install-frontend dev dev-backend dev-frontend setup-data download-data build-db test lint clean

# Install all dependencies
install: install-backend install-frontend

install-backend:
	cd backend && uv sync

install-frontend:
	cd deepdraft && npm install

# Development servers
dev:
	@echo "Run 'make dev-backend' and 'make dev-frontend' in separate terminals"

dev-backend:
	cd backend && uv run fastapi dev src/ban_teemo/main.py

dev-frontend:
	cd deepdraft && npm run dev

# =============================================================================
# Database Setup (run these for first-time setup)
# =============================================================================

# Full data setup: download CSVs from GitHub release + build DuckDB
setup-data: download-data build-db
	@echo ""
	@echo "✓ Data setup complete! You can now run 'make dev-backend'"

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
	@echo "==> Building DuckDB database..."
	cd backend && uv run python scripts/build_duckdb.py

# Testing
test: test-backend test-frontend

test-backend:
	cd backend && uv run pytest

test-frontend:
	cd deepdraft && npm test

# Linting
lint: lint-backend lint-frontend

lint-backend:
	cd backend && uv run ruff check src/

lint-frontend:
	cd deepdraft && npm run lint

# Build
build: build-backend build-frontend

build-backend:
	cd backend && uv build

build-frontend:
	cd deepdraft && npm run build

# Clean
clean:
	rm -rf backend/.venv
	rm -rf deepdraft/node_modules
	rm -rf deepdraft/dist

# Help
help:
	@echo "Available commands:"
	@echo ""
	@echo "  First-time setup:"
	@echo "    make install      - Install all dependencies (Python + Node)"
	@echo "    make setup-data   - Download data + build DuckDB (requires gh CLI)"
	@echo ""
	@echo "  Development:"
	@echo "    make dev-backend  - Start FastAPI dev server (port 8000)"
	@echo "    make dev-frontend - Start Vite dev server (port 5173)"
	@echo ""
	@echo "  Individual data commands:"
	@echo "    make download-data - Download CSVs from GitHub releases"
	@echo "    make build-db      - Build DuckDB from CSV files"
	@echo ""
	@echo "  Other:"
	@echo "    make test         - Run all tests"
	@echo "    make lint         - Run linters"
	@echo "    make build        - Build for production"
	@echo "    make clean        - Remove build artifacts"
