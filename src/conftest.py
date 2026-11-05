"""Shared pytest fixtures for the src test suite."""

import pytest
from fastapi.testclient import TestClient

from src.api import app
from src.storage import BaseStorage, FileStorage, MemoryStorage

# Every module that holds a reference to the storage singleton. Patching all of
# them keeps the app, the admin API and the OCI routes on the same backend.
STORAGE_MODULES = ("src.settings", "src.api", "src.routes.oci.routes")


@pytest.fixture(params=["memory", "file"])
def storage_backend(request, tmp_path, monkeypatch) -> BaseStorage:
    """Swap the app's storage for a fresh backend, run once per backend type."""
    if request.param == "memory":
        backend: BaseStorage = MemoryStorage()
    else:
        backend = FileStorage(data_dir=str(tmp_path / "data"))

    for module in STORAGE_MODULES:
        monkeypatch.setattr(f"{module}.storage", backend)
    return backend


@pytest.fixture
def client(storage_backend):
    """Provide a TestClient for the FastAPI app pre-authenticated as testuser."""
    from src.auth.token_service import create_token

    token = create_token("testuser")
    return TestClient(app, headers={"Authorization": f"Bearer {token}"})
