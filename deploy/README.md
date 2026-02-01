# Deployment Guide

This directory contains deployment configurations for the Ban Teemo application.

## Architecture Overview

```
┌─────────────────────────────────────┐
│     Cloudflare Pages (Frontend)     │
│     frontend/ React Application    │
│     Global CDN, Free Tier           │
└──────────────────┬──────────────────┘
                   │ HTTPS API + WebSocket
                   ▼
┌─────────────────────────────────────┐
│       Render (Backend)              │
│     FastAPI + Python 3.11           │
│     WebSocket Support               │
└──────────────────┬──────────────────┘
                   │
    ┌──────────────┼──────────────┐
    ▼              ▼              ▼
┌────────┐   ┌──────────┐   ┌──────────┐
│ DuckDB │   │Knowledge │   │External  │
│(Bundled)│  │  Files   │   │LLM APIs  │
└────────┘   └──────────┘   └──────────┘
```

## Directory Structure

```
deploy/
├── README.md              # This file
├── render/
│   ├── render.yaml        # Render Blueprint (Infrastructure as Code)
│   └── README.md          # Render-specific instructions
├── cloudflare/
│   └── README.md          # Cloudflare Pages setup instructions
├── docker/
│   ├── Dockerfile         # Backend container image
│   └── .dockerignore      # Docker build exclusions
└── env/
    ├── .env.example       # Backend environment template
    └── .env.frontend      # Frontend environment template
```

## Data Files

The application requires data files that are gitignored (too large for version control).

### Option A: GitHub Release (Recommended)

```bash
# 1. Create data archive locally
./deploy/scripts/prepare-data.sh

# 2. Create a GitHub release with the data
gh release create v0.1.0 ban-teemo-data.tar.gz --title "v0.1.0 - Initial Release"

# 3. Update Dockerfile to download from release (already configured)
```

### Option B: Include in Deployment Branch

```bash
# Create a deployment branch that includes data
git checkout -b deploy
git add -f outputs/full_2024_2025_v2/csv knowledge
git commit -m "Add data files for deployment"
git push origin deploy
# Configure Render to deploy from 'deploy' branch
```

### Option C: Cloud Storage

Upload `ban-teemo-data.tar.gz` to S3/R2/GCS and update Dockerfile to fetch during build.

---

## Quick Start

### 1. Deploy Backend to Render

```bash
# Option A: Using Render Dashboard
# 1. Go to https://dashboard.render.com
# 2. New > Blueprint
# 3. Connect this repository
# 4. Render auto-detects deploy/render/render.yaml

# Option B: Using Render CLI
render blueprint apply deploy/render/render.yaml
```

### 2. Deploy Frontend to Cloudflare Pages

```bash
# 1. Go to https://dash.cloudflare.com
# 2. Pages > Create a project
# 3. Connect Git repository
# 4. Configure build settings (see deploy/cloudflare/README.md)
```

### 3. Connect Frontend to Backend

After both are deployed:
1. Copy your Render backend URL (e.g., `https://ban-teemo-api.onrender.com`)
2. In Cloudflare Pages dashboard, add environment variable:
   - `VITE_API_URL` = `https://ban-teemo-api.onrender.com`
3. Trigger a redeploy

## Environment Variables

### Backend (Render)

| Variable | Required | Description |
|----------|----------|-------------|
| `PORT` | Auto | Set by Render (default: 10000) |
| `CORS_ORIGINS` | Yes | Frontend URL(s), comma-separated |
| `NEBIUS_API_KEY` | No | LLM provider for recommendations |
| `GROQ_API_KEY` | No | Alternative LLM provider |
| `TOGETHER_API_KEY` | No | Alternative LLM provider |
| `ENABLE_LLM` | No | Feature flag (default: true) |

### Frontend (Cloudflare)

| Variable | Required | Description |
|----------|----------|-------------|
| `VITE_API_URL` | Yes | Backend API URL |

## Free Tier Limitations

### Render Free Tier
- 750 hours/month of runtime
- Sleeps after 15 minutes of inactivity
- ~30-60 second cold start when waking
- 512MB RAM, 0.1 CPU

### Cloudflare Pages Free Tier
- Unlimited static requests
- 500 builds/month
- 100,000 Functions invocations/day (not used)

## Monitoring

### Health Check
```bash
curl https://your-backend.onrender.com/health
# Expected: {"status": "healthy", "service": "ban-teemo"}
```

### Logs
- Render: Dashboard > Service > Logs
- Cloudflare: Dashboard > Pages > Deployments > View logs

## Troubleshooting

### Backend won't start
1. Check Render logs for Python errors
2. Verify all data files are included in the Docker image
3. Ensure `PORT` environment variable is being used

### WebSocket connection fails
1. Verify CORS_ORIGINS includes your frontend URL
2. Check browser console for connection errors
3. Ensure Render service is awake (not sleeping)

### Frontend can't reach backend
1. Verify `VITE_API_URL` is set correctly
2. Check for mixed content (HTTPS frontend to HTTP backend)
3. Confirm backend is deployed and healthy
