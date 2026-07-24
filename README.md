# Trend Scout Enterprise

AI-powered, human-in-the-loop trend scouting platform for enterprise business teams. **v1.0**

Trend Scout Enterprise automates the full trend-intelligence pipeline: it collects signals from five kinds of data sources, scores them with a configurable multi-dimension LLM rubric, routes uncertain items to a human review queue, aggregates daily/weekly/monthly trends with full evidence traceability, and delivers PDF/PPTX/Card reports — self-hosted, workspace-isolated, and hardened for enterprise deployment.

## Features

**Data Collection**
- Five source scanners: RSS, arXiv, Web Search, SharePoint, Custom API
- SSRF protection on all outbound fetches (scheme allowlist, DNS resolution, private/loopback IP blocking)
- Scheduled recurring scans (Celery beat) with email / Microsoft Teams notifications

**AI Scoring & Triage**
- 5-dimension configurable LLM scoring profiles (relevance, business impact, maturity, feasibility, and more), per workspace
- Confidence-threshold routing: auto-approve high scores, queue the rest for human review
- Anomaly detection on scores (Z-score + IQR fence) to catch LLM scoring drift
- LLM fallback provider chain with per-call health logging

**Human-in-the-Loop Review**
- Signal review state machine: `auto` / `pending_review` / `approved` / `rejected` / `flagged`
- Review queue with filters, single and bulk review actions, score override
- Reviewer assignment per workspace + category (`assigned_to_me` queue)
- Feedback loop (`score_too_low` / `score_too_high` / `irrelevant` / `misclassified`) persisted for model iteration
- Full audit trail of every review action

**Trend Analysis**
- Daily / weekly / monthly aggregation per topic, with optional `only_approved` filtering
- Evidence traceability: every trend point links back to the original `RawItem`, source, and LLM reasoning
- `TrendAnalystAgent` deep-dives top evidence per bucket and writes themes, connections, and an executive summary

**Vector Semantic Search**
- Signal embeddings generated during scans (OpenAI-compatible `/embeddings`, fallback chain aware)
- Similar-signal discovery and semantic search APIs, workspace-scoped
- Dialect-agnostic storage (JSON vectors + Python cosine); pgvector evolution path documented

**Reports**
- PDF, PowerPoint, and HTML card reports with LLM-generated summaries
- Report generation as Celery tasks; direct SharePoint upload supported

**Collaboration**
- Team / Workspace isolation; every entity is workspace-scoped
- Roles: admin / analyst / viewer (API-key based)
- Time-limited, read-only Embed Tokens for SharePoint embedding

**Enterprise Security**
- bcrypt API key hashing (transparent migration from legacy SHA-256)
- JWT sessions signed with RS256 + `kid`-based key rotation (HS256 fallback window)
- Fernet encryption at rest for source configs and LLM provider keys
- Audit logs, per-endpoint rate limiting, CORS allowlist, security response headers (CSP, X-Frame-Options, HSTS opt-in)
- Fail-fast startup on missing `SECRET_KEY` / `ENCRYPTION_SALT`

**Platform**
- FastAPI + SQLAlchemy + Celery + LangGraph scan workflow + internal event bus
- Dual database dialects: SQLite for development, PostgreSQL for production, managed by Alembic migrations
- React + TypeScript + Fluent UI frontend (Signals / Sources / Scans / Trends / Reports / Settings / Team)
- SPFx web part for read-only SharePoint dashboards (`.sppkg` buildable in CI)
- 221 backend tests; 4 green CI workflows (Backend / Frontend / SPFx / Security Scans)

## Architecture

