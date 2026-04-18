"""
FTIAS Backend - Flight Tests Router
Flight test data management and CSV upload endpoints
"""

import csv
import io
import re
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import and_, distinct, func
from sqlalchemy.orm import Session

from app import auth, schemas
from app.database import get_db
from app.models import (
    AnalysisJob,
    DataPoint,
    DatasetVersion,
    FlightTest,
    IngestionSession,
    TestParameter,
    User,
)

router = APIRouter()


def _persist_ingestion_failure(
    db: Session,
    *,
    session_id: int | None,
    dataset_version_id: int | None,
    error_message: str,
    row_count: int | None = None,
) -> None:
    """Persist failed ingestion state in a separate commit-safe step."""
    if not session_id:
        return
    session = (
        db.query(IngestionSession)
        .filter(IngestionSession.id == session_id)
        .first()
    )
    if not session:
        return
    session.status = "failed"
    session.error_message = error_message[:1024]
    session.error_log = error_message[:4000]
    if row_count is not None and row_count >= 0:
        session.row_count = row_count
    db.add(session)
    if dataset_version_id:
        dataset_version = (
            db.query(DatasetVersion)
            .filter(DatasetVersion.id == dataset_version_id)
            .first()
        )
        if dataset_version:
            dataset_version.status = "failed"
            db.add(dataset_version)
    db.commit()


def _resolve_dataset_version_id(
    *,
    db: Session,
    flight_test: FlightTest,
    dataset_version_id: int | None,
) -> int | None:
    """Resolve requested dataset version or default to active dataset version."""
    if dataset_version_id is not None:
        dataset_version = (
            db.query(DatasetVersion)
            .filter(
                DatasetVersion.id == dataset_version_id,
                DatasetVersion.flight_test_id == flight_test.id,
            )
            .first()
        )
        if not dataset_version:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Dataset version not found for this flight test",
            )
        return dataset_version.id
    return flight_test.active_dataset_version_id


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


@router.get(
    "/{test_id}/ingestion-sessions",
    response_model=List[schemas.IngestionSessionResponse],
)
async def list_ingestion_sessions(
    test_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(auth.get_current_active_user),
):
    """List persisted ingestion sessions for a flight test, newest first."""
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

    sessions = (
        db.query(IngestionSession)
        .filter(
            IngestionSession.flight_test_id == test_id,
            IngestionSession.uploaded_by_id == current_user.id,
        )
        .order_by(IngestionSession.created_at.desc())
        .all()
    )
    return sessions


@router.get(
    "/{test_id}/dataset-versions",
    response_model=List[schemas.DatasetVersionResponse],
)
async def list_dataset_versions(
    test_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(auth.get_current_active_user),
):
    """List dataset versions for a flight test, newest first."""
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

    versions = (
        db.query(DatasetVersion)
        .filter(DatasetVersion.flight_test_id == test_id)
        .order_by(DatasetVersion.version_number.desc(), DatasetVersion.id.desc())
        .all()
    )

    return [
        schemas.DatasetVersionResponse(
            id=v.id,
            flight_test_id=v.flight_test_id,
            version_number=v.version_number,
            label=v.label,
            status=v.status,
            row_count=v.row_count,
            data_points_count=v.data_points_count,
            source_session_id=v.source_session_id,
            created_by_id=v.created_by_id,
            created_at=v.created_at,
            updated_at=v.updated_at,
            is_active=(flight_test.active_dataset_version_id == v.id),
        )
        for v in versions
    ]


@router.post(
    "/{test_id}/dataset-versions/{dataset_version_id}/activate",
    response_model=schemas.FlightTestResponse,
)
async def activate_dataset_version(
    test_id: int,
    dataset_version_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(auth.get_current_active_user),
):
    """Set active dataset version for a flight test."""
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

    dataset_version = (
        db.query(DatasetVersion)
        .filter(
            DatasetVersion.id == dataset_version_id,
            DatasetVersion.flight_test_id == test_id,
        )
        .first()
    )
    if not dataset_version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dataset version not found for this flight test",
        )
    if dataset_version.status != "success":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only successful dataset versions can be activated.",
        )

    flight_test.active_dataset_version_id = dataset_version.id
    db.add(flight_test)
    db.commit()
    db.refresh(flight_test)
    return flight_test


