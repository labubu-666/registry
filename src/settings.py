import secrets

from pydantic_settings import BaseSettings, SettingsConfigDict

from .storage.base import BaseStorage
from .storage.file import FileStorage
from .storage.memory import MemoryStorage


class Settings(BaseSettings):
    """Unified application settings.

    All fields are loaded from environment variables or a ``.env`` file.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ── Storage ───────────────────────────────────────────────────────────────

    storage_backend: str = "memory"
    """Storage backend to use: ``memory`` (default) or ``file``."""

    storage_dir: str = "data"
    """Directory used by the ``file`` storage backend."""

    # ── Authentication ────────────────────────────────────────────────────────

    auth_secret_key: str = secrets.token_hex(32)
    """HMAC secret used to sign JWTs.
    **Set a stable value in production** — the default is re-generated on every
    restart, which invalidates all previously issued tokens.
    Generate one with: ``python -c "import secrets; print(secrets.token_hex(32))"``
    """

    auth_token_expiration: int = 300
    """Token lifetime in seconds (default: 5 minutes)."""

    auth_realm: str = "http://localhost:5000/auth/token"
    """Token endpoint URL advertised in ``WWW-Authenticate`` challenges.
    Must be reachable by Docker clients.
    """

    auth_service: str = "registry"
    """Service name embedded in the JWT ``aud`` (audience) claim."""

    auth_issuer: str = "registry-token-service"
    """Issuer label embedded in the JWT ``iss`` claim (informational)."""

    registry_users: str = ""
    """Comma-separated ``username:password`` pairs bootstrapped on startup.
    Example: ``REGISTRY_USERS=alice:secret,bob:hunter2``
    """


settings = Settings()


def _make_storage(s: Settings) -> BaseStorage:
    if s.storage_backend == "file":
        return FileStorage(data_dir=s.storage_dir)
    return MemoryStorage()


storage: BaseStorage = _make_storage(settings)
