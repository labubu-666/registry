import secrets

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from .storage.base import BaseStorage
from .storage.file import FileStorage
from .storage.memory import MemoryStorage


class Settings(BaseSettings):
    """Unified application settings.

    All fields are loaded from environment variables or a ``.env`` file.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ── Storage (OCI Registry) ────────────────────────────────────────────────

    storage_backend: str = Field(
        default="memory", validation_alias="WAREHOUSE_OCI_REGISTRY_STORAGE_BACKEND"
    )
    """Storage backend to use: ``memory`` (default) or ``file``."""

    storage_dir: str = Field(
        default="data", validation_alias="WAREHOUSE_OCI_REGISTRY_STORAGE_DIR"
    )
    """Directory used by the ``file`` storage backend."""

    # ── Authentication ────────────────────────────────────────────────────────

    auth_secret_key: str = Field(
        default_factory=lambda: secrets.token_hex(32),
        validation_alias="WAREHOUSE_AUTH_SECRET_KEY",
    )
    """HMAC secret used to sign JWTs.
    **Set a stable value in production** — the default is re-generated on every
    restart, which invalidates all previously issued tokens.
    Generate one with: ``python -c "import secrets; print(secrets.token_hex(32))"``
    """

    auth_token_expiration: int = Field(
        default=300, validation_alias="WAREHOUSE_AUTH_TOKEN_EXPIRATION"
    )
    """Token lifetime in seconds (default: 5 minutes)."""

    auth_realm: str = Field(
        default="http://localhost:5000/auth/token",
        validation_alias="WAREHOUSE_AUTH_REALM",
    )
    """Token endpoint URL advertised in ``WWW-Authenticate`` challenges.
    Must be reachable by Docker clients.
    """

    auth_service: str = Field(
        default="registry", validation_alias="WAREHOUSE_AUTH_SERVICE"
    )
    """Service name embedded in the JWT ``aud`` (audience) claim."""

    auth_issuer: str = Field(
        default="registry-token-service", validation_alias="WAREHOUSE_AUTH_ISSUER"
    )
    """Issuer label embedded in the JWT ``iss`` claim (informational)."""

    registry_users: str = Field(
        default="", validation_alias="WAREHOUSE_OCI_REGISTRY_USERS"
    )
    """Comma-separated ``username:password`` pairs bootstrapped on startup.
    Example: ``WAREHOUSE_OCI_REGISTRY_USERS=alice:secret,bob:hunter2``
    """


settings = Settings()


def _make_storage(s: Settings) -> BaseStorage:
    if s.storage_backend == "file":
        return FileStorage(data_dir=s.storage_dir)
    return MemoryStorage()


storage: BaseStorage = _make_storage(settings)
