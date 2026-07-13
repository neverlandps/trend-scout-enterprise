import pytest
from fastapi.testclient import TestClient

from trend_scout_enterprise.main import app


client = TestClient(app)


def test_health_check():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "trend-scout-enterprise"


def test_list_sources_empty():
    response = client.get("/api/v1/sources")
    assert response.status_code == 200
    assert response.json() == {"sources": []}
