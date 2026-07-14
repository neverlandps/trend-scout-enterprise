import os
import tempfile

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from trend_scout_enterprise.core.database import Base, get_db
from trend_scout_enterprise.main import app
from trend_scout_enterprise.core.security import generate_api_key, hash_api_key, get_key_prefix
from trend_scout_enterprise.models.models import ApiKey


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
def client(test_db):
    """Return a TestClient with the test database override and API key auth."""
    from fastapi.testclient import TestClient

    # Create a deterministic API key in the test database
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

    app.dependency_overrides[get_db] = lambda: test_db
    test_client = TestClient(app, headers={"X-API-Key": plaintext})
    yield test_client
    app.dependency_overrides.clear()
