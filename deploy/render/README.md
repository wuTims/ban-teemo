# Render Deployment

Render hosts the FastAPI backend with WebSocket support.

## Deployment Methods

### Method 1: Blueprint (Recommended)

The `render.yaml` Blueprint automates service provisioning.

1. Push code to GitHub/GitLab
2. Go to [Render Dashboard](https://dashboard.render.com)
3. Click **New** > **Blueprint**
4. Connect your repository
5. Render detects `deploy/render/render.yaml` automatically
6. Review and click **Apply**

### Method 2: Manual Setup

1. Go to [Render Dashboard](https://dashboard.render.com)
2. Click **New** > **Web Service**
3. Connect your repository
4. Configure:
   - **Name**: `ban-teemo-api`
   - **Region**: Oregon (or closest to users)
   - **Branch**: `main`
   - **Runtime**: Docker
   - **Dockerfile Path**: `deploy/docker/Dockerfile`
   - **Docker Context**: `.` (repository root)
   - **Plan**: Free

## Environment Variables

Set these in Render Dashboard > Service > Environment:

| Variable | Value | Notes |
|----------|-------|-------|
| `PORT` | `10000` | Auto-set by Render |
| `CORS_ORIGINS` | `https://your-app.pages.dev` | Your Cloudflare URL |
| `ENABLE_LLM` | `true` | Optional LLM features |
| `NEBIUS_API_KEY` | `sk-...` | Secret - add in dashboard |
| `GROQ_API_KEY` | `gsk_...` | Secret - add in dashboard |

## Post-Deployment Checklist

- [ ] Service is running (check Logs tab)
- [ ] Health check passes: `curl https://your-service.onrender.com/health`
- [ ] Update `CORS_ORIGINS` with actual frontend URL
- [ ] Add any LLM API keys as secrets
- [ ] Test WebSocket connection from frontend

## Keeping Service Awake (Optional)

Free tier services sleep after 15 minutes. To prevent this:

1. Use an external cron service (UptimeRobot, cron-job.org)
2. Ping `/health` every 10 minutes

```bash
# Example cron-job.org setup
URL: https://ban-teemo-api.onrender.com/health
Schedule: Every 10 minutes
```

## Logs & Debugging

```bash
# View logs in dashboard
Render Dashboard > ban-teemo-api > Logs

# Common issues:
# - "No module named 'ban_teemo'" -> Check Dockerfile PYTHONPATH
# - "Connection refused" -> Service still starting, wait 30-60s
# - "CORS error" -> Update CORS_ORIGINS environment variable
```

## Scaling (Paid Tiers)

When ready to upgrade:

```yaml
# In render.yaml, change:
plan: starter  # $7/month - no sleep, 512MB RAM
# or
plan: standard # $25/month - 2GB RAM, dedicated CPU
```
