import time
from typing import Any

from jose import JWTError, jwt

from src.settings import settings

ALGORITHM = "HS256"


def create_token(
    subject: str,
    access: list[dict[str, Any]] | None = None,
) -> str:
    """Create a JWT token for the given subject with optional access claims."""
    now = int(time.time())
    payload: dict[str, Any] = {
        "iss": settings.auth_issuer,
        "sub": subject,
        "aud": settings.auth_service,
        "iat": now,
        "nbf": now,
        "exp": now + settings.auth_token_expiration,
        "access": access or [],
    }
    return jwt.encode(payload, settings.auth_secret_key, algorithm=ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT token. Raises JWTError on failure."""
    return jwt.decode(
        token,
        settings.auth_secret_key,
        algorithms=[ALGORITHM],
        audience=settings.auth_service,
    )


def get_subject(token: str) -> str | None:
    """Return the subject (username) from a token, or None if invalid."""
    try:
        payload = decode_token(token)
        return payload.get("sub")
    except JWTError:
        return None