@router.get(
    "/{test_id}/ingestion-sessions/{session_id}",
    response_model=schemas.IngestionSessionResponse,
)
async def get_ingestion_session(
    test_id: int,
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(auth.get_current_active_user),
):
    """Get one ingestion session record scoped to current user + flight test."""
    session = (
        db.query(IngestionSession)
        .join(FlightTest, FlightTest.id == IngestionSession.flight_test_id)
        .filter(
            IngestionSession.id == session_id,
            IngestionSession.flight_test_id == test_id,
            IngestionSession.uploaded_by_id == current_user.id,
            FlightTest.created_by_id == current_user.id,
        )
        .first()
    )
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ingestion session not found",
        )
    return session


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
    Delete a flight test and all associated provenance/data records.
    Uses an explicit, transaction-safe delete sequence to avoid FK-order issues
    introduced by dataset versioning/provenance entities.
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

    try:
        # Break the direct FlightTest -> DatasetVersion linkage first so
        # downstream deletes cannot trip over active dataset FK ordering.
        flight_test.active_dataset_version_id = None
        db.add(flight_test)
        db.flush()

        # Delete dependent rows explicitly in a safe order for current model graph:
        # 1) data points
        # 2) analysis jobs
        # 3) ingestion sessions
        # 4) dataset versions
        # 5) flight test
        db.query(DataPoint).filter(DataPoint.flight_test_id == test_id).delete(
            synchronize_session=False
        )
        db.query(AnalysisJob).filter(AnalysisJob.flight_test_id == test_id).delete(
            synchronize_session=False
        )
        db.query(IngestionSession).filter(
            IngestionSession.flight_test_id == test_id
        ).delete(
            synchronize_session=False
        )
        db.query(DatasetVersion).filter(
            DatasetVersion.flight_test_id == test_id
        ).delete(
            synchronize_session=False
        )

        db.delete(flight_test)
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete flight test: {str(exc)}",
        ) from exc

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

    ingestion_session = IngestionSession(
        dataset_version_id=None,
        flight_test_id=test_id,
        filename=file.filename,
        file_type="csv",
        source_format="csv",
        row_count=None,
        status="processing",
        error_message=None,
        error_log=None,
        uploaded_by_id=current_user.id,
    )
    latest_version_number = (
        db.query(func.max(DatasetVersion.version_number))
        .filter(DatasetVersion.flight_test_id == test_id)
        .scalar()
        or 0
    )
    next_version_number = int(latest_version_number) + 1
    dataset_version = DatasetVersion(
        flight_test_id=test_id,
        version_number=next_version_number,
        label=f"v{next_version_number}",
        status="processing",
        row_count=None,
        data_points_count=None,
        created_by_id=current_user.id,
    )
    db.add(dataset_version)
    db.flush()
    ingestion_session.dataset_version_id = dataset_version.id
    db.add(ingestion_session)
    db.commit()
    db.refresh(ingestion_session)
    db.refresh(dataset_version)

    row_count = 0

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
        headers = [h.strip() for h in next(csv.reader([header_row]))]
        units_list = [u.strip() for u in next(csv.reader([units_row]))]
        if not headers:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="CSV header row is empty.",
            )

        timestamp_candidates = {"timestamp", "time", "description"}
        timestamp_col_name = next(
            (h for h in headers if h and h.strip().lower() in timestamp_candidates),
            None,
        )
        if not timestamp_col_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "CSV must contain a timestamp column. "
                    "Accepted names: timestamp, time, or description."
                ),
            )

        param_units: dict[str, str] = {
            headers[i]: (units_list[i] if i < len(units_list) else "")
            for i in range(len(headers))
        }

        # ── Pre-load all existing parameters into a cache (1 query) ──────────
        existing_params = db.query(TestParameter).all()
        param_cache: dict[str, TestParameter] = {p.name: p for p in existing_params}

        # Identify which parameter names appear in this CSV (skip timestamp cols)
        TIMESTAMP_COLS = timestamp_candidates
        data_col_names = [
            h for h in headers if h and h != timestamp_col_name and h.lower() not in TIMESTAMP_COLS
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
        total_data_points = 0
        batch: list[DataPoint] = []

        def _parse_timestamp(ts_str: str) -> datetime:
            """Parse supported timestamp formats or raise ValueError."""
            ts_str = ts_str.strip()
            if not ts_str:
                raise ValueError("missing timestamp value")

            # Numeric offset in seconds from base_date (legacy CSV format).
            try:
                return base_date + timedelta(seconds=float(ts_str))
            except ValueError:
                pass

            # Day:HH:MM:SS[.ffffff]
            day_format = re.match(
                r"^\s*(\d+):(\d{1,2}):(\d{1,2}):(\d{1,2})(?:\.(\d{1,6}))?\s*$",
                ts_str,
            )
            if day_format:
                day = int(day_format.group(1))
                hour = int(day_format.group(2))
                minute = int(day_format.group(3))
                second = int(day_format.group(4))
                fraction = day_format.group(5) or ""
                if hour >= 24 or minute >= 60 or second >= 60:
                    raise ValueError("out-of-range timestamp component")
                microseconds = int(fraction.ljust(6, "0")) if fraction else 0
                return base_date + timedelta(
                    days=day,
                    hours=hour,
                    minutes=minute,
                    seconds=second,
                    microseconds=microseconds,
                )

            # ISO datetime support when present in imported datasets.
            try:
                iso_value = ts_str.replace("Z", "+00:00")
                return datetime.fromisoformat(iso_value)
            except ValueError as exc:
                raise ValueError("unsupported timestamp format") from exc

        timestamp_errors: list[str] = []
        max_timestamp_errors = 10

        for row in csv_reader:
            row_count += 1
            if row_count > MAX_ROWS:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"File exceeds the {MAX_ROWS:,} row limit. "
                           "Please split the file and upload in parts.",
                )

            csv_row_number = row_count + 2  # include header + units rows
            ts_raw = (row.get(timestamp_col_name) or "").strip()
            if not ts_raw:
                if len(timestamp_errors) < max_timestamp_errors:
                    timestamp_errors.append(f"row {csv_row_number}: missing timestamp")
                continue

            try:
                parsed_ts = _parse_timestamp(ts_raw)
            except ValueError:
                if len(timestamp_errors) < max_timestamp_errors:
                    timestamp_errors.append(
                        f"row {csv_row_number}: invalid timestamp '{ts_raw}'"
                    )
                continue

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
                        dataset_version_id=dataset_version.id,
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

        if timestamp_errors:
            error_count = len(timestamp_errors)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Timestamp validation failed. "
                    f"Found {error_count} row error(s): " + "; ".join(timestamp_errors)
                ),
            )

        # Insert any remaining data points
        if batch:
            db.bulk_save_objects(batch)
            total_data_points += len(batch)

        ingestion_session.status = "success"
        ingestion_session.row_count = row_count
        ingestion_session.error_message = None
        ingestion_session.error_log = None
        dataset_version.status = "success"
        dataset_version.row_count = row_count
        dataset_version.data_points_count = total_data_points
        dataset_version.source_session_id = ingestion_session.id
        flight_test.active_dataset_version_id = dataset_version.id
        db.add(ingestion_session)
        db.add(dataset_version)
        db.add(flight_test)
        db.commit()

        return {
            "message": "CSV data uploaded successfully",
            "filename": file.filename,
            "rows_processed": row_count,
            "data_points_created": total_data_points,
            "previous_data_points_deleted": 0,
            "session_id": ingestion_session.id,
            "dataset_version_id": dataset_version.id,
            "dataset_version_label": dataset_version.label,
            "active_dataset_version_id": dataset_version.id,
        }

    except HTTPException as exc:
        db.rollback()
        _persist_ingestion_failure(
            db,
            session_id=ingestion_session.id,
            dataset_version_id=dataset_version.id,
            error_message=str(exc.detail),
            row_count=row_count,
        )
        raise
    except Exception as e:
        db.rollback()
        _persist_ingestion_failure(
            db,
            session_id=ingestion_session.id,
            dataset_version_id=dataset_version.id,
            error_message=f"Error processing CSV file: {str(e)}",
            row_count=row_count,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing CSV file: {str(e)}",
        )


