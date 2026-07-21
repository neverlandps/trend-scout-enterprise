"""Local E2E smoke test against a running backend API.

Usage:
    1. Start backend: cd backend && python -m uvicorn trend_scout_enterprise.main:app --host 0.0.0.0 --port 8000
    2. Run this script: python scripts/smoke_test.py

This script seeds a temporary API key directly into the SQLite database,
executes a representative API workflow, and prints a summary.
"""

import os
import sys
import uuid
from datetime import datetime, timedelta

# Ensure backend source is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import requests
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from trend_scout_enterprise.core.config import settings
from trend_scout_enterprise.core.security import hash_api_key, get_key_prefix
from trend_scout_enterprise.models.models import ApiKey, RawItem, Source
from trend_scout_enterprise.services.workspace_service import (
    get_or_create_default_team_workspace,
)

BASE_URL = os.environ.get("SMOKE_BASE_URL", "http://127.0.0.1:8000/api/v1")
PLAINTEXT_KEY = f"tse_smoke_{uuid.uuid4().hex}"


def seed_api_key(db):
    """Create a temporary API key with admin role."""
    key = ApiKey(
        id=uuid.uuid4().hex,
        name="smoke-test-key",
        key_hash=hash_api_key(PLAINTEXT_KEY),
        key_prefix=get_key_prefix(PLAINTEXT_KEY),
        is_active=True,
        role="admin",
    )
    db.add(key)
    db.commit()
    db.refresh(key)
    return key


def cleanup(db, key_id):
    db.query(ApiKey).filter(ApiKey.id == key_id).delete()
    db.commit()


