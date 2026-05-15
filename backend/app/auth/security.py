"""
Authentication primitives: password hashing, JWT issuance/decoding,
TOTP secret generation/verification, and provisioning QR codes.
"""
import base64
import io
from datetime import datetime, timedelta, timezone
from typing import Optional

import pyotp
import qrcode
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 12


# ---- Password hashing ----------------------------------------------------

def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ---- JWT issuance --------------------------------------------------------

def create_access_token(subject: str, extra: Optional[dict] = None) -> str:
    payload = {
        "sub": subject,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None


# ---- TOTP ----------------------------------------------------------------

def generate_totp_secret() -> str:
    """Random base32 secret compatible with all TOTP apps."""
    return pyotp.random_base32()


def verify_totp(secret: str, code: str) -> bool:
    """Accepts 6-digit code with +/- 1 step tolerance (~30s skew)."""
    if not secret or not code:
        return False
    code = code.strip().replace(" ", "")
    if not code.isdigit() or len(code) != 6:
        return False
    return pyotp.TOTP(secret).verify(code, valid_window=1)


def provisioning_uri(secret: str, username: str, issuer: str = "Chicago Property Tracker") -> str:
    """otpauth:// URI that MS Authenticator scans to register the account."""
    return pyotp.TOTP(secret).provisioning_uri(name=username, issuer_name=issuer)


def qr_code_data_url(provisioning_uri_str: str) -> str:
    """PNG QR code rendered as a data:image/png;base64 URL — embedable in JSON."""
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=2,
    )
    qr.add_data(provisioning_uri_str)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")
