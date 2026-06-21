"""
Authentication endpoints:
  POST /api/auth/login   — verify credentials, set HttpOnly JWT cookie
  POST /api/auth/logout  — clear cookie
  GET  /api/auth/me      — return session info for frontend bootstrap
"""

import sys
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel
from sqlalchemy import text

from app.dependencies import COOKIE_NAME, get_current_user
from app.services.auth import create_access_token, verify_password

# Reuse the same session factory as the rest of the backend
_project_root = Path(__file__).resolve().parent.parent.parent.parent
_backend_root = _project_root / "backend"
for p in (str(_project_root), str(_backend_root)):
    if p not in sys.path:
        sys.path.insert(0, p)

from mcp_server.db import get_session  # noqa: E402

router = APIRouter(prefix="/api/auth", tags=["auth"])

_COOKIE_MAX_AGE = 8 * 3600  # 8 hours


class LoginRequest(BaseModel):
    email: str
    password: str


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        secure=False,   # localhost demo; set True behind HTTPS in production
        max_age=_COOKIE_MAX_AGE,
        path="/",
    )


@router.post("/login")
def login(req: LoginRequest, response: Response):
    """Verify credentials and set an HttpOnly session cookie."""
    db = get_session()
    try:
        row = db.execute(
            text("""
                SELECT u.password_hash, u.supplier_id, s.name AS supplier_name
                FROM users u
                JOIN suppliers s ON s.id = u.supplier_id
                WHERE u.email = :email
            """),
            {"email": req.email.lower().strip()},
        ).fetchone()
    finally:
        db.close()

    if not row or not verify_password(req.password, row.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    token = create_access_token(
        supplier_id=str(row.supplier_id),
        email=req.email.lower().strip(),
        supplier_name=row.supplier_name,
    )
    _set_session_cookie(response, token)
    return {
        "supplier_id": str(row.supplier_id),
        "supplier_name": row.supplier_name,
        "email": req.email.lower().strip(),
    }


@router.post("/logout")
def logout(response: Response):
    """Clear the session cookie."""
    response.delete_cookie(key=COOKIE_NAME, path="/", samesite="lax")
    return {"ok": True}


@router.get("/me")
def me(user: dict = Depends(get_current_user)):
    """Return current session info — used by the frontend to bootstrap auth state."""
    return user
