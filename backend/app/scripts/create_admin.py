"""
Bootstrap a single admin user.

Usage:
  python -m app.scripts.create_admin <username> <password>

Run this once after creating the database. The user will see the QR code
on first login at the web UI.
"""
import sys
from app.database import SessionLocal
from app.models.user import User
from app.auth.security import hash_password


def main():
    if len(sys.argv) != 3:
        print("Usage: python -m app.scripts.create_admin <username> <password>")
        sys.exit(1)

    username, password = sys.argv[1], sys.argv[2]
    if len(password) < 12:
        print("ERROR: password must be at least 12 characters")
        sys.exit(1)

    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.username == username).first()
        if existing:
            existing.password_hash = hash_password(password)
            db.commit()
            print(f"✓ Updated password for existing user '{username}'")
            return

        user = User(
            username=username,
            password_hash=hash_password(password),
            is_admin=True,
        )
        db.add(user)
        db.commit()
        print(f"✓ Created admin user '{username}'")
        print(f"  Log in at the web UI to complete TOTP setup.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
