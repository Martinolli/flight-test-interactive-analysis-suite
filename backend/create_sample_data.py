"""
Create sample flight test data for testing
"""
from datetime import datetime, timedelta
from app.database import SessionLocal
from app.models import FlightTest, User


def create_sample_data():
    db = SessionLocal()
    try:
        # Get the test user
        user = db.query(User).filter(User.email == "test@ftias.com").first()
        if not user:
            print("❌ Test user not found. Please create test user first.")
            return

        # Check if data already exists
        existing = db.query(FlightTest).first()
        if existing:
            print("✅ Sample data already exists!")
            return

        # Create sample flight tests
        sample_tests = [
            {
                "test_name": "Test Flight for Data Points",
                "aircraft_type": "Test Aircraft",
                "test_date": datetime.now() - timedelta(days=1),
                "description": "Test",
                "status": "draft",
                "created_by_id": user.id
            },
            {
                "test_name": "Test Flight for Update",
                "aircraft_type": "Test Aircraft",
                "test_date": datetime.now() - timedelta(days=1),
                "description": "Updated Description",
                "status": "completed",
                "created_by_id": user.id
            },
            {
                "test_name": "Test Flight",
                "aircraft_type": "Boeing 737",
                "test_date": datetime.now() - timedelta(days=1),
                "description": "Test Description",
                "status": "draft",
                "created_by_id": user.id
            },
            {
                "test_name": "Test Flight for Get",
                "aircraft_type": "Test Aircraft",
                "test_date": datetime.now() - timedelta(days=1),
                "description": "Test",
                "status": "draft",
                "created_by_id": user.id
            },
            {
                "test_name": "High Altitude Performance Test",
                "aircraft_type": "Airbus A320",
                "test_date": datetime.now() - timedelta(days=5),
                "description": "Testing aircraft performance at high altitude",
                "status": "in_progress",
                "created_by_id": user.id
            },
            {
                "test_name": "Engine Stress Test",
                "aircraft_type": "Boeing 777",
                "test_date": datetime.now() - timedelta(days=10),
                "description": ("Full engine stress testing under "
                                "various conditions"),
                "status": "completed",
                "created_by_id": user.id
            }
        ]

        for test_data in sample_tests:
            flight_test = FlightTest(**test_data)
            db.add(flight_test)

        db.commit()
        print(f"✅ Created {len(sample_tests)} sample flight tests!")
        print("\nSample data:")
        for test in sample_tests:
            print(f"  - {test['test_name']} ({test['status']})")

    except (ValueError, TypeError, AttributeError) as e:
        print(f"❌ Error creating sample data: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    create_sample_data()
