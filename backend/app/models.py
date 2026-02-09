"""
FTIAS Backend - Database Models
SQLAlchemy ORM models
"""

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class User(Base):
    """User model"""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, unique=True, index=True, nullable=False)
    full_name = Column(String, nullable=True)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return (
            f"<User(id={self.id}, username={self.username}, "
            f"email={self.email})>"
        )


class FlightTest(Base):
    """Flight Test model - stores test metadata"""

    __tablename__ = "flight_tests"

    id = Column(Integer, primary_key=True, index=True)
    test_name = Column(String(255), nullable=False, index=True)
    aircraft_type = Column(String(100), nullable=True)
    test_date = Column(DateTime(timezone=True), nullable=True)
    duration_seconds = Column(Float, nullable=True)
    description = Column(Text, nullable=True)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    created_by = relationship("User", backref="flight_tests")
    data_points = relationship(
        "DataPoint",
        back_populates="flight_test",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return (
            f"<FlightTest(id={self.id}, test_name={self.test_name}, "
            f"test_date={self.test_date})>"
        )


class TestParameter(Base):
    """Test Parameter model - stores parameter metadata"""

    __tablename__ = "test_parameters"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, unique=True, index=True)
    description = Column(Text, nullable=True)
    unit = Column(String(50), nullable=True)
    system = Column(String(100), nullable=True, index=True)
    category = Column(String(100), nullable=True, index=True)
    min_value = Column(Float, nullable=True)
    max_value = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    data_points = relationship("DataPoint", back_populates="parameter")

    def __repr__(self):
        return (
            f"<TestParameter(id={self.id}, name={self.name}, "
            f"unit={self.unit})>"
        )


class DataPoint(Base):
    """Data Point model - stores time-series flight test data"""

    __tablename__ = "data_points"

    id = Column(Integer, primary_key=True, index=True)
    flight_test_id = Column(
        Integer,
        ForeignKey("flight_tests.id"),
        nullable=False,
        index=True,
    )
    parameter_id = Column(
        Integer,
        ForeignKey("test_parameters.id"),
        nullable=False,
        index=True,
    )
    timestamp = Column(
        DateTime(timezone=True), nullable=False, index=True
    )
    value = Column(Float, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    flight_test = relationship("FlightTest", back_populates="data_points")
    parameter = relationship("TestParameter", back_populates="data_points")

    def __repr__(self):
        return (
            f"<DataPoint(id={self.id}, "
            f"flight_test_id={self.flight_test_id}, "
            f"parameter_id={self.parameter_id}, "
            f"value={self.value})>"
        )