```
┌───────────────────────────────────────────────────────────────────────────┐
│                         SharePoint Online                                  │
│              SPFx Web Part (read-only, X-Embed-Token)                      │
└──────────────────────────────────┬────────────────────────────────────────┘
                                   │ HTTPS
┌──────────────────────────────────▼────────────────────────────────────────┐
│                React Frontend (Vite + Fluent UI)                           │
│   Signals · Sources · Scans · Trends · Reports · Settings · Team           │
└──────────────────────────────────┬────────────────────────────────────────┘
                                   │ X-API-Key / X-Workspace-ID
┌──────────────────────────────────▼────────────────────────────────────────┐
│                     FastAPI Backend (Python 3.11)                          │
│  Middleware: security headers · rate limit · CORS · audit                  │
│                                                                            │
│  API routers ──► Services (scoring, trends, reports, embedding, LLM)       │
│       │                │                                                   │
│       │                ▼                                                   │
│       │         LangGraph scan workflow                                    │
│       │   load_context → collect → persist → score → embed → finalize      │
│       │                │                                    → notify       │
│       │                ▼                                                   │
│       │         Scanners (RSS / arXiv / Web / SharePoint / Custom API)     │
│       │                │                                                   │
│       │                ▼                                                   │
│       │         Event bus: scan.completed · signals.scored ·               │
│       │                  trend.analyzed                                    │
│       │                                                                    │
│  Celery worker + beat (Redis broker) ── scheduled scans, report tasks      │
│                                                                            │
│  ┌──────────────────────────┐   ┌──────────────────┐                      │
│  │ PostgreSQL / SQLite      │   │ Redis (broker)   │                      │
│  │ (SQLAlchemy + Alembic)   │   └──────────────────┘                      │
│  └──────────────────────────┘                                             │
└───────────────────────────────────────────────────────────────────────────┘
```

See [`docs/architecture.md`](docs/architecture.md) for the full architecture and feature documentation.

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

The compose stack starts PostgreSQL, Redis, the backend API, a Celery worker, and a Celery beat scheduler:

```bash
# Pull pre-built image (published by CI to ghcr.io) and start
GITHUB_REPOSITORY_OWNER=your-org docker compose up -d

# Or build locally
BACKEND_IMAGE= docker compose up -d --build
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite:///./trend_scout.db` | Database URL. SQLite for dev; use `postgresql+psycopg2://…` in production |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection |
| `CELERY_BROKER_URL` | `redis://localhost:6379/0` | Celery broker |
| `CELERY_RESULT_BACKEND` | `redis://localhost:6379/0` | Celery result backend |
| `SECRET_KEY` | — (**required**) | Encryption/signing key. Startup fails outside testing if unset or left at the default placeholder |
| `ENCRYPTION_SALT` | — (**required**) | Base64-encoded salt for Fernet key derivation. Required outside testing |
| `TESTING` | `false` | Test mode: allows default `SECRET_KEY` and a fixed encryption salt. Never set in production |
| `CORS_ORIGINS` | `http://localhost:5173` | Comma-separated CORS allowlist |
| `SSRF_ALLOW_PRIVATE` | `false` | Allow scanners to fetch private/loopback IPs (SSRF guard bypass — dev only) |
| `REVIEW_MODE_ENABLED` | `false` | Enable the human-in-the-loop signal review workflow |
| `HUMAN_REVIEW_THRESHOLD` | `0.4` | Lower bound of the review band; scores in `[HUMAN_REVIEW_THRESHOLD, AUTO_APPROVE_THRESHOLD)` go to `pending_review` |
| `AUTO_APPROVE_THRESHOLD` | `0.7` | With review mode on, scores at/above this are auto-approved |
| `ANOMALY_DETECTION_ENABLED` | `false` | Enable Z-score / IQR anomaly detection on LLM scores (only while review mode is on) |
| `ANOMALY_ZSCORE_THRESHOLD` | `2.5` | Absolute Z-score above which a score is flagged as anomalous |
| `VECTOR_SEARCH_ENABLED` | `false` | Generate embeddings during scans and enable similarity / semantic-search APIs |
| `EMBEDDING_MODEL` | `text-embedding-3-small` | Model name sent to the OpenAI-compatible `/embeddings` endpoint |
| `TREND_ANALYST_ENABLED` | `false` | Run `TrendAnalystAgent` per trend bucket during aggregation and fill point summaries |
| `JWT_ALGORITHM` | `HS256` | Session JWT signing algorithm (RS256 used when a private key is configured) |
| `JWT_EXPIRATION_MINUTES` | `60` | Session JWT lifetime |
| `JWT_PRIVATE_KEY_PEM` | — | RSA private key PEM for RS256 signing; empty = HS256 fallback with `SECRET_KEY` |
| `JWT_PUBLIC_KEYS_PEM` | — | JSON dict of `kid` → public key PEM for RS256 verification (supports rotation) |
| `JWT_KEY_ID` | `default` | `kid` header written into newly signed tokens |
| `HSTS_ENABLED` | `false` | Emit `Strict-Transport-Security` (enable behind HTTPS) |
| `FRAME_OPTIONS` | `DENY` | `X-Frame-Options` value; set `SAMEORIGIN` if a page must be framed by the same origin |
| `LLM_DEFAULT_BASE_URL` | `https://api.openai.com/v1` | OpenAI-compatible LLM endpoint |
| `LLM_DEFAULT_MODEL` | `gpt-4o-mini` | Default model |
| `ENTRA_DUMMY_MODE` | `false` | Stub Entra ID auth for local development |
| `ENTRA_TENANT_ID` / `ENTRA_CLIENT_ID` / `ENTRA_CLIENT_SECRET` / `ENTRA_REDIRECT_URI` | — | Microsoft Entra ID SSO configuration |
| `OUTPUT_DIR` | `./outputs` | Report output directory |
| `APP_NAME` | `Trend Scout Enterprise` | Application display name |
| `DEBUG` | `false` | Debug mode |

