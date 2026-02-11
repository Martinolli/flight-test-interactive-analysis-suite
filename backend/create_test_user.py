"""
Create a test user for FTIAS
"""

from sqlalchemy.exc import SQLAlchemyError

from app.auth import get_password_hash
from app.database import SessionLocal
from app.models import User


def create_test_user():
    db = SessionLocal()
    try:
        # Check if user already exists
        existing_user = (
            db.query(User)
            .filter(User.email == "test@ftias.com")
            .first()
        )
        if existing_user:
            print("✅ Test user already exists!")
            print("   Email: test@ftias.com")
            print("   Password: testpass123")
            return

        # Create new user
        user = User(
            email="test@ftias.com",
            username="testuser",
            full_name="Test User",
            hashed_password=get_password_hash("testpass123"),
            is_active=True,
            is_superuser=False,
        )
        db.add(user)
        db.commit()
        print("✅ Test user created successfully!")
        print("   Email: test@ftias.com")
        print("   Password: testpass123")
    except (SQLAlchemyError, ValueError) as e:
        print(f"❌ Error creating user: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    create_test_user()
