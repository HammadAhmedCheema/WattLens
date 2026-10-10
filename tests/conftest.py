import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine
from sqlalchemy.pool import StaticPool
from app.main import app
from app.db import get_session
from app.models import Household
from app.config import settings
from app import extraction, web
from dataclasses import replace

@pytest.fixture
def client(tmp_path,monkeypatch):
    engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        s.add(Household(id=1));s.commit()
    def session():
        with Session(engine) as s: yield s
    app.dependency_overrides[get_session]=session
    local=replace(settings,upload_dir=tmp_path/'uploads')
    monkeypatch.setattr(extraction,'settings',local)
    monkeypatch.setattr(web,'settings',local)
    yield TestClient(app)
    app.dependency_overrides.clear()

@pytest.fixture(autouse=True)
def mock_credentials(monkeypatch):
    from app import ai_client
    monkeypatch.setattr(ai_client, 'settings', replace(settings, api_key='test-key'))
