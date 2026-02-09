"""
FTIAS Backend - Flight Tests Router
Flight test data management and CSV upload endpoints
"""

import csv
import io
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import and_
from sqlalchemy.orm import Session

from app import auth, schemas
from app.database import get_db
from app.models import DataPoint, FlightTest, TestParameter, User

router = APIRouter()


@router.post("/", response_model=schemas.FlightTestResponse, status_code=status.HTTP_201_CREATED)
async def create_flight_test(
    flight_test: schemas.FlightTestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(auth.get_current_active_user),
):
    """
    Create a new flight test
    """
    # Check if test name already exists for this user
    existing = (
        db.query(FlightTest)
        .filter(
            and_(
                FlightTest.test_name == flight_test.test_name,
                FlightTest.created_by_id == current_user.id,
            )
        )
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Flight test with name '{flight_test.test_name}' already exists",
        )

    # Create new flight test
    db_flight_test = FlightTest(**flight_test.model_dump(), created_by_id=current_user.id)
    db.add(db_flight_test)
    db.commit()
    db.refresh(db_flight_test)

    return db_flight_test


@router.get("/", response_model=List[schemas.FlightTestResponse])
async def get_flight_tests(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(auth.get_current_active_user),
):
    """
    Get all flight tests for current user
    """
    flight_tests = (
        db.query(FlightTest)
        .filter(FlightTest.created_by_id == current_user.id)
        .offset(skip)
        .limit(limit)
        .all()
    )

    return flight_tests


@router.get("/{test_id}", response_model=schemas.FlightTestResponse)
async def get_flight_test(
    test_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(auth.get_current_active_user),
):
    """
    Get a specific flight test by ID
    """
    flight_test = (
        db.query(FlightTest)
        .filter(
            and_(FlightTest.id == test_id, FlightTest.created_by_id == current_user.id)
        )
        .first()
    )

    if not flight_test:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Flight test not found"
        )

    return flight_test


@router.delete("/{test_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_flight_test(
    test_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(auth.get_current_active_user),
):
    """
    Delete a flight test and all associated data points
    """
    flight_test = (
        db.query(FlightTest)
        .filter(
            and_(FlightTest.id == test_id, FlightTest.created_by_id == current_user.id)
        )
        .first()
    )

    if not flight_test:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Flight test not found"
        )

    db.delete(flight_test)
    db.commit()

    return None


