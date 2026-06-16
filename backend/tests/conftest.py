"""Pytest setup: configure a clean, deterministic environment BEFORE importing
the app, so config/secrets/admin/rate-limits are test-controlled.
"""
import os
import tempfile

# Must be set before `app` is imported (config reads env at import time).
os.environ.setdefault("JOBORA_ENV", "development")
os.environ["JWT_SECRET"] = "test-secret-please-ignore-0123456789abcdef"
os.environ["CREDENTIAL_KEY"] = "qjU2rteqskkZVxAi0W-5ycYvngD8IjVc4FH_fvgc_b0="  # valid Fernet (test only)
os.environ["ADMIN_EMAIL"] = "admin@jobara.io"
os.environ["ADMIN_PASSWORD"] = "AdminTest123"
os.environ["RL_LOGIN_PER_MIN"] = "5"
os.environ["INPROCESS_WORKER"] = "0"   # don't start the worker during tests
os.environ["JSEARCH_API_KEY"] = ""     # never hit the live JSearch API from tests (ignore local .env)
os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mkstemp(suffix='.db')[1]}"

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def admin_token(client):
    r = client.post("/api/auth/login", json={"email": "admin@jobara.io", "password": "AdminTest123"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]