@router.get("/{test_id}/data", response_model=List[schemas.DataPointResponse])
async def get_flight_test_data(
    test_id: int,
    parameter_id: Optional[int] = None,
    dataset_version_id: Optional[int] = Query(default=None),
    skip: int = 0,
    limit: int = 1000,
    db: Session = Depends(get_db),
    current_user: User = Depends(auth.get_current_active_user),
):
    """
    Get data points for a flight test, optionally filtered by parameter
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

    effective_dataset_version_id = _resolve_dataset_version_id(
        db=db,
        flight_test=flight_test,
        dataset_version_id=dataset_version_id,
    )

    query = db.query(DataPoint).filter(DataPoint.flight_test_id == test_id)
    if effective_dataset_version_id is not None:
        query = query.filter(DataPoint.dataset_version_id == effective_dataset_version_id)

    if parameter_id:
        query = query.filter(DataPoint.parameter_id == parameter_id)

    data_points = query.order_by(DataPoint.timestamp).offset(skip).limit(limit).all()
    return data_points


@router.get("/{test_id}/parameters")
async def get_flight_test_parameters(
    test_id: int,
    dataset_version_id: Optional[int] = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(auth.get_current_active_user),
):
    """
    Return the list of parameters that have data for this flight test,
    together with basic statistics (count, min, max, mean).
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

    effective_dataset_version_id = _resolve_dataset_version_id(
        db=db,
        flight_test=flight_test,
        dataset_version_id=dataset_version_id,
    )

    # One aggregation query: group data_points by parameter_id
    stats_query = (
        db.query(
            TestParameter.name,
            TestParameter.unit,
            TestParameter.description,
            func.count(DataPoint.id).label("sample_count"),
            func.min(DataPoint.value).label("min_value"),
            func.max(DataPoint.value).label("max_value"),
            func.avg(DataPoint.value).label("mean_value"),
        )
        .join(DataPoint, DataPoint.parameter_id == TestParameter.id)
        .filter(DataPoint.flight_test_id == test_id)
    )
    if effective_dataset_version_id is not None:
        stats_query = stats_query.filter(
            DataPoint.dataset_version_id == effective_dataset_version_id
        )
    rows = (
        stats_query
        .group_by(TestParameter.id, TestParameter.name, TestParameter.unit, TestParameter.description)
        .order_by(TestParameter.name)
        .all()
    )

    return [
        {
            "name": r.name,
            "unit": r.unit,
            "data_type": "float",
            "sample_count": r.sample_count,
            "min_value": r.min_value,
            "max_value": r.max_value,
            "mean_value": float(r.mean_value) if r.mean_value is not None else None,
        }
        for r in rows
    ]


