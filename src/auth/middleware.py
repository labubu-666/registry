from typing import Annotated

from fastapi import Depends, Header

from .token_service import get_subject
from .user import ANONYMOUS_USER


def get_current_user(authorization: Annotated[str | None, Header()] = None) -> str:
    """Extract the authenticated username from a Bearer token.

    Returns the username from the JWT token, or ``anonymous`` if no valid
    token is present.  This never raises — unauthenticated callers simply
    receive the anonymous identity.
    """
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[len("bearer ") :]
        subject = get_subject(token)
        if subject:
            return subject
    return ANONYMOUS_USER


CurrentUser = Annotated[str, Depends(get_current_user)]
