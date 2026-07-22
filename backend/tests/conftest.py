import base64
import os
import tempfile

os.environ.setdefault("TESTING", "1")
os.environ.setdefault("SECRET_KEY", "test-only-secret-key-not-for-production")
os.environ.setdefault(
    "ENCRYPTION_SALT", base64.urlsafe_b64encode(b"test-salt-123456").decode()
)

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from trend_scout_enterprise.core.database import Base, get_db
from trend_scout_enterprise.main import app
from trend_scout_enterprise.core.security import generate_api_key, hash_api_key, get_key_prefix
from trend_scout_enterprise.models.models import ApiKey, Team, TeamMembership, Workspace
from trend_scout_enterprise.services.workspace_service import get_or_create_default_team_workspace


@pytest.fixture(scope="function")
def test_db():
    """Create a fresh SQLite database for each test function."""
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    db_url = f"sqlite:///{db_path}"
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture(scope="function")
def default_api_key(test_db):
    """Create a test API key with a default team/workspace."""
    plaintext = "test_api_key_for_unit_tests"
    api_key = ApiKey(
        id="test-key-id",
        name="test",
        key_hash=hash_api_key(plaintext),
        key_prefix=get_key_prefix(plaintext),
        is_active=True,
        role="admin",
    )
    test_db.add(api_key)
    test_db.commit()
    get_or_create_default_team_workspace(test_db, api_key)
    return api_key, plaintext


@pytest.fixture(scope="function")
def client(default_api_key, test_db):
    """Return a TestClient with the test database override and API key auth."""
    from fastapi.testclient import TestClient

    _, plaintext = default_api_key
    app.dependency_overrides[get_db] = lambda: test_db
    test_client = TestClient(app, headers={"X-API-Key": plaintext})
    yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def second_workspace(test_db, default_api_key):
    """Create a second workspace in the same team as the default API key."""
    from uuid import uuid4

    api_key, _ = default_api_key
    membership = test_db.query(TeamMembership).filter(TeamMembership.api_key_id == api_key.id).first()
    workspace = Workspace(
        id=uuid4().hex,
        team_id=membership.team_id,
        name="Second Workspace",
        is_default=False,
    )
    test_db.add(workspace)
    test_db.commit()
    test_db.refresh(workspace)
    return workspace
@pytest.fixture(scope="function")
def default_workspace(test_db, default_api_key):
    """Return the default workspace for the test API key."""
    api_key, _ = default_api_key
    return get_or_create_default_team_workspace(test_db, api_key)


@pytest.fixture(scope="function")
def auth_headers(client):
    """Return headers including the test API key."""
    return {"X-API-Key": "test_api_key_for_unit_tests"}
