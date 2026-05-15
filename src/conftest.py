"""Shared pytest fixtures for the src test suite."""

import pytest
from fastapi.testclient import TestClient

from src.api import app
from src.storage import MemoryStorage


@pytest.fixture
def client():
    """Provide a TestClient for the FastAPI app pre-authenticated as testuser."""
    from src.auth.token_service import create_token

    token = create_token("testuser")
    return TestClient(app, headers={"Authorization": f"Bearer {token}"})


@pytest.fixture(autouse=True)
def reset_storage():
    """Reset storage before each test."""
    from src.api import storage

    if isinstance(storage, MemoryStorage):
        storage.manifests.clear()
        storage.blobs.clear()
        storage.repositories.clear()
    yield
