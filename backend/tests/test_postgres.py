import os

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from trend_scout_enterprise.core.database import Base, get_db
from trend_scout_enterprise.main import app
from trend_scout_enterprise.core.config import settings
from trend_scout_enterprise.models.models import ApiKey, Source, ScanRun, RawItem, ScoringProfile, LlmProvider, Report
from trend_scout_enterprise.models.auth import MicrosoftAuthConfig, UserSession
from trend_scout_enterprise.core.security import hash_api_key, get_key_prefix, verify_api_key_hash


POSTGRES_URL = os.environ.get("TEST_DATABASE_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/trend_scout_test")

psycopg2 = pytest.importorskip("psycopg2", reason="psycopg2 not installed; PostgreSQL tests skipped")


@pytest.fixture
def postgres_engine():
    engine = create_engine(POSTGRES_URL)
    try:
        with engine.connect():
            pass
    except Exception as exc:
        pytest.skip(f"PostgreSQL not available at {POSTGRES_URL}: {exc}")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def postgres_session(postgres_engine):
    Session = sessionmaker(bind=postgres_engine)
    session = Session()
    yield session
    session.close()


class TestPostgresSchema:
    def test_all_tables_exist(self, postgres_engine):
        inspector = inspect(postgres_engine)
        tables = inspector.get_table_names()
        expected = {
            "api_keys", "sources", "scan_runs", "raw_items",
            "scoring_profiles", "llm_providers", "reports",
            "microsoft_auth_configs", "user_sessions",
        }
        assert expected.issubset(set(tables))

    def test_api_key_crud(self, postgres_session):
        key = ApiKey(
            id="test-key-1",
            name="test",
            key_hash=hash_api_key("secret"),
            key_prefix=get_key_prefix("secret"),
            is_active=True,
        )
        postgres_session.add(key)
        postgres_session.commit()
        fetched = postgres_session.query(ApiKey).filter_by(id="test-key-1").first()
        assert fetched is not None
        # bcrypt hashes are salted and non-deterministic; verify instead of comparing.
        assert verify_api_key_hash("secret", fetched.key_hash)

    def test_source_relationship(self, postgres_session):
        owner = ApiKey(
            id="owner-1",
            name="owner",
            key_hash=hash_api_key("owner-secret"),
            key_prefix="own_",
            is_active=True,
        )
        postgres_session.add(owner)
        postgres_session.commit()

        source = Source(
            id="source-1",
            name="RSS",
            source_type="rss",
            config_encrypted="enc",
            owner_id="owner-1",
        )
        postgres_session.add(source)
        postgres_session.commit()

        assert source.owner.id == "owner-1"

    def test_json_columns(self, postgres_session):
        profile = ScoringProfile(
            id="profile-1",
            name="default",
            dimensions=[{"name": "relevance", "weight": 0.5}],
        )
        postgres_session.add(profile)
        postgres_session.commit()
        fetched = postgres_session.query(ScoringProfile).first()
        assert fetched.dimensions[0]["name"] == "relevance"


class TestSQLiteCompatibility:
    def test_sqlite_schema_creates_all_tables(self, tmp_path):
        db_path = tmp_path / "test.db"
        engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        expected = {
            "api_keys", "sources", "scan_runs", "raw_items",
            "scoring_profiles", "llm_providers", "reports",
            "microsoft_auth_configs", "user_sessions",
        }
        assert expected.issubset(set(tables))


def test_get_db_generator():
    db_gen = get_db()
    db = next(db_gen)
    assert db is not None
    try:
        next(db_gen)
    except StopIteration:
        pass
