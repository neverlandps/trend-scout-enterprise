# Architecture — Trend Scout Enterprise v1.0

This document describes the v1.0 system architecture: backend layering, key flows (scan, scoring, review, trends, reports), the data model, the dual-dialect database strategy, frontend and SPFx structure, deployment topology, and the security architecture.

## 1. System Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            SharePoint Online                                 │
│   SPFx Web Part  ── read-only dashboard (Signals/Sources/Trends/Reports)     │
│   Auth: X-Embed-Token (time-limited, read-only)                              │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    │ HTTPS
┌───────────────────────────────────▼─────────────────────────────────────────┐
│                 React Frontend (Vite + TypeScript + Fluent UI)               │
│   Signals · Sources · Scans · Trends · Reports · Settings · Team · Login     │
│   Auth: X-API-Key + X-Workspace-ID, or session JWT                           │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    │
┌───────────────────────────────────▼─────────────────────────────────────────┐
│                      FastAPI Backend (Python 3.11)                           │
│                                                                              │
│  Middleware stack: SecurityHeaders → SlowAPI rate limit → CORS               │
│                                                                              │
│  api/ (routers)                                                              │
│    health · auth · workspace · sources · scans · signals · reports           │
│    settings · sharepoint · schedules · trends · embed-tokens · llm-fallback  │
│        │                                                                     │
│        ▼                                                                     │
│  services/ ── business logic                                                 │
│    scoring · analysis · anomaly · embedding · trends · reports (pdf/pptx/    │
│    card) · llm (fallback chain) · notification · schedule · workspace ·      │
│    sharepoint · embed_token · source · auth                                  │
│        │                                                                     │
│        ▼                                                                     │
│  workflows/scan_graph.py ── LangGraph StateGraph                             │
│    load_context → collect → persist → score → embed → finalize → notify      │
│        │ calls scanners/ (RSS · arXiv · Web Search · SharePoint · Custom API)│
│        │ calls agents/ (TrendAnalystAgent during trend aggregation)          │
│        │                                                                     │
│  events/bus.py ── in-process pub/sub                                         │
│    scan.completed · scan.failed · signals.scored · trend.analyzed            │
│        │                                                                     │
│  models/ ── SQLAlchemy ORM (workspace-scoped)                                │
│        │                                                                     │
│  ┌─────▼───────────────┐   ┌─────────────────────────────┐                  │
│  │ PostgreSQL / SQLite │   │ Redis (Celery broker/result)│                  │
│  │ SQLAlchemy + Alembic│   └──────────────▲──────────────┘                  │
│  └─────────────────────┘                  │                                 │
│  workers/ ── celery_app · scan_worker (thin shell over the graph) ·          │
│              report_worker · beat_scheduler                                 │
│  core/ ── config · database · security (bcrypt/JWT) · encryption (Fernet) ·  │
│           rate_limit · security_headers · audit · dependencies · dummy_auth │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 2. Backend Layers

Code lives under `backend/src/trend_scout_enterprise/`.

