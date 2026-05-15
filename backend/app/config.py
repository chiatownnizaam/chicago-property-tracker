import secrets
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://postgres:password@localhost:5432/chicago_property_tracker"
    CHICAGO_DATA_PORTAL_APP_TOKEN: str = ""
    FRED_API_KEY: str = ""
    CORS_ORIGINS: str = "http://localhost:3000"
    # Used to sign JWTs. Auto-generated per process if not set, but you
    # MUST set this in production .env or sessions become invalid on
    # every restart and tokens won't survive a reboot.
    SECRET_KEY: str = secrets.token_urlsafe(64)
    # Number of consecutive failed logins before the account locks for 15 min.
    LOGIN_LOCKOUT_THRESHOLD: int = 5

    model_config = {"env_file": ".env"}


settings = Settings()
