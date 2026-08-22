"""Shared fixtures for integration tests (backed by the real FastAPI app)."""
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.src.api.main import app
from backend.src.core.objects.store import ObjectStore


@pytest.fixture()
def client(tmp_path):
    """A TestClient with an isolated, fresh ObjectStore on app.state (single
    uvicorn worker discipline — ADR-07)."""
    client = TestClient(app)
    client.app.state.store = ObjectStore(str(tmp_path / "store"))
    yield client


def hdr(user: str = "userA") -> dict:
    return {"X-User": user}