| Layer | Path | Responsibility |
|-------|------|----------------|
| API | `api/` | Thin FastAPI routers. Auth dependency injection (`X-API-Key` + `X-Workspace-ID`, session JWT, or embed token for read-only), request validation via `schemas/`, delegation to services. No business logic. |
| Services | `services/` | All business logic: LLM scoring and review routing (`scoring_service`), batch analysis (`analysis_service`), anomaly detection (`anomaly_service`), embeddings (`embedding_service`), trend aggregation (`trends_service`), report generation (`report_service` / `ppt_report_service` / `card_report_service`), LLM provider fallback chain (`llm_service`), notifications, schedules, workspace/team management, SharePoint, embed tokens. |
| Models | `models/` | SQLAlchemy ORM entities, one module per aggregate (`source`, `raw_item`, `signal_review`, `trends`, `team`, `scoring`, `llm_provider`, `llm_fallback`, `embed_token`, `audit_log`, `signal_embedding`, `review_assignment`, `report`, `schedule`, `sharepoint`, `auth`, `api_key`). Nearly every entity carries `workspace_id` for tenant isolation. |
| Scanners | `scanners/` | Pluggable source fetchers behind a common `base` interface: `rss_scanner`, `arxiv_scanner`, `web_search_scanner`, `sharepoint_scanner`, `custom_api_scanner`. All outbound URLs pass `url_validator` (SSRF guard) before fetching. |
| Workflows | `workflows/scan_graph.py` | LangGraph `StateGraph` orchestrating a single scan run end to end. See §3.1. |
| Agents | `agents/` | Framework-agnostic agent layer. `base.py` defines `AgentRole` constants and `BaseAgent` (structlog `agent_started`/`agent_completed` instrumentation); `trend_analyst.py` implements `TrendAnalystAgent`. See `docs/multi-agent-collaboration.md`. |
| Events | `events/bus.py` | In-process pub/sub event bus (`subscribe`/`publish`). Decouples side effects (notifications, analytics) from the core pipeline. `register_default_subscribers()` is wired in the app lifespan. Events: `scan.completed`, `scan.failed`, `signals.scored`, `trend.analyzed`. |
| Workers | `workers/` | Celery integration. `scan_worker.run_scan` is a thin shell over `run_scan_workflow` (keeps task signature, `max_retries=3`, failure handling). `report_worker` renders reports asynchronously; `beat_scheduler` enqueues due scheduled scans. |
| Core | `core/` | Cross-cutting infrastructure: `config` (pydantic-settings env), `database` (engine/session, dual dialect), `security` (bcrypt API keys, default key seeding), `dummy_auth` (JWT issue/verify, RS256 + rotation), `encryption` (Fernet field encryption), `rate_limit` (slowapi limiter), `security_headers` (CSP/XFO/HSTS middleware), `audit` (audit log writer), `dependencies` (auth/workspace injection). |
| Schemas | `schemas/` | Pydantic request/response models for the API layer. |
| CLI | `cli/` | Maintenance commands: `migrate_sqlite_to_postgres.py` (data copy preserving UUIDs), `backfill_embeddings.py` (embed existing signals). |

## 3. Key Flows

### 3.1 Scan Workflow (LangGraph)

A scan run is orchestrated by `workflows/scan_graph.py` as a LangGraph `StateGraph` over a `ScanState` TypedDict. Each node is a pure function that opens/closes its own SQLAlchemy session:

```
START → load_context ──(errors)──► finalize → END                    # fail path
              │
              └──► collect ──(no signals)──► finalize → END          # empty run
                        │
                        └──► persist → score → embed → finalize
                                                            │
                                                (status ≠ failed) └──► notify → END
```

- **load_context** — load `ScanRun` + `Source`, mark `running`; missing records route to `finalize` as failed (no retry).
- **collect** — decrypt source config, resolve the scanner, `asyncio.run(scanner.scan())`. Scanner exceptions propagate to Celery, which marks the run failed and retries (`max_retries=3`).
- **persist** — dedupe by URL, insert new `RawItem` rows.
- **score** — batch LLM scoring via `analysis_service.analyze_signals_batch`; review routing happens inside `scoring_service._apply_review_routing`. Skipped when no LLM is configured. Publishes `signals.scored`.
- **embed** — when `VECTOR_SEARCH_ENABLED=true`, generate embeddings for new items (best-effort; failures logged, never block the scan).
- **finalize** — update source health and scan-run statistics/status (`completed` / `completed_with_errors` / `failed`); publishes `scan.completed` / `scan.failed`.
- **notify** — `NotificationService` (email / Teams) for non-failed runs, best-effort.

Scheduling, queueing, and retries stay with Celery; the graph owns only the intra-scan steps. The first version deliberately does not suspend inside the graph — human review is a database state machine (§3.3), keeping the Celery fire-and-forget model intact. Details: `docs/scan-workflow-graph.md`.

### 3.2 Scoring and Routing

1. `analysis_service.analyze_signals_batch` iterates new items and calls `scoring_service.score_item_with_llm`.
2. The active `ScoringProfile` (5 weighted dimensions, per workspace) is rendered into a prompt; `LlmService.chat_completion` calls the default `LlmProvider`, falling back through `LlmFallbackProvider` entries by priority. Every call is recorded in `llm_health_logs`. Responses are parsed as JSON with fence-stripping tolerance.
3. Routing (only when `REVIEW_MODE_ENABLED=true`):
   - `overall_score >= AUTO_APPROVE_THRESHOLD` → `review_status = approved`
   - otherwise → `pending_review`, and `assigned_reviewer_id` is filled from `ReviewAssignment(workspace_id, category)`
4. Anomaly detection (only when `ANOMALY_DETECTION_ENABLED=true`, which itself requires review mode): `anomaly_service.detect_score_anomaly` runs a Z-score check (`|z| > ANOMALY_ZSCORE_THRESHOLD`, default 2.5σ) and an IQR fence check (`[Q1 − 1.5·IQR, Q3 + 1.5·IQR]`) against the item's historical category scores. Anomalies feed the review decision and are also used for source-health checks.

