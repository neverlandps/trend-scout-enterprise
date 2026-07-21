# Security Hardening

Summary of the security hardening delivered in the 2026-07 refactor. Each item lists what changed and the relevant configuration.

## bcrypt API Key Hashing (Dual-Mode Migration)

API keys were previously stored as unsalted SHA-256 hex digests. Hashing now uses bcrypt (`passlib` `CryptContext`, `backend/src/trend_scout_enterprise/core/security.py`). Verification accepts legacy SHA-256 hashes and transparently re-hashes them to bcrypt on first successful login, so existing keys keep working without a forced reset.

- Config: none (automatic migration on verify).

## SECRET_KEY Fail-Fast

The backend refuses to start when `SECRET_KEY` is unset or still the `change-me-in-production` placeholder, unless `TESTING=1`. This removes the silent fallback to a publicly known key.

- Config: `SECRET_KEY` (required outside testing), `TESTING`.

## ENCRYPTION_SALT Required for Field Encryption

Fernet keys for encrypting source configs / LLM provider keys are derived from `SECRET_KEY` + a salt. Outside testing, a missing `ENCRYPTION_SALT` raises `RuntimeError` instead of silently using a weak fixed salt (`backend/src/trend_scout_enterprise/core/encryption.py`).

- Config: `ENCRYPTION_SALT` (base64-encoded, required outside testing).

## SSRF URL Validation

Scanner/source URLs are validated before any outbound fetch: scheme allowlist (http/https), DNS resolution, and rejection of private/loopback/reserved IP ranges. This blocks server-side request forgery against internal services.

- Config: `SSRF_ALLOW_PRIVATE=true` disables the private-IP block for local development only.

## Rate Limiting

A shared `slowapi` limiter (`backend/src/trend_scout_enterprise/core/rate_limit.py`) is wired into the app via `SlowAPIMiddleware` in `main.py`, throttling sensitive endpoints (auth, scans, analyze) per client IP.

- Config: limits are declared per-endpoint in code; no env var.

## CORS Allowlist

CORS is restricted to an explicit origin allowlist instead of `*`. Multiple origins are comma-separated.

- Config: `CORS_ORIGINS` (default `http://localhost:5173`).

## Audit Logging

Sensitive operations (signal review/bulk-review/feedback, auth events, administrative changes) are recorded in the `audit_logs` table (`backend/src/trend_scout_enterprise/models/audit_log.py`, `core/audit.py`) with actor, action, workspace, resource, and detail fields.

- Config: none (always on).

## Docker Hardening

`deployment/Dockerfile` is a multi-stage build: a `builder` stage compiles dependencies, and the slim runtime image runs as a non-root user (`app`, uid 1000) with a nologin shell. Only the virtualenv and app code are copied into the final image.

- Config: none (image build).

## Error Sanitization

Unhandled exceptions return a generic error body to clients instead of leaking tracebacks, SQL, or internal paths; full details stay in server logs.

- Config: none (always on).

## Signal Review Workflow

See [`signal-review-workflow.md`](signal-review-workflow.md) for the human-in-the-loop review state machine, thresholds, and API.
