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


@router.put("/{test_id}", response_model=schemas.FlightTestResponse)
async def update_flight_test(
    test_id: int,
    flight_test: schemas.FlightTestUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(auth.get_current_active_user),
):
    """
    Update a flight test owned by the current user.
    """
    db_flight_test = (
        db.query(FlightTest)
        .filter(
            and_(FlightTest.id == test_id, FlightTest.created_by_id == current_user.id)
        )
        .first()
    )

    if not db_flight_test:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Flight test not found"
        )

    update_data = flight_test.model_dump(exclude_unset=True)
    if "test_name" in update_data:
        existing = (
            db.query(FlightTest)
            .filter(
                and_(
                    FlightTest.test_name == update_data["test_name"],
                    FlightTest.created_by_id == current_user.id,
                    FlightTest.id != test_id,
                )
            )
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Flight test with name '{update_data['test_name']}' already exists",
            )

    for key, value in update_data.items():
        setattr(db_flight_test, key, value)

    db.add(db_flight_test)
    db.commit()
    db.refresh(db_flight_test)

    return db_flight_test


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
    Upload CSV file with flight test data.
    Expected format: row 1 = parameter names, row 2 = units, rows 3+ = data.
    Uses batched inserts and a pre-built parameter cache to handle large files
    without blocking the server or exhausting the DB connection pool.
    """
    MAX_ROWS = 100_000
    BATCH_SIZE = 1_000

    # Verify flight test exists and belongs to the current user
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

    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be a CSV file",
        )

    try:
        contents = await file.read()
        try:
            text = contents.decode("utf-8")
        except UnicodeDecodeError:
            text = contents.decode("latin-1")

        lines = text.splitlines()
        if len(lines) < 3:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="CSV file must have at least 3 rows (header, units, data)",
            )

        header_row = lines[0]
        units_row = lines[1]

        # Build parameter-name → unit mapping from the first two rows
        headers = [h.strip() for h in header_row.split(",")]
        units_list = [u.strip() for u in units_row.split(",")]
        param_units: dict[str, str] = {
            headers[i]: (units_list[i] if i < len(units_list) else "")
            for i in range(len(headers))
        }

        # ── Pre-load all existing parameters into a cache (1 query) ──────────
        existing_params = db.query(TestParameter).all()
        param_cache: dict[str, TestParameter] = {p.name: p for p in existing_params}

        # Identify which parameter names appear in this CSV (skip timestamp cols)
        TIMESTAMP_COLS = {"timestamp", "time", "description"}
        data_col_names = [
            h for h in headers if h.lower() not in TIMESTAMP_COLS and h
        ]

        # Create any missing parameters in a single batch
        new_params: list[TestParameter] = []
        for col in data_col_names:
            if col not in param_cache:
                p = TestParameter(
                    name=col,
                    description=col,
                    unit=param_units.get(col, ""),
                )
                db.add(p)
                new_params.append(p)
        if new_params:
            db.flush()  # assigns IDs to all new params in one round-trip
            for p in new_params:
                param_cache[p.name] = p

        # ── Parse data rows ───────────────────────────────────────────────────
        csv_data_only = io.StringIO(header_row + "\n" + "\n".join(lines[2:]))
        csv_reader = csv.DictReader(csv_data_only)

        base_date = datetime(2025, 8, 6, 0, 0, 0)
        row_count = 0
        total_data_points = 0
        batch: list[DataPoint] = []

        def _parse_timestamp(ts_str: str, fallback_offset: float) -> datetime:
            """Parse the custom Day:HH:MM:SS.mmm format or a plain float offset."""
            ts_str = ts_str.strip()
            try:
                return base_date + timedelta(seconds=float(ts_str))
            except ValueError:
                pass
            try:
                parts = ts_str.split(":")
                if len(parts) == 4:
                    day = int(parts[0])
                    hour = int(parts[1])
                    minute = int(parts[2])
                    sec_parts = parts[3].split(".")
                    second = int(sec_parts[0])
                    millisecond = int(sec_parts[1]) if len(sec_parts) > 1 else 0
                    return base_date + timedelta(
                        days=day, hours=hour, minutes=minute,
                        seconds=second, milliseconds=millisecond,
                    )
            except (ValueError, IndexError):
                pass
            return base_date + timedelta(seconds=fallback_offset)

        for row in csv_reader:
            row_count += 1
            if row_count > MAX_ROWS:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"File exceeds the {MAX_ROWS:,} row limit. "
                           "Please split the file and upload in parts.",
                )

            ts_raw = (
                row.get("timestamp")
                or row.get("Timestamp")
                or row.get("TIME")
                or row.get("Description")
                or ""
            ).strip()
            if not ts_raw:
                continue  # skip rows with no timestamp rather than aborting

            parsed_ts = _parse_timestamp(ts_raw, row_count * 0.1)

            for col in data_col_names:
                value_str = (row.get(col) or "").strip()
                if not value_str:
                    continue
                try:
                    value = float(value_str)
                except ValueError:
                    continue

                param = param_cache.get(col)
                if param is None:
                    continue  # should not happen after pre-load, but guard anyway

                batch.append(
                    DataPoint(
                        flight_test_id=test_id,
                        parameter_id=param.id,
                        timestamp=parsed_ts,
                        value=value,
                    )
                )

            # Flush a batch to the DB every BATCH_SIZE data points
            if len(batch) >= BATCH_SIZE:
                db.bulk_save_objects(batch)
                db.flush()
                total_data_points += len(batch)
                batch = []

        # Insert any remaining data points
        if batch:
            db.bulk_save_objects(batch)
            total_data_points += len(batch)

        db.commit()

        return {
            "message": "CSV data uploaded successfully",
            "rows_processed": row_count,
            "data_points_created": total_data_points,
        }

    except HTTPException:
        raise
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