### 3.3 Human Review State Machine

Each `RawItem` carries `review_status`:

```
                 score ≥ AUTO_APPROVE_THRESHOLD
        ┌─────────────────────────────────────────┐
        ▼                                         │
   ┌─────────┐   review mode off    ┌──────────┐  │   ┌────────┐ approve/override
   │  auto   │◄─────────────────────│ (scoring)│──┴──►│approved│◄────────────────┐
   └─────────┘                      └──────────┘      └────────┘                 │
        ▲                               │ score < threshold                       │
        │                               ▼                                         │
        │                        ┌───────────────┐  approve    ┌──────────┐       │
        │                        │pending_review │────────────►│ (above)  │───────┘
        │                        └──────┬────────┘             └──────────┘
        │                               │ reject            ┌──────────┐
        │                               ├──────────────────►│ rejected │
        │                               │ flag              └──────────┘
        │                               ▼
        │                          ┌──────────┐
        │                          │ flagged  │
        │                          └──────────┘
```

- Actions: `approve` / `reject` / `flag` / `override` (override requires `human_score` 0–1), single (`POST /signals/{id}/review`) or bulk (`POST /signals/bulk-review`).
- Every action writes a `signal_reviews` row (with optional `feedback_type`: `score_too_low` / `score_too_high` / `irrelevant` / `misclassified`) and an `audit_logs` entry (`signal.review` / `signal.bulk_review` / `signal.feedback`).
- Reviewer assignment: `review_assignments` maps `(workspace_id, category) → reviewer`; the queue supports `assigned_to_me=true`.
- Embed tokens are read-only and cannot call review endpoints.
- Details: `docs/signal-review-workflow.md`.

### 3.4 Trend Aggregation and Evidence Chain

`POST /trends/aggregate` (via `trends_service.aggregate_trends_for_workspace`):

1. Bucket signals by day / week / month and category for the workspace.
2. Optionally filter to approved signals only (`only_approved=true` keeps `approved` + `auto`, the latter covering pre-review-mode history).
3. For each bucket, compute average score, signal count, and top categories; write a `TopicTrendPoint`.
4. Link the top evidence items to the point via `TrendEvidence` rows — each evidence row references the trend point, the original `RawItem`, and its `Source`, so every chart data point can be traced back to the original article and its LLM reasoning.
5. When `TREND_ANALYST_ENABLED=true` and an LLM is available, run `TrendAnalystAgent` over the bucket's top evidence: it returns themes, connections, recommended actions, and an executive summary. The summary fills `TopicTrendPoint.summary`; the full insight is stored on each item's `metadata_json["analyst_insight"]`. Best-effort — failures are logged and never block aggregation. Publishes `trend.analyzed`.

### 3.5 Report Generation

- `POST /reports` with `report_type ∈ {pdf, pptx, card}` enqueues a Celery task on `report_worker`.
- The worker gathers scored signals / trend points for the workspace, asks the LLM for a narrative summary (fallback chain applies), and dispatches to `report_service` (PDF), `ppt_report_service` (PPTX), or `card_report_service` (HTML card).
- Artifacts are written to `OUTPUT_DIR` and served under `/outputs/`; HTML responses receive a relaxed CSP (`default-src 'self' 'unsafe-inline'`) so they still render. Reports can also be uploaded to SharePoint (`sharepoint_service`).

## 4. Data Model

Workspace is the primary isolation boundary: `teams` → `workspaces` → everything else. `api_keys` are the actor identity (with team membership and role).

```
teams ──────────────┐
   │1               │
   │N               │
team_memberships ───┼──► api_keys ◄──┐
   │                │       │        │
   │N               │       │        │ created_by / owner / reviewer
workspaces ◄────────┘       │        │
   │1                       │        │
   │N (workspace_id on nearly every table)
   │
   ├──► sources ──1:N──► scan_runs
   │       │1
   │       │N
   │       └──► raw_items ──1:N──► signal_reviews (reviewer ─► api_keys)
   │               │  └──1:1──► signal_embeddings
   │               │  └──N:1──► review_assignments (reviewer ─► api_keys)
   │               │         (unique on workspace_id + category)
   │               │N
   ├──► topic_trend_points ──1:N──► trend_evidence ──N:1──► raw_items
   │                                                    └──► sources
   ├──► scoring_profiles (dimensions JSON, is_default)
   ├──► llm_providers ──1:N──► llm_fallback_providers
   │       └──1:N──► llm_health_logs
   ├──► reports (owner ─► api_keys)
   ├──► scan_schedules (source unique), notification_channels ──► notification_logs
   ├──► embed_tokens (workspace, created_by ─► api_keys)
   ├──► sharepoint_connections ──► sharepoint_upload_records
   ├──► audit_logs (actor, action, workspace, resource, detail)
   └──► microsoft_auth_configs, user_sessions
```

