# Trend Scout Enterprise

AI-powered trend scouting automation platform for enterprise business teams.

## What Is This Project?

Trend Scout Enterprise helps business teams discover, evaluate, and communicate emerging technology and market trends without manual research overhead. The platform automates the entire workflow from data collection to final report:

1. **Connect data sources** — add RSS feeds, arXiv queries, or web search terms to monitor.
2. **Run AI-powered scans** — the system fetches fresh articles, scores them against configurable criteria (relevance, business impact, maturity, feasibility, etc.), and surfaces high-signal items.
3. **Explore signals** — review scored articles with AI-generated summaries and reasoning.
4. **Track trends** — visualize historical scores per category or topic, and trace every data point back to the original source and LLM evidence.
5. **Generate reports** — export findings as PDF, PowerPoint, or HTML card reports for sharing with stakeholders.
6. **Embed in SharePoint** — use the included SPFx web part to display read-only trend dashboards inside SharePoint pages, secured with embed tokens.
7. **Automate on a schedule** — configure recurring scans and receive notifications via email or Microsoft Teams when new signals appear.

## Who Is It For?

- **Strategy and innovation teams** tracking emerging technology
- **Business analysts** preparing market intelligence reports
- **Research teams** that need reproducible, auditable scoring workflows
- **Enterprises** that want to self-host trend scouting with workspace isolation and API-key or SSO access

## Project Wrap-up

For a complete summary of the delivered MVP, architecture decisions, verification results, and P1 roadmap, see:

- [`docs/project-wrap-up.md`](docs/project-wrap-up.md)
- [`docs/verification-report.md`](docs/verification-report.md)
- [`docs/postgresql-migration-assessment.md`](docs/postgresql-migration-assessment.md)

## Quick Start (Local Development)

The backend refuses to start outside testing without a real `SECRET_KEY`, and encryption helpers require `ENCRYPTION_SALT`. Set both before running:

```bash
cd backend
pip install -e ".[dev]"

# Required outside testing (generate your own random values):
export SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"
export ENCRYPTION_SALT="$(python -c 'import secrets, base64; print(base64.urlsafe_b64encode(secrets.token_bytes(16)).decode())')"

python -m pytest tests/ -v   # tests set TESTING=1 and their own keys via conftest
python -m uvicorn trend_scout_enterprise.main:app --host 0.0.0.0 --port 8000
```

Then, in a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 and log in with the default API key configured in your backend environment.

## Deployment with Docker Compose

A pre-built image is produced by GitHub Actions and pushed to GitHub Container Registry (ghcr.io).

```bash
cd deployment
# Pull pre-built image and start
GITHUB_REPOSITORY_OWNER=your-org docker compose up -d

# Or build locally
BACKEND_IMAGE= docker compose up -d --build
```

The compose stack starts Redis, the backend API, a Celery worker, and a Celery beat scheduler.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| DATABASE_URL | sqlite:///data/trend_scout.db | SQLite database path (PostgreSQL also supported) |
| REDIS_URL | redis://redis:6379/0 | Redis connection |
| CELERY_BROKER_URL | redis://redis:6379/0 | Celery broker |
| CELERY_RESULT_BACKEND | redis://redis:6379/0 | Celery result backend |
| SECRET_KEY | — (**required**) | Encryption/signing key. Startup fails outside testing if unset or left at the default placeholder |
| ENCRYPTION_SALT | — (**required**) | Base64-encoded salt for key derivation (Fernet). Required outside testing |
| TESTING | false | Test mode: allows default SECRET_KEY and a fixed encryption salt. Never set in production |
| CORS_ORIGINS | http://localhost:5173 | Comma-separated CORS allowlist |
| SSRF_ALLOW_PRIVATE | false | Allow scanners to fetch private/loopback IPs (SSRF guard bypass — dev only) |
| REVIEW_MODE_ENABLED | false | Enable human-in-the-loop signal review workflow |
| HUMAN_REVIEW_THRESHOLD | 0.4 | Lower bound of the human-review score band (reserved; current routing uses AUTO_APPROVE_THRESHOLD only) |
| AUTO_APPROVE_THRESHOLD | 0.7 | When review mode is on, scores at/above this are auto-approved; lower scores go to pending_review |
| LLM_DEFAULT_BASE_URL | https://api.openai.com/v1 | OpenAI-compatible LLM endpoint |
| LLM_DEFAULT_MODEL | gpt-4o-mini | Default model |
| OUTPUT_DIR | /data/outputs | Report output directory |

## CI/CD

GitHub Actions workflows:

- `.github/workflows/docker.yml` — backend tests + Docker build and push
- `.github/workflows/frontend.yml` — frontend tests + production build
- `.github/workflows/spfx.yml` — SPFx web part build and `.sppkg` artifact

Images are pushed to `ghcr.io/<owner>/trend-scout-enterprise-backend`.

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
npm run test
npm run build
npm run dev
```

## Local Smoke Test

```bash
cd backend
python -m uvicorn trend_scout_enterprise.main:app --host 0.0.0.0 --port 8000
python scripts/smoke_test.py
```

The smoke test validates the API surface, workspace routing, and trends aggregation. Report creation is skipped when Redis/Celery is not available.

## License

MIT
