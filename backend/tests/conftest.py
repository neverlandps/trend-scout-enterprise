import os
import tempfile

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from trend_scout_enterprise.core.database import Base, get_db
from trend_scout_enterprise.main import app
from trend_scout_enterprise.core.config import settings


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
    """Return a TestClient with the test database override."""
    original_url = settings.database_url
    settings.database_url = f"sqlite:///{test_db.bind.url.database}"
    app.dependency_overrides[get_db] = lambda: test_db
    from fastapi.testclient import TestClient

    test_client = TestClient(app)
    yield test_client
    app.dependency_overrides.clear()
    settings.database_url = original_url