Main tables: `teams`, `team_memberships`, `workspaces`, `api_keys`, `sources`, `scan_runs`, `raw_items`, `signal_reviews`, `review_assignments`, `signal_embeddings`, `scoring_profiles`, `llm_providers`, `llm_fallback_providers`, `llm_health_logs`, `topic_trend_points`, `trend_evidence`, `reports`, `scan_schedules`, `notification_channels`, `notification_logs`, `embed_tokens`, `sharepoint_connections`, `sharepoint_upload_records`, `audit_logs`, `microsoft_auth_configs`, `user_sessions`.

Cascade rules: `signal_reviews` and `signal_embeddings` use `ondelete="CASCADE"` on `raw_items.id`.

## 5. Database Strategy

### Dual Dialects

- **Development / tests**: SQLite (`sqlite:///./trend_scout.db`) — zero external dependencies.
- **Production**: PostgreSQL via `DATABASE_URL=postgresql+psycopg2://…` (the docker-compose default, with a healthcheck-gated `postgres:16` service).

Models use dialect-agnostic SQLAlchemy types (`String`, `Text`, `JSON`, `Float`, `DateTime`). Two deliberate dialect-neutral choices:

- **Vector storage**: embeddings are stored as JSON float lists in `signal_embeddings` with Python-side cosine similarity — works on both dialects. The pgvector evolution path (ANN index, `ORDER BY embedding <=> :query`) is documented in `docs/vector-search.md` and marked in code comments.
- **Primary keys**: `uuid.uuid4().hex` 32-char strings, portable across dialects.

The original SQLite → PostgreSQL assessment lives in `docs/postgresql-migration-assessment.md`; `cli/migrate_sqlite_to_postgres.py` implements the data copy preserving IDs.

### Alembic Migration Chain

`backend/migrations/versions/`:

| Revision | Purpose |
|----------|---------|
| `001_initial` | Baseline snapshot of the full MVP schema |
| `002_bcrypt_hash_columns` | Wider hash columns for bcrypt API keys (dual-mode SHA-256 → bcrypt migration) |
| `003_signal_review` | Review workflow: `raw_items.review_status` / `assigned_reviewer_id`, `signal_reviews`, `review_assignments` |
| `004_signal_review_feedback_type` | `signal_reviews.feedback_type` for the scoring feedback loop |
| `005_signal_review_fk_cascade` | `ON DELETE CASCADE` on `signal_reviews.raw_item_id` |
| `006_signal_embeddings` | `signal_embeddings` table (defensive: skips if the table already exists) |

App startup still calls `Base.metadata.create_all` for dev convenience; production deployments should run Alembic migrations.

## 6. Frontend Architecture

`frontend/` — React 18 + TypeScript + Vite + Fluent UI.

- **Pages** (`src/pages/`): `LoginPage`, `SignalsPage` (review queue, status filters, inline approve/reject/flag, bulk review, override & feedback forms), `SourcesPage`, `ScansPage`, `TrendsPage` (Recharts overlays, evidence drill-down), `ReportsPage` (format selector), `SettingsPage` (LLM providers, scoring profiles), `TeamPage` (members, roles).
- **State**: `WorkspaceContext` holds the active workspace; `WorkspaceSelector` switches it. Auth headers (`X-API-Key`, `X-Workspace-ID`) are attached by the API client in `src/services/`.
- **Performance**: pages are lazy-loaded; Vite `manualChunks` splits `recharts`, `@fluentui`, `react-router-dom`, and vendor code (largest chunk ≈456 kB, no 500 kB+ warnings).
- **Tests**: Vitest (`api.test.ts`, `smoke.test.ts`).

## 7. SPFx Architecture

`spfx-webpart/` — SharePoint Framework 1.20 web part (`src/webparts/trendScout/`).

- Renders read-only Signals / Sources / Trends / Reports views inside SharePoint pages (`components/*.tsx`), reusing the same REST API.
- Authenticates with an **embed token** (property-pane configuration, `ITrendScoutWebPartProps`) sent as `X-Embed-Token`; tokens are time-limited and read-only — write endpoints reject them.
- `npm run build && npm run package` produces `sharepoint/solution/trend-scout-spfx-webpart.sppkg`; the `spfx.yml` workflow builds the package in CI and uploads the `.sppkg` artifact.