@router.post("/{test_id}/upload-csv", status_code=status.HTTP_201_CREATED)
async def upload_flight_data_csv(
    test_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(auth.get_current_active_user),
):
    """
    Upload CSV file with flight test data
    Expected format: timestamp, parameter1, parameter2, ...
    """
    # Verify flight test exists and belongs to user
    flight_test = (
        db.query(FlightTest)
        .filter(
            and_(FlightTest.id == test_id, FlightTest.created_by_id == current_user.id)
        )
        .first()
    )

    if not flight_test:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Flight test not found"
        )

    # Verify file is CSV
    if not file.filename.endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be a CSV file",
        )

    try:
        # Read CSV file
        contents = await file.read()
        csv_data = io.StringIO(contents.decode("utf-8"))
        
        # Read all lines
        lines = csv_data.getvalue().split('\n')
        if len(lines) < 3:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="CSV file must have at least 3 rows (headers + data)",
            )
        
        # First row: parameter names
        # Second row: units
        # Third row onwards: data
        header_row = lines[0]
        units_row = lines[1]
        
        # Parse headers and units
        headers = header_row.split(',')
        units = units_row.split(',')
        
        # Create a mapping of parameter names to units
        param_units = {}
        for i, header in enumerate(headers):
            if i < len(units):
                param_units[header.strip()] = units[i].strip()
        
        # Parse data rows (skip first 2 rows)
        csv_data_only = io.StringIO('\n'.join([header_row] + lines[2:]))
        csv_reader = csv.DictReader(csv_data_only)

        # Get or create parameters
        data_points = []
        row_count = 0

        for row in csv_reader:
            row_count += 1

            # Extract timestamp
            timestamp = row.get("timestamp") or row.get("Timestamp") or row.get("TIME") or row.get("Description")
            if not timestamp:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Missing timestamp in row {row_count}",
                )

            # Process each parameter in the row
            for param_name, value_str in row.items():
                if param_name.lower() in ["timestamp", "time", "description"]:
                    continue

                # Skip empty values
                if not value_str or value_str.strip() == "":
                    continue

                # Get or create parameter
                parameter = (
                    db.query(TestParameter)
                    .filter(TestParameter.name == param_name)
                    .first()
                )

                if not parameter:
                    # Create new parameter with unit from CSV
                    unit = param_units.get(param_name, "")
                    parameter = TestParameter(
                        name=param_name,
                        description=param_name,
                        unit=unit,
                    )
                    db.add(parameter)
                    db.flush()  # Get the ID

                # Parse value
                try:
                    value = float(value_str)
                except ValueError:
                    continue  # Skip non-numeric values

                # Parse timestamp
                try:
                    # Try parsing as float first
                    ts_float = float(timestamp)
                    # Use base date + seconds offset
                    base_date = datetime(2025, 8, 6, 0, 0, 0)
                    parsed_timestamp = base_date + timedelta(seconds=ts_float)
                except ValueError:
                    # Try parsing custom format: Day:Hour:Minute:Second.Millisecond
                    try:
                        parts = timestamp.split(':')
                        if len(parts) == 4:
                            day = int(parts[0])
                            hour = int(parts[1])
                            minute = int(parts[2])
                            sec_ms = parts[3].split('.')
                            second = int(sec_ms[0])
                            millisecond = int(sec_ms[1]) if len(sec_ms) > 1 else 0
                            
                            # Convert to datetime (use day as offset from base date)
                            base_date = datetime(2025, 8, 6, 0, 0, 0)
                            parsed_timestamp = base_date + timedelta(
                                days=day,
                                hours=hour,
                                minutes=minute,
                                seconds=second,
                                milliseconds=millisecond
                            )
                        else:
                            # Fallback: use current time + row offset
                            base_date = datetime(2025, 8, 6, 0, 0, 0)
                            parsed_timestamp = base_date + timedelta(seconds=row_count * 0.1)
                    except:
                        # Last fallback
                        base_date = datetime(2025, 8, 6, 0, 0, 0)
                        parsed_timestamp = base_date + timedelta(seconds=row_count * 0.1)
                
                # Create data point
                data_point = DataPoint(
                    flight_test_id=test_id,
                    parameter_id=parameter.id,
                    timestamp=parsed_timestamp,
                    value=value,
                )
                data_points.append(data_point)

        # Bulk insert data points
        if data_points:
            db.bulk_save_objects(data_points)
            db.commit()

        return {
            "message": "CSV data uploaded successfully",
            "rows_processed": row_count,
            "data_points_created": len(data_points),
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing CSV file: {str(e)}",
        )


@router.get("/{test_id}/data", response_model=List[schemas.DataPointResponse])
async def get_flight_test_data(
    test_id: int,
    parameter_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 1000,
    db: Session = Depends(get_db),
    current_user: User = Depends(auth.get_current_active_user),
):
    """
    Get data points for a flight test, optionally filtered by parameter
    """
    # Verify flight test exists and belongs to user
    flight_test = (
        db.query(FlightTest)
        .filter(
            and_(FlightTest.id == test_id, FlightTest.created_by_id == current_user.id)
        )
        .first()
    )

    if not flight_test:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Flight test not found"
        )

    # Build query
    query = db.query(DataPoint).filter(DataPoint.flight_test_id == test_id)

    if parameter_id:
        query = query.filter(DataPoint.parameter_id == parameter_id)

    # Get data points
    data_points = query.order_by(DataPoint.timestamp).offset(skip).limit(limit).all()

    return data_points
