"""Unit tests for source service and router."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from trend_scout_enterprise.core.database import Base, get_db
from trend_scout_enterprise.main import app
from trend_scout_enterprise.models.models import Source
from trend_scout_enterprise.schemas.schemas import SourceCreate, SourceUpdate
from trend_scout_enterprise.services.source_service import (
    create_source,
    delete_source,
    get_source,
    list_sources,
    update_source,
    validate_source_config,
)

SQLALCHEMY_DATABASE_URL = "sqlite:///./test_sources.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def test_validate_source_config_invalid_type():
    with pytest.raises(Exception) as exc_info:
        validate_source_config("invalid_type", {"url": "http://example.com"})
    assert "Invalid source type" in str(exc_info.value)


def test_validate_source_config_missing_url():
    with pytest.raises(Exception) as exc_info:
        validate_source_config("rss", {})
    assert "url" in str(exc_info.value)


def test_create_source():
    db = next(override_get_db())
    source = SourceCreate(name="Test RSS", source_type="rss", config={"url": "http://example.com/rss"})
    db_source = create_source(db, source)
    assert db_source.name == "Test RSS"
    assert db_source.source_type == "rss"


def test_get_source_not_found():
    db = next(override_get_db())
    with pytest.raises(Exception) as exc_info:
        get_source(db, "non-existent-id")
    assert "404" in str(exc_info.value) or "not found" in str(exc_info.value).lower()


def test_list_sources():
    db = next(override_get_db())
    create_source(db, SourceCreate(name="A", source_type="rss", config={"url": "http://a.com"}))
    create_source(db, SourceCreate(name="B", source_type="arxiv", config={"url": "http://b.com"}))
    sources = list_sources(db)
    assert len(sources) == 2


def test_update_source():
    db = next(override_get_db())
    db_source = create_source(db, SourceCreate(name="Old", source_type="rss", config={"url": "http://old.com"}))
    updated = update_source(db, db_source.id, SourceUpdate(name="New"))
    assert updated.name == "New"


def test_delete_source():
    db = next(override_get_db())
    db_source = create_source(db, SourceCreate(name="Del", source_type="rss", config={"url": "http://del.com"}))
    delete_source(db, db_source.id)
    assert db.query(Source).filter(Source.id == db_source.id).first() is None


def test_api_list_sources():
    response = client.get("/api/v1/sources", headers={"X-API-Key": "change-me-in-production"})
    assert response.status_code == 200


def test_api_create_source():
    response = client.post(
        "/api/v1/sources",
        headers={"X-API-Key": "change-me-in-production"},
        json={"name": "API RSS", "source_type": "rss", "config": {"url": "http://api.com"}},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "API RSS"


def test_api_create_source_invalid_type():
    response = client.post(
        "/api/v1/sources",
        headers={"X-API-Key": "change-me-in-production"},
        json={"name": "Bad", "source_type": "unknown", "config": {"url": "http://bad.com"}},
    )
    assert response.status_code == 400