## 8. Deployment Architecture

Root `docker-compose.yml` service topology:

```
            ┌──────────────┐
            │   postgres   │ postgres:16-alpine (healthcheck: pg_isready)
            └──────▲───────┘
                   │ DATABASE_URL (service_healthy)
   ┌───────────────┼────────────────┬────────────────┐
   │               │                │                │
┌──┴───────┐  ┌────┴─────┐  ┌───────┴──────┐  ┌──────┴──────┐
│ backend  │  │  worker  │  │     beat     │  │    redis    │
│ uvicorn  │  │ celery   │  │ celery beat  │  │ 7-alpine    │
│ :8000    │  │ worker   │  │ (schedules)  │  │ broker/     │
│ health:  │  │ concurr. │  │              │  │ result      │
│ /health  │  │    2     │  │              │  │ backend     │
└──────────┘  └──────────┘  └──────────────┘  └─────────────┘
```

- All three app containers share the same multi-stage image (`deployment/Dockerfile`, non-root `app` uid 1000) and the `app-data` volume (reports, SQLite fallback). `SECRET_KEY` and `ENCRYPTION_SALT` are mandatory (`:?` compose guards).
- The backend exposes `/api/v1/health` for the container healthcheck.
- A pre-built image is published by CI to `ghcr.io/<owner>/trend-scout-enterprise-backend`.

## 9. Security Architecture

### Authentication Flow

```
API client ──X-API-Key──► bcrypt verify (legacy SHA-256 auto-rehash) ─► api_keys
                         + X-Workspace-ID membership check

Browser SSO ──Entra ID──► auth_router ─► session JWT ─► RS256 sign (kid header)
                          (ENTRA_DUMMY_MODE for dev)    verify: kid → JWT_PUBLIC_KEYS_PEM
                                                        fallback: HS256 + SECRET_KEY

SharePoint SPFx ──X-Embed-Token──► embed_tokens (expiry, read-only scope)
```

- **API keys**: bcrypt via passlib; legacy unsalted SHA-256 hashes verify once and are transparently re-hashed.
- **JWT**: RS256 with `kid`-based rotation when `JWT_PRIVATE_KEY_PEM` is set (`scripts/generate_jwt_keys.py`); HS256 tokens remain verifiable during the migration window. Unknown kids / algorithms are rejected with a generic `Invalid JWT`.
- **Embed tokens**: time-limited, workspace-bound, read-only; created per workspace by an API-key holder.

### Encryption

- Field-level Fernet encryption (`core/encryption.py`) for source configs and LLM provider API keys; keys derived from `SECRET_KEY` + `ENCRYPTION_SALT`. Both are fail-fast required outside `TESTING=1`.

### Audit

- `core/audit.py` writes `audit_logs` rows (actor, action, workspace, resource, detail) for sensitive operations: signal review / bulk review / feedback, auth events, administrative changes. Always on.

### Rate Limiting

- Shared slowapi limiter (`core/rate_limit.py`) wired via `SlowAPIMiddleware`; sensitive endpoints (auth, scans, analyze) declare per-endpoint limits in code, throttled per client IP.

### Transport & Headers

- `SecurityHeadersMiddleware` on every response: `X-Content-Type-Options: nosniff`, `X-Frame-Options` (`FRAME_OPTIONS`, default `DENY`), `Referrer-Policy: strict-origin-when-cross-origin`, CSP (`default-src 'none'; frame-ancestors 'none'` for API/JSON; relaxed for report HTML). `Strict-Transport-Security` only when `HSTS_ENABLED=true`.
- CORS restricted to the `CORS_ORIGINS` allowlist.

### SSRF Protection

- `scanners/url_validator.py` validates every scanner/source URL before fetching: http/https scheme allowlist, DNS resolution, rejection of private/loopback/reserved ranges. `SSRF_ALLOW_PRIVATE=true` disables the private-IP block for local development only.

### Error Sanitization & Image Hardening

- Unhandled exceptions return generic error bodies; tracebacks/SQL stay in server logs.
- Docker image: multi-stage build, non-root user (`app`, uid 1000, nologin shell), only the virtualenv and app code in the final image. CI runs Bandit, pip-audit, Trivy, and Syft SBOM on every change (`security.yml`).

Full hardening details: `docs/security-hardening.md`.
