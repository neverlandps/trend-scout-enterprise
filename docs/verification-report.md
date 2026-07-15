# E2E Verification Report — Trend Scout Enterprise

**Date:** 2026-07-15  
**Commit under test:** `cf7d9d1` on `main`  
**Scope:** Local unit/smoke tests, frontend build, Docker build verification on GitHub Actions.

## 1. Local Backend Tests

| Check | Result |
|-------|--------|
| Backend pytest | **66 passed, 4 skipped** |
| Smoke tests (`tests/test_smoke.py`) | **6 passed** |
| Python compile check | **OK** |

### Smoke test coverage
- `GET /api/v1/health` → 200
- Workspace list / current workspace resolution
- Source CRUD (create, list, get, update, delete)
- LLM and scoring settings read
- Report workflow (source → scan → report creation)
- Invalid API key → 401

## 2. Frontend Build

| Check | Result |
|-------|--------|
| TypeScript compile (`tsc --noEmit`) | **passed** |
| Production build (`npm run build`) | **passed** (636 kB main bundle) |

## 3. Docker Build

### Local environment
- Docker CLI available (`Docker version 29.5.3`)
- **Docker daemon not accessible** due to permission denied on `/var/run/docker.sock`
- Local image build **not possible** in this environment

### GitHub Actions CI
- Workflow: `Build and Push Docker Image` (`.github/workflows/docker.yml`)
- Test job: `test-backend` → **success** ✅
- Build job: `build-and-push` → **intermittent failure** ❌

### Root cause
Docker build fails during `pip install -e "."` because of **network timeouts** while downloading packages from PyPI in the GitHub Actions runner:

```text
pip._vendor.urllib3.exceptions.ReadTimeoutError:
HTTPSConnectionPool(host='files.pythonhosted.org', port=443): Read timed out.
```

This is a **transient CI network / pip reliability issue**, not a code or dependency correctness issue. A local clean venv install of the same `pyproject.toml` succeeded in ~16 seconds.

### Mitigations applied
1. Switched base image to `python:3.11-bookworm` (full Debian image) for native WeasyPrint libraries.
2. Installed build dependencies: `libpq-dev`, `gcc`, `python3-dev`.
3. Added `setuptools`, `wheel`, `pip` upgrade.
4. Added `PIP_RETRIES=10`, `PIP_TIMEOUT=120`, `--retries 10`, `--timeout 120`.
5. Added `BUILDKIT_INLINE_CACHE=1` and disabled provenance for simpler buildx output.

### Recommendation
For deterministic CI builds, generate a **pinned `requirements.lock`** (e.g., with `pip-compile` or `uv pip compile`) and install from the lock file instead of `pyproject.toml` on every build. This avoids repeated PyPI metadata resolution and reduces download surface.

## 4. Files created / updated for deployment

| File | Change |
|------|--------|
| `/home/ps/trend-scout-enterprise/deployment/Dockerfile` | Created: Python 3.11 + WeasyPrint native deps + pip install |
| `/home/ps/trend-scout-enterprise/deployment/docker-compose.yml` | Updated: redis, backend, worker, beat services |
| `/home/ps/trend-scout-enterprise/.github/workflows/docker.yml` | Updated: buildx config, linux/amd64 only, provenance disabled |
| `/home/ps/trend-scout-enterprise/backend/tests/test_smoke.py` | Created: in-process E2E smoke tests |

## 5. Known limitations / follow-up

- Docker image build is **not yet green on CI** due to network flakiness.
- No local Docker daemon access, so image cannot be smoke-tested locally.
- P1: Add `requirements.lock` and multi-stage Dockerfile to shrink image size and improve CI reliability.
- P1: Add frontend container / nginx config for production deployment.
- P1: Add API health check in docker-compose `healthcheck`.

## 6. Verdict

- **Code quality / functionality:** PASS ✅ (tests + smoke + frontend build)
- **Docker image build:** BLOCKED by CI network timeouts ❌ (not a code issue)
- **Deployment readiness:** CONDITIONAL — deploy once CI image build stabilizes.