## Documentation

| Document | Contents |
|----------|----------|
| [`docs/architecture.md`](docs/architecture.md) | System architecture, backend layers, key flows, data model, deployment, security |
| [`docs/scan-workflow-graph.md`](docs/scan-workflow-graph.md) | LangGraph scan workflow nodes, state, and routing |
| [`docs/signal-review-workflow.md`](docs/signal-review-workflow.md) | Human-in-the-loop review state machine, thresholds, APIs |
| [`docs/vector-search.md`](docs/vector-search.md) | Embeddings, similar signals, semantic search, pgvector path |
| [`docs/multi-agent-collaboration.md`](docs/multi-agent-collaboration.md) | Agent roles, `TrendAnalystAgent`, events, CrewAI evolution path |
| [`docs/security-hardening.md`](docs/security-hardening.md) | bcrypt, SSRF, rate limiting, headers, JWT RS256 rotation |
| [`docs/project-wrap-up.md`](docs/project-wrap-up.md) | MVP delivery summary, decisions, verification results |
| [`docs/verification-report.md`](docs/verification-report.md) | Test and build verification report |
| [`docs/postgresql-migration-assessment.md`](docs/postgresql-migration-assessment.md) | SQLite → PostgreSQL migration analysis |

## CI/CD

GitHub Actions workflows, all green on main:

- `.github/workflows/docker.yml` — backend tests (221) + smoke test + Docker build and push
- `.github/workflows/frontend.yml` — frontend tests + production build
- `.github/workflows/spfx.yml` — SPFx web part build and `.sppkg` artifact
- `.github/workflows/security.yml` — Bandit, pip-audit, Trivy filesystem scan, Syft SBOM

The backend image is a multi-stage build running as a non-root user, pushed to `ghcr.io/<owner>/trend-scout-enterprise-backend`.

## SharePoint Framework (SPFx) Web Part

An SPFx web part under `spfx-webpart/` embeds read-only trend dashboards into SharePoint pages, authenticated with embed tokens:

```bash
cd spfx-webpart
npm install
npm run build
npm run package
# .sppkg is produced at sharepoint/solution/trend-scout-spfx-webpart.sppkg
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
