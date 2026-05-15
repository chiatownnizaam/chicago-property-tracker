"""FastAPI dependencies that resolve the current user from a JWT.

Two flavors:
  - `get_current_user` — requires a fully-authenticated token (totp_verified=True).
    Use this on every business endpoint.
  - `get_user_for_setup` — accepts either a setup_only token (for first-time
    TOTP enrollment) or a fully-authenticated token.
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.auth.security import decode_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


def _user_from_token(token: str, db: Session) -> tuple[User, dict]:
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_token(token)
    if not payload or not payload.get("sub"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = db.query(User).filter(User.username == payload["sub"]).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user, payload


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    user, payload = _user_from_token(token, db)
    if not payload.get("totp_verified"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="MFA required",
        )
    return user


def get_user_for_setup(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Used by /auth/setup-totp and /auth/confirm-totp during enrollment."""
    user, _ = _user_from_token(token, db)
    return user
