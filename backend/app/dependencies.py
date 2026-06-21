"""
FastAPI dependencies for authentication.
"""

from fastapi import Cookie, Depends, HTTPException, status
from jose import JWTError

from app.services.auth import decode_access_token

COOKIE_NAME = "session"


def get_current_user(session: str | None = Cookie(default=None, alias=COOKIE_NAME)) -> dict:
    """
    Extract and validate the JWT from the HttpOnly session cookie.
    Returns the decoded user payload or raises 401.
    """
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    try:
        payload = decode_access_token(session)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
        )
    return {
        "supplier_id": payload["supplier_id"],
        "supplier_name": payload["supplier_name"],
        "email": payload["sub"],
    }


def get_current_supplier_id(user: dict = Depends(get_current_user)) -> str:
    """Convenience dependency that returns only the supplier_id string."""
    return user["supplier_id"]
