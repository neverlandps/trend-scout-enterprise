"""Unit tests for source service and router."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from trend_scout_enterprise.core.database import Base, get_db
from trend_scout_enterprise.core.security import generate_api_key
from trend_scout_enterprise.main import app
from trend_scout_enterprise.models.models import ApiKey, Source
from trend_scout_enterprise.schemas.schemas import SourceCreate, SourceUpdate
from trend_scout_enterprise.services.workspace_service import get_or_create_default_team_workspace
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


def _create_owner(db) -> ApiKey:
    """Create a test API key owner."""
    plaintext = generate_api_key("test_")
    owner = ApiKey(
        id=__import__("uuid").uuid4().hex,
        name="test-owner",
        key_hash=__import__("hashlib").sha256(plaintext.encode()).hexdigest(),
        key_prefix=plaintext[:8],
        is_active=True,
        role="admin",
    )
    db.add(owner)
    db.commit()
    db.refresh(owner)
    get_or_create_default_team_workspace(db, owner)
    return owner, plaintext


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
    owner, _ = _create_owner(db)
    source = SourceCreate(name="Test RSS", source_type="rss", config={"url": "http://example.com/rss"})
    db_source = create_source(db, source, owner, owner.workspace_id if getattr(owner, "workspace_id", None) else None)
    assert db_source.name == "Test RSS"
    assert db_source.source_type == "rss"
    assert db_source.owner_id == owner.id


def test_get_source_not_found():
    db = next(override_get_db())
    owner, _ = _create_owner(db)
    with pytest.raises(Exception) as exc_info:
        get_source(db, "non-existent-id", owner, None)
    assert "404" in str(exc_info.value) or "not found" in str(exc_info.value).lower()


def test_list_sources():
    db = next(override_get_db())
    owner, _ = _create_owner(db)
    create_source(db, SourceCreate(name="A", source_type="rss", config={"url": "http://a.com"}), owner, owner.workspace_id if getattr(owner, "workspace_id", None) else None)
    create_source(db, SourceCreate(name="B", source_type="arxiv", config={"query": "trend"}) , owner, owner.workspace_id if getattr(owner, "workspace_id", None) else None)
    sources = list_sources(db, owner, None)
    assert len(sources) == 2


def test_update_source():
    db = next(override_get_db())
    owner, _ = _create_owner(db)
    db_source = create_source(db, SourceCreate(name="Old", source_type="rss", config={"url": "http://old.com"}), owner, owner.workspace_id if getattr(owner, "workspace_id", None) else None)
    updated = update_source(db, db_source.id, SourceUpdate(name="New"), owner, None)
    assert updated.name == "New"


def test_delete_source():
    db = next(override_get_db())
    owner, _ = _create_owner(db)
    db_source = create_source(db, SourceCreate(name="Del", source_type="rss", config={"url": "http://del.com"}), owner, owner.workspace_id if getattr(owner, "workspace_id", None) else None)
    delete_source(db, db_source.id, owner, None)
    assert db.query(Source).filter(Source.id == db_source.id).first() is None


def test_api_list_sources():
    db = next(override_get_db())
    owner, plaintext = _create_owner(db)
    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    response = client.get("/api/v1/sources", headers={"X-API-Key": plaintext})
    assert response.status_code == 200


def test_api_create_source():
    db = next(override_get_db())
    owner, plaintext = _create_owner(db)
    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    response = client.post(
        "/api/v1/sources",
        headers={"X-API-Key": plaintext},
        json={"name": "API RSS", "source_type": "rss", "config": {"url": "http://api.com"}},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "API RSS"


def test_api_create_source_invalid_type():
    db = next(override_get_db())
    owner, plaintext = _create_owner(db)
    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    response = client.post(
        "/api/v1/sources",
        headers={"X-API-Key": plaintext},
        json={"name": "Bad", "source_type": "unknown", "config": {"url": "http://bad.com"}},
    )
    assert response.status_code == 400
