from pydantic import BaseModel
from typing import Optional


class LoginRequest(BaseModel):
    username: str
    password: str
    totp_code: Optional[str] = None   # required only if user has confirmed TOTP


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    requires_totp_setup: bool = False


class TOTPSetupResponse(BaseModel):
    secret: str                # base32 — also encoded in the QR
    qr_code_data_url: str      # data:image/png;base64,... — show as <img src=...>
    provisioning_uri: str      # for manual entry into authenticator apps


class TOTPConfirmRequest(BaseModel):
    totp_code: str


class MeResponse(BaseModel):
    username: str
    is_admin: bool
    totp_confirmed: bool

    model_config = {"from_attributes": True}
