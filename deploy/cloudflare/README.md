# Cloudflare Pages Deployment

Cloudflare Pages hosts the React frontend with global CDN distribution.

## Setup Instructions

### 1. Connect Repository

1. Go to [Cloudflare Dashboard](https://dash.cloudflare.com)
2. Navigate to **Workers & Pages** > **Pages**
3. Click **Create a project** > **Connect to Git**
4. Select your repository and authorize access

### 2. Configure Build Settings

| Setting | Value |
|---------|-------|
| **Project name** | `ban-teemo` (or your preference) |
| **Production branch** | `main` |
| **Framework preset** | Vite |
| **Build command** | `cd frontend && npm install && npm run build` |
| **Build output directory** | `frontend/dist` |
| **Root directory** | `/` (repository root) |

### 3. Environment Variables

Add these in **Settings** > **Environment variables**:

| Variable | Value | Environment |
|----------|-------|-------------|
| `VITE_API_URL` | `https://ban-teemo-api.onrender.com` | Production |
| `VITE_API_URL` | `http://localhost:8000` | Preview |
| `NODE_VERSION` | `20` | All |

**Important**: `VITE_` prefix is required for Vite to expose variables to the frontend.

### 4. Deploy

Click **Save and Deploy**. Cloudflare will:
1. Clone the repository
2. Run the build command
3. Deploy to global CDN

## Build Command Details

The build command performs these steps:

```bash
cd frontend        # Navigate to frontend directory
npm install         # Install dependencies
npm run build       # Run: tsc -b && vite build
```

Output is placed in `frontend/dist/`.

## Custom Domain (Optional)

1. Go to **Pages** > **Your project** > **Custom domains**
2. Click **Set up a custom domain**
3. Enter your domain (e.g., `draft.yourdomain.com`)
4. Add the CNAME record to your DNS

```
Type: CNAME
Name: draft (or subdomain)
Target: ban-teemo.pages.dev
```

## Preview Deployments

Cloudflare automatically creates preview deployments for:
- Pull requests
- Non-production branches

Preview URLs follow the pattern:
```
https://<commit-hash>.ban-teemo.pages.dev
```

## Redirects & Headers (Optional)

Create `frontend/public/_redirects` for SPA routing:

```
/*    /index.html   200
```

Create `frontend/public/_headers` for security headers:

```
/*
  X-Frame-Options: DENY
  X-Content-Type-Options: nosniff
  Referrer-Policy: strict-origin-when-cross-origin
```

## Troubleshooting

### Build fails with "command not found: npm"

Ensure `NODE_VERSION` environment variable is set to `18` or `20`.

### API calls fail in production

1. Verify `VITE_API_URL` is set correctly
2. Check browser console for CORS errors
3. Confirm backend `CORS_ORIGINS` includes your Pages URL

### Old content showing after deploy

Cloudflare caches aggressively. Try:
1. Purge cache: **Caching** > **Configuration** > **Purge Everything**
2. Or wait a few minutes for cache to update

### Preview deployment can't reach backend

Preview deployments use the `Preview` environment variables.
Set `VITE_API_URL` for the Preview environment as well.

## Deployment Triggers

| Event | Action |
|-------|--------|
| Push to `main` | Production deployment |
| Push to other branches | Preview deployment |
| Pull request opened | Preview deployment |
| Pull request updated | New preview deployment |

## Analytics (Free)

Enable Web Analytics in **Pages** > **Your project** > **Analytics** for:
- Page views
- Visitor counts
- Core Web Vitals
- Geographic distribution
