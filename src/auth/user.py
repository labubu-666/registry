import hashlib
import secrets

from src.settings import settings

ANONYMOUS_USER = "anonymous"
_HASH_ITERATIONS = 200_000


def _hash_password(password: str, salt: str | None = None) -> str:
    """Return a salted hash of the password in the format 'salt:hash'."""
    if salt is None:
        salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), salt.encode(), _HASH_ITERATIONS
    )
    return f"{salt}:{dk.hex()}"


def _verify_password(password: str, stored: str) -> bool:
    """Verify a plaintext password against a stored 'salt:hash' value."""
    try:
        salt, _ = stored.split(":", 1)
        return secrets.compare_digest(stored, _hash_password(password, salt))
    except ValueError:
        return False


class UserStore:
    """In-memory user store bootstrapped from ``settings.registry_users``."""

    def __init__(self) -> None:
        self._users: dict[str, str] = {}
        self._load_from_settings()

    def _load_from_settings(self) -> None:
        for entry in settings.registry_users.split(","):
            entry = entry.strip()
            if ":" not in entry:
                continue
            username, _, password = entry.partition(":")
            username = username.strip()
            password = password.strip()
            if username and password:
                self._users[username] = _hash_password(password)

    def add_user(self, username: str, password: str) -> None:
        """Add or overwrite a user."""
        self._users[username] = _hash_password(password)

    def authenticate(self, username: str, password: str) -> bool:
        """Return True if credentials are valid."""
        stored = self._users.get(username)
        if stored is None:
            return False
        return _verify_password(password, stored)

    def exists(self, username: str) -> bool:
        return username in self._users


# Module-level singleton
user_store = UserStore()
