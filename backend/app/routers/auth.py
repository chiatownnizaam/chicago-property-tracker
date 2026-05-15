"""
Auth endpoints:
  POST /auth/login           — username+password (+ totp_code after enrollment)
  GET  /auth/me              — current user info
  POST /auth/setup-totp      — generate a TOTP secret + QR (called once)
  POST /auth/confirm-totp    — verify a 6-digit code, mark TOTP confirmed
"""
import logging
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.database import get_db
from app.models.user import User
from app.config import settings
from app.auth.security import (
    verify_password,
    create_access_token,
    generate_totp_secret,
    verify_totp,
    provisioning_uri,
    qr_code_data_url,
)
from app.auth.deps import get_current_user, get_user_for_setup
from app.schemas.auth import (
    LoginRequest,
    TokenResponse,
    TOTPSetupResponse,
    TOTPConfirmRequest,
    MeResponse,
)

log = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address)
router = APIRouter(prefix="/auth", tags=["auth"])

LOCKOUT_DURATION = timedelta(minutes=15)


def _is_locked(user: User) -> bool:
    return user.locked_until is not None and user.locked_until > datetime.utcnow()


def _record_failed_login(db: Session, user: User) -> None:
    user.failed_attempts = (user.failed_attempts or 0) + 1
    if user.failed_attempts >= settings.LOGIN_LOCKOUT_THRESHOLD:
        user.locked_until = datetime.utcnow() + LOCKOUT_DURATION
        log.warning(f"User {user.username} locked until {user.locked_until}")
    db.commit()


def _record_successful_login(db: Session, user: User) -> None:
    user.failed_attempts = 0
    user.locked_until = None
    user.last_login_at = datetime.utcnow()
    db.commit()


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
def login(request: Request, payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == payload.username).first()

    if not user or not verify_password(payload.password, user.password_hash):
        if user:
            _record_failed_login(db, user)
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if _is_locked(user):
        raise HTTPException(
            status_code=423,
            detail=f"Account locked until {user.locked_until.isoformat()}Z",
        )

    # First-time login: no TOTP confirmed yet. Issue a setup-only token.
    if not user.totp_confirmed:
        token = create_access_token(
            user.username,
            extra={"totp_verified": False, "setup_only": True},
        )
        _record_successful_login(db, user)
        return TokenResponse(access_token=token, requires_totp_setup=True)

    # Normal login: TOTP code required.
    if not payload.totp_code or not verify_totp(user.totp_secret, payload.totp_code):
        _record_failed_login(db, user)
        raise HTTPException(status_code=401, detail="Invalid TOTP code")

    _record_successful_login(db, user)
    token = create_access_token(user.username, extra={"totp_verified": True})
    return TokenResponse(access_token=token, requires_totp_setup=False)


@router.post("/setup-totp", response_model=TOTPSetupResponse)
def setup_totp(
    current_user: User = Depends(get_user_for_setup),
    db: Session = Depends(get_db),
):
    """
    Generate a fresh TOTP secret + QR code. Only allowed if the user has not
    already confirmed TOTP — call this only during initial enrollment.
    """
    if current_user.totp_confirmed:
        raise HTTPException(status_code=400, detail="TOTP already configured")

    secret = generate_totp_secret()
    current_user.totp_secret = secret
    db.commit()

    uri = provisioning_uri(secret, current_user.username)
    return TOTPSetupResponse(
        secret=secret,
        qr_code_data_url=qr_code_data_url(uri),
        provisioning_uri=uri,
    )


@router.post("/confirm-totp", response_model=TokenResponse)
def confirm_totp(
    payload: TOTPConfirmRequest,
    current_user: User = Depends(get_user_for_setup),
    db: Session = Depends(get_db),
):
    """Verify the 6-digit code from MS Authenticator and mark TOTP confirmed."""
    if current_user.totp_confirmed:
        raise HTTPException(status_code=400, detail="TOTP already confirmed")
    if not current_user.totp_secret:
        raise HTTPException(status_code=400, detail="Call /auth/setup-totp first")
    if not verify_totp(current_user.totp_secret, payload.totp_code):
        raise HTTPException(status_code=401, detail="Invalid TOTP code")

    current_user.totp_confirmed = True
    db.commit()

    token = create_access_token(current_user.username, extra={"totp_verified": True})
    return TokenResponse(access_token=token, requires_totp_setup=False)


@router.get("/me", response_model=MeResponse)
def me(current_user: User = Depends(get_current_user)):
    return current_user
