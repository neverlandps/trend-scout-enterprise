# Trend Scout Enterprise

AI-powered trend scouting automation platform for enterprise business teams.

## Project Wrap-up

For a complete summary of the delivered MVP, architecture decisions, verification results, and P1 roadmap, see:

- [`docs/project-wrap-up.md`](docs/project-wrap-up.md)
- [`docs/verification-report.md`](docs/verification-report.md)
- [`docs/postgresql-migration-assessment.md`](docs/postgresql-migration-assessment.md)

## Quick Start (Local Development)

```bash
cd backend
pip install -e .
python -m pytest tests/ -v
python -m uvicorn trend_scout_enterprise.main:app --host 0.0.0.0 --port 8000
```

## Deployment with Docker Compose

A pre-built image is produced by GitHub Actions and pushed to GitHub Container Registry (ghcr.io).

```bash
cd deployment
# Pull pre-built image and start
GITHUB_REPOSITORY_OWNER=your-org docker compose up -d

# Or build locally
BACKEND_IMAGE= docker compose up -d --build
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| DATABASE_URL | sqlite:///data/trend_scout.db | SQLite database path |
| REDIS_URL | redis://redis:6379/0 | Redis connection |
| CELERY_BROKER_URL | redis://redis:6379/0 | Celery broker |
| CELERY_RESULT_BACKEND | redis://redis:6379/0 | Celery result backend |
| SECRET_KEY | change-me-in-production | Encryption key |
| LLM_DEFAULT_BASE_URL | https://api.openai.com/v1 | OpenAI-compatible LLM endpoint |
| LLM_DEFAULT_MODEL | gpt-4o-mini | Default model |
| OUTPUT_DIR | /data/outputs | Report output directory |

## CI/CD

GitHub Actions workflow at `.github/workflows/docker.yml`:
- Runs backend tests on every push / PR
- Builds and pushes backend image to `ghcr.io/<owner>/trend-scout-enterprise-backend`


## SharePoint Framework (SPFx) Web Part

An SPFx web part is included under `spfx-webpart/` to embed the Trend Scout dashboard directly into SharePoint pages.

```bash
cd spfx-webpart
npm install
npm run build
npm run package
```

The packaged app is produced at `spfx-webpart/sharepoint/solution/trend-scout-spfx-webpart.sppkg`.

## Frontend

```bash
cd frontend
npm install
npm run dev
```
