"""
FTIAS Backend - Parameters Router
Test parameter management and Excel import endpoints
"""

import io
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from openpyxl import load_workbook
from sqlalchemy.orm import Session

from app import auth, schemas
from app.database import get_db
from app.models import TestParameter, User

router = APIRouter()


@router.post("/upload-excel", status_code=status.HTTP_201_CREATED)
async def upload_parameters_excel(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(auth.get_current_superuser),
):
    """
    Upload Excel file with test parameters (admin only)
    """
    if not (file.filename.endswith(".xlsx") or file.filename.endswith(".xls")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be an Excel file",
        )

    try:
        contents = await file.read()
        workbook = load_workbook(filename=io.BytesIO(contents))
        sheet = workbook.active
        headers = [cell.value for cell in sheet[1]]
        
        parameters = []
        row_count = 0

        for row in sheet.iter_rows(min_row=2, values_only=True):
            if not row[0]:
                continue
            row_count += 1
            
            existing = db.query(TestParameter).filter(TestParameter.parameter_name == row[0]).first()
            if not existing:
                parameter = TestParameter(
                    parameter_name=row[0],
                    display_name=row[1] if len(row) > 1 and row[1] else row[0],
                    unit=row[2] if len(row) > 2 and row[2] else "",
                    data_type="float",
                )
                parameters.append(parameter)

        if parameters:
            db.bulk_save_objects(parameters)
        db.commit()

        return {
            "message": "Excel parameters uploaded successfully",
            "rows_processed": row_count,
            "parameters_created": len(parameters),
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing Excel file: {str(e)}",
        )


@router.get("/", response_model=List[schemas.TestParameterResponse])
async def get_parameters(
    skip: int = 0,
    limit: int = 100,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(auth.get_current_active_user),
):
    """
    Get all test parameters with optional search
    """
    query = db.query(TestParameter)
    if search:
        query = query.filter(TestParameter.parameter_name.ilike(f"%{search}%"))
    parameters = query.offset(skip).limit(limit).all()
    return parameters


@router.get("/{parameter_id}", response_model=schemas.TestParameterResponse)
async def get_parameter(
    parameter_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(auth.get_current_active_user),
):
    """
    Get a specific parameter by ID
    """
    parameter = db.query(TestParameter).filter(TestParameter.id == parameter_id).first()
    if not parameter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Parameter not found"
        )
    return parameter
