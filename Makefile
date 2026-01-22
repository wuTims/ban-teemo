.PHONY: install install-backend install-frontend dev dev-backend dev-frontend seed test lint clean

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

# Database seeding
seed:
	cd backend && uv run python ../data/scripts/seed_database.py

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
	rm -f data/draft_assistant.db

# Help
help:
	@echo "Available commands:"
	@echo "  make install        - Install all dependencies"
	@echo "  make dev-backend    - Start FastAPI dev server (port 8000)"
	@echo "  make dev-frontend   - Start Vite dev server (port 5173)"
	@echo "  make seed           - Seed the SQLite database"
	@echo "  make test           - Run all tests"
	@echo "  make lint           - Run linters"
	@echo "  make build          - Build for production"
	@echo "  make clean          - Remove build artifacts"
