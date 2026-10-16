from collections.abc import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from vn_procurement_lakehouse.bootstrap.config import load_settings


@pytest.fixture(scope="session")
def db_session_factory() -> Generator[sessionmaker[Session]]:
    settings = load_settings()
    engine = create_engine(settings.database_url, pool_pre_ping=True)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    yield session_factory

    engine.dispose()
