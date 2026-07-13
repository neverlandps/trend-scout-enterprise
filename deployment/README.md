# Trend Scout Enterprise — Deployment Guide

## Standalone Docker

Build and run the backend service:

```bash
cd /home/ps/trend-scout-enterprise
docker build -f deployment/Dockerfile -t trend-scout-backend .
docker run -p 8000:8000 \
  -e SECRET_KEY=your-secret-key \
  -e API_KEY=your-api-key \
  -e DATABASE_URL=sqlite:///data/trend_scout.db \
  trend-scout-backend
```

## Docker Compose (Recommended)

Run the full stack (backend + Redis + Celery worker):

```bash
cd /home/ps/trend-scout-enterprise
docker-compose -f deployment/docker-compose.yml up --build
```

Services:
- **Backend**: http://localhost:8000
- **Redis**: localhost:6379
- **Health check**: GET http://localhost:8000/api/v1/health

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite:///./trend_scout.db` | SQLite database path |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis broker URL |
| `CELERY_BROKER_URL` | `redis://localhost:6379/0` | Celery broker |
| `CELERY_RESULT_BACKEND` | `redis://localhost:6379/0` | Celery result backend |
| `SECRET_KEY` | `change-me-in-production` | FastAPI secret key |
| `API_KEY` | `change-me-in-production` | Default admin API key |
| `CORS_ORIGINS` | `http://localhost:5173` | Comma-separated allowed origins |
| `ENCRYPTION_SALT` | (derived from SECRET_KEY) | Salt for Fernet encryption |

## SPFx Web Part (Future)

The `frontend/spfx/` directory contains a scaffolded SharePoint Framework web part for future SharePoint Online integration. It is not built or deployed in P0.

## Frontend Development

```bash
cd frontend
npm install
npm run dev
```

The Vite dev server proxies `/api` requests to `http://localhost:8000`.
