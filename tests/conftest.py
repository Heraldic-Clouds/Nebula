"""Tests use a disposable real PostgreSQL DB. Provider doubles exist ONLY in tests."""
import os
import pytest
from alembic import command
from alembic.config import Config
from cryptography.fernet import Fernet
from sqlalchemy import text


@pytest.fixture
def database(monkeypatch):
    url = os.environ.get("NEBULA_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set NEBULA_TEST_DATABASE_URL to a disposable PostgreSQL database")
    from sqlalchemy.engine import make_url
    name = make_url(url).database or ""
    if not name.endswith("_test"):
        pytest.fail("Refusing to truncate a DB without the _test suffix")
    monkeypatch.setenv("NEBULA_DATABASE_URL", url)
    monkeypatch.setenv("NEBULA_CREDENTIAL_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("NEBULA_COOKIE_SECURE", "false")
    monkeypatch.setenv("NEBULA_PROVISIONING_ENABLED", "true")
    from nebula.config import settings
    from nebula.db import engine
    settings.cache_clear()
    engine.cache_clear()
    command.upgrade(Config("alembic.ini"), "head")
    from nebula.models import Base
    with engine().begin() as c:
        tables = ",".join('"' + name + '"' for name in Base.metadata.tables)
        c.execute(text("TRUNCATE " + tables + " CASCADE"))
    yield
    engine().dispose()
    engine.cache_clear()
    settings.cache_clear()


@pytest.fixture
def customer(database):
    from argon2 import PasswordHasher
    from nebula.db import transaction
    from nebula.models import User, Project, Rate, now
    from nebula.security import encrypt_credentials
    with transaction() as db:
        user = User(email="customer@example.com", password_hash=PasswordHasher().hash("a-customer-test-password"))
        db.add(user)
        db.flush()
        project = Project(user_id=user.id, provider_id="tenant-a", auth_url="https://keystone.example.invalid/v3",
            credential=encrypt_credentials("scoped-test-id", "test-only-secret"),
            catalog={"images":["ubuntu"],"flavors":["small"],"networks":["private"]},last_collected_at=now())
        rate = Rate(cpu=10000, ram=1000, storage=100000)
        db.add_all([project,rate])
        db.flush()
        return user.id, project.id, rate.id


@pytest.fixture
def client(customer):
    from fastapi.testclient import TestClient
    from nebula.api import app
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post("/api/v1/auth/login",json={"email":"customer@example.com","password":"a-customer-test-password"})
        assert response.status_code == 200, response.text
        client.headers["X-CSRF-Token"] = client.cookies["nebula_csrf"]
        yield client