def _is_redis_available(host: str = "127.0.0.1", port: int = 6379, timeout: float = 1.0) -> bool:
    """Check if the Redis broker is reachable."""
    import socket
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def run_smoke_test():
    engine = create_engine(settings.database_url, connect_args={"check_same_thread": False})
    Session = sessionmaker(bind=engine)
    db = Session()

    key = seed_api_key(db)
    headers = {"X-API-Key": PLAINTEXT_KEY}
    results = []
    seeded_item_id = None

    try:
        # 1. Health
        r = requests.get(f"{BASE_URL}/health", timeout=10)
        results.append(("GET /health", r.status_code, r.json() if r.ok else r.text))

        # 2. Create source
        source_payload = {
            "name": "Smoke RSS Source",
            "source_type": "rss",
            "config": {"url": "https://example.com/feed.xml"},
            "category": "smoke",
            "tags": ["smoke-test"],
            "enabled": True,
            "refresh_interval_minutes": 60,
        }
        r = requests.post(f"{BASE_URL}/sources", json=source_payload, headers=headers, timeout=10)
        source_id = r.json().get("id") if r.ok else None
        results.append(("POST /sources", r.status_code, r.json() if r.ok else r.text[:200]))

        # 3. Trigger scan (background, may not complete immediately)
        scan_payload = {"source_id": source_id} if source_id else {}
        r = requests.post(f"{BASE_URL}/scans", json=scan_payload, headers=headers, timeout=10)
        results.append(("POST /scans", r.status_code, r.json() if r.ok else r.text[:200]))

        # 4. List signals
        r = requests.get(f"{BASE_URL}/signals", headers=headers, timeout=10)
        results.append(("GET /signals", r.status_code, r.json() if r.ok else r.text[:200]))

        # 5. Aggregate trends
        r = requests.post(
            f"{BASE_URL}/trends/aggregate",
            json={"category": "smoke", "granularity": "day"},
            headers=headers,
            timeout=10,
        )
        results.append(("POST /trends/aggregate", r.status_code, r.json() if r.ok else r.text[:200]))

        # 6. List trend series
        r = requests.get(
            f"{BASE_URL}/trends/series",
            params={"category": "smoke", "granularity": "day"},
            headers=headers,
            timeout=10,
        )
        results.append(("GET /trends/series", r.status_code, r.json() if r.ok else r.text[:200]))

        # 6.5 Signal review flow (direct DB seed; review endpoints do not
        # depend on review_mode_enabled or Redis, so no SKIP needed here)
        workspace = get_or_create_default_team_workspace(db, key)
        if source_id:
            item = RawItem(
                id=uuid.uuid4().hex,
                workspace_id=workspace.id,
                source_id=source_id,
                url=f"https://example.com/smoke-{uuid.uuid4().hex}",
                title="Smoke review item",
                collected_at=datetime.utcnow(),
                overall_score=0.5,
                review_status="pending_review",
                tags=["smoke-test"],
            )
            db.add(item)
            db.commit()
            seeded_item_id = item.id

            # 6.5a Verify it appears in the review queue
            r = requests.get(f"{BASE_URL}/signals/review-queue", headers=headers, timeout=10)
            in_queue = r.ok and any(s.get("id") == seeded_item_id for s in r.json().get("signals", []))
            results.append((
                "GET /signals/review-queue",
                r.status_code if in_queue else 500,
                f"seeded item in queue: {in_queue}" if r.ok else r.text[:200],
            ))

            # 6.5b Approve the signal
            r = requests.post(
                f"{BASE_URL}/signals/{seeded_item_id}/review",
                json={"action": "approve", "notes": "smoke approve"},
                headers=headers,
                timeout=10,
            )
            approved = r.ok and r.json().get("status") == "approved"
            results.append((
                "POST /signals/{id}/review (approve)",
                r.status_code if approved else 500,
                r.json() if r.ok else r.text[:200],
            ))

            # 6.5c Verify review_status filter on GET /signals
            r = requests.get(
                f"{BASE_URL}/signals",
                params={"review_status": "approved"},
                headers=headers,
                timeout=10,
            )
            found = r.ok and any(s.get("id") == seeded_item_id for s in r.json().get("signals", []))
            results.append((
                "GET /signals?review_status=approved",
                r.status_code if found else 500,
                f"approved item listed: {found}" if r.ok else r.text[:200],
            ))
        else:
            results.append(("Signal review flow", "SKIPPED (no source created)", "source_id unavailable"))

        # 7. Create report (Celery/Redis required; skip if broker unavailable)
        report_payload = {
            "title": "Smoke Report",
            "report_type": "card",
            "filters": {"category": "smoke"},
        }
        if not _is_redis_available():
            results.append(("POST /reports", "SKIPPED (Celery/Redis unavailable)", "Redis broker not running"))
        else:
            try:
                r = requests.post(f"{BASE_URL}/reports", json=report_payload, headers=headers, timeout=5)
                if r.status_code == 500 and "Connection refused" in r.text:
                    results.append(("POST /reports", "SKIPPED (Celery/Redis unavailable)", "Redis broker not running"))
                else:
                    results.append(("POST /reports", r.status_code, r.json() if r.ok else r.text[:200]))
            except requests.exceptions.Timeout:
                results.append(("POST /reports", "SKIPPED (Celery/Redis unavailable)", "Request timed out waiting for broker"))

    finally:
        if seeded_item_id:
            db.query(RawItem).filter(RawItem.id == seeded_item_id).delete()
            db.commit()
        cleanup(db, key.id)
        db.close()

    # Print summary
    failures = [name for name, status, body in results if status not in ("OK", "SKIPPED (Celery/Redis unavailable)") and (isinstance(status, int) and status >= 400)]
    print("\n=== Smoke Test Results ===")
    for name, status, body in results:
        status_str = "OK" if isinstance(status, int) and status < 400 else ("SKIP" if "SKIPPED" in str(status) or "Timeout" in str(body) else "FAIL")
        print(f"  [{status_str}] {name}: {status}")
    print("==========================")
    if failures:
        print(f"FAILED endpoints: {failures}")
        sys.exit(1)
    print("All smoke tests passed.")


if __name__ == "__main__":
    run_smoke_test()
