from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from quant_research_api.celery_app import celery_app
from quant_research_api.database import Base, get_db
from quant_research_api.main import app

# Run Celery tasks synchronously in-process -- no real Redis/worker needed for tests.
celery_app.conf.update(task_always_eager=True, task_eager_propagates=True)


@pytest.fixture
def db_engine():
    # StaticPool: every connection from this engine shares the same single
    # underlying SQLite connection, so independent Session objects (one per
    # request, one for the eager Celery task -- mirroring production, where
    # each also gets its own session) still see the same in-memory data.
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(db_engine, monkeypatch, tmp_path):
    testing_session_local = sessionmaker(bind=db_engine, autoflush=False, autocommit=False)

    def _override_get_db():
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_get_db

    # tasks.py opens its own SessionLocal() (Celery tasks aren't FastAPI
    # dependencies) -- point it at a sessionmaker on the same engine so eager
    # task execution sees data the test already committed via the API.
    import quant_research_api.tasks as tasks_module

    monkeypatch.setattr(tasks_module, "SessionLocal", testing_session_local)

    # keep run artifacts inside tmp_path, not the repo's real api_data/ dir
    from quant_research_api.settings import settings

    monkeypatch.setattr(settings, "artifacts_root", str(tmp_path / "reports"))

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
