"""
One-time script: reset testuser password to Ftias2026!
Run inside the Docker container:
  docker exec ftias-backend python reset_password.py
"""
import sys
import os

# Add /app to path so app.* imports work
sys.path.insert(0, "/app")

from app.auth import pwd_context
from app.database import SessionLocal
from app.models import User

NEW_PASSWORD = "Ftias2026!"
USERNAME = "testuser"

db = SessionLocal()
try:
    user = db.query(User).filter(User.username == USERNAME).first()
    if not user:
        print(f"ERROR: user '{USERNAME}' not found")
        sys.exit(1)

    new_hash = pwd_context.hash(NEW_PASSWORD)
    user.hashed_password = new_hash
    db.commit()
    print(f"Password for '{USERNAME}' reset successfully.")
    print(f"New hash: {new_hash}")

    # Verify it works
    ok = pwd_context.verify(NEW_PASSWORD, new_hash)
    print(f"Verification: {'PASS' if ok else 'FAIL'}")
finally:
    db.close()
