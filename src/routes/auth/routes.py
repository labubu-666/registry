"""Docker Registry v2 Token Authentication endpoint.

Implements: https://docs.docker.com/registry/spec/auth/token/

Docker login flow:
  1. Client hits GET /v2/ → 401 with WWW-Authenticate pointing here
  2. Docker sends GET /auth/token?service=<svc>&scope=<scope> with Basic Auth
  3. We validate credentials and return a JWT
  4. Docker retries the original request with Bearer <token>
"""

import base64
import logging
from typing import Optional

from fastapi import APIRouter, Header, Query, Response
from fastapi.responses import JSONResponse

from src.settings import settings
from src.auth.token_service import create_token
from src.auth.user import ANONYMOUS_USER, user_store

logger = logging.getLogger(__name__)

auth_router = APIRouter(prefix="", tags=["Authentication"])


def _decode_basic(authorization: str) -> tuple[str, str] | None:
    """Parse an HTTP Basic Authorization header.

    Returns ``(username, password)`` or ``None`` if the header is invalid.
    """
    if not authorization.lower().startswith("basic "):
        return None
    try:
        decoded = base64.b64decode(authorization[6:]).decode()
        username, _, password = decoded.partition(":")
        return username, password
    except Exception:
        return None


@auth_router.get("/auth/token")
async def token(
    service: Optional[str] = Query(default=None),
    scope: Optional[str] = Query(default=None),
    account: Optional[str] = Query(default=None),
    authorization: Optional[str] = Header(default=None),
) -> Response:
    """Issue a JWT for Docker clients.

    - No Authorization header → anonymous token
    - Valid Basic Auth credentials → token for that user
    - Invalid credentials → 401
    """
    # --- Determine the identity ---
    if authorization:
        creds = _decode_basic(authorization)
        if creds is None:
            return Response(status_code=400, content="Malformed Authorization header")

        username, password = creds

        if not user_store.authenticate(username, password):
            logger.warning("Failed login attempt for user %r", username)
            return JSONResponse(
                status_code=401,
                content={
                    "errors": [
                        {"code": "UNAUTHORIZED", "message": "invalid credentials"}
                    ]
                },
            )
        logger.info("Authenticated user %r", username)
    else:
        # No credentials → anonymous access
        username = account or ANONYMOUS_USER
        logger.debug("Issuing anonymous token for account=%r", account)

    # --- Build access list from scope parameter (e.g. "repository:alpine:pull") ---
    access: list[dict[str, object]] = []
    if scope:
        # scope format: "resource_type:resource_name:actions"
        parts = scope.split(":", 2)
        if len(parts) == 3:
            resource_type, resource_name, actions_str = parts
            actions = [a for a in actions_str.split(",") if a]
            access.append(
                {
                    "type": resource_type,
                    "name": resource_name,
                    "actions": actions,
                }
            )

    token_str = create_token(subject=username, access=access)

    return JSONResponse(
        content={
            "token": token_str,
            "access_token": token_str,  # some clients expect this field too
            "expires_in": settings.auth_token_expiration,
            "issued_at": None,  # optional; omitted for brevity
        }
    )
