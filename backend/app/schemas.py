"""
FTIAS Backend - Pydantic Schemas
Data validation and serialization schemas
"""

from datetime import date, datetime, time
from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


class UserBase(BaseModel):
    """Base user schema"""

    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50)
    full_name: Optional[str] = None


class UserCreate(UserBase):
    """Schema for creating a user"""

    password: str = Field(..., min_length=8, max_length=100)


class UserUpdate(BaseModel):
    """Schema for updating a user"""

    email: Optional[EmailStr] = None
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    full_name: Optional[str] = None
    password: Optional[str] = Field(None, min_length=8, max_length=100)


class UserResponse(UserBase):
    """Schema for user response"""

    id: int
    is_active: bool
    is_superuser: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class HealthResponse(BaseModel):
    """Schema for health check response"""

    status: str
    database: str
    timestamp: datetime


# Authentication Schemas


class Token(BaseModel):
    """Schema for JWT token response"""

    access_token: str
    refresh_token: Optional[str] = None
    token_type: str


class TokenData(BaseModel):
    """Schema for token data"""

    user_id: Optional[int] = None


class LoginRequest(BaseModel):
    """Schema for login request"""

    username: str
    password: str


class RefreshRequest(BaseModel):
    """Schema for refresh-token request"""

    refresh_token: str


# Flight Test Schemas


class FlightTestBase(BaseModel):
    """Base flight test schema"""

    test_name: str = Field(..., min_length=1, max_length=255)
    aircraft_type: Optional[str] = Field(None, max_length=100)
    test_date: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    description: Optional[str] = None

    @field_validator("test_date", mode="before")
    @classmethod
    def parse_test_date(cls, value):
        """Accept either a datetime or a YYYY-MM-DD date string."""
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, date):
            return datetime.combine(value, time.min)
        if isinstance(value, str):
            try:
                # Full ISO datetime
                return datetime.fromisoformat(value)
            except ValueError:
                # Date-only
                return datetime.combine(date.fromisoformat(value), time.min)
        return value


class FlightTestCreate(FlightTestBase):
    """Schema for creating a flight test"""

    pass


class FlightTestUpdate(BaseModel):
    """Schema for updating a flight test"""

    test_name: Optional[str] = Field(None, min_length=1, max_length=255)
    aircraft_type: Optional[str] = Field(None, max_length=100)
    test_date: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    description: Optional[str] = None

    @field_validator("test_date", mode="before")
    @classmethod
    def parse_test_date(cls, value):
        """Accept either a datetime or a YYYY-MM-DD date string."""
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, date):
            return datetime.combine(value, time.min)
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                return datetime.combine(date.fromisoformat(value), time.min)
        return value


class FlightTestResponse(FlightTestBase):
    """Schema for flight test response"""

    id: int
    created_by_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# Test Parameter Schemas


class TestParameterBase(BaseModel):
    """Base test parameter schema"""

    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    unit: Optional[str] = Field(None, max_length=50)
    system: Optional[str] = Field(None, max_length=100)
    category: Optional[str] = Field(None, max_length=100)
    min_value: Optional[float] = None
    max_value: Optional[float] = None


class TestParameterCreate(TestParameterBase):
    """Schema for creating a test parameter"""

    pass


class TestParameterUpdate(BaseModel):
    """Schema for updating a test parameter"""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    unit: Optional[str] = Field(None, max_length=50)
    system: Optional[str] = Field(None, max_length=100)
    category: Optional[str] = Field(None, max_length=100)
    min_value: Optional[float] = None
    max_value: Optional[float] = None


class TestParameterResponse(TestParameterBase):
    """Schema for test parameter response"""

    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class BulkParametersCreateRequest(BaseModel):
    parameters: List[TestParameterCreate]


class BulkParameterUpdateItem(BaseModel):
    id: int
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    unit: Optional[str] = Field(None, max_length=50)
    system: Optional[str] = Field(None, max_length=100)
    category: Optional[str] = Field(None, max_length=100)
    min_value: Optional[float] = None
    max_value: Optional[float] = None


class BulkParametersUpdateRequest(BaseModel):
    parameters: List[BulkParameterUpdateItem]


class BulkParametersDeleteRequest(BaseModel):
    parameter_ids: List[int]


# Data Point Schemas


class DataPointBase(BaseModel):
    """Base data point schema"""

    flight_test_id: int
    parameter_id: int
    timestamp: datetime
    value: float


class DataPointCreate(DataPointBase):
    """Schema for creating a data point"""

    pass


class DataPointResponse(DataPointBase):
    """Schema for data point response"""

    id: int
    created_at: datetime

    class Config:
        from_attributes = True