@router.get("/{test_id}/parameters/data")
async def get_flight_test_parameter_data(
    test_id: int,
    parameters: Optional[List[str]] = Query(default=None),
    dataset_version_id: Optional[int] = Query(default=None),
    limit: int = 50000,
    db: Session = Depends(get_db),
    current_user: User = Depends(auth.get_current_active_user),
):
    """
    Return time-series data for one or more named parameters of a flight test.
    Query: ?parameters=altitude&parameters=airspeed
    Each series includes timestamps, values, and statistics.
    If the total number of points exceeds MAX_CHART_POINTS, the series is
    downsampled using min-max bucket decimation so peaks and valleys are preserved.
    """
    MAX_CHART_POINTS = 5000  # max points sent to the frontend per series

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

    effective_dataset_version_id = _resolve_dataset_version_id(
        db=db,
        flight_test=flight_test,
        dataset_version_id=dataset_version_id,
    )

    if not parameters:
        return []

    result = []
    for param_name in parameters:
        param = db.query(TestParameter).filter(TestParameter.name == param_name).first()
        if not param:
            continue

        points_query = (
            db.query(DataPoint)
            .filter(
                DataPoint.flight_test_id == test_id,
                DataPoint.parameter_id == param.id,
            )
        )
        if effective_dataset_version_id is not None:
            points_query = points_query.filter(
                DataPoint.dataset_version_id == effective_dataset_version_id
            )
        points = (
            points_query
            .order_by(DataPoint.timestamp)
            .limit(limit)
            .all()
        )

        if not points:
            continue

        values = [p.value for p in points]
        n = len(values)
        mean = sum(values) / n
        variance = sum((v - mean) ** 2 for v in values) / n
        std_dev = variance ** 0.5

        # ── Min-max bucket downsampling ───────────────────────────────────────
        # Preserves peaks and valleys so the chart shows the true signal shape
        # even when the raw series has tens of thousands of points.
        if n > MAX_CHART_POINTS:
            bucket_size = n / MAX_CHART_POINTS
            sampled = []
            i = 0
            while i < n:
                end = min(int(i + bucket_size), n)
                bucket = points[i:end]
                # Always keep the min and max of each bucket
                min_pt = min(bucket, key=lambda p: p.value)
                max_pt = max(bucket, key=lambda p: p.value)
                # Add in chronological order
                if min_pt.timestamp <= max_pt.timestamp:
                    sampled.append(min_pt)
                    if min_pt is not max_pt:
                        sampled.append(max_pt)
                else:
                    sampled.append(max_pt)
                    if min_pt is not max_pt:
                        sampled.append(min_pt)
                i = end
            chart_data = [
                {"timestamp": p.timestamp.isoformat(), "value": p.value}
                for p in sampled
            ]
        else:
            chart_data = [
                {"timestamp": p.timestamp.isoformat(), "value": p.value}
                for p in points
            ]

        result.append({
            "parameter_name": param.name,
            "unit": param.unit,
            "data": chart_data,
            "statistics": {
                "min": min(values),
                "max": max(values),
                "mean": mean,
                "std_dev": std_dev,
                "count": n,
            },
        })

    return result
