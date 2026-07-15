# SQLite → PostgreSQL Migration Assessment

## Current State

Trend Scout Enterprise MVP uses SQLite as its primary data store. SQLAlchemy models
are database-agnostic, but the project relies on SQLite-specific behaviours in a
few places (see Risk sections below).

- **Engine**: `sqlite:///{path}` via `core/database.py`
- **Migrations**: Alembic was intentionally removed from MVP scope
- **Concurrency**: SQLite handles moderate read/write concurrency via WAL mode
  but does not scale horizontally across multiple backend workers
- **Backup**: manual file copy only

## Drivers for Migration

1. **Multi-instance / horizontal scaling**: SQLite locks the database file to one
   process group; running multiple backend containers requires a shared database.
2. **Concurrent writes**: high-frequency scan/report workers can block each
   other under SQLite WAL contention.
3. **Operational backup / PITR**: PostgreSQL offers WAL archiving, pg_dump,
   managed cloud services (Azure Database for PostgreSQL), and point-in-time
   recovery.
4. **SharePoint lists integration**: future P1 architecture may mirror raw items
   to SharePoint lists; PostgreSQL JSONB columns can still serve as the system of
   record.
5. **Team expectations**: enterprise deployments expect a managed relational
   database, not a file on the container filesystem.

## Schema Compatibility Analysis

### Green (no changes needed)

Most SQLAlchemy models use generic types that map cleanly to PostgreSQL:

- `String`, `Text`, `Boolean`, `Integer`, `Float`, `DateTime`, `JSON`, `ForeignKey`
- Standard `relationship()` and `Index` definitions

### Yellow (verify / minor changes)

1. **JSON column behaviour**
   - SQLite uses JSON1 extension; PostgreSQL uses native JSON / JSONB.
   - `metadata_json` and `tags` columns currently use `JSON` type. SQLAlchemy
     maps this to `JSON` on both dialects, but query operators differ.
   - Recommendation: add a JSONB variant for PostgreSQL and keep JSON for
     SQLite, or switch to JSONB globally with SQLite fallback to JSON.

2. **Case sensitivity**
   - SQLite `LIKE` is case-insensitive by default for ASCII; PostgreSQL `LIKE`
     is case-sensitive. Any text search filters should use `ilike()` explicitly.

3. **DateTime timezone**
   - Models store UTC `DateTime` without timezone. PostgreSQL `timestamp`
     without time zone is fine, but consider `timestamptz` in a future revision.

### Red (requires code changes)

1. **Primary key UUID generation**
   - Python `uuid.uuid4().hex` produces 32-char hex strings. This is compatible
     with PostgreSQL `CHAR(32)` / `VARCHAR(32)` primary keys, but using native
     `UUID` type is more efficient.
   - Changing to native UUID requires schema migration and client-side string
     handling updates.

2. **Auto-increment / serial IDs**
   - No model uses auto-increment integer keys, so migration is straightforward.

3. **SQLite-only file operations**
   - `Base.metadata.create_all(bind=engine)` works on both dialects.
   - Docker volume mounting must change from SQLite file to PostgreSQL data dir.

## Recommended Migration Path

### Phase 1: Preparation (P1, ~4 hours)

1. Add `psycopg2-binary` to `backend/pyproject.toml` and `requirements.txt`.
2. Introduce `DATABASE_URL` environment variable parsing in `core/config.py`.
3. Keep SQLite as default for local development; PostgreSQL opt-in via env var.
4. Add a dialect-agnostic JSON column helper that returns JSONB on PostgreSQL.

### Phase 2: Schema Migration (P1, ~8 hours)

1. Re-introduce Alembic with a single migration environment.
2. Generate initial migration from current `Base.metadata`.
3. Add a data migration script that copies SQLite data to PostgreSQL:
   - Read all rows from SQLite
   - Re-insert into PostgreSQL via SQLAlchemy session batches
   - Preserve `id` UUIDs to maintain foreign-key integrity
4. Test migration in CI against a PostgreSQL service container.

### Phase 3: CI/CD & Docker (P1, ~6 hours)

1. Update `docker-compose.yml` with `postgres` service.
2. Update GitHub Actions workflow to spin up `postgres:15` service container
   for backend tests.
3. Add health checks for PostgreSQL readiness before running tests.
4. Keep SQLite-only tests running in parallel to ensure local-dev parity.

### Phase 4: Operational Readiness (P2, ~8 hours)

1. Add connection pooling (`SQLAlchemy QueuePool`) settings.
2. Add database migration step to Docker entrypoint or init container.
3. Document backup/restore procedures for PostgreSQL.
4. Evaluate Azure Database for PostgreSQL / AWS RDS managed offering.

## Risks & Fallbacks

| Risk | Impact | Fallback |
|---|---|---|
| JSON column migration failures | Medium | Store JSON as text during migration, then cast to JSONB |
| PostgreSQL connection pool exhaustion | High | Tune pool size; add PgBouncer sidecar if needed |
| SQLAlchemy dialect differences in DateTime | Low | Keep `DateTime` without timezone; use UTC consistently in app code |
| Migration downtime | Medium | Use blue/green deployment or init-container migration before app start |
| Data loss during migration | High | Snapshot SQLite file before migration; validate row counts |
| Test flakiness from dual dialects | Medium | Run SQLite tests locally, PostgreSQL tests in CI nightly |

## Workload Estimate

- Phase 1: 4 hours
- Phase 2: 8 hours
- Phase 3: 6 hours
- Phase 4: 8 hours
- **Total: ~26 hours** (P1 scope: 18 hours, P2 scope: 8 hours)

## Decision Log

- **MVP**: Keep SQLite. No managed DB operational overhead.
- **P1**: PostgreSQL migration after the first production deployment.
- **P2**: Connection pooling, managed DB, and disaster recovery runbooks.

## References

- `backend/src/trend_scout_enterprise/core/database.py`
- `backend/src/trend_scout_enterprise/models/models.py`
- `backend/pyproject.toml`
- `docker-compose.yml`
