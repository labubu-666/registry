"""Tests for application start-up helpers: server() and storage backend selection."""

import pytest

import src.api as api_module
from src.settings import Settings, _make_storage
from src.storage.file import FileStorage
from src.storage.memory import MemoryStorage


def test_server_runs_uvicorn_on_port_5000(monkeypatch):
    """Test that server() starts uvicorn on 0.0.0.0:5000 with debug logging."""
    # Arrange
    calls: dict = {}

    def fake_run(app, host, port, log_level):
        calls.update(app=app, host=host, port=port, log_level=log_level)

    monkeypatch.setattr(api_module.uvicorn, "run", fake_run)

    # Act
    api_module.server()

    # Assert
    assert calls == {
        "app": api_module.app,
        "host": "0.0.0.0",
        "port": 5000,
        "log_level": "debug",
    }


@pytest.mark.parametrize(
    "backend,expected_type",
    [
        pytest.param("memory", MemoryStorage, id="memory"),
        pytest.param("file", FileStorage, id="file"),
    ],
)
def test_make_storage_selects_backend_from_settings(
    monkeypatch, tmp_path, backend, expected_type
):
    """Test that the configured backend name selects the storage class."""
    # Arrange
    monkeypatch.setenv("WAREHOUSE_OCI_REGISTRY_STORAGE_BACKEND", backend)
    monkeypatch.setenv("WAREHOUSE_OCI_REGISTRY_STORAGE_DIR", str(tmp_path / "data"))
    settings = Settings()

    # Act
    storage = _make_storage(settings)

    # Assert
    assert isinstance(storage, expected_type)
