# Ban Teemo - LoL Draft Assistant

An AI-powered League of Legends draft assistant that provides real-time recommendations during champion select, backed by professional match data and LLM reasoning.

## Project Structure

```
ban-teemo/
├── backend/           # Python FastAPI service ("ban-teemo")
│   ├── src/ban_teemo/ # Main application code
│   ├── knowledge/     # Domain expert files (prompts, team profiles)
│   └── tests/         # Backend tests
│
├── deepdraft/         # React frontend
│   └── src/
│       ├── components/  # UI components
│       ├── hooks/       # Custom React hooks
│       ├── api/         # API client
│       └── types/       # TypeScript types
│
├── data/              # Database and seeding
│   ├── scripts/       # Database seeding scripts
│   └── csv/           # Processed data files
│
└── docs/              # Documentation and specs
```

## Quick Start

### Prerequisites

- Python 3.14+ with [uv](https://docs.astral.sh/uv/)
- Node.js 18+ with npm
- Make (optional, for convenience commands)

### Installation

```bash
# Install all dependencies
make install

# Or manually:
cd backend && uv sync
cd deepdraft && npm install
```

### Development

Run backend and frontend in separate terminals:

```bash
# Terminal 1: Backend (FastAPI on port 8000)
make dev-backend

# Terminal 2: Frontend (Vite on port 5173)
make dev-frontend
```

### API Endpoints

- `GET /health` - Health check
- `GET /docs` - OpenAPI documentation (Swagger UI)

## Configuration

Backend configuration via environment variables (see `backend/.env.example`):

- `GROQ_API_KEY` - Groq API key for LLM
- `DATABASE_URL` - SQLite database path

## Tech Stack

**Backend:**
- FastAPI + uvicorn
- aiosqlite (async SQLite)
- Groq/Together for LLM inference
- pydantic-settings for configuration

**Frontend:**
- React 19 + TypeScript
- Vite
- Tailwind CSS v4

## License

MIT
