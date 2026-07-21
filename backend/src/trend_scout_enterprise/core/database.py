from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from trend_scout_enterprise.core.config import settings

_connect_args = {}
_engine_kwargs: dict = {"connect_args": _connect_args}
if settings.database_url.startswith("sqlite"):
    _connect_args["check_same_thread"] = False
elif settings.database_url.startswith("postgresql"):
    _engine_kwargs.update(
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
        pool_recycle=1800,
    )

engine = create_engine(settings.database_url, **_engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
